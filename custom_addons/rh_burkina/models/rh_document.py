# -*- coding: utf-8 -*-
from odoo import models, fields, api


class RhDocument(models.Model):
    _name = 'rh.document'
    _description = 'Documents Administratifs RH'
    _order = 'date_document desc'

    employe_id = fields.Many2one('rh.employe', string='Employé',
                                  required=True, ondelete='cascade')
    type_document = fields.Selection([
        ('contrat', 'Contrat de Travail'),
        ('avenant', 'Avenant au Contrat'),
        ('cnib', 'Copie CNIB / Passeport'),
        ('diplome', 'Diplôme'),
        ('attestation', 'Attestation de Travail'),
        ('bulletin', 'Bulletin de Paie'),
        ('courrier', 'Courrier RH'),
        ('avertissement', 'Avertissement / Sanction'),
        ('lettre_mission', 'Lettre de Mission'),
        ('medical', 'Document Médical'),
        ('autre', 'Autre'),
    ], string='Type de Document', required=True)
    titre = fields.Char(string='Titre / Référence', required=True)
    description = fields.Text(string='Description')
    date_document = fields.Date(string='Date du Document', required=True,
                                 default=fields.Date.today)
    date_expiration = fields.Date(string='Date d\'Expiration')
    expire = fields.Boolean(string='Expiré', compute='_compute_expire', store=True)
    confidentiel = fields.Boolean(string='Confidentiel', default=False)
    fichier = fields.Binary(string='Fichier', attachment=True, required=True)
    nom_fichier = fields.Char(string='Nom du Fichier')
    taille_fichier = fields.Char(string='Taille', compute='_compute_taille')
    ajoute_par = fields.Many2one('res.users', string='Ajouté par',
                                  default=lambda self: self.env.user, readonly=True)
    notes = fields.Text(string='Notes Internes')

    @api.depends('date_expiration')
    def _compute_expire(self):
        from datetime import date
        today = date.today()
        for rec in self:
            rec.expire = bool(rec.date_expiration and rec.date_expiration < today)

    @api.depends('fichier')
    def _compute_taille(self):
        import base64
        for rec in self:
            if rec.fichier:
                taille = len(base64.b64decode(rec.fichier))
                if taille < 1024:
                    rec.taille_fichier = f'{taille} o'
                elif taille < 1024 * 1024:
                    rec.taille_fichier = f'{taille // 1024} Ko'
                else:
                    rec.taille_fichier = f'{taille // (1024 * 1024)} Mo'
            else:
                rec.taille_fichier = '—'