# -*- coding: utf-8 -*-
from odoo import models, fields


class RhPrime(models.Model):
    _name = 'rh.prime'
    _description = 'Prime / Allocation'
    _order = 'date_effet desc'

    employe_id = fields.Many2one('rh.employe', string='Employé', required=True, ondelete='cascade')
    name = fields.Char(string='Libellé', required=True)
    type_prime = fields.Many2one('rh.type.prime', string='Type de Prime')
    montant = fields.Float(string='Montant (FCFA)', digits=(16, 0), required=True)
    date_effet = fields.Date(string='Date d\'effet', default=fields.Date.today)
    description = fields.Text(string='Description')
    active = fields.Boolean(string='Actif', default=True)
