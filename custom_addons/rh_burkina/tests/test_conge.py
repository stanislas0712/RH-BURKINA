from datetime import date

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged

from .common import RhBurkinaCommon


@tagged('post_install', '-at_install', 'rh_burkina')
class TestConge(RhBurkinaCommon):
    """Congés : acquisition, solde, chevauchement, fériés, workflow."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.annuel = cls.env.ref('rh_burkina.type_conge_annuel')
        cls.maladie = cls.env.ref('rh_burkina.type_conge_maladie')
        cls.maternite = cls.env.ref('rh_burkina.type_conge_maternite')
        cls.chef_emp = cls.env['hr.employee'].create({
            'name': 'Chef Services', 'user_id': cls.user_chef.id})
        cls.dep = cls.env['hr.department'].create({
            'name': 'Services', 'manager_id': cls.chef_emp.id})
        cat = cls.env['rh.categorie'].create({'categorie': 'Cat. 3'})
        cls.emp = cls.env['hr.employee'].create({
            'name': 'Awa Ouedraogo', 'department_id': cls.dep.id,
            'user_id': cls.user_employe.id, 'date_embauche': '2025-01-01'})
        cls.collegue = cls.env['hr.employee'].create({
            'name': 'Issa Sawadogo', 'department_id': cls.dep.id})
        Contrat = cls.env['rh.contrat']
        for emp, debut in ((cls.emp, date(2025, 1, 1)),
                           (cls.collegue, date(2025, 1, 16))):
            contrat = Contrat.create({
                'employee_id': emp.id, 'date_debut': debut,
                'categorie_id': cat.id, 'salaire_base': 100000,
                'avec_essai': False})
            contrat.action_demarrer()
        Acquisition = cls.env['rh.acquisition.conge']
        for mois in range(1, 6):                         # janvier → mai
            Acquisition._crediter_mois(date(2025, mois, 1))
        cls.solde = cls.env['rh.solde.conge'].search([
            ('employee_id', '=', cls.emp.id), ('annee', '=', 2025),
            ('type_conge_id', '=', cls.annuel.id)])

    def _demande(self, debut, fin, type_conge=None, user=None, **vals):
        Conge = self.env['rh.conge']
        if user:
            Conge = Conge.with_user(user)
        return Conge.create(dict({
            'employee_id': self.emp.id,
            'type_conge_id': (type_conge or self.annuel).id,
            'date_debut': debut, 'date_fin': fin}, **vals))

    # ------------------------------------------------------------------
    # Acquisition
    # ------------------------------------------------------------------
    def test_acquisition_mensuelle(self):
        self.assertEqual(len(self.solde.acquisition_ids), 5)
        self.assertAlmostEqual(self.solde.acquis, 12.5)       # 5 × 2,5
        # Idempotent : rien de nouveau pour un mois déjà crédité
        self.assertFalse(self.env['rh.acquisition.conge']._crediter_mois(
            date(2025, 5, 1)))

    def test_acquisition_entree_en_cours_de_mois(self):
        janvier = self.env['rh.acquisition.conge'].search([
            ('employee_id', '=', self.collegue.id),
            ('mois', '=', date(2025, 1, 1))])
        self.assertAlmostEqual(janvier.jours, round(2.5 * 16 / 31, 2))
        fevrier = self.env['rh.acquisition.conge'].search([
            ('employee_id', '=', self.collegue.id),
            ('mois', '=', date(2025, 2, 1))])
        self.assertAlmostEqual(fevrier.jours, 2.5)

    def test_acquisition_majoree_anciennete(self):
        self.config.conge_anciennete_ids = [(0, 0, {
            'annees_min': 5, 'jours_supplementaires': 2})]
        self.emp.date_embauche = date(2015, 1, 1)
        nouvelles = self.env['rh.acquisition.conge']._crediter_mois(
            date(2025, 6, 1))
        mienne = nouvelles.filtered(lambda a: a.employee_id == self.emp)
        self.assertAlmostEqual(mienne.jours, round(2.5 + 2 / 12, 2))

    def test_pas_d_acquisition_sans_contrat(self):
        sans_contrat = self.env['hr.employee'].create({'name': 'Sans'})
        self.assertFalse(self.env['rh.acquisition.conge'].search(
            [('employee_id', '=', sans_contrat.id)]))

    # ------------------------------------------------------------------
    # Décompte et contrôles
    # ------------------------------------------------------------------
    def test_jours_feries_exclus(self):
        # Lundi 2 → vendredi 6 juin 2025, en jours ouvrables : 5 jours
        demande = self._demande(date(2025, 6, 2), date(2025, 6, 6))
        self.assertEqual(demande.mode_decompte, 'ouvrable')
        self.assertEqual(demande.nb_jours, 5)
        self.env['rh.jour.ferie'].create({'name': 'Fête',
                                          'date': date(2025, 6, 4)})
        demande.date_fin = date(2025, 6, 7)          # recalcul (samedi inclus)
        self.assertEqual(demande.nb_jours, 5)        # 6 ouvrables − 1 férié

    def test_solde_insuffisant(self):
        demande = self._demande(date(2025, 6, 2), date(2025, 6, 20))  # 16 j
        with self.assertRaises(UserError):
            demande.action_soumettre()
        self.assertEqual(demande.state, 'brouillon')

    def test_demandes_en_attente_comptees(self):
        premiere = self._demande(date(2025, 6, 2), date(2025, 6, 11))  # 9 j
        premiere.action_soumettre()
        seconde = self._demande(date(2025, 7, 1), date(2025, 7, 5))    # 5 j
        with self.assertRaises(UserError):           # 9 + 5 > 12,5
            seconde.action_soumettre()

    def test_chevauchement_interdit(self):
        self._demande(date(2025, 6, 2), date(2025, 6, 6)).action_soumettre()
        doublon = self._demande(date(2025, 6, 5), date(2025, 6, 9),
                                type_conge=self.env.ref(
                                    'rh_burkina.type_conge_sans_solde'))
        with self.assertRaises(ValidationError):
            doublon.action_soumettre()

    def test_justificatif_et_duree_max(self):
        maladie = self._demande(date(2025, 6, 2), date(2025, 6, 4),
                                type_conge=self.maladie)
        with self.assertRaises(UserError):
            maladie.action_soumettre()
        maladie.justificatif = b'Q2VydGlmaWNhdA=='
        maladie.action_soumettre()
        maternite = self._demande(date(2025, 8, 1), date(2025, 11, 30),
                                  type_conge=self.maternite,
                                  justificatif=b'Q2VydGlmaWNhdA==')
        self.assertEqual(maternite.nb_jours, 122)     # jours calendaires
        with self.assertRaises(UserError):            # > 98 jours
            maternite.action_soumettre()

    # ------------------------------------------------------------------
    # Workflow et droits
    # ------------------------------------------------------------------
    def test_workflow_complet(self):
        demande = self._demande(date(2025, 6, 2), date(2025, 6, 6),
                                user=self.user_employe)
        self.assertRegex(demande.name, r'^CNG-\d{4}$')
        demande.action_soumettre()
        self.assertEqual(demande.state, 'soumis')
        self.assertAlmostEqual(self.solde.en_attente, 5)
        with self.assertRaises(AccessError):
            demande.action_valider_chef()            # l'employé lui-même
        with self.assertRaises(AccessError):
            demande.with_user(self.user_chef).action_approuver()
        demande.with_user(self.user_chef).action_valider_chef()
        self.assertEqual(demande.state, 'valide_chef')
        demande.with_user(self.user_gestionnaire).action_approuver()
        self.assertEqual(demande.state, 'approuve')
        self.assertAlmostEqual(self.solde.pris, 5)
        self.assertAlmostEqual(self.solde.restant, 7.5)
        # Annulation par les RH : le solde est rétabli
        demande.with_user(self.user_gestionnaire).action_annuler()
        self.assertAlmostEqual(self.solde.restant, 12.5)

    def test_employe_ne_modifie_que_ses_brouillons(self):
        demande = self._demande(date(2025, 6, 2), date(2025, 6, 3),
                                user=self.user_employe)
        demande.write({'motif': 'Voyage'})
        demande.action_soumettre()
        with self.assertRaises(AccessError):
            demande.write({'date_fin': date(2025, 6, 4)})
        with self.assertRaises(AccessError):
            self._demande(date(2025, 6, 2), date(2025, 6, 3),
                          user=self.user_employe,
                          employee_id=self.collegue.id)
        with self.assertRaises(UserError):
            demande.with_user(self.user_admin).unlink()

    def test_refus_motif_obligatoire(self):
        demande = self._demande(date(2025, 6, 2), date(2025, 6, 3))
        demande.action_soumettre()
        with self.assertRaises(UserError):
            demande.with_user(self.user_chef)._refuser('  ')
        action = demande.with_user(self.user_chef).action_refuser()
        self.env['rh.wizard.refus'].with_user(self.user_chef).with_context(
            action['context']).create({'motif': 'Période chargée'}
                                      ).action_valider()
        self.assertEqual(demande.state, 'refuse')
        self.assertAlmostEqual(self.solde.en_attente, 0)

    def test_sans_chef_passe_directement_aux_rh(self):
        isole = self.env['hr.employee'].create({'name': 'Isolé'})
        demande = self.env['rh.conge'].create({
            'employee_id': isole.id,
            'type_conge_id': self.env.ref(
                'rh_burkina.type_conge_sans_solde').id,
            'date_debut': date(2025, 6, 2), 'date_fin': date(2025, 6, 3)})
        demande.action_soumettre()
        self.assertEqual(demande.state, 'valide_chef')

    def test_visibilite_des_demandes(self):
        mienne = self._demande(date(2025, 6, 2), date(2025, 6, 3))
        sienne = self._demande(date(2025, 6, 2), date(2025, 6, 3),
                               employee_id=self.collegue.id,
                               type_conge_id=self.env.ref(
                                   'rh_burkina.type_conge_sans_solde').id)
        ids = (mienne | sienne).ids
        Conge = self.env['rh.conge']
        self.assertEqual(Conge.with_user(self.user_employe).search(
            [('id', 'in', ids)]), mienne)
        self.assertEqual(len(Conge.with_user(self.user_chef).search(
            [('id', 'in', ids)])), 2)
        self.assertFalse(Conge.with_user(self.user_recruteur).search(
            [('id', 'in', ids)]))
        self.assertEqual(len(Conge.with_user(self.user_paie).search(
            [('id', 'in', ids)])), 2)
        with self.assertRaises(AccessError):
            sienne.with_user(self.user_auditeur).write({'motif': 'x'})

    def test_report_de_solde(self):
        self.solde.action_reporter()
        suivant = self.env['rh.solde.conge'].search([
            ('employee_id', '=', self.emp.id), ('annee', '=', 2026),
            ('type_conge_id', '=', self.annuel.id)])
        self.assertAlmostEqual(suivant.report, 12.5)
        with self.assertRaises(UserError):
            self.solde.action_reporter()
