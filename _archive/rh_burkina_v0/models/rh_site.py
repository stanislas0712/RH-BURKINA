# -*- coding: utf-8 -*-
from odoo import models, fields, api


class RhSite(models.Model):
    _name = 'rh.site'
    _description = 'Site / Agence'
    _rec_name = 'nom'
    _order = 'nom'

    nom = fields.Char(string='Nom du Site', required=True)
    code = fields.Char(string='Code')
    adresse = fields.Text(string='Adresse')
    ville = fields.Char(string='Ville')
    telephone = fields.Char(string='Téléphone')
    responsable_id = fields.Many2one('rh.employe', string='Responsable du Site')
    nb_employes = fields.Integer(
        string='Nb Employés', compute='_compute_nb_employes', store=False
    )
    active = fields.Boolean(string='Actif', default=True)

    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'Le code du site doit être unique.'),
    ]

    @api.depends_context('active_test')
    def _compute_nb_employes(self):
        for rec in self:
            rec.nb_employes = self.env['rh.employe'].search_count(
                [('site_id', '=', rec.id)]
            )

    def name_get(self):
        return [
            (rec.id, f"[{rec.code}] {rec.nom}" if rec.code else rec.nom)
            for rec in self
        ]
