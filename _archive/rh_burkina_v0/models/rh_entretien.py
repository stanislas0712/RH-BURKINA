# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class RhEntretien(models.Model):
    _name = 'rh.entretien'
    _description = 'Planification des Entretiens'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_heure desc'

    candidat_id = fields.Many2one('rh.candidat', string='Candidat',
                                   required=True, ondelete='cascade')
    offre_id = fields.Many2one(related='candidat_id.offre_id', string='Offre',
                                store=True, readonly=True)
    type_entretien = fields.Selection([
        ('telephonique', 'Entretien Téléphonique'),
        ('visio', 'Visioconférence'),
        ('presentiel', 'Entretien Présentiel'),
        ('technique', 'Test Technique'),
        ('panel', 'Entretien Panel'),
    ], string='Type', required=True, default='presentiel')
    statut = fields.Selection([
        ('planifie', 'Planifié'),
        ('confirme', 'Confirmé'),
        ('realise', 'Réalisé'),
        ('annule', 'Annulé'),
        ('reporte', 'Reporté'),
    ], string='Statut', default='planifie', tracking=True)

    date_heure = fields.Datetime(string='Date & Heure', required=True, tracking=True)
    duree_minutes = fields.Integer(string='Durée (min)', default=60)
    lieu = fields.Char(string='Lieu / Lien Visio')

    intervieweur_ids = fields.Many2many('res.users', string='Intervieweurs',
                                         relation='rh_entretien_user_rel')
    note_globale = fields.Float(string='Note Globale (/20)', digits=(4, 1))
    note_competences = fields.Float(string='Note Compétences (/20)', digits=(4, 1))
    note_communication = fields.Float(string='Note Communication (/20)', digits=(4, 1))
    note_motivation = fields.Float(string='Note Motivation (/20)', digits=(4, 1))
    recommandation = fields.Selection([
        ('fortement_recommande', 'Fortement Recommandé'),
        ('recommande', 'Recommandé'),
        ('reserve', 'Réservé'),
        ('non_recommande', 'Non Recommandé'),
    ], string='Recommandation', tracking=True)
    compte_rendu = fields.Text(string='Compte-Rendu')
    points_forts = fields.Text(string='Points Forts')
    points_faibles = fields.Text(string='Points à Améliorer')
    questions_posees = fields.Text(string='Questions Posées')

    @api.constrains('note_globale', 'note_competences', 'note_communication', 'note_motivation')
    def _check_notes(self):
        for rec in self:
            for note in [rec.note_globale, rec.note_competences,
                         rec.note_communication, rec.note_motivation]:
                if note and (note < 0 or note > 20):
                    raise ValidationError('Les notes doivent être comprises entre 0 et 20.')

    def action_confirmer(self):
        self.write({'statut': 'confirme'})

    def action_realiser(self):
        self.write({'statut': 'realise'})

    def name_get(self):
        return [(rec.id,
                 f"{rec.candidat_id.nom_complet} – {fields.Datetime.to_string(rec.date_heure)}")
                for rec in self]