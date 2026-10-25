# -*- coding: utf-8 -*-
from odoo import models, fields


class RhTypeConge(models.Model):
    _name = 'rh.type.conge'
    _description = 'Type de Congé'
    _order = 'name'

    name = fields.Char(string='Nom', required=True, translate=True)
    code = fields.Char(string='Code')
    duree_max_jours = fields.Integer(string='Durée max. (jours)', default=30)
    est_payee = fields.Boolean(string='Payé', default=True)
    description = fields.Text(string='Description')
    active = fields.Boolean(string='Actif', default=True)

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Le code du type de congé doit être unique.')
    ]
