# -*- coding: utf-8 -*-
from odoo import models, fields


class RhContactUrgence(models.Model):
    _name = 'rh.contact.urgence'
    _description = 'Contact d\'Urgence Employé'
    _order = 'priorite, nom'

    employe_id = fields.Many2one('rh.employe', string='Employé',
                                  required=True, ondelete='cascade')
    nom = fields.Char(string='Nom Complet', required=True)
    lien = fields.Selection([
        ('conjoint', 'Conjoint(e)'),
        ('pere', 'Père'),
        ('mere', 'Mère'),
        ('frere', 'Frère'),
        ('soeur', 'Sœur'),
        ('enfant', 'Enfant'),
        ('ami', 'Ami(e)'),
        ('autre', 'Autre'),
    ], string='Lien de Parenté', required=True)
    telephone = fields.Char(string='Téléphone', required=True)
    telephone2 = fields.Char(string='Téléphone 2')
    email = fields.Char(string='Email')
    adresse = fields.Text(string='Adresse')
    priorite = fields.Integer(string='Priorité', default=1,
                               help='1 = contact prioritaire')
    notes = fields.Text(string='Notes')