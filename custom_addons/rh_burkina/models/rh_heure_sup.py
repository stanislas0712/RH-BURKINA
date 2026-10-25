from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .rh_configuration import TYPES_HEURE_SUP

ETATS_HS = [
    ('brouillon', 'Brouillon'),
    ('soumis', 'Soumis'),
    ('valide_chef', 'Validé par le chef'),
    ('valide', 'Validé RH'),
    ('refuse', 'Refusé'),
]
# Heures comptées dans les plafonds et le rang hebdomadaire
ETATS_COMPTES = ('soumis', 'valide_chef', 'valide')


class RhHeureSup(models.Model):
    """Heures supplémentaires : déclaration, double validation, majoration.

    Le taux de majoration dépend du type d'heures et du rang de l'heure
    dans la semaine (tranches paramétrées, à vérifier). Le montant est
    calculé par la paie à partir du taux horaire du contrat.
    """

    _name = 'rh.heure.sup'
    _description = 'Heures supplémentaires'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    _check_company_auto = True

    employee_id = fields.Many2one(
        'hr.employee', string='Employé', required=True, index=True,
        ondelete='restrict', check_company=True, tracking=True,
        default=lambda self: self.env.user.employee_id)
    company_id = fields.Many2one(
        related='employee_id.company_id', store=True, index=True)
    department_id = fields.Many2one(
        related='employee_id.department_id', store=True, string='Département')
    date = fields.Date(string='Date', required=True, index=True,
                       tracking=True, default=fields.Date.context_today)
    type_heure = fields.Selection(
        TYPES_HEURE_SUP, string="Type d'heures", required=True,
        default='jour', tracking=True)
    nb_heures = fields.Float(string='Nombre d’heures', required=True,
                             tracking=True)
    description = fields.Char(string='Travaux effectués')
    state = fields.Selection(ETATS_HS, string='État', default='brouillon',
                             required=True, tracking=True, copy=False)
    motif_refus = fields.Char(string='Motif du refus', tracking=True,
                              copy=False)
    semaine_debut = fields.Date(string='Semaine du',
                                compute='_compute_semaine', store=True)
    repartition = fields.Char(string='Majorations',
                              compute='_compute_majoration')
    taux_moyen = fields.Float(string='Majoration moyenne (%)',
                              compute='_compute_majoration')
    bulletin_id = fields.Many2one('rh.bulletin.paie',
                                  string='Payé sur le bulletin',
                                  readonly=True, copy=False)

    @api.depends('date')
    def _compute_semaine(self):
        for rec in self:
            rec.semaine_debut = rec.date - timedelta(days=rec.date.weekday()) \
                if rec.date else False

    @api.depends('date', 'type_heure', 'nb_heures', 'employee_id')
    def _compute_majoration(self):
        for rec in self:
            try:
                tranches = rec._calculer_repartition()
            except UserError:
                tranches = []
            rec.repartition = ' + '.join(
                '%s h à %s %%' % (round(h, 2), t) for h, t in tranches)
            total = sum(h for h, _t in tranches)
            rec.taux_moyen = sum(h * t for h, t in tranches) / total \
                if total else 0.0

    # ------------------------------------------------------------------
    # Calculs
    # ------------------------------------------------------------------
    def _get_config(self):
        self.ensure_one()
        return self.env['rh.configuration']._get_en_vigueur(
            self.date, self.employee_id.sudo().company_id)

    def _heures_semaine_avant(self):
        """Heures sup. du même type déjà comptées avant celle-ci dans la
        semaine (ordre : date puis identifiant)."""
        self.ensure_one()
        autres = self.sudo().search([
            ('employee_id', '=', self.employee_id.id),
            ('semaine_debut', '=', self.semaine_debut),
            ('type_heure', '=', self.type_heure),
            ('state', 'in', ETATS_COMPTES),
            ('id', '!=', self._origin.id or 0),
        ])
        avant = autres.filtered(
            lambda h: (h.date, h.id) < (self.date, self._origin.id or 10**12))
        return sum(avant.mapped('nb_heures'))

    def _calculer_repartition(self):
        """Liste de (heures, taux %) selon les tranches paramétrées."""
        self.ensure_one()
        if not (self.date and self.nb_heures and self.employee_id):
            return []
        config = self._get_config()
        debut = self._heures_semaine_avant()
        fin = debut + self.nb_heures
        tranches = config.majoration_hs_ids.filtered(
            lambda t: t.type_heure == self.type_heure).sorted('heure_debut')
        resultat = []
        couvert = 0.0
        for t in tranches:
            bas = max(debut, t.heure_debut)
            haut = min(fin, t.heure_fin) if t.heure_fin else fin
            if haut > bas:
                resultat.append((haut - bas, t.taux))
                couvert += haut - bas
        if abs(couvert - self.nb_heures) > 1e-6:
            raise UserError(_(
                "Les tranches de majoration paramétrées ne couvrent pas "
                "toutes les heures de type « %s ».",
                dict(TYPES_HEURE_SUP)[self.type_heure]))
        return resultat

    # ------------------------------------------------------------------
    # Contraintes
    # ------------------------------------------------------------------
    @api.constrains('nb_heures')
    def _check_nb_heures(self):
        for rec in self:
            if rec.nb_heures <= 0 or rec.nb_heures > 24:
                raise ValidationError(
                    _("Le nombre d'heures doit être compris entre 0 et 24."))

    def _verifier_plafonds(self):
        """Bloque au-delà des plafonds hebdomadaire et annuel."""
        for rec in self:
            config = rec._get_config()
            HS = self.sudo()
            base = [('employee_id', '=', rec.employee_id.id),
                    ('state', 'in', ETATS_COMPTES), ('id', '!=', rec.id)]
            if config.hs_plafond_hebdo:
                semaine = sum(HS.search(base + [
                    ('semaine_debut', '=', rec.semaine_debut)]).mapped(
                    'nb_heures')) + rec.nb_heures
                if semaine > config.hs_plafond_hebdo + 1e-6:
                    raise UserError(_(
                        "%(emp)s : %(h)s h supplémentaires sur la semaine du "
                        "%(sem)s, au-delà du plafond hebdomadaire de "
                        "%(max)s h.", emp=rec.employee_id.name, h=semaine,
                        sem=rec.semaine_debut, max=config.hs_plafond_hebdo))
            if config.hs_plafond_annuel:
                annee = sum(HS.search(base + [
                    ('date', '>=', rec.date.replace(month=1, day=1)),
                    ('date', '<=', rec.date.replace(month=12, day=31))]
                ).mapped('nb_heures')) + rec.nb_heures
                if annee > config.hs_plafond_annuel + 1e-6:
                    raise UserError(_(
                        "%(emp)s : %(h)s h supplémentaires sur l'année, "
                        "au-delà du plafond annuel de %(max)s h.",
                        emp=rec.employee_id.name, h=annee,
                        max=config.hs_plafond_annuel))

    # ------------------------------------------------------------------
    # Onchange
    # ------------------------------------------------------------------
    @api.onchange('date')
    def _onchange_date(self):
        if not self.date:
            return
        if self.env['rh.jour.ferie']._get_dates_feriees(
                self.date, self.date, self.employee_id.company_id
                or self.env.company):
            self.type_heure = 'ferie'
        elif self.date.weekday() == 6:
            self.type_heure = 'dimanche'

    # ------------------------------------------------------------------
    # Droits et écriture
    # ------------------------------------------------------------------
    def _est_rh(self):
        return self.env.user.has_group('rh_burkina.group_rh_gestionnaire')

    def _est_chef_de(self, employee):
        emp = employee.sudo()
        user = self.env.user
        return emp.department_id.manager_id.user_id == user \
            or emp.parent_id.user_id == user

    def write(self, vals):
        if not self.env.su and not self._est_rh():
            for rec in self:
                if rec.state != 'brouillon' or \
                        rec.employee_id.sudo().user_id != self.env.user:
                    raise AccessError(_(
                        "Seule une déclaration en brouillon qui vous "
                        "concerne peut être modifiée."))
            if 'state' in vals:
                raise AccessError(_("Utilisez les boutons de validation."))
        return super().write(vals)

    def unlink(self):
        if not self.env.su:
            raise UserError(_("Une déclaration d'heures supplémentaires ne "
                              "peut pas être supprimée : refusez-la."))
        return super().unlink()

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def action_soumettre(self):
        for rec in self:
            if rec.state != 'brouillon':
                raise UserError(_("Déclaration déjà soumise."))
            if not (rec._est_rh() or rec.employee_id.sudo().user_id
                    == self.env.user or rec._est_chef_de(rec.employee_id)):
                raise AccessError(_("Vous ne pouvez pas soumettre cette "
                                    "déclaration."))
            rec._verifier_plafonds()
            rec._calculer_repartition()
            rec.sudo().state = 'soumis'

    def action_valider_chef(self):
        for rec in self:
            if rec.state != 'soumis':
                raise UserError(_("La déclaration n'est pas en attente du "
                                  "chef."))
            if not (rec._est_chef_de(rec.employee_id) or rec._est_rh()):
                raise AccessError(_("Seul le chef de l'employé peut "
                                    "valider à ce niveau."))
            if rec.employee_id.sudo().user_id == self.env.user \
                    and not rec._est_rh():
                raise AccessError(_("Vous ne pouvez pas valider vos "
                                    "propres heures."))
            rec.sudo().state = 'valide_chef'

    def action_valider_rh(self):
        if not self._est_rh():
            raise AccessError(_("Validation réservée aux ressources "
                                "humaines."))
        for rec in self:
            if rec.state != 'valide_chef':
                raise UserError(_("La déclaration doit d'abord être validée "
                                  "par le chef."))
            rec._verifier_plafonds()
            rec.state = 'valide'

    def action_refuser(self):
        return self.env['rh.wizard.refus']._ouvrir(self)

    def _refuser(self, motif):
        for rec in self:
            if rec.state not in ('soumis', 'valide_chef'):
                raise UserError(_("Seule une déclaration en attente peut "
                                  "être refusée."))
            if not (rec._est_rh() or (rec.state == 'soumis'
                                      and rec._est_chef_de(rec.employee_id))):
                raise AccessError(_("Vous ne pouvez pas refuser cette "
                                    "déclaration."))
            if not (motif or '').strip():
                raise UserError(_("Indiquez le motif du refus."))
            rec.sudo().write({'state': 'refuse', 'motif_refus': motif})
