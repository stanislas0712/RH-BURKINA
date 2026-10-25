# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class RhSanction(models.Model):
    _name = 'rh.sanction'
    _description = 'Sanction Disciplinaire'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'reference'
    _order = 'date_sanction desc'

    reference = fields.Char(
        string='Référence', required=True, copy=False,
        readonly=True, default='Nouveau', tracking=True
    )
    employe_id = fields.Many2one(
        'rh.employe', string='Employé',
        required=True, ondelete='cascade', tracking=True
    )
    type_sanction = fields.Selection([
        ('avertissement', 'Avertissement'),
        ('blame', 'Blâme'),
        ('mise_en_demeure', 'Mise en Demeure'),
        ('suspension', 'Suspension sans solde'),
        ('licenciement', 'Licenciement'),
    ], string='Type de Sanction', required=True, tracking=True)

    date_sanction = fields.Date(
        string='Date de la Sanction', required=True,
        default=fields.Date.today, tracking=True
    )
    motif = fields.Text(string='Motif / Faute reprochée', required=True)
    description = fields.Text(string='Description détaillée')

    duree_suspension = fields.Integer(
        string='Durée de suspension (jours)',
        help='Renseigner uniquement pour une suspension'
    )
    decision_par = fields.Char(string='Décision prise par')
    reference_decision = fields.Char(string='Réf. Décision / Arrêté')
    piece_jointe = fields.Binary(string='Document Joint', attachment=True)
    nom_fichier = fields.Char(string='Nom du fichier')

    statut = fields.Selection([
        ('brouillon', 'Brouillon'),
        ('notifie', 'Notifié à l\'employé'),
        ('confirme', 'Confirmé'),
        ('annule', 'Annulé'),
    ], string='Statut', default='brouillon', tracking=True)
    active = fields.Boolean(string='Actif', default=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', 'Nouveau') == 'Nouveau':
                vals['reference'] = (
                    self.env['ir.sequence'].next_by_code('rh.sanction')
                    or 'SANC-0001'
                )
        return super().create(vals_list)

    @api.constrains('type_sanction', 'duree_suspension')
    def _check_suspension(self):
        for rec in self:
            if rec.type_sanction == 'suspension' and not rec.duree_suspension:
                raise ValidationError(
                    'Veuillez renseigner la durée de suspension en jours.'
                )

    def action_notifier(self):
        self.write({'statut': 'notifie'})

    def action_confirmer(self):
        for rec in self:
            rec.write({'statut': 'confirme'})
            if rec.type_sanction == 'licenciement':
                rec.employe_id.write({'statut': 'licencie'})

    def action_annuler(self):
        self.write({'statut': 'annule'})

    def name_get(self):
        return [
            (rec.id, f"[{rec.reference}] {rec.employe_id.nom_complet} — {dict(rec._fields['type_sanction'].selection).get(rec.type_sanction, '')}")
            for rec in self
        ]
