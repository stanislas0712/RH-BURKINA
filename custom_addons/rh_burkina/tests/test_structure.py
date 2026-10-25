from psycopg2 import IntegrityError

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from ..models.res_company import RH_SEQUENCE_CODES
from .common import RhBurkinaCommon


@tagged('post_install', '-at_install', 'rh_burkina')
class TestStructure(RhBurkinaCommon):
    """Structure organisationnelle et séquences."""

    def test_categorie_libelle_et_cadre(self):
        cat = self.env['rh.categorie'].create({
            'categorie': 'Catégorie 5', 'echelon': 'B',
            'groupe_professionnel': 'cadre'})
        self.assertEqual(cat.name, 'Catégorie 5 - Échelon B')
        self.assertTrue(cat.est_cadre)

    def test_categorie_fourchette_invalide(self):
        with self.assertRaises(ValidationError):
            self.env['rh.categorie'].create({
                'categorie': 'Cat. X', 'salaire_min': 200000,
                'salaire_max': 100000})

    def test_categorie_unique_par_societe(self):
        vals = {'categorie': 'Cat. 2', 'echelon': 'A'}
        self.env['rh.categorie'].create(vals)
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            self.env['rh.categorie'].create(vals)
            self.env.flush_all()

    def test_poste_service_coherent(self):
        dep_a = self.env['hr.department'].create({'name': 'Finances'})
        dep_b = self.env['hr.department'].create({'name': 'Technique'})
        service = self.env['rh.service'].create({
            'name': 'Comptabilité', 'department_id': dep_a.id})
        self.assertEqual(dep_a.service_count, 1)
        with self.assertRaises(ValidationError):
            self.env['rh.poste'].create({
                'name': 'Comptable', 'department_id': dep_b.id,
                'service_id': service.id})
        poste = self.env['rh.poste'].create({
            'name': 'Comptable', 'department_id': dep_a.id,
            'service_id': service.id, 'salaire_min': 150000,
            'salaire_max': 300000})
        self.assertEqual(poste.service_id, service)

    def test_sequences_societe_principale(self):
        Sequence = self.env['ir.sequence']
        for code in RH_SEQUENCE_CODES:
            self.assertEqual(Sequence.search_count([
                ('code', '=', code),
                ('company_id', '=', self.env.ref('base.main_company').id)]),
                1, code)

    def test_sequences_creees_pour_nouvelle_societe(self):
        societe = self.env['res.company'].create({'name': 'Filiale Bobo'})
        Sequence = self.env['ir.sequence']
        for code in RH_SEQUENCE_CODES:
            self.assertEqual(Sequence.search_count([
                ('code', '=', code), ('company_id', '=', societe.id)]),
                1, code)
        # Numérotation indépendante par société
        numero = Sequence.with_company(societe).next_by_code('rh.employe')
        self.assertEqual(numero, 'EMP-0001')
        numero = Sequence.with_company(societe).next_by_code(
            'rh.bulletin.paie')
        self.assertEqual(numero, 'BP-00001')
        # Appel répété : pas de doublon
        societe._rh_create_sequences()
        self.assertEqual(Sequence.search_count([
            ('code', '=', 'rh.employe'), ('company_id', '=', societe.id)]), 1)
