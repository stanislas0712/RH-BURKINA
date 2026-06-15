# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta


class RhPresence(models.Model):
    _name = 'rh.presence'
    _description = 'Pointage Présence (Arrivées / Départs)'
    _order = 'date desc, employe_id'

    employe_id = fields.Many2one('rh.employe', string='Employé',
                                  required=True, ondelete='cascade', index=True)
    date = fields.Date(string='Date', required=True, default=fields.Date.today, index=True)
    heure_arrivee = fields.Float(string='Heure d\'Arrivée', digits=(4, 2),
                                  help='Format décimal : 8.5 = 08h30')
    heure_depart = fields.Float(string='Heure de Départ', digits=(4, 2))
    heures_travaillees = fields.Float(string='Heures Travaillées',
                                       compute='_compute_heures', store=True, digits=(4, 2))
    heures_normales = fields.Float(string='Heures Normales', default=8.0, digits=(4, 2))
    heures_supplementaires = fields.Float(string='Heures Sup.',
                                           compute='_compute_heures', store=True, digits=(4, 2))
    statut = fields.Selection([
        ('present', 'Présent'),
        ('absent', 'Absent'),
        ('retard', 'Retard'),
        ('conge', 'En Congé'),
        ('mission', 'En Mission'),
        ('teletravail', 'Télétravail'),
        ('ferie', 'Jour Férié'),
    ], string='Statut', default='present', required=True)
    type_pointage = fields.Selection([
        ('manuel', 'Saisie Manuelle'),
        ('badge', 'Badge / Pointeuse'),
        ('biometrique', 'Biométrique'),
        ('mobile', 'Application Mobile'),
    ], string='Mode de Pointage', default='manuel')
    notes = fields.Text(string='Notes / Observations')
    valide_par = fields.Many2one('res.users', string='Validé par')
    valide = fields.Boolean(string='Validé', default=False)

    _sql_constraints = [
        ('employe_date_unique', 'UNIQUE(employe_id, date)',
         'Un seul enregistrement de présence par employé et par jour.')
    ]

    @api.depends('heure_arrivee', 'heure_depart', 'heures_normales')
    def _compute_heures(self):
        for rec in self:
            if rec.heure_arrivee and rec.heure_depart and rec.heure_depart > rec.heure_arrivee:
                rec.heures_travaillees = rec.heure_depart - rec.heure_arrivee
                rec.heures_supplementaires = max(
                    0, rec.heures_travaillees - rec.heures_normales
                )
            else:
                rec.heures_travaillees = 0.0
                rec.heures_supplementaires = 0.0

    @api.constrains('heure_arrivee', 'heure_depart')
    def _check_heures(self):
        for rec in self:
            if rec.heure_arrivee and rec.heure_depart:
                if rec.heure_depart <= rec.heure_arrivee:
                    raise ValidationError(
                        'L\'heure de départ doit être postérieure à l\'heure d\'arrivée.')
            if rec.heure_arrivee and (rec.heure_arrivee < 0 or rec.heure_arrivee > 24):
                raise ValidationError('L\'heure d\'arrivée doit être entre 0 et 24.')

    def action_valider(self):
        self.write({'valide': True, 'valide_par': self.env.uid})

    def name_get(self):
        return [(rec.id, f"{rec.employe_id.nom_complet} – {rec.date}") for rec in self]