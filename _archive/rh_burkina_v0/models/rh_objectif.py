# -*- coding: utf-8 -*-
from odoo import models, fields


class RhObjectif(models.Model):
    _name = 'rh.objectif'
    _description = 'Objectif de Performance'
    _order = 'date_debut desc'

    employe_id = fields.Many2one('rh.employe', string='Employé', required=True, ondelete='cascade')
    name = fields.Char(string='Objectif', required=True)
    description = fields.Text(string='Description')
    date_debut = fields.Date(string='Date de début', default=fields.Date.today)
    date_fin = fields.Date(string='Date de fin')
    ponderation = fields.Float(string='Pondération (%)', digits=(4, 1), default=100.0)
    statut = fields.Selection([
        ('en_cours', 'En cours'),
        ('atteint', 'Atteint'),
        ('partiel', 'Partiel'),
        ('echec', 'Échec'),
    ], string='Statut', default='en_cours')
    commentaire = fields.Text(string='Commentaire')
