from odoo.exceptions import AccessError
from odoo.tests import new_test_user, tagged

from .common import RhBurkinaCommon

PARAMETRES = ['rh.configuration', 'rh.cnss', 'rh.iuts',
              'rh.bareme.licenciement']


@tagged('post_install', '-at_install', 'rh_burkina')
class TestSecurite(RhBurkinaCommon):
    """Rôles, droits d'accès et confidentialité des salaires."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.categorie = cls.env['rh.categorie'].create({
            'categorie': 'Cat. 6', 'groupe_professionnel': 'cadre',
            'salaire_min': 250000, 'salaire_max': 450000})

    def test_hierarchie_des_roles(self):
        self.assertTrue(self.user_admin.has_group(
            'rh_burkina.group_rh_responsable'))
        self.assertTrue(self.user_responsable.has_group(
            'rh_burkina.group_rh_gestionnaire'))
        self.assertTrue(self.user_gestionnaire.has_group(
            'rh_burkina.group_rh_employe'))
        for user in (self.user_chef, self.user_recruteur, self.user_paie,
                     self.user_formation, self.user_dg, self.user_auditeur):
            self.assertTrue(user.has_group('rh_burkina.group_rh_employe'))
            self.assertFalse(user.has_group('rh_burkina.group_rh_gestionnaire'))
        self.assertTrue(self.env.ref('base.user_admin').has_group(
            'rh_burkina.group_rh_admin'))

    def test_acces_aux_salaires(self):
        autorises = (self.user_paie, self.user_responsable, self.user_admin,
                     self.user_dg, self.user_auditeur)
        refuses = (self.user_employe, self.user_gestionnaire, self.user_chef,
                   self.user_recruteur, self.user_formation)
        for user in autorises:
            self.assertEqual(
                self.categorie.with_user(user).salaire_min, 250000,
                user.login)
        for user in refuses:
            cat = self.categorie.with_user(user)
            self.assertEqual(cat.name, 'Cat. 6')  # structure lisible
            with self.assertRaises(AccessError, msg=user.login):
                cat.read(['salaire_min'])

    def test_parametres_legaux_lecture(self):
        lecteurs = (self.user_responsable, self.user_paie, self.user_dg,
                    self.user_auditeur, self.user_admin)
        sans_acces = (self.user_employe, self.user_gestionnaire,
                      self.user_chef, self.user_recruteur,
                      self.user_formation)
        for model in PARAMETRES:
            for user in lecteurs:
                self.assertTrue(
                    self.env[model].with_user(user).search_count([]),
                    '%s / %s' % (model, user.login))
            for user in sans_acces:
                with self.assertRaises(AccessError,
                                       msg='%s / %s' % (model, user.login)):
                    self.env[model].with_user(user).search([])

    def test_parametres_legaux_ecriture(self):
        for user in (self.user_responsable, self.user_paie, self.user_dg,
                     self.user_auditeur):
            with self.assertRaises(AccessError, msg=user.login):
                self.cnss.with_user(user).plafond_mensuel = 1
        self.cnss.with_user(self.user_admin).plafond_mensuel = 1600000
        self.assertEqual(self.cnss.plafond_mensuel, 1600000)

    def test_structure_ecriture_admin_seulement(self):
        for user in (self.user_responsable, self.user_gestionnaire,
                     self.user_auditeur, self.user_dg):
            with self.assertRaises(AccessError, msg=user.login):
                self.env['rh.site'].with_user(user).create({'name': 'X'})
        site = self.env['rh.site'].with_user(self.user_admin).create(
            {'name': 'Siège'})
        with self.assertRaises(AccessError):
            site.with_user(self.user_admin).unlink()

    def test_auditeur_lecture_seule(self):
        with self.assertRaises(AccessError):
            self.categorie.with_user(self.user_auditeur).write(
                {'description': 'modif'})

    def test_isolation_multi_societe(self):
        autre = self.env['res.company'].create({'name': 'Société B'})
        cat_b = self.env['rh.categorie'].create({
            'categorie': 'Cat. B', 'company_id': autre.id})
        user_b = new_test_user(
            self.env, login='rh_admin_b', groups='rh_burkina.group_rh_admin',
            company_id=autre.id, company_ids=[(6, 0, [autre.id])])
        visibles = self.env['rh.categorie'].with_user(user_b).search([])
        self.assertIn(cat_b, visibles)
        self.assertNotIn(self.categorie, visibles)
        # Les paramètres communs (sans société) restent visibles
        self.assertIn(self.cnss,
                      self.env['rh.cnss'].with_user(user_b).search([]))
