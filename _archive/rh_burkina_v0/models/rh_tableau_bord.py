# -*- coding: utf-8 -*-
from odoo import models, fields, api


class RhTableauBord(models.Model):
    _name = 'rh.tableau.bord'
    _description = 'Tableau de Bord RH'
    _order = 'date_reference desc'

    name = fields.Char(string='Libellé', required=True, default='Tableau de bord RH')
    date_reference = fields.Date(string='Mis à jour le', default=fields.Date.today)
    notes = fields.Text(string='Notes')

    # ── Effectifs ────────────────────────────────────────────────────
    total_employes = fields.Integer(string='Total Employés', compute='_compute_stats')
    employes_actifs = fields.Integer(string='Actifs', compute='_compute_stats')
    employes_hommes = fields.Integer(string='Hommes', compute='_compute_stats')
    employes_femmes = fields.Integer(string='Femmes', compute='_compute_stats')
    employes_inactifs = fields.Integer(string='Inactifs', compute='_compute_stats')

    # ── Contrats ─────────────────────────────────────────────────────
    contrats_actifs = fields.Integer(string='Contrats Actifs', compute='_compute_stats')
    contrats_cdi = fields.Integer(string='CDI', compute='_compute_stats')
    contrats_cdd = fields.Integer(string='CDD', compute='_compute_stats')
    masse_salariale = fields.Float(
        string='Masse Salariale (FCFA)', digits=(16, 0), compute='_compute_stats'
    )

    # ── Congés ───────────────────────────────────────────────────────
    conges_en_cours = fields.Integer(string='Congés en Cours', compute='_compute_stats')
    conges_en_attente = fields.Integer(string='En Attente d\'Approbation', compute='_compute_stats')

    # ── Recrutement ──────────────────────────────────────────────────
    recrutements_actifs = fields.Integer(string='Postes Ouverts', compute='_compute_stats')
    candidatures = fields.Integer(string='Candidatures', compute='_compute_stats')

    # ── Formation ────────────────────────────────────────────────────
    formations_total = fields.Integer(string='Formations', compute='_compute_stats')
    inscriptions_formation = fields.Integer(string='Inscriptions', compute='_compute_stats')

    @api.depends()
    def _compute_stats(self):
        Employe = self.env['rh.employe']
        Contrat = self.env['rh.contrat']
        Conge = self.env['rh.conge']
        Recrutement = self.env['rh.recrutement']
        Formation = self.env['rh.formation']
        Candidat = self.env['rh.candidat']
        Inscription = self.env['rh.inscription.formation']
        today = fields.Date.today()

        for rec in self:
            # Effectifs
            rec.total_employes = Employe.search_count([])
            rec.employes_actifs = Employe.search_count([('statut', '=', 'actif')])
            rec.employes_hommes = Employe.search_count([('genre', '=', 'M'), ('statut', '=', 'actif')])
            rec.employes_femmes = Employe.search_count([('genre', '=', 'F'), ('statut', '=', 'actif')])
            rec.employes_inactifs = Employe.search_count([('statut', '!=', 'actif')])

            # Contrats
            rec.contrats_actifs = Contrat.search_count([('statut', '=', 'actif')])
            rec.contrats_cdi = Contrat.search_count([('statut', '=', 'actif'), ('type_contrat', '=', 'cdi')])
            rec.contrats_cdd = Contrat.search_count([('statut', '=', 'actif'), ('type_contrat', '=', 'cdd')])
            actifs = Employe.search([('statut', '=', 'actif')])
            rec.masse_salariale = sum(actifs.mapped('salaire_base'))

            # Congés
            rec.conges_en_cours = Conge.search_count([
                ('statut', '=', 'accepte'),
                ('date_debut', '<=', today),
                ('date_fin', '>=', today),
            ])
            rec.conges_en_attente = Conge.search_count([('statut', 'in', ['brouillon', 'en_cours'])])

            # Recrutement
            rec.recrutements_actifs = Recrutement.search_count([('statut', 'in', ['publie', 'en_cours'])])
            rec.candidatures = Candidat.search_count([])

            # Formation
            rec.formations_total = Formation.search_count([('active', '=', True)])
            rec.inscriptions_formation = Inscription.search_count([])
