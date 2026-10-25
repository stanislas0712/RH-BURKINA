from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .rh_cnss import REGIMES_SOCIAUX

# Les champs privés de hr.employee sont réservés par Odoo au groupe
# hr.group_hr_user. On les ouvre aux rôles RH Burkina : les règles
# d'enregistrement limitent ensuite les fiches visibles (la sienne, son
# équipe ou toutes selon le rôle).
GROUPES_DOSSIER = 'hr.group_hr_user,rh_burkina.group_rh_employe'
GROUPES_SALAIRE = 'rh_burkina.group_rh_salaire'

STATUTS_RH = [
    ('actif', 'Actif'),
    ('inactif', 'Inactif'),
    ('suspendu', 'Suspendu'),
    ('demissionnaire', 'Démissionnaire'),
    ('licencie', 'Licencié'),
    ('retraite', 'Retraité'),
]

MODES_PAIEMENT = [
    ('virement', 'Virement bancaire'),
    ('especes', 'Espèces'),
    ('orange_money', 'Orange Money'),
    ('moov_money', 'Moov Money'),
]

# Changements qui alimentent automatiquement l'historique des postes.
CHAMPS_HISTORIQUE = {
    'poste_id': 'poste',
    'department_id': 'departement',
    'categorie_id': 'categorie',
    'salaire_base': 'salaire',
}


class HrEmployee(models.Model):
    """Dossier du personnel : extension de la fiche employé standard."""

    _inherit = 'hr.employee'

    # ------------------------------------------------------------------
    # Ouverture des champs privés standard aux rôles RH Burkina
    # ------------------------------------------------------------------
    private_street = fields.Char(groups=GROUPES_DOSSIER)
    private_street2 = fields.Char(groups=GROUPES_DOSSIER)
    private_city = fields.Char(groups=GROUPES_DOSSIER)
    private_state_id = fields.Many2one(groups=GROUPES_DOSSIER)
    private_zip = fields.Char(groups=GROUPES_DOSSIER)
    private_country_id = fields.Many2one(groups=GROUPES_DOSSIER)
    private_phone = fields.Char(groups=GROUPES_DOSSIER)
    private_email = fields.Char(groups=GROUPES_DOSSIER)
    country_id = fields.Many2one(groups=GROUPES_DOSSIER)
    gender = fields.Selection(groups=GROUPES_DOSSIER)
    marital = fields.Selection(groups=GROUPES_DOSSIER)
    spouse_complete_name = fields.Char(groups=GROUPES_DOSSIER)
    spouse_birthdate = fields.Date(groups=GROUPES_DOSSIER)
    children = fields.Integer(
        string='Enfants à charge', groups=GROUPES_DOSSIER)
    place_of_birth = fields.Char(groups=GROUPES_DOSSIER)
    country_of_birth = fields.Many2one(groups=GROUPES_DOSSIER)
    birthday = fields.Date(groups=GROUPES_DOSSIER)
    ssnid = fields.Char(
        string='N° CNSS / CARFO', groups=GROUPES_DOSSIER,
        help="Numéro d'immatriculation à la caisse de sécurité sociale.")
    identification_id = fields.Char(
        string='N° CNIB', groups=GROUPES_DOSSIER,
        help="Carte nationale d'identité burkinabè.")
    passport_id = fields.Char(groups=GROUPES_DOSSIER)
    certificate = fields.Selection(groups=GROUPES_DOSSIER)
    study_field = fields.Char(groups=GROUPES_DOSSIER)
    study_school = fields.Char(groups=GROUPES_DOSSIER)
    emergency_contact = fields.Char(groups=GROUPES_DOSSIER)
    emergency_phone = fields.Char(groups=GROUPES_DOSSIER)
    employee_type = fields.Selection(groups=GROUPES_DOSSIER)
    category_ids = fields.Many2many(groups=GROUPES_DOSSIER)
    departure_date = fields.Date(groups=GROUPES_DOSSIER)
    departure_reason_id = fields.Many2one(groups=GROUPES_DOSSIER)
    currency_id = fields.Many2one(groups=GROUPES_DOSSIER)
    company_country_id = fields.Many2one(
        groups='base.group_system,' + GROUPES_DOSSIER)
    company_country_code = fields.Char(
        groups='base.group_system,' + GROUPES_DOSSIER)
    work_permit_scheduled_activity = fields.Boolean(groups=GROUPES_DOSSIER)
    # Chatter et activités : traçabilité consultable par les rôles RH
    message_main_attachment_id = fields.Many2one(groups=GROUPES_DOSSIER)
    activity_ids = fields.One2many(groups=GROUPES_DOSSIER)
    activity_state = fields.Selection(groups=GROUPES_DOSSIER)
    activity_user_id = fields.Many2one(groups=GROUPES_DOSSIER)
    activity_type_id = fields.Many2one(groups=GROUPES_DOSSIER)
    activity_type_icon = fields.Char(groups=GROUPES_DOSSIER)
    activity_date_deadline = fields.Date(groups=GROUPES_DOSSIER)
    my_activity_date_deadline = fields.Date(groups=GROUPES_DOSSIER)
    activity_summary = fields.Char(groups=GROUPES_DOSSIER)
    activity_exception_decoration = fields.Selection(groups=GROUPES_DOSSIER)
    activity_exception_icon = fields.Char(groups=GROUPES_DOSSIER)
    message_is_follower = fields.Boolean(groups=GROUPES_DOSSIER)
    message_follower_ids = fields.One2many(groups=GROUPES_DOSSIER)
    message_partner_ids = fields.Many2many(groups=GROUPES_DOSSIER)
    message_ids = fields.One2many(groups=GROUPES_DOSSIER)
    has_message = fields.Boolean(groups=GROUPES_DOSSIER)
    message_needaction = fields.Boolean(groups=GROUPES_DOSSIER)
    message_needaction_counter = fields.Integer(groups=GROUPES_DOSSIER)
    message_has_error = fields.Boolean(groups=GROUPES_DOSSIER)
    message_has_error_counter = fields.Integer(groups=GROUPES_DOSSIER)
    message_attachment_count = fields.Integer(groups=GROUPES_DOSSIER)

    # ------------------------------------------------------------------
    # Identité
    # ------------------------------------------------------------------
    matricule = fields.Char(
        string='Matricule', readonly=True, copy=False, index=True,
        tracking=True, groups=GROUPES_DOSSIER)
    nom = fields.Char(string='Nom', tracking=True, groups=GROUPES_DOSSIER)
    prenom = fields.Char(string='Prénom(s)', tracking=True,
                         groups=GROUPES_DOSSIER)
    nombre_enfants = fields.Integer(
        string="Nombre d'enfants", groups=GROUPES_DOSSIER, tracking=True)
    conjoint_a_charge = fields.Boolean(
        string='Conjoint à charge', groups=GROUPES_DOSSIER, tracking=True,
        help="Conjoint sans revenu propre (règle à vérifier auprès de la "
             "DGI).")
    nb_autres_charges = fields.Integer(
        string='Autres personnes à charge', groups=GROUPES_DOSSIER,
        tracking=True)
    nb_charges_iuts = fields.Integer(
        string='Charges de famille (IUTS)',
        compute='_compute_nb_charges_iuts', store=True,
        groups=GROUPES_DOSSIER,
        help="Conjoint à charge (si marié ou en concubinage) + enfants à "
             "charge + autres personnes à charge. Sert à la réduction "
             "IUTS pour charges de famille (règle à vérifier).")

    # Pièces
    cnib_date_expiration = fields.Date(
        string='Expiration CNIB', groups=GROUPES_DOSSIER, tracking=True)
    numero_ifu = fields.Char(string='N° IFU', groups=GROUPES_DOSSIER,
                             tracking=True)
    regime_social = fields.Selection(
        REGIMES_SOCIAUX, string='Régime social', default='cnss',
        required=True, groups=GROUPES_DOSSIER, tracking=True)

    # ------------------------------------------------------------------
    # Situation professionnelle
    # ------------------------------------------------------------------
    poste_id = fields.Many2one(
        'rh.poste', string='Poste', check_company=True, tracking=True,
        groups=GROUPES_DOSSIER)
    service_id = fields.Many2one(
        'rh.service', string='Service', check_company=True, tracking=True,
        domain="[('department_id', '=?', department_id)]",
        groups=GROUPES_DOSSIER)
    site_id = fields.Many2one(
        'rh.site', string='Site', check_company=True, tracking=True,
        groups=GROUPES_DOSSIER)
    categorie_id = fields.Many2one(
        'rh.categorie', string='Catégorie / échelon', check_company=True,
        tracking=True, groups=GROUPES_DOSSIER)
    est_cadre = fields.Boolean(
        related='categorie_id.est_cadre', string='Cadre',
        groups=GROUPES_DOSSIER)
    date_embauche = fields.Date(
        string="Date d'embauche", tracking=True, groups=GROUPES_DOSSIER)
    statut_rh = fields.Selection(
        STATUTS_RH, string='Statut', default='actif', required=True,
        tracking=True, groups=GROUPES_DOSSIER)

    # ------------------------------------------------------------------
    # Rémunération (confidentiel)
    # ------------------------------------------------------------------
    salaire_base = fields.Monetary(
        string='Salaire de base', currency_field='currency_id',
        tracking=True, groups=GROUPES_SALAIRE)
    mode_paiement = fields.Selection(
        MODES_PAIEMENT, string='Mode de paiement', default='virement',
        tracking=True, groups=GROUPES_SALAIRE)
    banque_id = fields.Many2one(
        'res.bank', string='Banque', tracking=True, groups=GROUPES_SALAIRE)
    numero_compte = fields.Char(
        string='N° de compte / RIB', tracking=True, groups=GROUPES_SALAIRE)
    numero_mobile_money = fields.Char(
        string='N° mobile money', tracking=True, groups=GROUPES_SALAIRE)

    # Vue de l'employé sur sa propre rémunération (sans droit global)
    ma_remuneration = fields.Monetary(
        string='Mon salaire de base', currency_field='currency_id',
        compute='_compute_ma_remuneration', groups=GROUPES_DOSSIER)
    mon_paiement = fields.Char(
        string='Mes coordonnées de paiement',
        compute='_compute_ma_remuneration', groups=GROUPES_DOSSIER)

    # ------------------------------------------------------------------
    # Calculés
    # ------------------------------------------------------------------
    age = fields.Integer(string='Âge', compute='_compute_age',
                         groups=GROUPES_DOSSIER)
    anciennete_mois = fields.Integer(
        string='Ancienneté (mois)', compute='_compute_anciennete',
        groups=GROUPES_DOSSIER)
    anciennete_texte = fields.Char(
        string='Ancienneté', compute='_compute_anciennete',
        groups=GROUPES_DOSSIER)
    date_retraite = fields.Date(
        string='Retraite prévisionnelle', compute='_compute_date_retraite',
        groups=GROUPES_DOSSIER,
        help="Date de naissance + âge légal de retraite en vigueur "
             "(paramètre à vérifier).")

    # ------------------------------------------------------------------
    # Données annexes
    # ------------------------------------------------------------------
    historique_ids = fields.One2many(
        'rh.historique.poste', 'employee_id', string='Historique des postes',
        groups=GROUPES_DOSSIER)
    document_ids = fields.One2many(
        'rh.document', 'employee_id', string='Documents',
        groups=GROUPES_DOSSIER)
    diplome_ids = fields.One2many(
        'rh.diplome', 'employee_id', string='Diplômes',
        groups=GROUPES_DOSSIER)
    contact_urgence_ids = fields.One2many(
        'rh.contact.urgence', 'employee_id', string="Contacts d'urgence",
        groups=GROUPES_DOSSIER)
    contrat_ids = fields.One2many(
        'rh.contrat', 'employee_id', string='Contrats',
        groups=GROUPES_DOSSIER)
    contrat_en_cours_id = fields.Many2one(
        'rh.contrat', string='Contrat en cours',
        compute='_compute_contrat_en_cours', groups=GROUPES_DOSSIER)
    contrat_count = fields.Integer(
        compute='_compute_counts', groups=GROUPES_DOSSIER)
    conge_ids = fields.One2many(
        'rh.conge', 'employee_id', string='Congés', groups=GROUPES_DOSSIER)
    solde_conge_ids = fields.One2many(
        'rh.solde.conge', 'employee_id', string='Soldes de congés',
        groups=GROUPES_DOSSIER)
    presence_ids = fields.One2many(
        'rh.presence', 'employee_id', string='Présences',
        groups=GROUPES_DOSSIER)
    bulletin_ids = fields.One2many(
        'rh.bulletin.paie', 'employee_id', string='Bulletins de paie',
        groups=GROUPES_DOSSIER)
    pret_ids = fields.One2many(
        'rh.pret', 'employee_id', string='Prêts et avances',
        groups=GROUPES_DOSSIER)
    prime_ids = fields.One2many(
        'rh.prime', 'employee_id', string='Primes', groups=GROUPES_SALAIRE)
    retenue_ids = fields.One2many(
        'rh.retenue', 'employee_id', string='Retenues',
        groups=GROUPES_SALAIRE)
    retard_minutes_mois = fields.Integer(
        string='Retards du mois (min)', compute='_compute_retards_mois',
        groups=GROUPES_DOSSIER)
    document_count = fields.Integer(
        compute='_compute_counts', groups=GROUPES_DOSSIER)
    peut_gerer_dossier = fields.Boolean(
        compute='_compute_peut_gerer_dossier', groups=GROUPES_DOSSIER)

    _sql_constraints = [
        ('rh_matricule_company_uniq', 'unique(matricule, company_id)',
         'Ce matricule est déjà attribué dans cette société.'),
        ('rh_ssnid_company_uniq', 'unique(ssnid, company_id)',
         'Ce numéro CNSS / CARFO est déjà attribué dans cette société.'),
        ('rh_cnib_company_uniq', 'unique(identification_id, company_id)',
         'Ce numéro de CNIB est déjà attribué dans cette société.'),
    ]

    # ------------------------------------------------------------------
    # Calculs
    # ------------------------------------------------------------------
    @api.depends('children', 'nb_autres_charges', 'conjoint_a_charge',
                 'marital')
    def _compute_nb_charges_iuts(self):
        for emp in self:
            conjoint = 1 if (emp.conjoint_a_charge and emp.marital in (
                'married', 'cohabitant')) else 0
            emp.nb_charges_iuts = conjoint + max(emp.children, 0) \
                + max(emp.nb_autres_charges, 0)

    @api.depends_context('uid')
    @api.depends('user_id')
    def _compute_ma_remuneration(self):
        voit_tout = self.env.user.has_group(GROUPES_SALAIRE)
        modes = dict(MODES_PAIEMENT)
        for emp in self:
            emp_sudo = emp.sudo()
            if voit_tout or (emp_sudo.user_id
                             and emp_sudo.user_id == self.env.user):
                emp.ma_remuneration = emp_sudo.salaire_base
                detail = emp_sudo.numero_compte \
                    if emp_sudo.mode_paiement == 'virement' \
                    else emp_sudo.numero_mobile_money
                emp.mon_paiement = ' – '.join(filter(None, [
                    modes.get(emp_sudo.mode_paiement),
                    emp_sudo.banque_id.name
                    if emp_sudo.mode_paiement == 'virement' else False,
                    detail]))
            else:
                emp.ma_remuneration = 0.0
                emp.mon_paiement = False

    @api.depends('birthday')
    def _compute_age(self):
        today = fields.Date.context_today(self)
        for emp in self:
            emp.age = relativedelta(today, emp.birthday).years \
                if emp.birthday else 0

    @api.depends('date_embauche', 'departure_date')
    def _compute_anciennete(self):
        today = fields.Date.context_today(self)
        for emp in self:
            if not emp.date_embauche:
                emp.anciennete_mois = 0
                emp.anciennete_texte = False
                continue
            fin = emp.departure_date or today
            delta = relativedelta(fin, emp.date_embauche)
            emp.anciennete_mois = max(delta.years * 12 + delta.months, 0)
            emp.anciennete_texte = _(
                '%(a)s an(s) %(m)s mois', a=max(delta.years, 0),
                m=max(delta.months, 0))

    @api.depends('birthday', 'company_id')
    def _compute_date_retraite(self):
        Config = self.env['rh.configuration']
        today = fields.Date.context_today(self)
        for emp in self:
            emp.date_retraite = False
            if not emp.birthday:
                continue
            config = Config._get_en_vigueur(
                today, emp.company_id, raise_if_missing=False)
            if config:
                emp.date_retraite = emp.birthday + relativedelta(
                    years=config.age_retraite)

    def _compute_counts(self):
        for emp in self:
            emp.document_count = len(emp.document_ids)
            emp.contrat_count = len(emp.contrat_ids)

    def _compute_retards_mois(self):
        debut = fields.Date.context_today(self).replace(day=1)
        data = self.env['rh.retard'].sudo()._read_group(
            [('employee_id', 'in', self.ids), ('date', '>=', debut)],
            ['employee_id'], ['duree_minutes:sum'])
        cumul = {emp.id: total for emp, total in data}
        for emp in self:
            emp.retard_minutes_mois = cumul.get(emp.id, 0)

    @api.depends('contrat_ids.state', 'contrat_ids.date_debut')
    @api.depends_context('date')
    def _compute_contrat_en_cours(self):
        today = fields.Date.context_today(self)
        for emp in self:
            emp.contrat_en_cours_id = emp.contrat_ids.filtered(
                lambda c: c.state in ('essai', 'actif', 'suspendu')
                and c.date_debut <= today)[:1]

    def action_rh_contrats(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'rh_burkina.action_rh_contrat')
        action['domain'] = [('employee_id', '=', self.id)]
        action['context'] = {'default_employee_id': self.id}
        return action

    @api.depends_context('uid')
    def _compute_peut_gerer_dossier(self):
        peut = self.env.user.has_group('rh_burkina.group_rh_gestionnaire')
        for emp in self:
            emp.peut_gerer_dossier = peut

    # ------------------------------------------------------------------
    # Contraintes
    # ------------------------------------------------------------------
    @api.constrains('birthday', 'date_embauche')
    def _check_age_minimum(self):
        Config = self.env['rh.configuration']
        for emp in self:
            if not emp.birthday or not emp.date_embauche:
                continue
            if emp.birthday >= emp.date_embauche:
                raise ValidationError(_(
                    "%s : la date d'embauche doit être postérieure à la "
                    "date de naissance.", emp.name))
            config = Config._get_en_vigueur(
                emp.date_embauche, emp.company_id, raise_if_missing=False)
            if not config:
                continue
            age = relativedelta(emp.date_embauche, emp.birthday).years
            if age < config.age_minimum_embauche:
                raise ValidationError(_(
                    "%(nom)s avait %(age)s ans à l'embauche : l'âge minimum "
                    "est de %(min)s ans.", nom=emp.name, age=age,
                    min=config.age_minimum_embauche))

    @api.constrains('children', 'nombre_enfants', 'nb_autres_charges')
    def _check_charges(self):
        for emp in self:
            if emp.children < 0 or emp.nombre_enfants < 0 \
                    or emp.nb_autres_charges < 0:
                raise ValidationError(
                    _("Le nombre de personnes à charge ne peut pas être "
                      "négatif."))
            if emp.nombre_enfants and emp.children > emp.nombre_enfants:
                raise ValidationError(_(
                    "%s : le nombre d'enfants à charge dépasse le nombre "
                    "d'enfants.", emp.name))

    @api.constrains('salaire_base')
    def _check_salaire_base(self):
        for emp in self.sudo():
            if emp.salaire_base < 0:
                raise ValidationError(
                    _("Le salaire de base ne peut pas être négatif."))

    @api.constrains('service_id', 'department_id')
    def _check_service_department(self):
        for emp in self:
            if emp.service_id and emp.department_id \
                    and emp.service_id.department_id != emp.department_id:
                raise ValidationError(_(
                    "Le service %(s)s n'appartient pas au département "
                    "%(d)s.", s=emp.service_id.name,
                    d=emp.department_id.name))

    # ------------------------------------------------------------------
    # Onchanges
    # ------------------------------------------------------------------
    @api.onchange('nom', 'prenom')
    def _onchange_nom_prenom(self):
        nom_complet = self._rh_nom_complet(self.nom, self.prenom)
        if nom_complet:
            self.name = nom_complet

    @api.onchange('poste_id')
    def _onchange_poste_id(self):
        poste = self.poste_id
        if poste:
            self.department_id = poste.department_id or self.department_id
            self.service_id = poste.service_id or self.service_id
            self.categorie_id = poste.categorie_id or self.categorie_id
            self.job_title = poste.name

    @api.onchange('service_id')
    def _onchange_service_id(self):
        if self.service_id:
            self.department_id = self.service_id.department_id

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    @api.model
    def _rh_nom_complet(self, nom, prenom):
        nom = (nom or '').strip().upper()
        prenom = (prenom or '').strip()
        return ' '.join(filter(None, [nom, prenom]))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            nom_complet = self._rh_nom_complet(
                vals.get('nom'), vals.get('prenom'))
            if nom_complet and not vals.get('name'):
                vals['name'] = nom_complet
        employees = super().create(vals_list)
        for emp in employees.sudo():
            if not emp.matricule:
                emp.matricule = self.env['ir.sequence'].with_company(
                    emp.company_id).next_by_code('rh.employe')
        employees._rh_historiser_embauche()
        return employees

    def write(self, vals):
        if ('nom' in vals or 'prenom' in vals) and 'name' not in vals \
                and len(self) == 1:
            nom_complet = self._rh_nom_complet(
                vals.get('nom', self.sudo().nom),
                vals.get('prenom', self.sudo().prenom))
            if nom_complet:
                vals['name'] = nom_complet
        suivis = [f for f in CHAMPS_HISTORIQUE if f in vals]
        anciens = {}
        if suivis:
            for emp in self.sudo():
                anciens[emp.id] = {f: emp[f] for f in suivis}
        res = super().write(vals)
        if suivis:
            # Le motif peut être transmis par le contexte (contrat, sanction…)
            self._rh_historiser_changements(
                anciens, self.env.context.get('rh_motif_changement'))
        return res

    def unlink(self):
        if not self.env.su:
            raise UserError(_(
                "La suppression d'un dossier du personnel est interdite. "
                "Archivez la fiche à la place."))
        return super().unlink()

    # ------------------------------------------------------------------
    # Historique
    # ------------------------------------------------------------------
    def _rh_historiser_embauche(self):
        Historique = self.env['rh.historique.poste'].sudo()
        vals_list = []
        for emp in self.sudo():
            vals_list.append({
                'employee_id': emp.id,
                'date': emp.date_embauche or fields.Date.context_today(self),
                'type_changement': 'embauche',
                'nouveau_poste_id': emp.poste_id.id,
                'nouveau_department_id': emp.department_id.id,
                'nouvelle_categorie_id': emp.categorie_id.id,
                'nouveau_salaire': emp.salaire_base,
                'motif': _('Création du dossier'),
            })
        Historique.create(vals_list)

    def _rh_historiser_changements(self, anciens, motif=None):
        """Crée une ligne d'historique par champ suivi réellement modifié."""
        Historique = self.env['rh.historique.poste'].sudo()
        vals_list = []
        today = fields.Date.context_today(self)
        for emp in self.sudo():
            for fname, ancien in anciens.get(emp.id, {}).items():
                nouveau = emp[fname]
                if fname == 'salaire_base':
                    if emp.currency_id.compare_amounts(ancien, nouveau) == 0:
                        continue
                elif ancien == nouveau:
                    continue
                vals = {
                    'employee_id': emp.id,
                    'date': today,
                    'type_changement': CHAMPS_HISTORIQUE[fname],
                    'motif': motif or False,
                }
                if fname == 'salaire_base':
                    vals.update(ancien_salaire=ancien, nouveau_salaire=nouveau)
                else:
                    prefixes = {
                        'poste_id': ('ancien_poste_id', 'nouveau_poste_id'),
                        'department_id': ('ancien_department_id',
                                          'nouveau_department_id'),
                        'categorie_id': ('ancienne_categorie_id',
                                         'nouvelle_categorie_id'),
                    }[fname]
                    vals.update({prefixes[0]: ancien.id,
                                 prefixes[1]: nouveau.id})
                vals_list.append(vals)
        if vals_list:
            Historique.create(vals_list)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    @api.model
    def action_rh_mon_dossier(self):
        """Ouvre la fiche de l'utilisateur connecté (self-service)."""
        employee = self.search([('user_id', '=', self.env.uid)], limit=1)
        if not employee:
            raise UserError(_(
                "Aucun dossier du personnel n'est lié à votre compte. "
                "Contactez le service RH."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Mon dossier'),
            'res_model': 'hr.employee',
            'res_id': employee.id,
            'view_mode': 'form',
            'views': [(self.env.ref(
                'rh_burkina.view_rh_employe_form_self').id, 'form')],
            'target': 'current',
        }

    def action_rh_modifier_coordonnees(self):
        """Assistant de mise à jour des coordonnées et contacts d'urgence."""
        self.ensure_one()
        wizard = self.env['rh.wizard.coordonnees'].create(
            self.env['rh.wizard.coordonnees']._valeurs_initiales(self))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Modifier mes coordonnées'),
            'res_model': 'rh.wizard.coordonnees',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_rh_documents(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'rh_burkina.action_rh_document')
        action['domain'] = [('employee_id', '=', self.id)]
        action['context'] = {'default_employee_id': self.id}
        return action
