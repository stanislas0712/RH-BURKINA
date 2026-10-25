import calendar
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

ETATS_CONGE = [
    ('brouillon', 'Brouillon'),
    ('soumis', 'Soumis'),
    ('valide_chef', 'Validé par le chef'),
    ('approuve', 'Approuvé RH'),
    ('refuse', 'Refusé'),
    ('annule', 'Annulé'),
]
ETATS_EN_ATTENTE = ('soumis', 'valide_chef')
# États qui bloquent le calendrier (chevauchements)
ETATS_ACTIFS = ('soumis', 'valide_chef', 'approuve')

MODES_DECOMPTE = [
    ('config', 'Selon les paramètres généraux'),
    ('ouvrable', 'Jours ouvrables (hors dimanches et fériés)'),
    ('ouvre', 'Jours ouvrés (calendrier de travail, hors fériés)'),
    ('calendaire', 'Jours calendaires'),
]


class RhTypeConge(models.Model):
    _name = 'rh.type.conge'
    _description = 'Type de congé ou d’absence'
    _order = 'sequence, name'

    name = fields.Char(string='Type', required=True, translate=True)
    code = fields.Char(string='Code')
    sequence = fields.Integer(default=10)
    categorie = fields.Selection(
        [('annuel', 'Congé annuel'), ('maternite', 'Maternité'),
         ('familial', 'Événement familial'), ('maladie', 'Maladie'),
         ('sans_solde', 'Sans solde'), ('absence', 'Absence'),
         ('autre', 'Autre')],
        string='Catégorie', required=True, default='autre')
    deductible = fields.Boolean(
        string='Déduit du solde',
        help="Les jours pris sont décomptés du solde de ce type.")
    acquisition_mensuelle = fields.Boolean(
        string='Acquis chaque mois',
        help="Le solde est crédité chaque mois de service effectif selon "
             "les paramètres généraux.")
    paye = fields.Boolean(string='Rémunéré', default=True,
                          help="Décoché : une retenue est proposée sur le "
                               "bulletin pour les jours d'absence.")
    justificatif_obligatoire = fields.Boolean(
        string='Justificatif obligatoire')
    duree_max_jours = fields.Float(
        string='Durée maximale (jours)', help="0 = pas de limite.")
    decompte = fields.Selection(MODES_DECOMPTE, string='Décompte des jours',
                                required=True, default='config')
    description = fields.Text(string='Description / référence légale')
    company_id = fields.Many2one('res.company', string='Société',
                                 help="Vide : commun à toutes les sociétés.")
    color = fields.Integer(string='Couleur')
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('code_uniq', 'unique(code, company_id)',
         'Le code du type de congé doit être unique.'),
    ]

    @api.constrains('deductible', 'acquisition_mensuelle', 'duree_max_jours')
    def _check_type(self):
        for rec in self:
            if rec.acquisition_mensuelle and not rec.deductible:
                raise ValidationError(_(
                    "Un congé acquis mensuellement doit être déduit du "
                    "solde."))
            if rec.duree_max_jours < 0:
                raise ValidationError(_("Durée maximale invalide."))


class RhSoldeConge(models.Model):
    """Solde d'un employé pour un type de congé et une année."""

    _name = 'rh.solde.conge'
    _description = 'Solde de congés'
    _order = 'annee desc, employee_id'
    _check_company_auto = True

    employee_id = fields.Many2one(
        'hr.employee', string='Employé', required=True, index=True,
        ondelete='restrict', check_company=True)
    company_id = fields.Many2one(
        related='employee_id.company_id', store=True, index=True)
    department_id = fields.Many2one(
        related='employee_id.department_id', store=True, string='Département')
    type_conge_id = fields.Many2one('rh.type.conge', string='Type',
                                    required=True, ondelete='restrict')
    annee = fields.Integer(string='Année', required=True, index=True)
    report = fields.Float(string='Report année précédente', digits=(16, 2))
    acquisition_ids = fields.One2many('rh.acquisition.conge', 'solde_id',
                                      string='Acquisitions')
    conge_ids = fields.One2many('rh.conge', 'solde_id', string='Demandes')
    acquis = fields.Float(string='Acquis', compute='_compute_soldes',
                          store=True, digits=(16, 2))
    pris = fields.Float(string='Pris', compute='_compute_soldes',
                        store=True, digits=(16, 2))
    en_attente = fields.Float(string='En attente', compute='_compute_soldes',
                              store=True, digits=(16, 2))
    restant = fields.Float(string='Restant', compute='_compute_soldes',
                           store=True, digits=(16, 2))
    disponible = fields.Float(
        string='Disponible', compute='_compute_soldes', store=True,
        digits=(16, 2), help="Restant moins les demandes en attente.")
    reporte = fields.Boolean(string='Reporté sur l’année suivante',
                             readonly=True, copy=False)

    _sql_constraints = [
        ('solde_uniq', 'unique(employee_id, type_conge_id, annee)',
         'Un seul solde par employé, type et année.'),
    ]

    @api.depends('report', 'acquisition_ids.jours', 'conge_ids.state',
                 'conge_ids.nb_jours')
    def _compute_soldes(self):
        for rec in self:
            rec.acquis = sum(rec.acquisition_ids.mapped('jours'))
            rec.pris = sum(rec.conge_ids.filtered(
                lambda c: c.state == 'approuve').mapped('nb_jours'))
            rec.en_attente = sum(rec.conge_ids.filtered(
                lambda c: c.state in ETATS_EN_ATTENTE).mapped('nb_jours'))
            rec.restant = rec.report + rec.acquis - rec.pris
            rec.disponible = rec.restant - rec.en_attente

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s – %s %s' % (
                rec.employee_id.name, rec.type_conge_id.name, rec.annee)

    @api.model
    def _get_solde(self, employee, type_conge, annee):
        """Retourne (en le créant si besoin) le solde demandé."""
        Solde = self.sudo()
        solde = Solde.search([('employee_id', '=', employee.id),
                              ('type_conge_id', '=', type_conge.id),
                              ('annee', '=', annee)], limit=1)
        if not solde:
            solde = Solde.create({'employee_id': employee.id,
                                  'type_conge_id': type_conge.id,
                                  'annee': annee})
        return solde

    def write(self, vals):
        if 'report' in vals and self.filtered('reporte') \
                and not self.env.su:
            raise UserError(_("Ce solde a déjà été reporté."))
        return super().write(vals)

    def action_reporter(self):
        """Reporte le restant sur le solde de l'année suivante."""
        for rec in self:
            if rec.reporte:
                raise UserError(_("Le solde %s a déjà été reporté.",
                                  rec.display_name))
            suivant = self._get_solde(rec.employee_id, rec.type_conge_id,
                                      rec.annee + 1)
            suivant.sudo().report = max(rec.restant, 0.0)
            rec.sudo().reporte = True
        return True


class RhAcquisitionConge(models.Model):
    """Crédit mensuel de congés (une ligne par employé, type et mois)."""

    _name = 'rh.acquisition.conge'
    _description = 'Acquisition mensuelle de congés'
    _order = 'mois desc'

    solde_id = fields.Many2one('rh.solde.conge', required=True,
                               ondelete='cascade', index=True)
    employee_id = fields.Many2one(related='solde_id.employee_id', store=True)
    company_id = fields.Many2one(related='solde_id.company_id', store=True)
    type_conge_id = fields.Many2one(related='solde_id.type_conge_id',
                                    store=True)
    mois = fields.Date(string='Mois', required=True,
                       help="Premier jour du mois crédité.")
    jours = fields.Float(string='Jours acquis', digits=(16, 2))
    detail = fields.Char(string='Détail')

    _sql_constraints = [
        ('mois_uniq', 'unique(employee_id, type_conge_id, mois)',
         'Ce mois a déjà été crédité.'),
    ]

    @api.model
    def _crediter_mois(self, mois=None):
        """Crédite les congés acquis pour le mois ``mois`` (par défaut, le
        mois précédent). Idempotent : un mois déjà crédité est ignoré.

        Jours = (acquisition mensuelle + supplément d'ancienneté / 12)
        × part du mois couverte par un contrat (prorata calendaire).
        """
        if mois is None:
            mois = fields.Date.context_today(self).replace(day=1) \
                - relativedelta(months=1)
        mois = mois.replace(day=1)
        fin_mois = mois.replace(day=calendar.monthrange(mois.year,
                                                        mois.month)[1])
        nb_jours_mois = fin_mois.day
        types = self.env['rh.type.conge'].sudo().search(
            [('acquisition_mensuelle', '=', True)])
        Contrat = self.env['rh.contrat'].sudo()
        contrats = Contrat.search([
            ('state', 'not in', ('brouillon',)),
            ('date_debut', '<=', fin_mois),
            '|', ('date_resiliation', '=', False),
            ('date_resiliation', '>=', mois),
            '|', ('date_fin', '=', False), ('date_fin', '>=', mois),
        ])
        crees = self.browse()
        for employee in contrats.employee_id:
            emp_contrats = contrats.filtered(
                lambda c: c.employee_id == employee)
            jours_couverts = set()
            for c in emp_contrats:
                debut = max(c.date_debut, mois)
                fin = min(filter(None, [c.date_resiliation, c.date_fin,
                                        fin_mois]))
                jour = debut
                while jour <= fin:
                    jours_couverts.add(jour)
                    jour += relativedelta(days=1)
            if not jours_couverts:
                continue
            prorata = len(jours_couverts) / nb_jours_mois
            config = self.env['rh.configuration']._get_en_vigueur(
                fin_mois, employee.company_id, raise_if_missing=False)
            if not config:
                continue
            anciennete = relativedelta(
                fin_mois, employee.date_embauche).years \
                if employee.date_embauche else 0
            supplement = config._get_conge_supplementaire(anciennete) / 12.0
            jours = round((config.conge_jours_par_mois + supplement)
                          * prorata, 2)
            for type_conge in types.filtered(
                    lambda t: not t.company_id
                    or t.company_id == employee.company_id):
                if self.sudo().search_count([
                        ('employee_id', '=', employee.id),
                        ('type_conge_id', '=', type_conge.id),
                        ('mois', '=', mois)]):
                    continue
                solde = self.env['rh.solde.conge']._get_solde(
                    employee, type_conge, mois.year)
                crees |= self.sudo().create({
                    'solde_id': solde.id, 'mois': mois, 'jours': jours,
                    'detail': _('%(base)s j × %(pct)s %% du mois'
                                '%(supp)s',
                                base=config.conge_jours_par_mois,
                                pct=round(prorata * 100),
                                supp=_(' + ancienneté') if supplement
                                else ''),
                })
        return crees

    @api.model
    def _cron_crediter_conges(self):
        return self._crediter_mois()


class RhConge(models.Model):
    """Demande de congé ou d'absence."""

    _name = 'rh.conge'
    _description = 'Demande de congé'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_debut desc, id desc'
    _check_company_auto = True

    name = fields.Char(string='Référence', readonly=True, copy=False,
                       default='/')
    employee_id = fields.Many2one(
        'hr.employee', string='Employé', required=True, index=True,
        ondelete='restrict', check_company=True, tracking=True,
        default=lambda self: self.env.user.employee_id)
    company_id = fields.Many2one(
        related='employee_id.company_id', store=True, index=True)
    department_id = fields.Many2one(
        related='employee_id.department_id', store=True, string='Département')
    type_conge_id = fields.Many2one('rh.type.conge', string='Type',
                                    required=True, tracking=True)
    date_debut = fields.Date(string='Du', required=True, tracking=True)
    date_fin = fields.Date(string='Au', required=True, tracking=True)
    nb_jours = fields.Float(string='Jours décomptés',
                            compute='_compute_nb_jours', store=True,
                            digits=(16, 2), tracking=True)
    mode_decompte = fields.Selection(
        MODES_DECOMPTE[1:], string='Décompte', compute='_compute_nb_jours',
        store=True)
    motif = fields.Text(string='Motif')
    justificatif = fields.Binary(string='Justificatif', attachment=True)
    nom_justificatif = fields.Char()
    state = fields.Selection(ETATS_CONGE, string='État', default='brouillon',
                             required=True, tracking=True, copy=False,
                             index=True)
    motif_refus = fields.Text(string='Motif du refus', tracking=True,
                              copy=False)
    solde_id = fields.Many2one('rh.solde.conge', string='Solde',
                               readonly=True, copy=False, index=True)
    solde_disponible = fields.Float(related='solde_id.disponible',
                                    string='Solde disponible')
    validateur_chef_id = fields.Many2one('res.users', string='Validé par',
                                         readonly=True, copy=False)
    approbateur_id = fields.Many2one('res.users', string='Approuvé par',
                                     readonly=True, copy=False)
    paye = fields.Boolean(related='type_conge_id.paye', store=True)

    @api.depends('date_debut', 'date_fin', 'type_conge_id', 'employee_id')
    def _compute_nb_jours(self):
        Ferie = self.env['rh.jour.ferie']
        for rec in self:
            mode = rec.type_conge_id.decompte or 'config'
            if mode == 'config' and rec.date_debut:
                config = self.env['rh.configuration']._get_en_vigueur(
                    rec.date_debut, rec.employee_id.company_id
                    or self.env.company, raise_if_missing=False)
                mode = config.conge_type_jours if config else 'ouvrable'
            if mode == 'config':
                mode = 'ouvrable'
            rec.mode_decompte = mode
            rec.nb_jours = Ferie._compter_jours(
                rec.date_debut, rec.date_fin, mode, rec.employee_id) \
                if rec.employee_id else 0

    # ------------------------------------------------------------------
    # Contraintes
    # ------------------------------------------------------------------
    @api.constrains('date_debut', 'date_fin')
    def _check_dates(self):
        for rec in self:
            if rec.date_fin < rec.date_debut:
                raise ValidationError(_("La date de fin précède la date de "
                                        "début."))

    @api.constrains('state', 'date_debut', 'date_fin', 'employee_id')
    def _check_chevauchement(self):
        for rec in self.filtered(lambda c: c.state in ETATS_ACTIFS):
            autre = self.sudo().search([
                ('id', '!=', rec.id),
                ('employee_id', '=', rec.employee_id.id),
                ('state', 'in', ETATS_ACTIFS),
                ('date_debut', '<=', rec.date_fin),
                ('date_fin', '>=', rec.date_debut),
            ], limit=1)
            if autre:
                raise ValidationError(_(
                    "Cette demande chevauche la demande %(ref)s du %(d1)s "
                    "au %(d2)s.", ref=autre.name, d1=autre.date_debut,
                    d2=autre.date_fin))

    def _verifier_demande(self, inclure_attente=True):
        """Contrôles métier à la soumission et à l'approbation."""
        for rec in self:
            type_c = rec.type_conge_id
            if rec.nb_jours <= 0:
                raise UserError(_(
                    "La période choisie ne contient aucun jour à décompter "
                    "(week-end ou jours fériés)."))
            if type_c.duree_max_jours and \
                    rec.nb_jours > type_c.duree_max_jours:
                raise UserError(_(
                    "%(type)s : %(n)s jours demandés pour un maximum de "
                    "%(max)s.", type=type_c.name, n=rec.nb_jours,
                    max=type_c.duree_max_jours))
            if type_c.justificatif_obligatoire and not rec.justificatif:
                raise UserError(_(
                    "Un justificatif est obligatoire pour « %s ».",
                    type_c.name))
            if type_c.deductible:
                solde = self.env['rh.solde.conge']._get_solde(
                    rec.employee_id, type_c, rec.date_debut.year)
                rec.sudo().solde_id = solde
                disponible = solde.restant - sum(solde.conge_ids.filtered(
                    lambda c: c.state in ETATS_EN_ATTENTE
                    and c.id != rec.id).mapped('nb_jours')) \
                    if inclure_attente else solde.restant
                if rec.nb_jours > disponible + 1e-6:
                    raise UserError(_(
                        "Solde insuffisant : %(n)s jours demandés, "
                        "%(dispo)s jours disponibles (%(type)s %(annee)s).",
                        n=rec.nb_jours, dispo=round(disponible, 2),
                        type=type_c.name, annee=rec.date_debut.year))

    # ------------------------------------------------------------------
    # Droits
    # ------------------------------------------------------------------
    def _est_rh(self):
        return self.env.user.has_group('rh_burkina.group_rh_gestionnaire')

    def _est_chef_de(self, employee):
        emp = employee.sudo()
        user = self.env.user
        return emp.department_id.manager_id.user_id == user \
            or emp.parent_id.user_id == user

    def _a_un_chef(self):
        emp = self.employee_id.sudo()
        return bool(emp.department_id.manager_id.user_id
                    or emp.parent_id.user_id)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        if not self._est_rh():
            for vals in vals_list:
                emp = self.env['hr.employee'].sudo().browse(
                    vals.get('employee_id'))
                if emp.user_id != self.env.user:
                    raise AccessError(_("Vous ne pouvez créer une demande "
                                        "que pour vous-même."))
                if vals.get('state', 'brouillon') != 'brouillon':
                    raise AccessError(_("Une demande est créée en "
                                        "brouillon."))
        records = super().create(vals_list)
        for rec in records:
            if rec.name == '/':
                rec.name = self.env['ir.sequence'].with_company(
                    rec.company_id).sudo().next_by_code('rh.conge') or '/'
        return records

    def write(self, vals):
        if not self.env.su and not self._est_rh():
            for rec in self:
                if rec.state != 'brouillon' or \
                        rec.employee_id.sudo().user_id != self.env.user:
                    raise AccessError(_(
                        "Seule votre demande en brouillon peut être "
                        "modifiée."))
            if {'state', 'employee_id', 'solde_id'} & set(vals):
                raise AccessError(_("Utilisez les boutons de la demande."))
        return super().write(vals)

    def unlink(self):
        if not self.env.su:
            raise UserError(_("Une demande de congé ne peut pas être "
                              "supprimée : annulez-la."))
        return super().unlink()

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def action_soumettre(self):
        for rec in self:
            if rec.state != 'brouillon':
                raise UserError(_("La demande %s est déjà soumise.",
                                  rec.name))
            if not (rec._est_rh() or rec.employee_id.sudo().user_id
                    == self.env.user):
                raise AccessError(_("Seul l'employé ou les RH peuvent "
                                    "soumettre cette demande."))
            rec._verifier_demande()
            # Sans chef désigné, la demande passe directement aux RH
            rec.sudo().state = 'soumis' if rec._a_un_chef() \
                else 'valide_chef'

    def action_valider_chef(self):
        for rec in self:
            if rec.state != 'soumis':
                raise UserError(_("La demande %s n'attend pas la "
                                  "validation du chef.", rec.name))
            if not (rec._est_chef_de(rec.employee_id) or rec._est_rh()):
                raise AccessError(_("Seul le chef de l'employé peut "
                                    "valider à ce niveau."))
            if rec.employee_id.sudo().user_id == self.env.user:
                raise AccessError(_("Vous ne pouvez pas valider votre "
                                    "propre demande."))
            rec.sudo().write({'state': 'valide_chef',
                              'validateur_chef_id': self.env.uid})

    def action_approuver(self):
        if not self._est_rh():
            raise AccessError(_("L'approbation est réservée aux "
                                "ressources humaines."))
        for rec in self:
            if rec.state not in ETATS_EN_ATTENTE:
                raise UserError(_("La demande %s n'est pas en attente.",
                                  rec.name))
            if rec.employee_id.sudo().user_id == self.env.user:
                raise AccessError(_("Vous ne pouvez pas approuver votre "
                                    "propre demande."))
            rec._verifier_demande()
            rec.write({'state': 'approuve', 'approbateur_id': self.env.uid})

    def action_refuser(self):
        return self.env['rh.wizard.refus']._ouvrir(self)

    def _refuser(self, motif):
        for rec in self:
            if rec.state not in ETATS_EN_ATTENTE:
                raise UserError(_("Seule une demande en attente peut être "
                                  "refusée."))
            if not (rec._est_rh() or (rec.state == 'soumis'
                                      and rec._est_chef_de(rec.employee_id))):
                raise AccessError(_("Vous ne pouvez pas refuser cette "
                                    "demande."))
            if not (motif or '').strip():
                raise UserError(_("Le motif du refus est obligatoire."))
            rec.sudo().write({'state': 'refuse', 'motif_refus': motif})

    def action_annuler(self):
        for rec in self:
            proprietaire = rec.employee_id.sudo().user_id == self.env.user
            if rec.state in ('brouillon', 'soumis') and proprietaire:
                pass
            elif rec.state in ('brouillon', 'soumis', 'valide_chef',
                               'approuve') and rec._est_rh():
                pass
            else:
                raise AccessError(_("Vous ne pouvez pas annuler cette "
                                    "demande."))
            rec.sudo().state = 'annule'
