# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class RhSoldeConge(models.Model):
    _name = 'rh.solde.conge'
    _description = 'Solde de Congés par Employé'
    _rec_name = 'type_conge_id'
    _order = 'annee desc, type_conge_id'

    employe_id = fields.Many2one(
        'rh.employe', string='Employé', required=True, ondelete='cascade'
    )
    type_conge_id = fields.Many2one(
        'rh.type.conge', string='Type de Congé', required=True
    )
    annee = fields.Integer(
        string='Année', required=True,
        default=lambda self: fields.Date.today().year
    )
    jours_acquis = fields.Float(
        string='Jours Acquis', digits=(5, 1), default=0.0,
        help='Nombre de jours de congé attribués pour cette année'
    )
    jours_pris = fields.Float(
        string='Jours Pris', digits=(5, 1),
        compute='_compute_jours_pris', store=True
    )
    jours_restants = fields.Float(
        string='Jours Restants', digits=(5, 1),
        compute='_compute_jours_restants', store=True
    )

    _sql_constraints = [
        ('employe_type_annee_unique',
         'UNIQUE(employe_id, type_conge_id, annee)',
         'Un seul solde par employé, type de congé et année.'),
    ]

    @api.depends('employe_id', 'type_conge_id', 'annee')
    def _compute_jours_pris(self):
        Conge = self.env['rh.conge']
        for rec in self:
            if rec.employe_id and rec.type_conge_id and rec.annee:
                conges = Conge.search([
                    ('employe_id', '=', rec.employe_id.id),
                    ('type_conge_id', '=', rec.type_conge_id.id),
                    ('statut', '=', 'accepte'),
                    ('date_debut', '>=', f'{rec.annee}-01-01'),
                    ('date_debut', '<=', f'{rec.annee}-12-31'),
                ])
                rec.jours_pris = sum(conges.mapped('duree_jours'))
            else:
                rec.jours_pris = 0.0

    @api.depends('jours_acquis', 'jours_pris')
    def _compute_jours_restants(self):
        for rec in self:
            rec.jours_restants = rec.jours_acquis - rec.jours_pris

    @api.constrains('jours_acquis')
    def _check_jours_acquis(self):
        for rec in self:
            if rec.jours_acquis < 0:
                raise ValidationError('Les jours acquis ne peuvent pas être négatifs.')

    def action_recharger(self):
        for rec in self:
            rec._compute_jours_pris()
