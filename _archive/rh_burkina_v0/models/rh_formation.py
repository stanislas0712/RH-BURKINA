# -*- coding: utf-8 -*-
from odoo import models, fields


class RhFormation(models.Model):
    _name = 'rh.formation'
    _description = 'Formation / Atelier'
    _order = 'date_debut desc'

    name = fields.Char(string='Intitulé', required=True, translate=True)
    code = fields.Char(string='Code')
    categorie = fields.Selection([
        ('technique', 'Technique'),
        ('manageriale', 'Managériale'),
        ('qualite', 'Qualité'),
        ('securite', 'Sécurité'),
        ('autre', 'Autre'),
    ], string='Catégorie')
    date_debut = fields.Date(string='Date de début')
    date_fin = fields.Date(string='Date de fin')
    duree_jours = fields.Integer(string='Durée (jours)', default=1)
    lieu = fields.Char(string='Lieu')
    formateur = fields.Char(string='Formateur')
    description = fields.Text(string='Description')
    active = fields.Boolean(string='Actif', default=True)

    inscription_ids = fields.One2many('rh.inscription.formation', 'formation_id', string='Inscriptions')
