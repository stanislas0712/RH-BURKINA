# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class RhConge(models.Model):
    _name = 'rh.conge'
    _description = 'Demande de Congé'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_debut desc'

    employe_id = fields.Many2one('rh.employe', string='Employé', required=True, ondelete='cascade')
    type_conge_id = fields.Many2one('rh.type.conge', string='Type de Congé', required=True)
    reference = fields.Char(string='Référence', required=True, copy=False, readonly=True, default='Nouveau')
    date_demande = fields.Date(string='Date de demande', default=fields.Date.today)
    date_debut = fields.Date(string='Date de début', required=True)
    date_fin = fields.Date(string='Date de fin', required=True)
    duree_jours = fields.Integer(string='Durée (jours)', compute='_compute_duree', store=True)
    motif = fields.Text(string='Motif')
    statut = fields.Selection([
        ('brouillon', 'Brouillon'),
        ('en_cours', 'En cours'),
        ('accepte', 'Accepté'),
        ('refuse', 'Refusé'),
    ], string='Statut', default='brouillon', tracking=True)
    commentaire = fields.Text(string='Commentaire RH')

    @api.depends('date_debut', 'date_fin')
    def _compute_duree(self):
        for rec in self:
            if rec.date_debut and rec.date_fin:
                rec.duree_jours = (rec.date_fin - rec.date_debut).days + 1
            else:
                rec.duree_jours = 0

    @api.constrains('date_debut', 'date_fin')
    def _check_dates(self):
        for rec in self:
            if rec.date_fin and rec.date_debut and rec.date_fin < rec.date_debut:
                raise ValidationError('La date de fin doit être postérieure ou égale à la date de début.')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', 'Nouveau') == 'Nouveau':
                vals['reference'] = self.env['ir.sequence'].next_by_code('rh.conge') or 'CNG-0001'
        return super().create(vals_list)

    def action_accepter(self):
        for rec in self:
            # Vérification du solde disponible
            annee = rec.date_debut.year if rec.date_debut else fields.Date.today().year
            solde = self.env['rh.solde.conge'].search([
                ('employe_id', '=', rec.employe_id.id),
                ('type_conge_id', '=', rec.type_conge_id.id),
                ('annee', '=', annee),
            ], limit=1)
            if solde and solde.jours_restants < rec.duree_jours:
                raise ValidationError(
                    f"Solde insuffisant pour {rec.employe_id.nom_complet}.\n"
                    f"Jours demandés : {rec.duree_jours} | "
                    f"Jours restants : {solde.jours_restants}"
                )
        self.write({'statut': 'accepte'})
        # Recalcul des soldes concernés
        for rec in self:
            annee = rec.date_debut.year if rec.date_debut else fields.Date.today().year
            solde = self.env['rh.solde.conge'].search([
                ('employe_id', '=', rec.employe_id.id),
                ('type_conge_id', '=', rec.type_conge_id.id),
                ('annee', '=', annee),
            ], limit=1)
            if solde:
                solde._compute_jours_pris()

    def action_refuser(self):
        self.write({'statut': 'refuse'})
