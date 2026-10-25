# -*- coding: utf-8 -*-
from odoo import models, fields


class RhDepartement(models.Model):
    _name = 'rh.departement'
    _description = 'Département / Direction'
    _rec_name = 'nom'
    _order = 'nom'

    nom = fields.Char(string='Nom', required=True)
    code = fields.Char(string='Code', required=True, help='Ex: RH, FIN, TECH')
    description = fields.Text(string='Description')
    parent_id = fields.Many2one(
        'rh.departement', string='Département Parent',
        ondelete='restrict', help='Pour les sous-départements'
    )
    child_ids = fields.One2many('rh.departement', 'parent_id', string='Sous-départements')
    responsable_id = fields.Many2one('rh.employe', string='Responsable / Directeur')
    service_ids = fields.One2many('rh.service', 'departement_id', string='Services')
    nb_employes = fields.Integer(string='Nb Employés', compute='_compute_nb_employes')
    active = fields.Boolean(string='Actif', default=True)

    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'Le code du département doit être unique.'),
    ]

    def _compute_nb_employes(self):
        for rec in self:
            rec.nb_employes = self.env['rh.employe'].search_count([('departement_id', '=', rec.id)])

    def name_get(self):
        return [(rec.id, f"[{rec.code}] {rec.nom}") for rec in self]
