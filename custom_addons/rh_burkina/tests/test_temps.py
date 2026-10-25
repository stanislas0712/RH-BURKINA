from datetime import date

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import Form, tagged

from .common import RhBurkinaCommon


@tagged('post_install', '-at_install', 'rh_burkina')
class TestTemps(RhBurkinaCommon):
    """Jours fériés, présences, retards, heures supplémentaires."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.chef_emp = cls.env['hr.employee'].create({
            'name': 'Chef Atelier', 'user_id': cls.user_chef.id})
        cls.dep = cls.env['hr.department'].create({
            'name': 'Atelier', 'manager_id': cls.chef_emp.id})
        cls.emp = cls.env['hr.employee'].create({
            'name': 'Awa Ouedraogo', 'department_id': cls.dep.id,
            'user_id': cls.user_employe.id})
        cls.autre = cls.env['hr.employee'].create({'name': 'Hors équipe'})
        cls.Ferie = cls.env['rh.jour.ferie']
        # Semaine du lundi 2 au dimanche 8 juin 2025
        cls.lundi = date(2025, 6, 2)
        cls.dimanche = date(2025, 6, 8)

    # ------------------------------------------------------------------
    # Jours fériés et décompte
    # ------------------------------------------------------------------
    def test_decompte_jours(self):
        compter = self.Ferie._compter_jours
        self.assertEqual(compter(self.lundi, self.dimanche, 'calendaire',
                                 self.emp), 7)
        self.assertEqual(compter(self.lundi, self.dimanche, 'ouvrable',
                                 self.emp), 6)          # sans le dimanche
        self.assertEqual(compter(self.lundi, self.dimanche, 'ouvre',
                                 self.emp), 5)          # lundi → vendredi
        self.Ferie.create({'name': 'Fête test', 'date': date(2025, 6, 4),
                           'type_fete': 'variable'})
        self.assertEqual(compter(self.lundi, self.dimanche, 'ouvrable',
                                 self.emp), 5)
        self.assertEqual(compter(self.lundi, self.dimanche, 'ouvre',
                                 self.emp), 4)

    def test_ferie_propre_a_une_autre_societe_ignore(self):
        autre = self.env['res.company'].create({'name': 'Société B'})
        self.Ferie.create({'name': 'Fête locale', 'date': date(2025, 6, 4),
                           'company_id': autre.id})
        self.assertEqual(self.Ferie._compter_jours(
            self.lundi, self.dimanche, 'ouvre', self.emp), 5)

    def test_doublon_ferie_refuse(self):
        self.Ferie.create({'name': 'A', 'date': date(2025, 6, 4)})
        with self.assertRaises(ValidationError):
            self.Ferie.create({'name': 'B', 'date': date(2025, 6, 4)})

    def test_recopie_fetes_fixes(self):
        fetes_2026 = self.Ferie.search([('annee', '=', 2026),
                                        ('type_fete', '=', 'fixe')])
        self.assertTrue(fetes_2026)
        crees = self.Ferie._recopier_fetes_fixes(2026, 2027)
        self.assertEqual(len(crees), len(fetes_2026))
        self.assertIn(date(2027, 8, 5), crees.mapped('date'))
        self.assertFalse(self.Ferie._recopier_fetes_fixes(2026, 2027))

    # ------------------------------------------------------------------
    # Présences et retards
    # ------------------------------------------------------------------
    def test_presence_heures_et_retard(self):
        presence = self.env['rh.presence'].create({
            'employee_id': self.emp.id, 'date': self.lundi,
            'heure_arrivee': 8 + 20 / 60, 'heure_depart': 17.5,
            'duree_pause': 1})
        self.assertAlmostEqual(presence.heures_travaillees, 8 + 10 / 60)
        self.assertEqual(presence.heure_prevue, 8.0)
        self.assertEqual(presence.retard_minutes, 20)
        presence.action_declarer_retard()
        self.assertEqual(presence.retard_ids.duree_minutes, 20)
        presence.action_declarer_retard()               # pas de doublon
        self.assertEqual(len(presence.retard_ids), 1)
        with self.assertRaises(ValidationError):
            presence.heure_depart = 7

    def test_cumul_retards_du_mois(self):
        today = date.today()
        Retard = self.env['rh.retard']
        Retard.create({'employee_id': self.emp.id, 'date': today,
                       'duree_minutes': 15})
        Retard.create({'employee_id': self.emp.id, 'date': today,
                       'duree_minutes': 10, 'justifie': True})
        self.assertEqual(self.emp.retard_minutes_mois, 25)

    def test_presences_visibles_selon_role(self):
        Presence = self.env['rh.presence']
        mienne = Presence.create({'employee_id': self.emp.id,
                                  'date': self.lundi, 'heure_arrivee': 8})
        autre = Presence.create({'employee_id': self.autre.id,
                                 'date': self.lundi, 'heure_arrivee': 8})
        ids = (mienne | autre).ids
        self.assertEqual(Presence.with_user(self.user_employe).search(
            [('id', 'in', ids)]), mienne)
        self.assertEqual(Presence.with_user(self.user_chef).search(
            [('id', 'in', ids)]), mienne)
        self.assertFalse(Presence.with_user(self.user_recruteur).search(
            [('id', 'in', ids)]))
        self.assertEqual(len(Presence.with_user(self.user_auditeur).search(
            [('id', 'in', ids)])), 2)
        with self.assertRaises(AccessError):
            mienne.with_user(self.user_employe).heure_arrivee = 7

    # ------------------------------------------------------------------
    # Heures supplémentaires
    # ------------------------------------------------------------------
    def _hs(self, jour, heures, type_heure='jour', employee=None):
        hs = self.env['rh.heure.sup'].create({
            'employee_id': (employee or self.emp).id, 'date': jour,
            'nb_heures': heures, 'type_heure': type_heure})
        hs.action_soumettre()
        return hs

    def test_majoration_par_tranche_hebdomadaire(self):
        # Tranches (à vérifier) : 8 premières h à 15 %, au-delà 35 %
        lundi = self._hs(self.lundi, 6)
        self.assertEqual(lundi._calculer_repartition(), [(6, 15.0)])
        mardi = self._hs(date(2025, 6, 3), 4)
        self.assertEqual(mardi._calculer_repartition(),
                         [(2, 15.0), (2, 35.0)])
        self.assertAlmostEqual(mardi.taux_moyen, 25.0)
        nuit = self._hs(date(2025, 6, 3), 2, 'nuit')
        self.assertEqual(nuit._calculer_repartition(), [(2, 50.0)])
        # Nouvelle semaine : le compteur repart de zéro
        suivant = self._hs(date(2025, 6, 9), 3)
        self.assertEqual(suivant._calculer_repartition(), [(3, 15.0)])

    def test_plafond_hebdomadaire_bloquant(self):
        self._hs(self.lundi, 10)
        self._hs(date(2025, 6, 3), 8)
        with self.assertRaises(UserError):        # 10 + 8 + 4 > 20 h
            self._hs(date(2025, 6, 4), 4)

    def test_plafond_annuel_bloquant(self):
        self.config.hs_plafond_annuel = 15
        self._hs(self.lundi, 10)
        with self.assertRaises(UserError):
            self._hs(date(2025, 9, 1), 6)

    def test_type_automatique_dimanche_et_ferie(self):
        form = Form(self.env['rh.heure.sup'])
        form.employee_id = self.emp
        form.date = self.dimanche
        self.assertEqual(form.type_heure, 'dimanche')
        self.Ferie.create({'name': 'Fête', 'date': date(2025, 6, 4)})
        form.date = date(2025, 6, 4)
        self.assertEqual(form.type_heure, 'ferie')

    def test_double_validation_heures_sup(self):
        hs = self.env['rh.heure.sup'].with_user(self.user_employe).create({
            'employee_id': self.emp.id, 'date': self.lundi,
            'nb_heures': 3})
        hs.action_soumettre()
        self.assertEqual(hs.state, 'soumis')
        with self.assertRaises(AccessError):          # pas sa propre validation
            hs.with_user(self.user_employe).action_valider_chef()
        with self.assertRaises(AccessError):
            hs.with_user(self.user_employe).write({'nb_heures': 9})
        with self.assertRaises(AccessError):          # RH avant le chef
            hs.with_user(self.user_chef).action_valider_rh()
        hs.with_user(self.user_chef).action_valider_chef()
        self.assertEqual(hs.state, 'valide_chef')
        hs.with_user(self.user_gestionnaire).action_valider_rh()
        self.assertEqual(hs.state, 'valide')

    def test_refus_heures_sup_avec_motif(self):
        hs = self._hs(self.lundi, 3)
        action = hs.with_user(self.user_chef).action_refuser()
        wizard = self.env['rh.wizard.refus'].with_user(
            self.user_chef).with_context(action['context']).create(
            {'motif': 'Non autorisées au préalable'})
        wizard.action_valider()
        self.assertEqual(hs.state, 'refuse')
        self.assertEqual(hs.motif_refus, 'Non autorisées au préalable')
        # Les heures refusées ne comptent plus dans le plafond
        self._hs(date(2025, 6, 3), 20)

    def test_chef_hors_equipe_ne_valide_pas(self):
        hs = self._hs(self.lundi, 3, employee=self.autre)
        with self.assertRaises(AccessError):
            hs.with_user(self.user_chef).action_valider_chef()
