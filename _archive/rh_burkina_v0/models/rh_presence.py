# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


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
    heure_pause = fields.Float(string='Heure de Pause', digits=(4, 2), default=1.0,
                                help='Durée de la pause à déduire, ex : 1.0 = 1h00')
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
    valide_par = fields.Many2one('res.users', string='Validé par', readonly=True)
    valide = fields.Boolean(string='Validé', default=False)

    _sql_constraints = [
        ('employe_date_unique', 'UNIQUE(employe_id, date)',
         'Un seul enregistrement de présence par employé et par jour.')
    ]

    @api.depends('heure_arrivee', 'heure_depart', 'heure_pause', 'heures_normales')
    def _compute_heures(self):
        for rec in self:
            if rec.heure_arrivee and rec.heure_depart and rec.heure_depart > rec.heure_arrivee:
                brut = rec.heure_depart - rec.heure_arrivee
                rec.heures_travaillees = max(brut - (rec.heure_pause or 0.0), 0.0)
                rec.heures_supplementaires = max(
                    0, rec.heures_travaillees - rec.heures_normales
                )
            else:
                rec.heures_travaillees = 0.0
                rec.heures_supplementaires = 0.0

    @api.constrains('heure_arrivee', 'heure_depart', 'heure_pause')
    def _check_heures(self):
        for rec in self:
            if rec.heure_arrivee and rec.heure_depart:
                if rec.heure_depart <= rec.heure_arrivee:
                    raise ValidationError(
                        'L\'heure de départ doit être postérieure à l\'heure d\'arrivée.')
                if rec.heure_pause and rec.heure_pause > (rec.heure_depart - rec.heure_arrivee):
                    raise ValidationError(
                        'La pause ne peut pas dépasser la durée totale de présence.')
            if rec.heure_arrivee and (rec.heure_arrivee < 0 or rec.heure_arrivee > 24):
                raise ValidationError('L\'heure d\'arrivée doit être entre 0 et 24.')
            if rec.heure_pause and rec.heure_pause < 0:
                raise ValidationError('La pause ne peut pas être négative.')

    @api.model_create_multi
    def create(self, vals_list):
        """Un employé simple (sans rôle Gestionnaire RH ou supérieur) ne peut
        créer que ses propres présences — jamais celles d'un collègue."""
        if not self.env.user.has_group('rh_burkina.group_rh_user'):
            employe = self.env['rh.employe'].search(
                [('user_id', '=', self.env.user.id)], limit=1
            )
            if not employe:
                raise ValidationError(
                    "Aucun dossier employé n'est lié à votre compte utilisateur. "
                    "Contactez votre gestionnaire RH."
                )
            for vals in vals_list:
                if vals.get('employe_id') != employe.id:
                    raise ValidationError(
                        "Vous ne pouvez saisir que votre propre présence."
                    )
        return super().create(vals_list)

    def write(self, vals):
        """Un employé simple ne peut pas s'auto-valider sa présence."""
        if not self.env.user.has_group('rh_burkina.group_rh_user'):
            if 'valide' in vals or 'valide_par' in vals:
                raise ValidationError(
                    "Seul un gestionnaire RH peut valider une présence."
                )
        return super().write(vals)

    def action_valider(self):
        if not self.env.user.has_group('rh_burkina.group_rh_user'):
            raise ValidationError("Seul un gestionnaire RH peut valider une présence.")
        self.write({'valide': True, 'valide_par': self.env.uid})

    def name_get(self):
        return [(rec.id, f"{rec.employe_id.nom_complet} – {rec.date}") for rec in self]