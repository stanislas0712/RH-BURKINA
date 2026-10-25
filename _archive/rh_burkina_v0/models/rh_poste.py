# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class RhPoste(models.Model):
    _name = 'rh.poste'
    _description = 'Poste / Emploi'
    _rec_name = 'titre'
    _order = 'titre'

    titre = fields.Char(string='Titre du Poste', required=True)
    code = fields.Char(string='Code Poste', help='Ex: DEV_SR, COMPT_01')
    description_missions = fields.Text(string='Description des Missions')
    competences_requises = fields.Text(string='Compétences Requises')
    statut = fields.Selection([
        ('actif', 'Actif'),
        ('en_recrutement', 'En Recrutement'),
        ('obsolete', 'Obsolète'),
    ], string='Statut', default='actif', required=True)
    salaire_min = fields.Float(string='Salaire Min (FCFA)', digits=(16, 0))
    salaire_max = fields.Float(string='Salaire Max (FCFA)', digits=(16, 0))
    service_id = fields.Many2one('rh.service', string='Service')
    poste_superieur_id = fields.Many2one(
        'rh.poste', string='Poste N+1 (Supérieur)',
        ondelete='set null', help='Poste hiérarchique supérieur (théorique)'
    )
    postes_subordonnes_ids = fields.One2many(
        'rh.poste', 'poste_superieur_id', string='Postes Subordonnés'
    )
    nb_employes = fields.Integer(string='Nb Titulaires', compute='_compute_nb_employes')
    active = fields.Boolean(string='Actif', default=True)

    def _compute_nb_employes(self):
        for rec in self:
            rec.nb_employes = self.env['rh.employe'].search_count([('poste_id', '=', rec.id)])

    @api.constrains('salaire_min', 'salaire_max')
    def _check_salaires(self):
        for rec in self:
            if rec.salaire_min and rec.salaire_max and rec.salaire_min > rec.salaire_max:
                raise ValidationError('Le salaire minimum ne peut pas dépasser le maximum.')

    def name_get(self):
        return [(rec.id, rec.titre) for rec in self]
