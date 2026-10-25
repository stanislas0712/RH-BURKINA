# -*- coding: utf-8 -*-
from odoo import models, fields


class RhTypeRetenue(models.Model):
    _name = 'rh.type.retenue'
    _description = 'Type de Retenue'
    _rec_name = 'nom'
    _order = 'nom'

    nom = fields.Char(string='Libellé', required=True)
    code = fields.Char(string='Code')
    description = fields.Text(string='Description')
    taux = fields.Float(
        string='Taux (%)',
        help='Taux de retenue en pourcentage (ex: 5.5 pour CNSS employé)'
    )
    base_calcul = fields.Selection([
        ('salaire_brut', 'Salaire Brut'),
        ('salaire_base', 'Salaire de Base'),
        ('montant_fixe', 'Montant Fixe'),
    ], string='Base de Calcul', default='salaire_base')
    est_obligatoire = fields.Boolean(
        string='Obligatoire', default=False,
        help='Retenue légale obligatoire (CNSS, IUTS, etc.)'
    )
    active = fields.Boolean(string='Actif', default=True)

    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'Le code du type de retenue doit être unique.'),
    ]

    def name_get(self):
        return [
            (rec.id, f"[{rec.code}] {rec.nom}" if rec.code else rec.nom)
            for rec in self
        ]
