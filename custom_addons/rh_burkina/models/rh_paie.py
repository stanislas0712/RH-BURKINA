import calendar
import logging

from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .rh_bulletin_paie import ETATS_CONTRAT_PAYES

_logger = logging.getLogger(__name__)


class RhPaie(models.Model):
    """Période de paie mensuelle d'une société."""

    _name = 'rh.paie'
    _description = 'Période de paie'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_debut desc'

    name = fields.Char(string='Référence', readonly=True, copy=False,
                       default='/')
    libelle = fields.Char(string='Mois', compute='_compute_libelle',
                          store=True)
    company_id = fields.Many2one('res.company', string='Société',
                                 required=True, index=True,
                                 default=lambda self: self.env.company)
    # La paie est toujours tenue en XOF, arrondie à l'unité.
    currency_id = fields.Many2one(
        'res.currency', string='Devise', required=True, readonly=True,
        default=lambda self: self.env.ref('base.XOF'))
    date_debut = fields.Date(string='Du', required=True, tracking=True,
                             default=lambda self: fields.Date.context_today(
                                 self).replace(day=1))
    date_fin = fields.Date(string='Au', compute='_compute_date_fin',
                           store=True)
    state = fields.Selection(
        [('brouillon', 'Brouillon'), ('en_cours', 'En cours'),
         ('cloture', 'Clôturée')], string='État', default='brouillon',
        required=True, tracking=True, copy=False)
    bulletin_ids = fields.One2many('rh.bulletin.paie', 'paie_id',
                                   string='Bulletins')
    bulletin_count = fields.Integer(compute='_compute_totaux')
    total_brut = fields.Monetary(compute='_compute_totaux',
                                 string='Masse salariale brute')
    total_net = fields.Monetary(compute='_compute_totaux',
                                string='Total net à payer')
    total_cotisations = fields.Monetary(
        compute='_compute_totaux', string='Cotisations (salariales + '
                                          'patronales)')
    total_iuts = fields.Monetary(compute='_compute_totaux',
                                 string='IUTS à reverser')
    anomalies = fields.Html(string='Anomalies', compute='_compute_anomalies',
                            sanitize=False)
    nb_anomalies = fields.Integer(compute='_compute_anomalies')

    _sql_constraints = [
        ('periode_uniq', 'unique(company_id, date_debut)',
         'Une seule période de paie par mois et par société.'),
    ]

    @api.depends('date_debut')
    def _compute_date_fin(self):
        for rec in self:
            if rec.date_debut:
                d = rec.date_debut
                rec.date_fin = d.replace(
                    day=calendar.monthrange(d.year, d.month)[1])
            else:
                rec.date_fin = False

    @api.depends('date_debut')
    def _compute_libelle(self):
        mois = [_('Janvier'), _('Février'), _('Mars'), _('Avril'), _('Mai'),
                _('Juin'), _('Juillet'), _('Août'), _('Septembre'),
                _('Octobre'), _('Novembre'), _('Décembre')]
        for rec in self:
            rec.libelle = '%s %s' % (mois[rec.date_debut.month - 1],
                                     rec.date_debut.year) \
                if rec.date_debut else False

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s – %s' % (rec.name, rec.libelle or '')

    def _bulletins_actifs(self):
        return self.bulletin_ids.filtered(lambda b: b.state != 'annule')

    @api.depends('bulletin_ids.state', 'bulletin_ids.net_a_payer')
    def _compute_totaux(self):
        for rec in self:
            actifs = rec._bulletins_actifs()
            rec.bulletin_count = len(actifs)
            rec.total_brut = sum(actifs.mapped('brut'))
            rec.total_net = sum(actifs.mapped('net_a_payer'))
            rec.total_cotisations = sum(actifs.mapped(
                'cotisation_salariale')) + sum(actifs.mapped(
                    'charges_patronales'))
            rec.total_iuts = sum(actifs.mapped('iuts'))

    @api.constrains('date_debut')
    def _check_date_debut(self):
        for rec in self:
            if rec.date_debut.day != 1:
                raise ValidationError(_("Une période de paie commence le "
                                        "premier jour du mois."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('date_debut'):
                vals['date_debut'] = fields.Date.to_date(
                    vals['date_debut']).replace(day=1)
        records = super().create(vals_list)
        for rec in records:
            if rec.name == '/':
                rec.name = self.env['ir.sequence'].with_company(
                    rec.company_id).next_by_code('rh.paie') or '/'
        return records

    def write(self, vals):
        if self.filtered(lambda p: p.state == 'cloture') and \
                not self.env.su and set(vals) - {'message_main_attachment_id'}:
            raise UserError(_("Une période clôturée ne peut plus être "
                              "modifiée."))
        if 'date_debut' in vals and self.bulletin_ids:
            raise UserError(_("La période contient des bulletins : son mois "
                              "ne peut plus changer."))
        return super().write(vals)

    def unlink(self):
        if not self.env.su:
            raise UserError(_("Une période de paie ne peut pas être "
                              "supprimée."))
        return super().unlink()

    def _verifier_ouverte(self):
        for rec in self:
            if rec.state == 'cloture':
                raise UserError(_("La période %s est clôturée : aucun "
                                  "bulletin ne peut plus être créé ni "
                                  "modifié.", rec.name))

    # ------------------------------------------------------------------
    # Anomalies
    # ------------------------------------------------------------------
    def _employes_sous_contrat(self):
        self.ensure_one()
        contrats = self.env['rh.contrat'].sudo().search([
            ('company_id', '=', self.company_id.id),
            ('state', 'in', ETATS_CONTRAT_PAYES),
            ('date_debut', '<=', self.date_fin),
            '|', ('date_resiliation', '=', False),
            ('date_resiliation', '>=', self.date_debut),
            '|', ('date_fin', '=', False), ('date_fin', '>=', self.date_debut),
        ])
        return contrats.employee_id

    def _lister_anomalies(self):
        """Liste de (employé, message) à corriger avant la paie."""
        self.ensure_one()
        anomalies = []
        if self.company_id.currency_id != self.currency_id:
            anomalies.append((None, _(
                "La devise de la société (%(soc)s) n'est pas le franc CFA : "
                "les salaires des contrats sont lus comme des montants en "
                "XOF.", soc=self.company_id.currency_id.name)))
        sous_contrat = self._employes_sous_contrat()
        actifs = self.env['hr.employee'].sudo().search([
            ('company_id', '=', self.company_id.id),
            ('statut_rh', '=', 'actif')])
        for emp in actifs - sous_contrat:
            anomalies.append((emp, _("Employé actif sans contrat sur la "
                                     "période.")))
        config = self.env['rh.configuration']._get_en_vigueur(
            self.date_fin, self.company_id, raise_if_missing=False)
        if not config:
            anomalies.append((None, _("Aucun paramètre général en vigueur.")))
        for emp in sous_contrat.sudo():
            contrat = emp.contrat_ids.filtered(
                lambda c: c.state in ('essai', 'actif', 'suspendu'))[:1]
            if config and contrat and contrat.remuneration_type == \
                    'mensuelle' and contrat.temps_travail == 'plein' and \
                    contrat.type_contrat != 'stage' and \
                    contrat.salaire_base < config.smig_mensuel:
                anomalies.append((emp, _(
                    "Salaire du contrat %(c)s inférieur au SMIG en vigueur "
                    "(%(smig)s).", c=contrat.name,
                    smig=self.currency_id.format(config.smig_mensuel))))
            if contrat.state == 'suspendu':
                anomalies.append((emp, _("Contrat suspendu : vérifier le "
                                         "salaire dû.")))
            if emp.mode_paiement == 'virement' and not (
                    emp.banque_id and emp.numero_compte):
                anomalies.append((emp, _("Coordonnées bancaires "
                                         "manquantes.")))
            if emp.mode_paiement in ('orange_money', 'moov_money') and \
                    not emp.numero_mobile_money:
                anomalies.append((emp, _("Numéro mobile money manquant.")))
            if not emp.ssnid:
                anomalies.append((emp, _("N° CNSS / CARFO manquant.")))
        for bulletin in self.bulletin_ids.filtered('erreur_calcul'):
            anomalies.append((bulletin.employee_id, bulletin.erreur_calcul))
        return anomalies

    @api.depends('bulletin_ids.erreur_calcul', 'date_debut', 'company_id')
    def _compute_anomalies(self):
        parametrage = _('Paramétrage')
        for rec in self:
            if not rec.date_debut or not rec.id:
                rec.anomalies = False
                rec.nb_anomalies = 0
                continue
            liste = rec._lister_anomalies()
            rec.nb_anomalies = len(liste)
            rec.anomalies = Markup('<ul>%s</ul>') % Markup('').join(
                Markup('<li><b>%s</b> : %s</li>') % (
                    emp.name if emp else parametrage, escape(msg))
                for emp, msg in liste) if liste else False

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_generer_bulletins(self):
        """Crée et calcule les bulletins des employés sous contrat.

        Un échec de calcul n'interrompt pas la génération : l'erreur est
        consignée sur le bulletin, qui reste en brouillon.
        """
        Bulletin = self.env['rh.bulletin.paie']
        for rec in self:
            rec._verifier_ouverte()
            deja = rec._bulletins_actifs().employee_id
            nouveaux = Bulletin.create([
                {'paie_id': rec.id, 'employee_id': emp.id}
                for emp in rec._employes_sous_contrat() - deja])
            a_calculer = nouveaux | rec.bulletin_ids.filtered(
                lambda b: b.state in ('brouillon', 'calcule'))
            for bulletin in a_calculer:
                try:
                    with self.env.cr.savepoint():
                        bulletin.action_calculer()
                except UserError as err:
                    bulletin._ecrire({'erreur_calcul': str(err.args[0]),
                                      'state': 'brouillon'})
            if rec.state == 'brouillon':
                rec.state = 'en_cours'
        return True

    def action_valider_bulletins(self):
        for rec in self:
            rec.bulletin_ids.filtered(
                lambda b: b.state == 'calcule').action_valider()
        return True

    def action_marquer_payes(self):
        for rec in self:
            rec.bulletin_ids.filtered(
                lambda b: b.state == 'valide').action_payer()
        return True

    def action_cloturer(self):
        for rec in self:
            restants = rec.bulletin_ids.filtered(
                lambda b: b.state in ('brouillon', 'calcule'))
            if restants:
                raise UserError(_(
                    "%(n)s bulletin(s) ne sont pas validés (%(noms)s). "
                    "Validez-les ou annulez-les avant de clôturer.",
                    n=len(restants),
                    noms=', '.join(restants[:5].employee_id.mapped('name'))))
            rec.state = 'cloture'
            rec.message_post(body=_("Période clôturée : bulletins "
                                    "verrouillés."))
        return True

    def action_voir_bulletins(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'rh_burkina.action_rh_bulletin_paie')
        action['domain'] = [('paie_id', '=', self.id)]
        action['context'] = {'default_paie_id': self.id}
        return action
