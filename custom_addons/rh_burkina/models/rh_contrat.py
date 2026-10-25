from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

GROUPES_SALAIRE = 'rh_burkina.group_rh_salaire'

TYPES_CONTRAT = [
    ('cdi', 'CDI'),
    ('cdd', 'CDD'),
    ('stage', 'Stage'),
    ('consultant', 'Consultant'),
    ('vacataire', 'Vacataire'),
]

ETATS_CONTRAT = [
    ('brouillon', 'Brouillon'),
    ('essai', "Période d'essai"),
    ('actif', 'Actif'),
    ('suspendu', 'Suspendu'),
    ('resilie', 'Résilié'),
    ('expire', 'Expiré'),
]

# États où le contrat lie l'employé (un seul à une date donnée)
ETATS_EN_COURS = ('essai', 'actif', 'suspendu')

MOTIFS_FIN = [
    ('rupture_essai', "Rupture de la période d'essai"),
    ('demission', 'Démission'),
    ('licenciement', 'Licenciement'),
    ('fin_cdd', 'Fin de CDD'),
    ('retraite', 'Retraite'),
    ('deces', 'Décès'),
    ('abandon', 'Abandon de poste'),
    ('accord', 'Rupture d’un commun accord'),
    ('autre', 'Autre'),
]

# Champs figés dès que le contrat a démarré (avenant = nouveau contrat)
CHAMPS_FIGES = ['employee_id', 'type_contrat', 'date_debut',
                'contrat_precedent_id', 'avec_essai', 'essai_duree',
                'essai_unite']


class RhContrat(models.Model):
    """Contrat de travail."""

    _name = 'rh.contrat'
    _description = 'Contrat de travail'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_debut desc, id desc'
    _check_company_auto = True

    name = fields.Char(string='Référence', readonly=True, copy=False,
                       default='/', index=True)
    employee_id = fields.Many2one(
        'hr.employee', string='Employé', required=True, index=True,
        ondelete='restrict', check_company=True, tracking=True)
    company_id = fields.Many2one(
        'res.company', string='Société', required=True, index=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    type_contrat = fields.Selection(
        TYPES_CONTRAT, string='Type', required=True, default='cdi',
        tracking=True)
    state = fields.Selection(
        ETATS_CONTRAT, string='État', default='brouillon', required=True,
        tracking=True, index=True, copy=False)
    active = fields.Boolean(default=True)

    # Dates
    date_signature = fields.Date(string='Date de signature')
    date_debut = fields.Date(string='Date de début', required=True,
                             tracking=True)
    date_fin = fields.Date(
        string='Date de fin', tracking=True,
        help="Obligatoire pour un CDD.")

    # Affectation
    poste_id = fields.Many2one('rh.poste', string='Poste',
                               check_company=True, tracking=True)
    department_id = fields.Many2one('hr.department', string='Département',
                                    check_company=True, tracking=True)
    categorie_id = fields.Many2one('rh.categorie', string='Catégorie',
                                   check_company=True, tracking=True)
    site_id = fields.Many2one('rh.site', string='Lieu de travail',
                              check_company=True)

    # Temps de travail et rémunération
    temps_travail = fields.Selection(
        [('plein', 'Temps plein'), ('partiel', 'Temps partiel')],
        string='Temps de travail', default='plein', required=True)
    heures_hebdo = fields.Float(
        string='Heures hebdomadaires', compute='_compute_heures_hebdo',
        store=True, readonly=False, precompute=True)
    remuneration_type = fields.Selection(
        [('mensuelle', 'Salaire mensuel'), ('horaire', 'Taux horaire'),
         ('forfait', 'Forfait / honoraires')],
        string='Mode de rémunération', compute='_compute_remuneration_type',
        store=True, readonly=False, precompute=True, required=True)
    salaire_base = fields.Monetary(
        string='Salaire de base mensuel', tracking=True,
        groups=GROUPES_SALAIRE)
    taux_horaire = fields.Monetary(
        string='Taux horaire', tracking=True, groups=GROUPES_SALAIRE)
    hors_fourchette = fields.Boolean(
        string='Hors fourchette de la catégorie',
        compute='_compute_hors_fourchette', groups=GROUPES_SALAIRE)
    mon_salaire = fields.Monetary(
        string='Mon salaire', compute='_compute_mon_salaire')

    # Période d'essai
    avec_essai = fields.Boolean(
        string="Période d'essai", compute='_compute_avec_essai',
        store=True, readonly=False, precompute=True)
    essai_duree = fields.Integer(
        string="Durée de l'essai", compute='_compute_essai',
        store=True, readonly=False, precompute=True)
    essai_unite = fields.Selection(
        [('jour', 'Jour(s)'), ('mois', 'Mois')], string='Unité',
        compute='_compute_essai', store=True, readonly=False,
        precompute=True)
    essai_renouvelable = fields.Boolean(
        compute='_compute_essai', store=True, readonly=False,
        precompute=True, string='Essai renouvelable')
    essai_renouvele = fields.Boolean(string='Essai renouvelé', readonly=True,
                                     copy=False, tracking=True)
    date_fin_essai = fields.Date(
        string="Fin de la période d'essai", compute='_compute_date_fin_essai',
        store=True, tracking=True)

    # Renouvellement (CDD)
    contrat_precedent_id = fields.Many2one(
        'rh.contrat', string='Renouvelle le contrat', copy=False,
        check_company=True, domain="[('employee_id', '=', employee_id)]")
    renouvellement_ids = fields.One2many(
        'rh.contrat', 'contrat_precedent_id', string='Renouvellements')
    numero_renouvellement = fields.Integer(
        string='N° de renouvellement', compute='_compute_chaine_cdd',
        store=True, recursive=True)
    duree_cumulee_mois = fields.Float(
        string='Durée cumulée (mois)', compute='_compute_chaine_cdd',
        store=True, recursive=True, digits=(16, 1))

    # Préavis (calculé selon catégorie et ancienneté)
    preavis_texte = fields.Char(string='Préavis applicable',
                                compute='_compute_preavis')

    # Fin de contrat
    motif_suspension = fields.Char(string='Motif de suspension',
                                   tracking=True, copy=False)
    date_resiliation = fields.Date(string='Date de fin effective',
                                   tracking=True, copy=False)
    motif_fin = fields.Selection(MOTIFS_FIN, string='Motif de fin',
                                 tracking=True, copy=False)
    note_fin = fields.Text(string='Commentaire de fin', copy=False)

    clauses = fields.Html(string='Clauses particulières')
    note = fields.Text(string='Notes internes')

    # ------------------------------------------------------------------
    # Calculs
    # ------------------------------------------------------------------
    @api.depends('temps_travail', 'company_id', 'date_debut')
    def _compute_heures_hebdo(self):
        for rec in self:
            if rec.heures_hebdo and rec.temps_travail == 'partiel':
                continue
            config = rec._get_config(raise_if_missing=False)
            rec.heures_hebdo = config.heures_legales_hebdo if config else 0.0

    @api.depends('type_contrat')
    def _compute_remuneration_type(self):
        for rec in self:
            if rec.state not in (False, 'brouillon') and rec.remuneration_type:
                continue
            rec.remuneration_type = {
                'vacataire': 'horaire', 'consultant': 'forfait',
            }.get(rec.type_contrat, 'mensuelle')

    @api.depends('type_contrat')
    def _compute_avec_essai(self):
        for rec in self:
            if rec.state not in (False, 'brouillon'):
                continue
            rec.avec_essai = rec.type_contrat in ('cdi', 'cdd')

    @api.depends('avec_essai', 'categorie_id', 'date_debut', 'company_id')
    def _compute_essai(self):
        for rec in self:
            # Une fois le contrat démarré, l'essai convenu ne change plus
            if rec.state not in (False, 'brouillon') and rec.essai_duree:
                continue
            duree, unite, renouvelable = 0, 'mois', False
            if rec.avec_essai and rec.categorie_id:
                config = rec._get_config(raise_if_missing=False)
                if config:
                    try:
                        duree, unite = config._get_periode_essai(
                            rec.categorie_id)
                        ligne = config.essai_ids.filtered(
                            lambda l: l.categorie_id == rec.categorie_id) \
                            or config.essai_ids.filtered(
                                lambda l: not l.categorie_id
                                and l.groupe_professionnel
                                == rec.categorie_id.groupe_professionnel)
                        renouvelable = ligne[:1].renouvelable
                    except UserError:
                        pass
            rec.essai_duree = duree
            rec.essai_unite = unite
            rec.essai_renouvelable = renouvelable

    @api.depends('avec_essai', 'date_debut', 'essai_duree', 'essai_unite',
                 'essai_renouvele')
    def _compute_date_fin_essai(self):
        for rec in self:
            if not (rec.avec_essai and rec.date_debut and rec.essai_duree):
                rec.date_fin_essai = False
                continue
            duree = rec.essai_duree * (2 if rec.essai_renouvele else 1)
            delta = relativedelta(months=duree) if rec.essai_unite == 'mois' \
                else relativedelta(days=duree)
            rec.date_fin_essai = rec.date_debut + delta - relativedelta(days=1)

    @api.depends('contrat_precedent_id.numero_renouvellement',
                 'contrat_precedent_id.date_debut', 'date_debut',
                 'date_fin', 'type_contrat')
    def _compute_chaine_cdd(self):
        for rec in self:
            chaine = rec._get_chaine_cdd()
            rec.numero_renouvellement = len(chaine) - 1
            premier = chaine[-1]
            if rec.type_contrat == 'cdd' and premier.date_debut \
                    and rec.date_fin:
                rec.duree_cumulee_mois = rec._mois_entre(
                    premier.date_debut, rec.date_fin)
            else:
                rec.duree_cumulee_mois = 0.0

    @api.depends('salaire_base', 'categorie_id')
    def _compute_hors_fourchette(self):
        for rec in self:
            cat = rec.categorie_id.sudo()
            rec.hors_fourchette = bool(
                cat and rec.salaire_base and (
                    (cat.salaire_min and rec.salaire_base < cat.salaire_min)
                    or (cat.salaire_max
                        and rec.salaire_base > cat.salaire_max)))

    @api.depends_context('uid')
    @api.depends('employee_id')
    def _compute_mon_salaire(self):
        voit_tout = self.env.user.has_group(GROUPES_SALAIRE)
        for rec in self:
            sudo = rec.sudo()
            if voit_tout or sudo.employee_id.user_id == self.env.user:
                rec.mon_salaire = sudo.salaire_base or sudo.taux_horaire
            else:
                rec.mon_salaire = 0.0

    @api.depends('categorie_id', 'employee_id', 'company_id')
    def _compute_preavis(self):
        unites = {'jour': _('jour(s)'), 'mois': _('mois')}
        for rec in self:
            rec.preavis_texte = False
            if not rec.categorie_id:
                continue
            config = rec._get_config(fields.Date.context_today(rec),
                                     raise_if_missing=False)
            if not config:
                continue
            try:
                duree, unite = config._get_preavis(
                    rec.categorie_id, rec.employee_id.sudo().anciennete_mois)
            except UserError:
                continue
            rec.preavis_texte = '%s %s' % (duree, unites[unite])

    # ------------------------------------------------------------------
    # Outils
    # ------------------------------------------------------------------
    def _get_config(self, date=None, raise_if_missing=True):
        self.ensure_one()
        return self.env['rh.configuration']._get_en_vigueur(
            date or self.date_debut or fields.Date.context_today(self),
            self.company_id or self.env.company,
            raise_if_missing=raise_if_missing)

    @staticmethod
    def _mois_entre(debut, fin):
        """Nombre de mois (décimal) de ``debut`` à ``fin`` inclus."""
        delta = relativedelta(fin + relativedelta(days=1), debut)
        return delta.years * 12 + delta.months + delta.days / 30.0

    def _get_chaine_cdd(self):
        """Contrat courant puis ses prédécesseurs, du plus récent au plus
        ancien."""
        self.ensure_one()
        chaine = self
        courant = self.contrat_precedent_id
        while courant and courant not in chaine:
            chaine |= courant
            courant = courant.contrat_precedent_id
        return chaine

    def _date_fin_effective(self):
        self.ensure_one()
        return self.date_resiliation or self.date_fin

    # ------------------------------------------------------------------
    # Contraintes
    # ------------------------------------------------------------------
    @api.constrains('date_debut', 'date_fin', 'type_contrat')
    def _check_dates(self):
        for rec in self:
            if rec.type_contrat == 'cdd' and not rec.date_fin:
                raise ValidationError(_(
                    "Un CDD doit avoir une date de fin (%s).", rec.name))
            if rec.date_fin and rec.date_fin < rec.date_debut:
                raise ValidationError(_(
                    "Contrat %s : la date de fin précède la date de début.",
                    rec.name))

    @api.constrains('state', 'date_debut', 'date_fin', 'date_resiliation',
                    'employee_id')
    def _check_un_seul_contrat_en_cours(self):
        for rec in self.filtered(lambda c: c.state in ETATS_EN_COURS):
            fin = rec._date_fin_effective()
            domain = [
                ('id', '!=', rec.id),
                ('employee_id', '=', rec.employee_id.id),
                ('state', 'in', ETATS_EN_COURS),
                '|', '|',
                ('date_resiliation', '>=', rec.date_debut),
                '&', ('date_resiliation', '=', False),
                ('date_fin', '>=', rec.date_debut),
                '&', ('date_resiliation', '=', False),
                ('date_fin', '=', False),
            ]
            if fin:
                domain.append(('date_debut', '<=', fin))
            autre = self.sudo().search(domain, limit=1)
            if autre:
                raise ValidationError(_(
                    "%(emp)s a déjà un contrat en cours sur cette période "
                    "(%(ref)s). Un seul contrat actif est autorisé à une "
                    "date donnée.", emp=rec.employee_id.name, ref=autre.name))

    @api.constrains('contrat_precedent_id', 'type_contrat', 'date_fin',
                    'date_debut')
    def _check_renouvellement_cdd(self):
        for rec in self.filtered(lambda c: c.type_contrat == 'cdd'):
            config = rec._get_config(raise_if_missing=False)
            if not config:
                continue
            prec = rec.contrat_precedent_id
            if prec:
                if prec.type_contrat != 'cdd' or \
                        prec.employee_id != rec.employee_id:
                    raise ValidationError(_(
                        "Seul un CDD du même employé peut être renouvelé."))
                if prec.date_fin and rec.date_debut <= prec.date_fin:
                    raise ValidationError(_(
                        "Le renouvellement doit commencer après la fin du "
                        "contrat %s.", prec.name))
            if config.cdd_renouvellements_max >= 0 and \
                    rec.numero_renouvellement > config.cdd_renouvellements_max:
                raise ValidationError(_(
                    "Nombre maximal de renouvellements de CDD atteint "
                    "(%(max)s autorisé(s)).",
                    max=config.cdd_renouvellements_max))
            if config.cdd_duree_max_mois and \
                    rec.duree_cumulee_mois > config.cdd_duree_max_mois + 1e-6:
                raise ValidationError(_(
                    "Durée cumulée des CDD dépassée : %(duree).1f mois pour "
                    "un maximum de %(max)s mois. Au-delà, le contrat doit "
                    "être conclu à durée indéterminée.",
                    duree=rec.duree_cumulee_mois,
                    max=config.cdd_duree_max_mois))

    @api.constrains('salaire_base', 'taux_horaire', 'heures_hebdo')
    def _check_montants(self):
        for rec in self.sudo():
            if rec.salaire_base < 0 or rec.taux_horaire < 0 \
                    or rec.heures_hebdo < 0:
                raise ValidationError(
                    _("Les montants et la durée du travail ne peuvent pas "
                      "être négatifs."))

    def _verifier_smig(self):
        """Bloque un salaire inférieur au SMIG en vigueur au début."""
        for rec in self.sudo():
            config = rec._get_config()
            if rec.type_contrat == 'consultant' or \
                    rec.remuneration_type == 'forfait':
                continue
            if rec.type_contrat == 'stage' and not config.smig_stage:
                continue
            if rec.remuneration_type == 'horaire':
                # À défaut de SMIG horaire saisi : SMIG mensuel / durée
                # légale mensuelle.
                smig_h = config.smig_horaire or rec.currency_id.round(
                    config.smig_mensuel / config.heures_legales_mensuelles)
                if rec.currency_id.compare_amounts(
                        rec.taux_horaire, smig_h) < 0:
                    raise UserError(_(
                        "Contrat %(ref)s : taux horaire inférieur au SMIG "
                        "horaire en vigueur (%(smig)s).", ref=rec.name,
                        smig=smig_h))
                continue
            minimum = config.smig_mensuel
            if rec.temps_travail == 'partiel' and \
                    config.smig_prorata_temps_partiel and rec.heures_hebdo:
                minimum = config.smig_mensuel * rec.heures_hebdo \
                    / config.heures_legales_hebdo
            minimum = rec.currency_id.round(minimum)
            if rec.currency_id.compare_amounts(rec.salaire_base, minimum) < 0:
                raise UserError(_(
                    "Contrat %(ref)s : salaire de base (%(sal)s) inférieur au "
                    "SMIG en vigueur (%(smig)s).", ref=rec.name,
                    sal=rec.salaire_base, smig=minimum))

    # ------------------------------------------------------------------
    # Onchanges
    # ------------------------------------------------------------------
    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        emp = self.employee_id.sudo()
        if emp:
            self.company_id = emp.company_id
            self.poste_id = emp.poste_id
            self.department_id = emp.department_id
            self.categorie_id = emp.categorie_id
            self.site_id = emp.site_id

    @api.onchange('poste_id')
    def _onchange_poste_id(self):
        if self.poste_id:
            self.department_id = self.poste_id.department_id \
                or self.department_id
            self.categorie_id = self.poste_id.categorie_id \
                or self.categorie_id

    @api.onchange('salaire_base', 'categorie_id')
    def _onchange_fourchette(self):
        if self.hors_fourchette:
            cat = self.categorie_id.sudo()
            return {'warning': {
                'title': _('Salaire hors fourchette'),
                'message': _(
                    "Le salaire est en dehors de la fourchette de la "
                    "catégorie %(cat)s (%(min)s – %(max)s). Ce n'est pas "
                    "bloquant, mais vérifiez la classification.",
                    cat=cat.name, min=cat.salaire_min, max=cat.salaire_max),
            }}

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                company = self.env['res.company'].browse(
                    vals.get('company_id')) or self.env.company
                if vals.get('employee_id'):
                    company = self.env['hr.employee'].sudo().browse(
                        vals['employee_id']).company_id or company
                    vals.setdefault('company_id', company.id)
                vals['name'] = self.env['ir.sequence'].with_company(
                    company).next_by_code('rh.contrat') or '/'
        return super().create(vals_list)

    def write(self, vals):
        figes = [f for f in CHAMPS_FIGES if f in vals]
        if figes:
            for rec in self.filtered(lambda c: c.state != 'brouillon'):
                for fname in figes:
                    nouveau = vals[fname]
                    ancien = rec[fname]
                    if isinstance(ancien, models.BaseModel):
                        ancien = ancien.id
                    if fname == 'date_debut':
                        nouveau = fields.Date.to_date(nouveau)
                    if nouveau != ancien:
                        raise UserError(_(
                            "Le contrat %s a démarré : ses éléments "
                            "essentiels ne peuvent plus être modifiés. "
                            "Établissez un avenant ou un nouveau contrat.",
                            rec.name))
        if any(f in vals for f in ('date_fin',)) and self.filtered(
                lambda c: c.state in ('resilie', 'expire')):
            raise UserError(_("Un contrat terminé ne peut plus être "
                              "modifié."))
        res = super().write(vals)
        if {'salaire_base', 'poste_id', 'categorie_id',
                'department_id'} & set(vals):
            self.filtered(lambda c: c.state in ETATS_EN_COURS
                          )._appliquer_a_employe()
        return res

    def unlink(self):
        if not self.env.su:
            raise UserError(_("Un contrat ne peut pas être supprimé. "
                              "Archivez-le s'il s'agit d'un brouillon."))
        return super().unlink()

    # ------------------------------------------------------------------
    # Lien avec le dossier de l'employé
    # ------------------------------------------------------------------
    def _appliquer_a_employe(self):
        """Reporte salaire, poste et catégorie du contrat sur l'employé.

        L'écriture déclenche la ligne d'historique du dossier.
        """
        for rec in self.sudo():
            emp = rec.employee_id
            vals = {}
            if rec.salaire_base and emp.currency_id.compare_amounts(
                    emp.salaire_base, rec.salaire_base):
                vals['salaire_base'] = rec.salaire_base
            for fname in ('poste_id', 'categorie_id', 'department_id',
                          'site_id'):
                if rec[fname] and emp[fname] != rec[fname]:
                    vals[fname] = rec[fname].id
            if not emp.date_embauche:
                vals['date_embauche'] = rec.date_debut
            if vals:
                emp.with_context(rh_motif_changement=_(
                    'Contrat %s', rec.name)).write(vals)

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def action_demarrer(self):
        """Brouillon → période d'essai (ou actif s'il n'y a pas d'essai)."""
        for rec in self:
            if rec.state != 'brouillon':
                raise UserError(_("Seul un contrat brouillon peut être "
                                  "démarré."))
            sudo = rec.sudo()
            if sudo.remuneration_type == 'horaire' and not sudo.taux_horaire:
                raise UserError(_("Renseignez le taux horaire du contrat "
                                  "%s.", rec.name))
            if sudo.remuneration_type == 'mensuelle' and \
                    not sudo.salaire_base:
                raise UserError(_("Renseignez le salaire du contrat %s.",
                                  rec.name))
            rec._verifier_smig()
            rec.state = 'essai' if rec.avec_essai and rec.date_fin_essai \
                else 'actif'
            rec._appliquer_a_employe()
            if sudo.hors_fourchette:
                rec.message_post(body=_(
                    "Attention : salaire hors fourchette de la catégorie "
                    "%s.", rec.categorie_id.name))

    def action_confirmer_embauche(self):
        for rec in self:
            if rec.state != 'essai':
                raise UserError(_("Le contrat %s n'est pas en période "
                                  "d'essai.", rec.name))
            rec.state = 'actif'
            rec.message_post(body=_("Embauche confirmée à l'issue de la "
                                    "période d'essai."))

    def action_renouveler_essai(self):
        for rec in self:
            if rec.state != 'essai' or not rec.essai_renouvelable \
                    or rec.essai_renouvele:
                raise UserError(_(
                    "La période d'essai du contrat %s ne peut pas être "
                    "renouvelée.", rec.name))
            rec.essai_renouvele = True
            rec.message_post(body=_(
                "Période d'essai renouvelée jusqu'au %s.",
                rec.date_fin_essai))

    def action_suspendre(self):
        for rec in self:
            if rec.state != 'actif':
                raise UserError(_("Seul un contrat actif peut être "
                                  "suspendu."))
            if not rec.motif_suspension:
                raise UserError(_("Indiquez le motif de la suspension."))
            rec.state = 'suspendu'

    def action_reprendre(self):
        for rec in self:
            if rec.state != 'suspendu':
                raise UserError(_("Le contrat %s n'est pas suspendu.",
                                  rec.name))
            rec.state = 'actif'

    def action_ouvrir_fin(self):
        """Assistant de fin de contrat (résiliation ou rupture d'essai)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Mettre fin au contrat'),
            'res_model': 'rh.wizard.fin.contrat',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_contrat_id': self.id,
                'default_motif_fin':
                    'rupture_essai' if self.state == 'essai' else False,
            },
        }

    def _terminer(self, motif, date_fin, note=False):
        """Résilie le contrat à ``date_fin`` pour ``motif``."""
        for rec in self:
            if rec.state not in ETATS_EN_COURS:
                raise UserError(_("Le contrat %s n'est pas en cours.",
                                  rec.name))
            if motif == 'rupture_essai' and rec.state != 'essai':
                raise UserError(_("Le contrat %s n'est plus en période "
                                  "d'essai.", rec.name))
            if date_fin < rec.date_debut:
                raise UserError(_("La date de fin précède le début du "
                                  "contrat."))
            rec.write({'state': 'resilie', 'motif_fin': motif,
                       'date_resiliation': date_fin, 'note_fin': note})

    def action_renouveler(self):
        """Prépare le renouvellement d'un CDD (nouveau contrat brouillon)."""
        self.ensure_one()
        if self.type_contrat != 'cdd' or self.state not in ETATS_EN_COURS:
            raise UserError(_("Seul un CDD en cours peut être renouvelé."))
        # Le nouveau CDD doit recevoir sa date de fin : on ouvre un
        # formulaire pré-rempli plutôt que de créer un contrat incomplet.
        return {
            'type': 'ir.actions.act_window',
            'name': _('Renouvellement de %s', self.name),
            'res_model': 'rh.contrat',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_employee_id': self.employee_id.id,
                'default_type_contrat': 'cdd',
                'default_contrat_precedent_id': self.id,
                'default_date_debut': fields.Date.to_string(
                    self.date_fin + relativedelta(days=1)),
                'default_avec_essai': False,
                'default_poste_id': self.poste_id.id,
                'default_department_id': self.department_id.id,
                'default_categorie_id': self.categorie_id.id,
                'default_site_id': self.site_id.id,
                'default_temps_travail': self.temps_travail,
            },
        }

    @api.model
    def _cron_expirer_contrats(self):
        """Passe à « Expiré » les contrats arrivés à échéance."""
        today = fields.Date.context_today(self)
        echus = self.search([('state', 'in', ETATS_EN_COURS),
                             ('date_fin', '!=', False),
                             ('date_fin', '<', today)])
        for rec in echus:
            rec.write({'state': 'expire', 'date_resiliation': rec.date_fin,
                       'motif_fin': 'fin_cdd'
                       if rec.type_contrat == 'cdd' else 'autre'})
            rec.message_post(body=_("Contrat arrivé à échéance le %s.",
                                    rec.date_fin))
        return echus
