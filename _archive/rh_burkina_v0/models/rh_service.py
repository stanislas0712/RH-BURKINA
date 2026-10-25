# -*- coding: utf-8 -*-
from odoo import models, fields


class RhService(models.Model):
    _name = 'rh.service'
    _description = 'Service'
    _rec_name = 'nom'
    _order = 'departement_id, nom'

    nom = fields.Char(string='Nom', required=True)
    code = fields.Char(string='Code', required=True, help='Ex: RH_REC, FIN_PAI')
    departement_id = fields.Many2one(
        'rh.departement', string='Département',
        required=True, ondelete='restrict'
    )
    responsable_id = fields.Many2one('rh.employe', string='Chef de Service')
    poste_ids = fields.One2many('rh.poste', 'service_id', string='Postes')
    nb_employes = fields.Integer(string='Nb Employés', compute='_compute_nb_employes')
    active = fields.Boolean(string='Actif', default=True)

    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'Le code du service doit être unique.'),
    ]

    def _compute_nb_employes(self):
        for rec in self:
            rec.nb_employes = self.env['rh.employe'].search_count([('service_id', '=', rec.id)])

    def name_get(self):
        return [(rec.id, f"[{rec.departement_id.code}] {rec.nom}") for rec in self]
