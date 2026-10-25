# -*- coding: utf-8 -*-
from odoo import models, fields, api


class RhInscriptionFormation(models.Model):
    _name = 'rh.inscription.formation'
    _description = 'Inscription à une Formation'
    _order = 'date_inscription desc'

    employe_id = fields.Many2one('rh.employe', string='Employé', required=True, ondelete='cascade')
    formation_id = fields.Many2one('rh.formation', string='Formation', required=True, ondelete='cascade')
    date_inscription = fields.Date(string='Date d\'inscription', default=fields.Date.today)
    statut = fields.Selection([
        ('inscrit', 'Inscrit'),
        ('confirme', 'Confirmé'),
        ('annule', 'Annulé'),
        ('termine', 'Terminé'),
    ], string='Statut', default='inscrit')
    note = fields.Float(string='Note', digits=(4, 1))
    commentaire = fields.Text(string='Commentaire')

    def name_get(self):
        return [
            (rec.id, f"{rec.employe_id.nom_complet or '?'} — {rec.formation_id.name or '?'}")
            for rec in self
        ]