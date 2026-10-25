from datetime import date

from psycopg2 import IntegrityError

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import RhBurkinaCommon


@tagged('post_install', '-at_install', 'rh_burkina')
class TestEmploye(RhBurkinaCommon):
    """Dossier du personnel : identité, calculs, historique."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dep = cls.env['hr.department'].create({'name': 'Finances'})
        cls.cat_cadre = cls.env['rh.categorie'].create({
            'categorie': 'Cat. 8', 'groupe_professionnel': 'cadre'})
        cls.poste_compta = cls.env['rh.poste'].create({
            'name': 'Comptable', 'department_id': cls.dep.id,
            'categorie_id': cls.cat_cadre.id})
        cls.poste_chef = cls.env['rh.poste'].create({
            'name': 'Chef comptable', 'department_id': cls.dep.id})

    def _employe(self, **vals):
        base = {'nom': 'Ouedraogo', 'prenom': 'Awa'}
        base.update(vals)
        return self.env['hr.employee'].create(base)

    def test_matricule_et_nom_complet(self):
        emp = self._employe()
        self.assertRegex(emp.matricule, r'^EMP-\d{4}$')
        self.assertEqual(emp.name, 'OUEDRAOGO Awa')
        autre = self._employe(nom='Sawadogo', prenom='Issa')
        self.assertNotEqual(emp.matricule, autre.matricule)
        emp.prenom = 'Awa Mariam'
        self.assertEqual(emp.name, 'OUEDRAOGO Awa Mariam')

    def test_unicite_cnss_cnib_par_societe(self):
        self._employe(ssnid='CNSS-001', identification_id='B1234567')
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            with self.env.cr.savepoint():
                self._employe(nom='Kabore', ssnid='CNSS-001')
                self.env.flush_all()
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            with self.env.cr.savepoint():
                self._employe(nom='Kabore', identification_id='B1234567')
                self.env.flush_all()
        # Autorisé dans une autre société
        autre = self.env['res.company'].create({'name': 'Société B'})
        self._employe(nom='Kabore', ssnid='CNSS-001', company_id=autre.id)
        self.env.flush_all()

    def test_age_minimum_embauche(self):
        with self.assertRaises(ValidationError):
            self._employe(birthday=date(2012, 1, 1),
                          date_embauche=date(2025, 1, 1))   # 13 ans
        emp = self._employe(birthday=date(2000, 1, 1),
                            date_embauche=date(2025, 1, 1))
        self.assertTrue(emp)
        with self.assertRaises(ValidationError):
            emp.date_embauche = date(1999, 1, 1)

    def test_charges_de_famille_iuts(self):
        emp = self._employe(marital='married', conjoint_a_charge=True,
                            nombre_enfants=3, children=2,
                            nb_autres_charges=1)
        self.assertEqual(emp.nb_charges_iuts, 4)
        emp.marital = 'single'      # le conjoint ne compte plus
        self.assertEqual(emp.nb_charges_iuts, 3)
        with self.assertRaises(ValidationError):
            emp.children = 5        # plus d'enfants à charge que d'enfants

    def test_calculs_age_anciennete_retraite(self):
        emp = self._employe(birthday=date(1980, 3, 15),
                            date_embauche=date(2015, 1, 10))
        emp = emp.with_context(tz='UTC')
        self.assertEqual(emp.date_retraite, date(2040, 3, 15))
        self.assertGreaterEqual(emp.age, 45)
        self.assertGreaterEqual(emp.anciennete_mois, 12 * 10)
        emp.departure_date = date(2020, 4, 9)
        self.assertEqual(emp.anciennete_mois, 62)   # 5 ans 2 mois

    def test_historique_automatique(self):
        emp = self._employe(poste_id=self.poste_compta.id,
                            department_id=self.dep.id,
                            categorie_id=self.cat_cadre.id,
                            salaire_base=300000)
        hist = emp.historique_ids
        self.assertEqual(hist.mapped('type_changement'), ['embauche'])
        self.assertEqual(hist.nouveau_salaire, 300000)

        emp.write({'poste_id': self.poste_chef.id, 'salaire_base': 350000})
        types = set(emp.historique_ids.mapped('type_changement'))
        self.assertEqual(types, {'embauche', 'poste', 'salaire'})
        ligne_salaire = emp.historique_ids.filtered(
            lambda h: h.type_changement == 'salaire')
        self.assertEqual(ligne_salaire.ancien_salaire, 300000)
        self.assertEqual(ligne_salaire.nouveau_salaire, 350000)

        # Écriture sans changement réel : pas de nouvelle ligne
        emp.write({'poste_id': self.poste_chef.id, 'salaire_base': 350000})
        self.assertEqual(len(emp.historique_ids), 3)

        # Motif transmis par le contexte
        emp.with_context(rh_motif_changement='Avenant n°2').write(
            {'department_id': self.env['hr.department'].create(
                {'name': 'Audit'}).id})
        self.assertIn('Avenant n°2', emp.historique_ids.mapped('motif'))

    def test_historique_inalterable(self):
        emp = self._employe()
        ligne = emp.historique_ids
        with self.assertRaises(UserError):
            ligne.with_user(self.user_admin).write({'motif': 'x'})
        with self.assertRaises(UserError):
            ligne.with_user(self.user_admin).unlink()

    def test_suppression_interdite_archivage(self):
        emp = self._employe()
        with self.assertRaises(UserError):
            emp.with_user(self.user_admin).unlink()
        emp.with_user(self.user_admin).action_archive()
        self.assertFalse(emp.active)

    def test_service_coherent_avec_departement(self):
        autre_dep = self.env['hr.department'].create({'name': 'Technique'})
        service = self.env['rh.service'].create({
            'name': 'Maintenance', 'department_id': autre_dep.id})
        with self.assertRaises(ValidationError):
            self._employe(department_id=self.dep.id, service_id=service.id)

    def test_document_etat(self):
        emp = self._employe()
        Doc = self.env['rh.document']
        cnib = self.env.ref('rh_burkina.type_document_cnib')
        today = date.today()
        expire = Doc.create({'name': 'CNIB', 'employee_id': emp.id,
                             'type_document_id': cnib.id,
                             'date_expiration': date(today.year - 1, 1, 1)})
        valide = Doc.create({'name': 'CNIB 2', 'employee_id': emp.id,
                             'type_document_id': cnib.id,
                             'date_expiration': date(today.year + 2, 1, 1)})
        self.assertEqual(expire.etat, 'expire')
        self.assertEqual(valide.etat, 'valide')
        self.assertEqual(Doc.search([('etat', '=', 'expire'),
                                     ('employee_id', '=', emp.id)]), expire)
        with self.assertRaises(ValidationError):
            Doc.create({'name': 'X', 'employee_id': emp.id,
                        'type_document_id': cnib.id,
                        'date_emission': date(2025, 5, 1),
                        'date_expiration': date(2025, 1, 1)})
