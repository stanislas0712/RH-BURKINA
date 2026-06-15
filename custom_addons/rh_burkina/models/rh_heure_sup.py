# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class RhHeureSup(models.Model):
    _name = 'rh.heure.sup'
    _description = 'Heures Supplémentaires'
    _order = 'date desc'

    employe_id = fields.Many2one('rh.employe', string='Employé', required=True, ondelete='cascade')
    presence_id = fields.Many2one('rh.presence', string='Présence', ondelete='set null')
    date = fields.Date(string='Date', required=True, default=fields.Date.today)
    heures = fields.Float(string='Heures', digits=(4, 2), required=True)
    motif = fields.Text(string='Motif')
    statut = fields.Selection([
        ('brouillon', 'Brouillon'),
        ('valide', 'Validé'),
        ('refuse', 'Refusé'),
    ], string='Statut', default='brouillon')

    @api.constrains('heures')
    def _check_heures(self):
        for rec in self:
            if rec.heures <= 0:
                raise ValidationError('Le nombre d\'heures doit être strictement positif.')

    def action_valider(self):
        self.write({'statut': 'valide'})
