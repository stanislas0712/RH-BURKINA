# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class RhRecrutement(models.Model):
    _name = 'rh.recrutement'
    _description = 'Offre d\'Emploi / Recrutement'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_publication desc'

    reference = fields.Char(string='Référence', required=True, copy=False,
                             readonly=True, default='Nouveau')
    titre_poste = fields.Char(string='Titre du Poste', required=True, tracking=True)
    poste_id = fields.Many2one('rh.configuration', string='Poste',
                                domain=[('type_config', '=', 'poste')])
    departement_id = fields.Many2one('rh.configuration', string='Département',
                                      domain=[('type_config', '=', 'departement')], tracking=True)
    type_contrat = fields.Selection([
        ('cdi', 'CDI'),
        ('cdd', 'CDD'),
        ('stage', 'Stage'),
        ('consultant', 'Consultant'),
    ], string='Type de Contrat', required=True, tracking=True)
    nombre_postes = fields.Integer(string='Nombre de Postes', default=1, required=True)
    statut = fields.Selection([
        ('brouillon', 'Brouillon'),
        ('publie', 'Publié'),
        ('en_cours', 'En Cours'),
        ('cloture', 'Clôturé'),
        ('annule', 'Annulé'),
    ], string='Statut', default='brouillon', tracking=True)

    date_publication = fields.Date(string='Date de Publication')
    date_cloture = fields.Date(string='Date de Clôture', tracking=True)
    description_poste = fields.Html(string='Description du Poste')
    profil_recherche = fields.Html(string='Profil Recherché')
    niveau_etude = fields.Selection([
        ('bac', 'Baccalauréat'),
        ('bac2', 'Bac+2 (BTS/DUT)'),
        ('bac3', 'Bac+3 (Licence)'),
        ('bac5', 'Bac+5 (Master/Ingénieur)'),
        ('doctorat', 'Doctorat'),
    ], string='Niveau d\'Études Minimum')
    experience_min = fields.Integer(string='Expérience Minimum (années)')
    salaire_min = fields.Float(string='Salaire Min (FCFA)', digits=(16, 0))
    salaire_max = fields.Float(string='Salaire Max (FCFA)', digits=(16, 0))
    lieu = fields.Char(string='Lieu de Travail')
    responsable_id = fields.Many2one('res.users', string='Responsable RH',
                                      default=lambda self: self.env.user)

    candidat_ids = fields.One2many('rh.candidat', 'offre_id', string='Candidatures')
    nombre_candidats = fields.Integer(string='Nb Candidatures',
                                       compute='_compute_stats', store=True)
    nombre_entretiens = fields.Integer(string='Nb Entretiens',
                                        compute='_compute_stats', store=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', 'Nouveau') == 'Nouveau':
                vals['reference'] = self.env['ir.sequence'].next_by_code('rh.recrutement') or 'REC-0001'
        return super().create(vals_list)

    @api.depends('candidat_ids', 'candidat_ids.statut')
    def _compute_stats(self):
        for rec in self:
            rec.nombre_candidats = len(rec.candidat_ids)
            rec.nombre_entretiens = len(rec.candidat_ids.filtered(
                lambda c: c.statut in ('entretien', 'test', 'selectionne')
            ))

    @api.constrains('salaire_min', 'salaire_max')
    def _check_salaires(self):
        for rec in self:
            if rec.salaire_min and rec.salaire_max and rec.salaire_min > rec.salaire_max:
                raise ValidationError('Le salaire minimum ne peut pas dépasser le maximum.')

    def action_publier(self):
        self.write({'statut': 'publie', 'date_publication': fields.Date.today()})

    def action_cloturer(self):
        self.write({'statut': 'cloture'})

    def name_get(self):
        return [(rec.id, f"[{rec.reference}] {rec.titre_poste}") for rec in self]