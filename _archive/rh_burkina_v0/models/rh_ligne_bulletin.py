# -*- coding: utf-8 -*-
from odoo import models, fields


class RhLigneBulletin(models.Model):
    _name = 'rh.ligne.bulletin'
    _description = 'Ligne de Bulletin de Paie'
    _order = 'sequence, id'

    bulletin_id = fields.Many2one(
        'rh.bulletin.paie', string='Bulletin',
        required=True, ondelete='cascade'
    )
    sequence = fields.Integer(string='Ordre', default=10)
    code = fields.Char(string='Code')
    libelle = fields.Char(string='Libellé', required=True)
    categorie = fields.Selection([
        ('revenu', 'Revenu / Prime'),
        ('retenue_sal', 'Retenue Salariale'),
        ('charge_pat', 'Charge Patronale'),
    ], string='Catégorie', required=True)
    base = fields.Float(string='Base (FCFA)', digits=(16, 0))
    taux = fields.Float(string='Taux (%)', digits=(5, 4))
    montant = fields.Float(string='Montant (FCFA)', digits=(16, 0))
    is_imposable = fields.Boolean(string='Imposable', default=True)
