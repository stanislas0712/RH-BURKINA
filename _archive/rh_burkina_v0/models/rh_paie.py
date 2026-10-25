# -*- coding: utf-8 -*-
from odoo import models, fields, api


class RhPaie(models.Model):
    _name = 'rh.paie'
    _description = 'Paie / Lot de Paie'
    _order = 'date_generation desc'

    reference = fields.Char(string='Référence', required=True, copy=False, readonly=True, default='Nouveau')
    date_generation = fields.Date(string='Date de génération', required=True, default=fields.Date.today)
    periode_debut = fields.Date(string='Période début', required=True)
    periode_fin = fields.Date(string='Période fin', required=True)
    statut = fields.Selection([
        ('brouillon', 'Brouillon'),
        ('generee', 'Générée'),
        ('paye', 'Payée'),
    ], string='Statut', default='brouillon')
    montant_total = fields.Float(string='Montant total', digits=(16, 0), default=0.0)
    bulletin_ids = fields.One2many('rh.bulletin.paie', 'paie_id', string='Bulletins')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', 'Nouveau') == 'Nouveau':
                vals['reference'] = self.env['ir.sequence'].next_by_code('rh.paie') or 'PAIE-0001'
        return super().create(vals_list)

    def action_generer(self):
        self.write({'statut': 'generee'})

    def action_payer(self):
        self.write({'statut': 'paye'})
