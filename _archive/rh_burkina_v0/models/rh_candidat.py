# -*- coding: utf-8 -*-
from odoo import models, fields, api


class RhCandidat(models.Model):
    _name = 'rh.candidat'
    _description = 'Candidature / CV'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_candidature desc'

    reference = fields.Char(string='Référence', required=True, copy=False,
                             readonly=True, default='Nouveau')
    offre_id = fields.Many2one('rh.recrutement', string='Offre d\'Emploi',
                                required=True, ondelete='cascade')
    nom = fields.Char(string='Nom', required=True, tracking=True)
    prenom = fields.Char(string='Prénom', required=True)
    nom_complet = fields.Char(string='Nom Complet', compute='_compute_nom_complet', store=True)
    genre = fields.Selection([('M', 'Masculin'), ('F', 'Féminin')], string='Genre')
    date_naissance = fields.Date(string='Date de Naissance')
    telephone = fields.Char(string='Téléphone', required=True)
    email = fields.Char(string='Email')
    ville = fields.Char(string='Ville de Résidence')

    niveau_etude = fields.Selection([
        ('bac', 'Baccalauréat'),
        ('bac2', 'Bac+2'),
        ('bac3', 'Bac+3'),
        ('bac5', 'Bac+5'),
        ('doctorat', 'Doctorat'),
    ], string='Niveau d\'Études')
    annees_experience = fields.Integer(string='Années d\'Expérience')
    domaine_expertise = fields.Char(string='Domaine d\'Expertise')

    statut = fields.Selection([
        ('recu', 'Reçu'),
        ('en_cours', 'En Cours d\'Analyse'),
        ('entretien', 'Convoqué Entretien'),
        ('test', 'Test Technique'),
        ('selectionne', 'Sélectionné'),
        ('rejete', 'Rejeté'),
        ('embauche', 'Embauché'),
    ], string='Statut', default='recu', tracking=True)

    date_candidature = fields.Date(string='Date de Candidature',
                                    required=True, default=fields.Date.today)
    source = fields.Selection([
        ('site_web', 'Site Web'),
        ('linkedin', 'LinkedIn'),
        ('recommandation', 'Recommandation'),
        ('agence', 'Agence de Recrutement'),
        ('candidature_spontanee', 'Candidature Spontanée'),
        ('autre', 'Autre'),
    ], string='Source', default='site_web')

    cv = fields.Binary(string='CV', attachment=True)
    nom_cv = fields.Char(string='Nom du fichier CV')
    lettre_motivation = fields.Binary(string='Lettre de Motivation', attachment=True)
    note_cv = fields.Float(string='Note CV (/20)', digits=(4, 1))
    commentaire_rh = fields.Text(string='Commentaire RH')

    entretien_ids = fields.One2many('rh.entretien', 'candidat_id', string='Entretiens')
    employe_id = fields.Many2one('rh.employe', string='Employé Créé',
                                  help='Renseigné si le candidat a été embauché')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', 'Nouveau') == 'Nouveau':
                vals['reference'] = self.env['ir.sequence'].next_by_code('rh.candidat') or 'CAN-0001'
        return super().create(vals_list)

    @api.depends('nom', 'prenom')
    def _compute_nom_complet(self):
        for rec in self:
            rec.nom_complet = f"{rec.nom or ''} {rec.prenom or ''}".strip()

    def name_get(self):
        return [(rec.id, f"[{rec.reference}] {rec.nom_complet}") for rec in self]