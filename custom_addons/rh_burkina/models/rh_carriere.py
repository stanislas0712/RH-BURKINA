# -*- coding: utf-8 -*-
from odoo import models, fields


class RhCarriere(models.Model):
    _name = 'rh.carriere'
    _description = 'Évolution de Carrière'
    _order = 'date_debut desc'

    employe_id = fields.Many2one('rh.employe', string='Employé', required=True, ondelete='cascade')
    poste_id = fields.Many2one('rh.configuration', string='Nouveau Poste',
                                domain=[('type_config', '=', 'poste')])
    departement_id = fields.Many2one('rh.configuration', string='Nouveau Département',
                                      domain=[('type_config', '=', 'departement')])
    date_debut = fields.Date(string='Date de début', required=True)
    date_fin = fields.Date(string='Date de fin')
    motif = fields.Selection([
        ('promotion', 'Promotion'),
        ('mutation', 'Mutation'),
        ('reclassement', 'Reclassement'),
        ('restructuration', 'Restructuration'),
        ('autre', 'Autre'),
    ], string='Motif')
    notes = fields.Text(string='Notes')
    active = fields.Boolean(string='Actif', default=True)
