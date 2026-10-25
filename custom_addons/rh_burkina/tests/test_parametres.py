from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import RhBurkinaCommon


@tagged('post_install', '-at_install', 'rh_burkina')
class TestParametres(RhBurkinaCommon):
    """Paramètres légaux datés et calculs de barème."""

    # ------------------------------------------------------------------
    # Lecture datée
    # ------------------------------------------------------------------
    def test_valeurs_initiales_a_verifier(self):
        for rec in (self.config, self.cnss, self.iuts, self.licenciement):
            self.assertTrue(rec.a_verifier)
            self.assertIn('à vérifier', rec.name)
        self.assertEqual(self.config.currency_id, self.xof)
        self.assertTrue(self.xof.active)

    def test_bareme_en_vigueur_selon_date(self):
        Config = self.env['rh.configuration']
        nouveau = Config.create({
            'name': 'Paramètres juillet 2025',
            'date_debut': '2025-07-01',
            'smig_mensuel': 50000,
            'heures_legales_hebdo': 40,
            'heures_legales_mensuelles': 173.33,
            'age_minimum_embauche': 16,
            'age_retraite': 60,
            'conge_jours_par_mois': 2.5,
        })
        self.assertEqual(Config._get_en_vigueur('2025-06-30'), self.config)
        self.assertEqual(Config._get_en_vigueur('2025-07-01'), nouveau)
        self.assertEqual(Config._get_en_vigueur('2026-01-15').smig_mensuel,
                         50000)
        self.assertEqual(str(self.config.date_fin), '2025-06-30')
        self.assertFalse(nouveau.date_fin)

    def test_aucun_bareme_avant_entree_en_vigueur(self):
        with self.assertRaises(UserError):
            self.env['rh.configuration']._get_en_vigueur('2023-12-31')
        self.assertFalse(self.env['rh.configuration']._get_en_vigueur(
            '2023-12-31', raise_if_missing=False))

    def test_bareme_societe_prioritaire(self):
        specifique = self.cnss.copy({
            'name': 'CNSS propre à la société',
            'company_id': self.company.id,
            'plafond_mensuel': 800000,
        })
        autre = self.env['res.company'].create({'name': 'Autre société'})
        Cnss = self.env['rh.cnss']
        self.assertEqual(Cnss._get_bareme('cnss', '2024-06-01'), specifique)
        self.assertEqual(
            Cnss._get_bareme('cnss', '2024-06-01', company=autre), self.cnss)
        with self.assertRaises(UserError):
            Cnss._get_bareme('carfo', '2024-06-01')

    def test_date_unique_par_perimetre(self):
        with self.assertRaises(ValidationError):
            self.iuts.copy({'name': 'Doublon'})

    def test_suppression_interdite_archivage(self):
        with self.assertRaises(Exception):
            self.cnss.with_user(self.user_admin).unlink()
        self.cnss.with_user(self.user_admin).active = False
        self.assertFalse(self.cnss.active)

    # ------------------------------------------------------------------
    # Cotisations sociales
    # ------------------------------------------------------------------
    def test_cnss_cas_simple(self):
        res = self.cnss._calculer_cotisations(200000)
        self.assertEqual(res['base'], 200000)
        self.assertEqual(res['total_salarial'], 11000)    # 5,5 %
        self.assertEqual(res['total_patronal'], 32000)    # 16 %
        detail = {d['code']: d for d in res['detail']}
        self.assertEqual(detail['pf']['patronal'], 14000)
        self.assertEqual(detail['rp']['patronal'], 7000)
        self.assertEqual(detail['pension']['patronal'], 11000)

    def test_cnss_plafond_atteint(self):
        res = self.cnss._calculer_cotisations(2000000)
        self.assertEqual(res['base'], 1500000)
        self.assertEqual(res['base_non_plafonnee'], 2000000)
        self.assertEqual(res['total_salarial'], 82500)
        self.assertEqual(res['total_patronal'], 240000)

    def test_cnss_arrondi_unite(self):
        res = self.cnss._calculer_cotisations(123457)
        detail = {d['code']: d for d in res['detail']}
        self.assertEqual(detail['pension']['salarial'], 6790)  # 6 790,135
        self.assertEqual(detail['pf']['patronal'], 8642)        # 8 641,99
        self.assertEqual(detail['rp']['patronal'], 4321)        # 4 320,995
        self.assertEqual(res['total_patronal'], 19753)

    def test_cnss_branche_non_plafonnee(self):
        self.cnss.branche_ids.filtered(
            lambda b: b.code == 'rp').plafonnee = False
        res = self.cnss._calculer_cotisations(2000000)
        detail = {d['code']: d for d in res['detail']}
        self.assertEqual(detail['rp']['base'], 2000000)
        self.assertEqual(detail['rp']['patronal'], 70000)
        self.assertEqual(detail['pf']['base'], 1500000)

    # ------------------------------------------------------------------
    # IUTS
    # ------------------------------------------------------------------
    def test_iuts_sous_premiere_tranche(self):
        self.assertEqual(self.iuts._calculer_iuts(25000)['impot_net'], 0)

    def test_iuts_progressif_et_arrondi_base(self):
        # Base 187 350 arrondie à 187 300 :
        # 20 000×12,1 % + 30 000×13,9 % + 40 000×15,7 % + 50 000×18,4 %
        # + 17 300×21,7 % = 25 824,1
        res = self.iuts._calculer_iuts(187350)
        self.assertEqual(res['base'], 187300)
        self.assertEqual(res['impot_brut'], 25824)
        self.assertEqual(res['impot_net'], 25824)

    def test_iuts_charges_de_famille(self):
        res = self.iuts._calculer_iuts(187350, nb_charges=2)
        self.assertEqual(res['taux_reduction'], 10.0)
        self.assertEqual(res['reduction'], 2582)
        self.assertEqual(res['impot_net'], 23242)

    def test_iuts_derniere_tranche_et_palier_max(self):
        # 2 420 + 4 170 + 6 280 + 9 200 + 17 360 + 12 500 = 51 930
        res = self.iuts._calculer_iuts(300000, nb_charges=5)
        self.assertEqual(res['impot_brut'], 51930)
        self.assertEqual(res['taux_reduction'], 14.0)   # dernier palier
        self.assertEqual(res['impot_net'], 51930 - 7270)

    def test_iuts_abattement(self):
        self.assertEqual(self.iuts._get_abattement(True), 20.0)
        self.assertEqual(self.iuts._get_abattement(False), 25.0)

    def test_iuts_exoneration_plafonnee(self):
        assiettes = {'brut': 300000, 'base': 200000}
        # Plafond 20 % du brut (60 000) inférieur au plafond en montant
        self.assertEqual(self.iuts._get_exoneration(
            'logement', 100000, assiettes), 60000)
        # Plafond en montant (75 000) inférieur à 20 % du brut (100 000)
        self.assertEqual(self.iuts._get_exoneration(
            'logement', 100000, {'brut': 500000}), 75000)
        # Indemnité sous les plafonds : totalement exonérée
        self.assertEqual(self.iuts._get_exoneration(
            'transport', 10000, assiettes), 10000)
        # Type sans règle : rien d'exonéré
        self.assertEqual(self.iuts._get_exoneration(
            'autre', 10000, assiettes), 0)

    def test_iuts_tranches_chevauchantes(self):
        with self.assertRaises(ValidationError):
            self.iuts.tranche_ids[1].borne_inf = 20000

    # ------------------------------------------------------------------
    # Licenciement
    # ------------------------------------------------------------------
    def test_indemnite_licenciement(self):
        # 12 ans 6 mois : 5×25 % + 5×30 % + 2,5×40 % = 3,75 mois
        self.assertEqual(
            self.licenciement._calculer_indemnite(200000, 150), 750000)
        self.assertEqual(
            self.licenciement._calculer_indemnite(200000, 6), 0)
        self.licenciement.proratiser = False
        # 12 ans complets : 1,25 + 1,5 + 0,8 = 3,55
        self.assertEqual(
            self.licenciement._calculer_indemnite(200000, 150), 710000)

    # ------------------------------------------------------------------
    # Paramètres généraux
    # ------------------------------------------------------------------
    def test_periode_essai_et_preavis(self):
        Categorie = self.env['rh.categorie']
        cadre = Categorie.create({
            'categorie': 'Cat. 9', 'groupe_professionnel': 'cadre'})
        ouvrier = Categorie.create({
            'categorie': 'Cat. 1', 'groupe_professionnel': 'ouvrier'})
        self.assertEqual(self.config._get_periode_essai(cadre), (3, 'mois'))
        self.assertEqual(self.config._get_periode_essai(ouvrier), (1, 'mois'))
        self.assertEqual(self.config._get_preavis(cadre, 24), (3, 'mois'))
        # Une ligne propre à la catégorie prime sur le groupe
        self.config.essai_ids = [(0, 0, {
            'groupe_professionnel': 'cadre', 'categorie_id': cadre.id,
            'duree': 6, 'unite': 'mois'})]
        self.assertEqual(self.config._get_periode_essai(cadre), (6, 'mois'))

    def test_majoration_heures_sup(self):
        self.assertEqual(self.config._get_taux_majoration_hs('jour', 5), 15)
        self.assertEqual(self.config._get_taux_majoration_hs('jour', 8), 15)
        self.assertEqual(self.config._get_taux_majoration_hs('jour', 9), 35)
        self.assertEqual(self.config._get_taux_majoration_hs('nuit', 1), 50)

    def test_quotite_saisissable(self):
        with self.assertRaises(UserError):
            self.config._get_quotite_saisissable(250000)
        self.config.quotite_ids = [
            (0, 0, {'borne_inf': 0, 'borne_sup': 100000, 'taux': 10}),
            (0, 0, {'borne_inf': 100000, 'borne_sup': 0, 'taux': 20}),
        ]
        self.assertEqual(self.config._get_quotite_saisissable(250000), 40000)
        self.assertEqual(self.config._get_quotite_saisissable(50000), 5000)

    def test_prime_anciennete(self):
        self.assertEqual(self.config._get_taux_anciennete(10), 0.0)
        self.config.anciennete_ids = [
            (0, 0, {'annees_min': 2, 'taux': 5}),
            (0, 0, {'annees_min': 5, 'taux': 10}),
        ]
        self.assertEqual(self.config._get_taux_anciennete(1), 0.0)
        self.assertEqual(self.config._get_taux_anciennete(3), 5.0)
        self.assertEqual(self.config._get_taux_anciennete(7), 10.0)

    def test_valeurs_incoherentes_refusees(self):
        with self.assertRaises(ValidationError):
            self.config.smig_mensuel = 0
        with self.assertRaises(ValidationError):
            self.config.age_retraite = 15
