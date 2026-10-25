# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class RhCategorie(models.Model):
    _name = 'rh.categorie'
    _description = 'Catégorie / Échelon'
    _rec_name = 'nom'
    _order = 'niveau, nom'

    nom = fields.Char(string='Libellé', required=True)
    code = fields.Char(string='Code')
    niveau = fields.Integer(string='Niveau / Échelon', default=1)
    description = fields.Text(string='Description')
    salaire_min = fields.Float(string='Salaire Min (FCFA)', digits=(16, 0))
    salaire_max = fields.Float(string='Salaire Max (FCFA)', digits=(16, 0))
    nb_employes = fields.Integer(
        string='Nb Employés', compute='_compute_nb_employes', store=False
    )
    active = fields.Boolean(string='Actif', default=True)

    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'Le code de la catégorie doit être unique.'),
    ]

    @api.depends_context('active_test')
    def _compute_nb_employes(self):
        for rec in self:
            rec.nb_employes = self.env['rh.employe'].search_count(
                [('categorie_id', '=', rec.id)]
            )

    @api.constrains('salaire_min', 'salaire_max')
    def _check_salaires(self):
        for rec in self:
            if rec.salaire_min and rec.salaire_max and rec.salaire_min > rec.salaire_max:
                raise ValidationError('Le salaire minimum ne peut pas dépasser le maximum.')

    def name_get(self):
        return [
            (rec.id, f"[{rec.code}] {rec.nom}" if rec.code else rec.nom)
            for rec in self
        ]
