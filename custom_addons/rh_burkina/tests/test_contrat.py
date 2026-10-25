from datetime import date

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import Form, tagged

from .common import RhBurkinaCommon


@tagged('post_install', '-at_install', 'rh_burkina')
class TestContrat(RhBurkinaCommon):
    """Contrats : essai, SMIG, CDD, préavis, chevauchements."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.chef_emp = cls.env['hr.employee'].create({
            'name': 'Chef Finances', 'user_id': cls.user_chef.id})
        cls.dep = cls.env['hr.department'].create({
            'name': 'Finances', 'manager_id': cls.chef_emp.id})
        cls.cat_cadre = cls.env['rh.categorie'].create({
            'categorie': 'Cat. 8', 'groupe_professionnel': 'cadre',
            'salaire_min': 200000, 'salaire_max': 500000})
        cls.cat_ouvrier = cls.env['rh.categorie'].create({
            'categorie': 'Cat. 1', 'groupe_professionnel': 'ouvrier'})
        cls.poste = cls.env['rh.poste'].create({
            'name': 'Comptable', 'department_id': cls.dep.id,
            'categorie_id': cls.cat_cadre.id})
        cls.emp = cls.env['hr.employee'].create({
            'name': 'Awa Ouedraogo', 'department_id': cls.dep.id,
            'user_id': cls.user_employe.id})
        cls.autre = cls.env['hr.employee'].create({'name': 'Issa Sawadogo'})

    def _contrat(self, employee=None, **vals):
        base = {
            'employee_id': (employee or self.emp).id,
            'type_contrat': 'cdi',
            'date_debut': date(2025, 1, 1),
            'poste_id': self.poste.id,
            'categorie_id': self.cat_cadre.id,
            'salaire_base': 300000,
        }
        base.update(vals)
        return self.env['rh.contrat'].create(base)

    # ------------------------------------------------------------------
    # Cycle de vie
    # ------------------------------------------------------------------
    def test_cycle_cdi_avec_essai(self):
        contrat = self._contrat()
        self.assertRegex(contrat.name, r'^CTR-\d{4}$')
        self.assertTrue(contrat.avec_essai)
        self.assertEqual((contrat.essai_duree, contrat.essai_unite),
                         (3, 'mois'))                  # cadre : 3 mois
        self.assertEqual(contrat.date_fin_essai, date(2025, 3, 31))
        contrat.action_demarrer()
        self.assertEqual(contrat.state, 'essai')
        # Report sur le dossier + historique
        self.assertEqual(self.emp.salaire_base, 300000)
        self.assertEqual(self.emp.poste_id, self.poste)
        self.assertEqual(self.emp.categorie_id, self.cat_cadre)
        self.assertEqual(self.emp.date_embauche, date(2025, 1, 1))
        ligne = self.emp.historique_ids.filtered(
            lambda h: h.type_changement == 'salaire')
        self.assertIn(contrat.name, ligne.motif)
        self.assertEqual(self.emp.contrat_en_cours_id, contrat)
        contrat.action_confirmer_embauche()
        self.assertEqual(contrat.state, 'actif')

    def test_sans_essai_demarre_actif(self):
        contrat = self._contrat(avec_essai=False)
        contrat.action_demarrer()
        self.assertEqual(contrat.state, 'actif')

    def test_rupture_essai(self):
        contrat = self._contrat()
        contrat.action_demarrer()
        action = contrat.action_ouvrir_fin()
        wizard = Form(self.env['rh.wizard.fin.contrat'].with_context(
            action['context']))
        wizard.date_fin = date(2025, 2, 10)
        wizard.save().action_valider()
        self.assertEqual(contrat.state, 'resilie')
        self.assertEqual(contrat.motif_fin, 'rupture_essai')
        self.assertEqual(contrat.date_resiliation, date(2025, 2, 10))
        with self.assertRaises(UserError):
            contrat.action_confirmer_embauche()

    def test_renouvellement_essai_unique(self):
        self.config.essai_ids.filtered(
            lambda l: l.groupe_professionnel == 'cadre').renouvelable = True
        contrat = self._contrat()
        self.assertTrue(contrat.essai_renouvelable)
        contrat.action_demarrer()
        contrat.action_renouveler_essai()
        self.assertEqual(contrat.date_fin_essai, date(2025, 6, 30))
        with self.assertRaises(UserError):
            contrat.action_renouveler_essai()

    def test_suspension_motif_obligatoire(self):
        contrat = self._contrat(avec_essai=False)
        contrat.action_demarrer()
        with self.assertRaises(UserError):
            contrat.action_suspendre()
        contrat.motif_suspension = 'Maladie de longue durée'
        contrat.action_suspendre()
        self.assertEqual(contrat.state, 'suspendu')
        contrat.action_reprendre()
        self.assertEqual(contrat.state, 'actif')

    # ------------------------------------------------------------------
    # SMIG et fourchette
    # ------------------------------------------------------------------
    def test_salaire_inferieur_smig_refuse(self):
        contrat = self._contrat(salaire_base=40000,
                                categorie_id=self.cat_ouvrier.id)
        with self.assertRaises(UserError):
            contrat.action_demarrer()
        self.assertEqual(contrat.state, 'brouillon')
        contrat.salaire_base = 45000                     # = SMIG : accepté
        contrat.action_demarrer()

    def test_smig_temps_partiel_proratise(self):
        # 20 h / 40 h : minimum 22 500
        contrat = self._contrat(temps_travail='partiel', heures_hebdo=20,
                                salaire_base=22000,
                                categorie_id=self.cat_ouvrier.id)
        with self.assertRaises(UserError):
            contrat.action_demarrer()
        contrat.salaire_base = 22500
        contrat.action_demarrer()

    def test_smig_stage_et_vacataire(self):
        stage = self._contrat(type_contrat='stage', salaire_base=10000,
                              categorie_id=self.cat_ouvrier.id)
        self.assertFalse(stage.avec_essai)
        stage.action_demarrer()                  # SMIG non applicable
        vacation = self._contrat(self.autre, type_contrat='vacataire',
                                 salaire_base=0, taux_horaire=200,
                                 categorie_id=self.cat_ouvrier.id)
        self.assertEqual(vacation.remuneration_type, 'horaire')
        with self.assertRaises(UserError):       # 45 000 / 173,33 = 260
            vacation.action_demarrer()
        vacation.taux_horaire = 260
        vacation.action_demarrer()

    def test_hors_fourchette_non_bloquant(self):
        contrat = self._contrat(salaire_base=600000)
        self.assertTrue(contrat.hors_fourchette)
        contrat.action_demarrer()
        self.assertEqual(contrat.state, 'essai')
        self.assertTrue(any('hors fourchette' in (m.body or '')
                            for m in contrat.message_ids))

    # ------------------------------------------------------------------
    # Un seul contrat en cours
    # ------------------------------------------------------------------
    def test_deux_contrats_en_cours_refuses(self):
        premier = self._contrat(avec_essai=False)
        premier.action_demarrer()
        second = self._contrat(date_debut=date(2025, 6, 1))
        with self.assertRaises(ValidationError):
            second.action_demarrer()
        # Après la fin du premier, un nouveau contrat est possible
        premier._terminer('demission', date(2025, 5, 31))
        second.action_demarrer()
        self.assertEqual(second.state, 'essai')

    # ------------------------------------------------------------------
    # CDD
    # ------------------------------------------------------------------
    def test_cdd_date_fin_obligatoire(self):
        with self.assertRaises(ValidationError):
            self._contrat(type_contrat='cdd')

    def test_cdd_renouvellements_plafonnes(self):
        cdd = self._contrat(type_contrat='cdd', avec_essai=False,
                            date_fin=date(2025, 12, 31))
        cdd.action_demarrer()
        action = cdd.action_renouveler()
        self.assertEqual(action['context']['default_date_debut'],
                         '2026-01-01')
        renouv = self._contrat(type_contrat='cdd', avec_essai=False,
                               contrat_precedent_id=cdd.id,
                               date_debut=date(2026, 1, 1),
                               date_fin=date(2026, 12, 31))
        self.assertEqual(renouv.numero_renouvellement, 1)
        self.assertAlmostEqual(renouv.duree_cumulee_mois, 24.0, places=1)
        # 2e renouvellement : refusé (1 autorisé)
        with self.assertRaises(ValidationError):
            self._contrat(type_contrat='cdd', avec_essai=False,
                          contrat_precedent_id=renouv.id,
                          date_debut=date(2027, 1, 1),
                          date_fin=date(2027, 3, 31))

    def test_cdd_duree_cumulee_plafonnee(self):
        cdd = self._contrat(type_contrat='cdd', avec_essai=False,
                            date_fin=date(2026, 6, 30))       # 18 mois
        with self.assertRaises(ValidationError):              # 27 mois
            self._contrat(type_contrat='cdd', avec_essai=False,
                          contrat_precedent_id=cdd.id,
                          date_debut=date(2026, 7, 1),
                          date_fin=date(2027, 3, 31))
        with self.assertRaises(ValidationError):  # un seul CDD > 24 mois
            self._contrat(self.autre, type_contrat='cdd', avec_essai=False,
                          date_fin=date(2027, 6, 30))

    def test_cron_expiration_cdd(self):
        cdd = self._contrat(type_contrat='cdd', avec_essai=False,
                            date_fin=date(2025, 6, 30))
        cdd.action_demarrer()
        echus = self.env['rh.contrat']._cron_expirer_contrats()
        self.assertIn(cdd, echus)
        self.assertEqual(cdd.state, 'expire')
        self.assertEqual(cdd.motif_fin, 'fin_cdd')

    # ------------------------------------------------------------------
    # Préavis, verrouillage, suppression
    # ------------------------------------------------------------------
    def test_preavis_selon_categorie(self):
        self.assertEqual(self._contrat().preavis_texte, '3 mois')
        self.assertEqual(self._contrat(
            self.autre, categorie_id=self.cat_ouvrier.id).preavis_texte,
            '1 mois')

    def test_elements_figes_et_avenant_salaire(self):
        contrat = self._contrat(avec_essai=False)
        contrat.action_demarrer()
        with self.assertRaises(UserError):
            contrat.date_debut = date(2025, 2, 1)
        with self.assertRaises(UserError):
            contrat.type_contrat = 'cdd'
        contrat.salaire_base = 320000            # avenant de salaire
        self.assertEqual(self.emp.salaire_base, 320000)
        self.assertEqual(len(self.emp.historique_ids.filtered(
            lambda h: h.type_changement == 'salaire')), 2)

    def test_suppression_interdite(self):
        contrat = self._contrat()
        with self.assertRaises(UserError):
            contrat.with_user(self.user_admin).unlink()
        contrat.with_user(self.user_admin).action_archive()
        self.assertFalse(contrat.active)

    # ------------------------------------------------------------------
    # Sécurité
    # ------------------------------------------------------------------
    def test_securite_contrats(self):
        mien = self._contrat()
        autre = self._contrat(self.autre)
        Contrat = self.env['rh.contrat']
        # Employé : le sien, avec son salaire mais sans le champ protégé
        vus = Contrat.with_user(self.user_employe).search([])
        self.assertEqual(vus, mien)
        self.assertEqual(mien.with_user(self.user_employe).mon_salaire,
                         300000)
        with self.assertRaises(AccessError):
            mien.with_user(self.user_employe).read(['salaire_base'])
        with self.assertRaises(AccessError):
            mien.with_user(self.user_employe).write({'note': 'x'})
        # Recruteur et Responsable Formation : seulement les leurs
        for user in (self.user_recruteur, self.user_formation):
            self.assertFalse(Contrat.with_user(user).search(
                [('id', 'in', (mien | autre).ids)]), user.login)
        # Chef : son équipe, sans montants
        vus = Contrat.with_user(self.user_chef).search(
            [('id', 'in', (mien | autre).ids)])
        self.assertEqual(vus, mien)
        self.assertEqual(mien.with_user(self.user_chef).mon_salaire, 0)
        # Gestionnaire : gère sans montants
        gest = Contrat.with_user(self.user_gestionnaire)
        self.assertEqual(len(gest.search([('id', 'in', (mien | autre).ids)])),
                         2)
        with self.assertRaises(AccessError):
            autre.with_user(self.user_gestionnaire).read(['salaire_base'])
        nouveau = gest.create({
            'employee_id': self.autre.id, 'type_contrat': 'cdi',
            'date_debut': date(2026, 1, 1),
            'categorie_id': self.cat_cadre.id})
        with self.assertRaises(AccessError):
            nouveau.write({'salaire_base': 300000})
        with self.assertRaises(UserError):       # pas de salaire saisi
            nouveau.action_demarrer()
        # Paie, DG, Auditeur : lecture avec montants, sans écriture
        for user in (self.user_paie, self.user_dg, self.user_auditeur):
            self.assertEqual(autre.with_user(user).salaire_base, 300000)
            with self.assertRaises(AccessError, msg=user.login):
                autre.with_user(user).write({'note': 'x'})
