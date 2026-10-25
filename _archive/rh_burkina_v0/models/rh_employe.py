# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import date


class RhEmploye(models.Model):
    _name = 'rh.employe'
    _description = 'Dossier Personnel Employé'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'nom_complet'
    _order = 'nom, prenom'

    # ── Identification ──────────────────────────────────────────────
    matricule = fields.Char(
        string='Matricule', required=True, copy=False, readonly=True,
        default='Nouveau', tracking=True
    )
    nom = fields.Char(string='Nom', required=True, tracking=True)
    prenom = fields.Char(string='Prénom', required=True, tracking=True)
    nom_complet = fields.Char(
        string='Nom Complet', compute='_compute_nom_complet', store=True
    )
    genre = fields.Selection([
        ('M', 'Masculin'),
        ('F', 'Féminin'),
    ], string='Genre', required=True, tracking=True)
    date_naissance = fields.Date(string='Date de Naissance', tracking=True)
    lieu_naissance = fields.Char(string='Lieu de Naissance')
    nationalite = fields.Char(string='Nationalité', default='Burkinabè')
    situation_familiale = fields.Selection([
        ('celibataire', 'Célibataire'),
        ('marie', 'Marié(e)'),
        ('divorce', 'Divorcé(e)'),
        ('veuf', 'Veuf/Veuve'),
    ], string='Situation Familiale', tracking=True)
    nombre_enfants = fields.Integer(string='Nombre d\'Enfants', default=0)
    photo = fields.Binary(string='Photo', attachment=True)
    user_id = fields.Many2one(
        'res.users', string='Utilisateur Odoo', copy=False,
        help="Compte utilisateur Odoo lié à cet employé. Requis pour le self-service RH (accès restreint à ses propres données).",
    )

    # ── Identification Administrative ────────────────────────────────
    numero_cnib = fields.Char(string='N° CNIB / Passeport', tracking=True)
    date_expiration_cnib = fields.Date(string='Expiration CNIB')
    numero_cnss = fields.Char(string='N° CNSS', tracking=True)
    numero_ifu = fields.Char(string='N° IFU (NIF)', tracking=True)

    # ── Coordonnées ──────────────────────────────────────────────────
    telephone = fields.Char(string='Téléphone')
    telephone2 = fields.Char(string='Téléphone 2')
    email_perso = fields.Char(string='Email Personnel')
    email_pro = fields.Char(string='Email Professionnel')
    adresse = fields.Text(string='Adresse')
    ville = fields.Char(string='Ville')
    pays_id = fields.Many2one('res.country', string='Pays',
                              default=lambda self: self.env.ref('base.bf', raise_if_not_found=False))

    # ── Informations Professionnelles ────────────────────────────────
    date_embauche = fields.Date(string='Date d\'Embauche', required=True, tracking=True)
    date_fin_contrat = fields.Date(string='Date Fin de Contrat', tracking=True)
    poste_id = fields.Many2one('rh.poste', string='Poste Actuel', tracking=True)
    departement_id = fields.Many2one('rh.departement', string='Département', tracking=True)
    service_id = fields.Many2one('rh.service', string='Service', tracking=True)
    site_id = fields.Many2one('rh.site', string='Site / Agence', tracking=True)
    superieur_id = fields.Many2one('rh.employe', string='Supérieur Hiérarchique', tracking=True)
    type_contrat = fields.Selection([
        ('cdi', 'CDI'),
        ('cdd', 'CDD'),
        ('stage', 'Stage'),
        ('consultant', 'Consultant'),
        ('vacataire', 'Vacataire'),
    ], string='Type de Contrat', tracking=True)
    categorie_id = fields.Many2one('rh.categorie', string='Catégorie / Échelon', tracking=True)

    # ── Rémunération ─────────────────────────────────────────────────
    salaire_base = fields.Float(string='Salaire de Base (FCFA)', digits=(16, 0), tracking=True)
    mode_paiement = fields.Selection([
        ('virement', 'Virement Bancaire'),
        ('cash', 'Espèces'),
        ('mobile_money', 'Mobile Money'),
    ], string='Mode de Paiement', default='virement')
    banque = fields.Char(string='Banque')
    numero_compte = fields.Char(string='N° Compte Bancaire')
    rib = fields.Char(string='RIB / IBAN')

    # ── Statut ───────────────────────────────────────────────────────
    statut = fields.Selection([
        ('actif', 'Actif'),
        ('inactif', 'Inactif'),
        ('suspendu', 'Suspendu'),
        ('demission', 'Démissionnaire'),
        ('licencie', 'Licencié'),
        ('retraite', 'Retraité'),
    ], string='Statut', default='actif', required=True, tracking=True)
    anciennete = fields.Integer(
        string='Ancienneté (années)', compute='_compute_anciennete', store=False
    )
    age = fields.Integer(string='Âge', compute='_compute_age', store=False)

    # ── Relations ────────────────────────────────────────────────────
    contact_urgence_ids = fields.One2many('rh.contact.urgence', 'employe_id',
                                          string='Contacts d\'Urgence')
    diplome_ids = fields.One2many('rh.diplome', 'employe_id', string='Diplômes')
    historique_poste_ids = fields.One2many('rh.historique.poste', 'employe_id',
                                            string='Historique des Postes')
    document_ids = fields.One2many('rh.document', 'employe_id', string='Documents')
    contrat_ids = fields.One2many('rh.contrat', 'employe_id', string='Contrats')
    conge_ids = fields.One2many('rh.conge', 'employe_id', string='Congés')
    solde_conge_ids = fields.One2many('rh.solde.conge', 'employe_id', string='Soldes de Congés')
    presence_ids = fields.One2many('rh.presence', 'employe_id', string='Présences')
    evaluation_ids = fields.One2many('rh.evaluation', 'employe_id', string='Évaluations')
    formation_ids = fields.One2many('rh.inscription.formation', 'employe_id',
                                    string='Formations')
    prime_ids = fields.One2many('rh.prime', 'employe_id', string='Primes')
    retenue_ids = fields.One2many('rh.retenue', 'employe_id', string='Retenues')
    sanction_ids = fields.One2many('rh.sanction', 'employe_id', string='Sanctions')

    # ── Contraintes & Séquence ───────────────────────────────────────
    _sql_constraints = [
        ('matricule_unique', 'UNIQUE(matricule)', 'Le matricule doit être unique.'),
        ('cnib_unique', 'UNIQUE(numero_cnib)', 'Le numéro CNIB doit être unique.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('matricule', 'Nouveau') == 'Nouveau':
                vals['matricule'] = self.env['ir.sequence'].next_by_code('rh.employe') or 'EMP-0001'
        return super().create(vals_list)

    @api.depends('nom', 'prenom')
    def _compute_nom_complet(self):
        for rec in self:
            rec.nom_complet = f"{rec.nom or ''} {rec.prenom or ''}".strip()

    @api.depends('date_embauche')
    def _compute_anciennete(self):
        today = date.today()
        for rec in self:
            if rec.date_embauche:
                delta = today - rec.date_embauche
                rec.anciennete = delta.days // 365
            else:
                rec.anciennete = 0

    @api.depends('date_naissance')
    def _compute_age(self):
        today = date.today()
        for rec in self:
            if rec.date_naissance:
                delta = today - rec.date_naissance
                rec.age = delta.days // 365
            else:
                rec.age = 0

    @api.constrains('date_naissance')
    def _check_date_naissance(self):
        for rec in self:
            if rec.date_naissance and rec.date_naissance >= date.today():
                raise ValidationError('La date de naissance doit être dans le passé.')

    @api.constrains('salaire_base')
    def _check_salaire(self):
        for rec in self:
            if rec.salaire_base < 0:
                raise ValidationError('Le salaire de base ne peut pas être négatif.')

    def name_get(self):
        return [(rec.id, f"[{rec.matricule}] {rec.nom_complet}") for rec in self]