# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class RhHistoriquePoste(models.Model):
    _name = 'rh.historique.poste'
    _description = 'Historique Professionnel (Postes)'
    _order = 'date_debut desc'

    employe_id = fields.Many2one('rh.employe', string='Employé',
                                  required=True, ondelete='cascade')
    type_mouvement = fields.Selection([
        ('embauche', 'Embauche'),
        ('promotion', 'Promotion'),
        ('mutation', 'Mutation'),
        ('reaffectation', 'Réaffectation'),
        ('degradation', 'Rétrogradation'),
        ('fin_contrat', 'Fin de Contrat'),
    ], string='Type de Mouvement', required=True, default='embauche')

    # Ancien poste
    ancien_poste_id = fields.Many2one('rh.poste', string='Ancien Poste')
    ancien_departement_id = fields.Many2one('rh.departement', string='Ancien Département')
    ancien_salaire = fields.Float(string='Ancien Salaire (FCFA)', digits=(16, 0))

    # Nouveau poste
    nouveau_poste_id = fields.Many2one('rh.poste', string='Nouveau Poste', required=True)
    nouveau_departement_id = fields.Many2one('rh.departement', string='Nouveau Département')
    nouveau_salaire = fields.Float(string='Nouveau Salaire (FCFA)', digits=(16, 0))

    date_debut = fields.Date(string='Date Effet', required=True)
    date_fin = fields.Date(string='Date Fin')
    motif = fields.Text(string='Motif / Justification')
    decision_par = fields.Char(string='Décision prise par')
    reference_decision = fields.Char(string='Réf. Décision / Arrêté')
    piece_jointe = fields.Binary(string='Document Joint', attachment=True)
    nom_fichier = fields.Char(string='Nom du Fichier')

    duree_jours = fields.Integer(
        string='Durée (jours)', compute='_compute_duree', store=False
    )

    @api.depends('date_debut', 'date_fin')
    def _compute_duree(self):
        from datetime import date
        for rec in self:
            fin = rec.date_fin or date.today()
            if rec.date_debut:
                rec.duree_jours = (fin - rec.date_debut).days
            else:
                rec.duree_jours = 0

    @api.constrains('date_debut', 'date_fin')
    def _check_dates(self):
        for rec in self:
            if rec.date_fin and rec.date_debut and rec.date_fin < rec.date_debut:
                raise ValidationError('La date de fin doit être après la date de début.')