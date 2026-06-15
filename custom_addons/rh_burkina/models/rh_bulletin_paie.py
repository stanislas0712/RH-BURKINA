# -*- coding: utf-8 -*-
from odoo import models, fields, api


class RhBulletinPaie(models.Model):
    _name = 'rh.bulletin.paie'
    _description = 'Bulletin de Paie'
    _order = 'date_bulletin desc'

    employe_id = fields.Many2one('rh.employe', string='Employé', required=True, ondelete='cascade')
    paie_id = fields.Many2one('rh.paie', string='Paie', ondelete='cascade')
    reference = fields.Char(string='Référence', required=True, copy=False, readonly=True, default='Nouveau')
    date_bulletin = fields.Date(string='Date du Bulletin', required=True, default=fields.Date.today)
    periode_debut = fields.Date(string='Période début')
    periode_fin = fields.Date(string='Période fin')
    salaire_base = fields.Float(string='Salaire de base', digits=(16, 0))
    primes = fields.Float(string='Primes', digits=(16, 0), default=0.0)
    retenues = fields.Float(string='Retenues', digits=(16, 0), default=0.0)
    net_a_payer = fields.Float(string='Net à payer', digits=(16, 0), compute='_compute_net', store=True)
    statut = fields.Selection([
        ('brouillon', 'Brouillon'),
        ('valide', 'Validé'),
        ('paye', 'Payé'),
    ], string='Statut', default='brouillon')
    notes = fields.Text(string='Notes')

    @api.depends('salaire_base', 'primes', 'retenues')
    def _compute_net(self):
        for rec in self:
            rec.net_a_payer = rec.salaire_base + rec.primes - rec.retenues

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', 'Nouveau') == 'Nouveau':
                vals['reference'] = self.env['ir.sequence'].next_by_code('rh.bulletin.paie') or 'BUL-0001'
        return super().create(vals_list)

    def action_valider(self):
        self.write({'statut': 'valide'})

    def action_payer(self):
        self.write({'statut': 'paye'})
