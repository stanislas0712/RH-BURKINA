# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class RhContrat(models.Model):
    _name = 'rh.contrat'
    _description = 'Contrat de Travail'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_debut desc'

    employe_id = fields.Many2one('rh.employe', string='Employé',
                                  required=True, ondelete='cascade', tracking=True)
    reference = fields.Char(string='Référence', required=True, copy=False,
                             readonly=True, default='Nouveau')
    type_contrat = fields.Selection([
        ('cdi', 'CDI – Contrat à Durée Indéterminée'),
        ('cdd', 'CDD – Contrat à Durée Déterminée'),
        ('stage', 'Convention de Stage'),
        ('apprentissage', 'Contrat d\'Apprentissage'),
        ('consultant', 'Contrat de Consultation'),
        ('vacataire', 'Contrat Vacataire'),
    ], string='Type de Contrat', required=True, tracking=True)
    statut = fields.Selection([
        ('brouillon', 'Brouillon'),
        ('actif', 'Actif'),
        ('expire', 'Expiré'),
        ('resilie', 'Résilié'),
        ('renouvele', 'Renouvelé'),
    ], string='Statut', default='brouillon', tracking=True)

    date_debut = fields.Date(string='Date de Début', required=True, tracking=True)
    date_fin = fields.Date(string='Date de Fin', tracking=True,
                            help='Laisser vide pour un CDI')
    duree_mois = fields.Integer(string='Durée (mois)', compute='_compute_duree', store=True)
    periode_essai_fin = fields.Date(string='Fin de Période d\'Essai')

    poste_id = fields.Many2one('rh.configuration', string='Poste',
                                domain=[('type_config', '=', 'poste')], tracking=True)
    salaire_base = fields.Float(string='Salaire de Base (FCFA)', digits=(16, 0),
                                 required=True, tracking=True)
    mode_paiement = fields.Selection([
        ('virement', 'Virement Bancaire'),
        ('cash', 'Espèces'),
        ('mobile_money', 'Mobile Money'),
    ], string='Mode de Paiement', default='virement')

    clause_confidentialite = fields.Boolean(string='Clause de Confidentialité')
    clause_non_concurrence = fields.Boolean(string='Clause de Non-Concurrence')
    duree_preavis = fields.Integer(string='Préavis (jours)')

    contrat_precedent_id = fields.Many2one('rh.contrat', string='Renouvellement du Contrat')
    document = fields.Binary(string='Document Signé', attachment=True)
    nom_fichier = fields.Char(string='Nom du Fichier')
    notes = fields.Text(string='Clauses Particulières')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', 'Nouveau') == 'Nouveau':
                vals['reference'] = self.env['ir.sequence'].next_by_code('rh.contrat') or 'CTR-0001'
        return super().create(vals_list)

    @api.depends('date_debut', 'date_fin')
    def _compute_duree(self):
        for rec in self:
            if rec.date_debut and rec.date_fin:
                delta = rec.date_fin - rec.date_debut
                rec.duree_mois = delta.days // 30
            else:
                rec.duree_mois = 0

    @api.constrains('date_debut', 'date_fin')
    def _check_dates(self):
        for rec in self:
            if rec.date_fin and rec.date_debut and rec.date_fin <= rec.date_debut:
                raise ValidationError('La date de fin doit être postérieure à la date de début.')

    @api.constrains('salaire_base')
    def _check_salaire(self):
        for rec in self:
            if rec.salaire_base <= 0:
                raise ValidationError('Le salaire de base doit être positif.')

    def action_activer(self):
        self.write({'statut': 'actif'})

    def action_resilier(self):
        self.write({'statut': 'resilie'})

    def name_get(self):
        return [(rec.id, f"{rec.reference} – {rec.employe_id.nom_complet}") for rec in self]