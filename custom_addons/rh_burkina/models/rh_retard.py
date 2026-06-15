# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class RhRetard(models.Model):
    _name = 'rh.retard'
    _description = 'Gestion des Retards'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc'

    employe_id = fields.Many2one('rh.employe', string='Employé',
                                  required=True, ondelete='cascade', index=True)
    presence_id = fields.Many2one('rh.presence', string='Fiche de Présence',
                                   ondelete='set null')
    date = fields.Date(string='Date', required=True, default=fields.Date.today)
    heure_prevue = fields.Float(string='Heure Prévue d\'Arrivée', digits=(4, 2),
                                 help='Ex : 8.0 pour 08h00')
    heure_reelle = fields.Float(string='Heure Réelle d\'Arrivée', digits=(4, 2))
    duree_retard = fields.Float(string='Durée du Retard (min)',
                                 compute='_compute_duree', store=True)

    motif = fields.Selection([
        ('transport', 'Problème de Transport'),
        ('panne', 'Panne de Véhicule'),
        ('famille', 'Problème Familial'),
        ('medical', 'Rendez-vous Médical'),
        ('administratif', 'Démarche Administrative'),
        ('sans_motif', 'Sans Motif'),
        ('autre', 'Autre'),
    ], string='Motif', default='sans_motif')
    justifie = fields.Boolean(string='Retard Justifié', default=False, tracking=True)
    justification = fields.Text(string='Justification Détaillée')
    piece_jointe = fields.Binary(string='Justificatif', attachment=True)

    statut = fields.Selection([
        ('signale', 'Signalé'),
        ('valide', 'Validé'),
        ('excuse', 'Excusé'),
        ('sanctionne', 'Sanctionné'),
    ], string='Statut', default='signale', tracking=True)
    retenue_appliquee = fields.Boolean(string='Retenue Appliquée', default=False)
    montant_retenue = fields.Float(string='Montant Retenue (FCFA)', digits=(16, 0))
    notes_rh = fields.Text(string='Notes RH')

    @api.depends('heure_prevue', 'heure_reelle')
    def _compute_duree(self):
        for rec in self:
            if rec.heure_reelle and rec.heure_prevue and rec.heure_reelle > rec.heure_prevue:
                rec.duree_retard = (rec.heure_reelle - rec.heure_prevue) * 60
            else:
                rec.duree_retard = 0.0

    @api.constrains('heure_prevue', 'heure_reelle')
    def _check_heures(self):
        for rec in self:
            if rec.heure_prevue and rec.heure_reelle and rec.heure_reelle < rec.heure_prevue:
                raise ValidationError(
                    'L\'heure réelle d\'arrivée doit être supérieure à l\'heure prévue.')

    def action_valider(self):
        self.write({'statut': 'valide'})

    def action_excuser(self):
        self.write({'statut': 'excuse', 'justifie': True})

    def name_get(self):
        return [(rec.id, f"{rec.employe_id.nom_complet} – {rec.date} ({rec.duree_retard:.0f} min)")
                for rec in self]