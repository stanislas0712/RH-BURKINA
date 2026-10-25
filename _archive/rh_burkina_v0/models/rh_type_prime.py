# -*- coding: utf-8 -*-
from odoo import models, fields


class RhTypePrime(models.Model):
    _name = 'rh.type.prime'
    _description = 'Type de Prime'
    _rec_name = 'nom'
    _order = 'nom'

    nom = fields.Char(string='Libellé', required=True)
    code = fields.Char(string='Code')
    description = fields.Text(string='Description')
    est_imposable = fields.Boolean(
        string='Imposable (ITS)', default=False,
        help='Cocher si cette prime est soumise à l\'impôt sur les traitements et salaires'
    )
    montant_fixe = fields.Float(
        string='Montant Fixe (FCFA)', digits=(16, 0),
        help='Montant forfaitaire si la prime est à montant fixe'
    )
    taux_pourcentage = fields.Float(
        string='Taux (%)',
        help='Taux en pourcentage du salaire de base si prime en %'
    )
    active = fields.Boolean(string='Actif', default=True)

    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'Le code du type de prime doit être unique.'),
    ]

    def name_get(self):
        return [
            (rec.id, f"[{rec.code}] {rec.nom}" if rec.code else rec.nom)
            for rec in self
        ]
