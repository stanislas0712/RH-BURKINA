"""Paie : chaque montant attendu est recalculé à la main dans le commentaire,
à partir des barèmes initiaux (à vérifier) :
CNSS 5,5 % salarié / 16 % employeur, plafond 1 500 000 ;
IUTS 0 / 12,1 / 13,9 / 15,7 / 18,4 / 21,7 / 25 %, base arrondie à 100 ;
abattement 20 % cadre, 25 % non-cadre sur le salaire de base.
"""
from datetime import date

from psycopg2 import IntegrityError

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import RhBurkinaCommon


@tagged('post_install', '-at_install', 'rh_burkina')
class TestPaie(RhBurkinaCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cat_agent = cls.env['rh.categorie'].create({
            'categorie': 'Cat. 4', 'groupe_professionnel': 'ouvrier'})
        cls.cat_cadre = cls.env['rh.categorie'].create({
            'categorie': 'Cat. 9', 'groupe_professionnel': 'cadre'})
        cls.banque = cls.env['res.bank'].create({'name': 'Banque Test BF',
                                                 'bic': 'BTBFBFBF'})
        cls.juin = cls.env['rh.paie'].create({'date_debut': '2025-06-01'})

    # ------------------------------------------------------------------
    # Outils
    # ------------------------------------------------------------------
    def _employe(self, salaire, cadre=False, debut=date(2025, 1, 1),
                 user=None, **vals):
        emp = self.env['hr.employee'].create(dict({
            'name': 'Employé %s' % salaire,
            'mode_paiement': 'virement', 'banque_id': self.banque.id,
            'numero_compte': 'BF00 %s' % salaire,
            'ssnid': 'CNSS-%s-%s' % (salaire, debut),
            'user_id': user.id if user else False}, **vals))
        contrat = self.env['rh.contrat'].create({
            'employee_id': emp.id, 'date_debut': debut,
            'categorie_id': (self.cat_cadre if cadre else self.cat_agent).id,
            'salaire_base': salaire, 'avec_essai': False})
        contrat.action_demarrer()
        return emp

    def _bulletin(self, emp, paie=None):
        bulletin = self.env['rh.bulletin.paie'].create({
            'paie_id': (paie or self.juin).id, 'employee_id': emp.id})
        bulletin.action_calculer()
        return bulletin

    def _ligne(self, bulletin, code):
        return sum(bulletin.ligne_ids.filtered(
            lambda l: l.code == code).mapped('montant'))

    # ------------------------------------------------------------------
    # Cas de calcul
    # ------------------------------------------------------------------
    def test_cas_simple(self):
        b = self._bulletin(self._employe(200000))
        self.assertRegex(b.name, r'^BP-\d{5}$')
        self.assertEqual(b.state, 'calcule')
        self.assertEqual(b.brut, 200000)
        self.assertEqual(b.cotisation_salariale, 11000)       # 5,5 %
        self.assertEqual(b.charges_patronales, 32000)         # 16 %
        self.assertEqual(b.abattement, 50000)                 # 25 % × base
        # 200 000 − 11 000 − 50 000 = 139 000
        self.assertEqual(b.base_iuts, 139000)
        # 2 420 + 4 170 + 6 280 + 19 000 × 18,4 % (3 496) = 16 366
        self.assertEqual(b.iuts, 16366)
        self.assertEqual(b.net_a_payer, 172634)
        self.assertEqual(b.cout_employeur, 232000)
        self.assertEqual(self._ligne(b, 'NET'), 172634)

    def test_charges_de_famille(self):
        emp = self._employe(200000, nombre_enfants=2, children=2)
        b = self._bulletin(emp)
        self.assertEqual(b.nb_charges, 2)
        self.assertEqual(b.iuts_brut, 16366)
        self.assertEqual(b.reduction_iuts, 1637)              # 10 % arrondi
        self.assertEqual(b.iuts, 14729)
        self.assertEqual(b.net_a_payer, 174271)

    def test_plafond_de_cotisation(self):
        b = self._bulletin(self._employe(2000000, cadre=True))
        self.assertEqual(b.base_cotisation, 1500000)
        self.assertEqual(b.cotisation_salariale, 82500)
        self.assertEqual(b.charges_patronales, 240000)
        self.assertEqual(b.abattement, 400000)                # 20 % cadre
        # 2 000 000 − 82 500 − 400 000 = 1 517 500
        self.assertEqual(b.base_iuts, 1517500)
        # 39 430 (tranches jusqu'à 250 000) + 1 267 500 × 25 % = 356 305
        self.assertEqual(b.iuts, 356305)
        self.assertEqual(b.net_a_payer, 1561195)

    def test_prime_non_imposable_non_cotisable(self):
        panier = self.env['rh.type.prime'].create({
            'name': 'Prime de panier', 'code': 'PANIER', 'imposable': False,
            'soumis_cotisation': False, 'montant': 20000})
        emp = self._employe(200000)
        self.env['rh.prime'].create({'employee_id': emp.id,
                                     'type_prime_id': panier.id,
                                     'montant': 20000,
                                     'date_debut': date(2025, 1, 1)})
        b = self._bulletin(emp)
        self.assertEqual(b.brut, 220000)
        self.assertEqual(b.brut_soumis, 200000)
        self.assertEqual(b.brut_imposable, 200000)
        self.assertEqual(b.iuts, 16366)                       # inchangé
        self.assertEqual(b.net_a_payer, 192634)

    def test_indemnite_au_dela_du_plafond_exonere(self):
        emp = self._employe(300000)
        self.env['rh.prime'].create({
            'employee_id': emp.id,
            'type_prime_id': self.env.ref(
                'rh_burkina.type_prime_logement').id,
            'montant': 100000, 'date_debut': date(2025, 1, 1)})
        b = self._bulletin(emp)
        self.assertEqual(b.brut, 400000)
        self.assertEqual(b.cotisation_salariale, 22000)
        # min(100 000 ; 20 % × 400 000 ; 75 000) = 75 000 exonérés
        self.assertEqual(b.exonerations, 75000)
        self.assertEqual(b.abattement, 75000)                 # 25 % × 300 000
        # 400 000 − 22 000 − 75 000 − 75 000 = 228 000
        self.assertEqual(b.base_iuts, 228000)
        # 12 870 + 9 200 + 58 000 × 21,7 % (12 586) = 34 656
        self.assertEqual(b.iuts, 34656)
        self.assertEqual(b.net_a_payer, 343344)

    def test_entree_en_cours_de_mois(self):
        b = self._bulletin(self._employe(300000, debut=date(2025, 6, 16)))
        # 15 jours (16 → 30 juin) / 30 × 300 000 = 150 000
        self.assertEqual(b.jours_payes, 15)
        self.assertEqual(b.salaire_base, 150000)
        self.assertEqual(b.cotisation_salariale, 8250)
        # 150 000 − 8 250 − 37 500 = 104 250 → 104 200 ;
        # 6 590 + 24 200 × 15,7 % (3 799,4) = 10 389
        self.assertEqual(b.base_iuts, 104200)
        self.assertEqual(b.iuts, 10389)
        self.assertEqual(b.net_a_payer, 131361)

    def test_heures_supplementaires(self):
        emp = self._employe(200000)
        hs = self.env['rh.heure.sup'].create({
            'employee_id': emp.id, 'date': date(2025, 6, 2),
            'nb_heures': 10, 'type_heure': 'jour'})
        hs.action_soumettre()
        hs.action_valider_chef()
        hs.action_valider_rh()
        b = self._bulletin(emp)
        # Taux horaire : 200 000 × 12 / (40 × 52) = 1 153,85
        # 8 h × 1,15 = 10 615 ; 2 h × 1,35 = 3 115
        lignes = b.ligne_ids.filtered(lambda l: l.code == 'HS')
        self.assertEqual(sorted(lignes.mapped('montant')), [3115, 10615])
        self.assertEqual(b.brut, 213730)
        b.action_valider()
        self.assertEqual(hs.bulletin_id, b)

    def test_remboursement_pret_et_quotite(self):
        emp = self._employe(200000)
        pret = self.env['rh.pret'].create({
            'employee_id': emp.id, 'montant': 120000, 'nb_echeances': 6,
            'date_premiere_echeance': date(2025, 6, 1)})
        pret.action_confirmer()
        self.assertRegex(pret.name, r'^PRT-\d{4}$')
        self.assertEqual(pret.echeance_ids.mapped('montant'), [20000] * 6)
        bulletin = self.env['rh.bulletin.paie'].create({
            'paie_id': self.juin.id, 'employee_id': emp.id})
        # Barème de quotité non renseigné : refus explicite
        with self.assertRaises(UserError):
            bulletin.action_calculer()
        # Quotité 10 % de 172 634 = 17 263 < 20 000 : dépassée
        self.config.quotite_ids = [(0, 0, {'borne_inf': 0, 'taux': 10})]
        with self.assertRaises(UserError):
            bulletin.action_calculer()
        self.config.quotite_ids.taux = 20                     # 34 527
        bulletin.action_calculer()
        self.assertEqual(self._ligne(bulletin, 'PRET'), 20000)
        self.assertEqual(bulletin.net_a_payer, 152634)
        bulletin.action_valider()
        self.assertEqual(pret.echeance_ids[0].state, 'paye')
        self.assertEqual(pret.solde_restant, 100000)
        # Annulation : l'échéance redevient due
        bulletin.action_annuler()
        self.assertEqual(pret.echeance_ids[0].state, 'a_payer')
        self.assertEqual(pret.solde_restant, 120000)

    def test_arrondi_a_l_unite(self):
        b = self._bulletin(self._employe(123457))
        # 123 457 × 5,5 % = 6 790,135 → 6 790 ; abattement 30 864,25 → 30 864
        self.assertEqual(b.cotisation_salariale, 6790)
        self.assertEqual(b.abattement, 30864)
        # 123 457 − 6 790 − 30 864 = 85 803 → 85 800 ;
        # 6 590 + 5 800 × 15,7 % (910,6) = 7 500,6 → 7 501
        self.assertEqual(b.base_iuts, 85800)
        self.assertEqual(b.iuts, 7501)
        self.assertEqual(b.net_a_payer, 109166)
        for ligne in b.ligne_ids:
            self.assertEqual(ligne.montant, round(ligne.montant), ligne.name)

    def test_prime_anciennete(self):
        self.config.anciennete_ids = [(0, 0, {'annees_min': 2, 'taux': 5})]
        emp = self._employe(200000, date_embauche=date(2020, 1, 1))
        b = self._bulletin(emp)
        self.assertEqual(self._ligne(b, 'ANC'), 10000)        # 5 % × 200 000
        self.assertEqual(b.brut, 210000)

    def test_absence_non_remuneree(self):
        emp = self._employe(200000)
        absence = self.env['rh.conge'].create({
            'employee_id': emp.id,
            'type_conge_id': self.env.ref(
                'rh_burkina.type_absence_injustifiee').id,
            'date_debut': date(2025, 6, 10), 'date_fin': date(2025, 6, 11)})
        absence.action_soumettre()
        absence.action_approuver()
        b = self._bulletin(emp)
        # 2 jours × 200 000 / 30 = 13 333
        self.assertEqual(self._ligne(b, 'ABS'), -13333)
        self.assertEqual(b.salaire_base, 186667)
        self.assertEqual(b.brut, 186667)

    def test_bareme_date_applique(self):
        nouveau = self.cnss.copy({'name': 'CNSS juin 2025',
                                  'date_debut': date(2025, 6, 1)})
        nouveau.branche_ids.filtered(
            lambda br: br.code == 'pension').taux_salarial = 6.0
        emp = self._employe(200000)
        mai = self.env['rh.paie'].create({'date_debut': '2025-05-01'})
        self.assertEqual(self._bulletin(emp, mai).cotisation_salariale, 11000)
        self.assertEqual(self._bulletin(emp).cotisation_salariale, 12000)

    # ------------------------------------------------------------------
    # Règles du bulletin
    # ------------------------------------------------------------------
    def test_un_seul_bulletin_par_periode(self):
        emp = self._employe(200000)
        self._bulletin(emp)
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            self.env['rh.bulletin.paie'].create({
                'paie_id': self.juin.id, 'employee_id': emp.id})
            self.env.flush_all()

    def test_bulletin_verrouille_puis_annule_et_refait(self):
        emp = self._employe(200000)
        b = self._bulletin(emp)
        b.action_valider()
        with self.assertRaises(UserError):
            b.write({'net_a_payer': 1})
        with self.assertRaises(UserError):
            b.action_calculer()
        with self.assertRaises(UserError):
            b.ligne_ids[0].with_user(self.user_paie).write({'montant': 1})
        b.action_annuler(motif='Erreur de saisie')
        self.assertEqual(b.state, 'annule')
        self.assertTrue(any('Erreur de saisie' in (m.body or '')
                            for m in b.message_ids))
        nouveau = self._bulletin(emp)
        self.assertEqual(nouveau.net_a_payer, 172634)

    def test_validation_refusee_si_elements_modifies(self):
        emp = self._employe(200000)
        b = self._bulletin(emp)
        self.env['rh.prime'].create({
            'employee_id': emp.id, 'montant': 5000,
            'type_prime_id': self.env.ref(
                'rh_burkina.type_prime_rendement').id,
            'date_debut': date(2025, 6, 15)})
        with self.assertRaises(UserError):
            b.action_valider()
        b.action_calculer()
        b.action_valider()
        prime = self.env['rh.prime'].search([('employee_id', '=', emp.id)])
        self.assertEqual(prime.bulletin_id, b)      # ponctuelle consommée

    # ------------------------------------------------------------------
    # Période : génération, anomalies, clôture
    # ------------------------------------------------------------------
    def test_periode_generation_anomalies_cloture(self):
        payable = self._employe(200000)
        sans_contrat = self.env['hr.employee'].create({'name': 'Sans contrat'})
        sans_banque = self._employe(150000, banque_id=False,
                                    numero_compte=False)
        en_erreur = self._employe(180000)
        pret = self.env['rh.pret'].create({
            'employee_id': en_erreur.id, 'montant': 50000,
            'date_premiere_echeance': date(2025, 6, 1)})
        pret.action_confirmer()                  # quotité non renseignée
        self.juin.action_generer_bulletins()
        self.assertEqual(self.juin.state, 'en_cours')
        bulletins = self.juin.bulletin_ids
        self.assertIn(payable, bulletins.employee_id)
        self.assertNotIn(sans_contrat, bulletins.employee_id)
        erreur = bulletins.filtered(lambda b: b.employee_id == en_erreur)
        self.assertEqual(erreur.state, 'brouillon')
        self.assertIn('quotité', erreur.erreur_calcul)
        anomalies = self.juin.anomalies
        self.assertIn('Sans contrat', anomalies)
        self.assertIn('bancaires', anomalies)
        # Clôture impossible tant qu'un bulletin n'est pas validé
        self.juin.action_valider_bulletins()
        with self.assertRaises(UserError):
            self.juin.action_cloturer()
        erreur.action_annuler()
        self.juin.action_cloturer()
        self.assertEqual(self.juin.state, 'cloture')
        valide = bulletins.filtered(lambda b: b.employee_id == payable)
        with self.assertRaises(UserError):
            valide.action_annuler()
        with self.assertRaises(UserError):
            self.env['rh.bulletin.paie'].create({
                'paie_id': self.juin.id, 'employee_id': en_erreur.id})
        self.assertTrue(sans_banque)

    # ------------------------------------------------------------------
    # Exports
    # ------------------------------------------------------------------
    def test_exports_paiement_et_declarations(self):
        emp_banque = self._employe(200000)
        emp_mobile = self._employe(150000, mode_paiement='orange_money',
                                   numero_mobile_money='70112233')
        for emp in (emp_banque, emp_mobile):
            self._bulletin(emp).action_valider()
        Export = self.env['rh.wizard.export.paiement']
        for mode in ('virement', 'mobile'):
            wizard = Export.create({'paie_id': self.juin.id, 'mode': mode})
            wizard.action_generer()
            self.assertTrue(wizard.fichier, mode)
            self.assertTrue(wizard.nom_fichier.endswith('.xlsx'))
        with self.assertRaises(UserError):
            Export.create({'paie_id': self.juin.id,
                           'mode': 'especes'}).action_generer()
        Declaration = self.env['rh.wizard.declaration']
        for type_etat in ('cnss', 'iuts'):
            wizard = Declaration.create({'type_etat': type_etat,
                                         'paie_id': self.juin.id})
            wizard.action_generer()
            self.assertTrue(wizard.fichier, type_etat)
        annuel = Declaration.create({'type_etat': 'annuel', 'annee': 2025})
        annuel.action_generer()
        self.assertEqual(annuel.nom_fichier, 'ANNUEL_2025.xlsx')

    # ------------------------------------------------------------------
    # Sécurité
    # ------------------------------------------------------------------
    def test_vues_paie_chargent(self):
        for user in (self.user_employe, self.user_paie, self.user_dg,
                     self.user_auditeur, self.user_admin):
            for model in ('rh.bulletin.paie', 'rh.pret'):
                res = self.env[model].with_user(user).get_views(
                    [(False, 'list'), (False, 'form')])
                self.assertIn(model, res['models'], user.login)
        for user in (self.user_paie, self.user_dg):
            self.env['rh.paie'].with_user(user).get_views(
                [(False, 'list'), (False, 'form'), (False, 'kanban')])
            self.juin.with_user(user).read(['anomalies', 'total_net'])

    def test_securite_bulletins(self):
        chef_emp = self.env['hr.employee'].create({
            'name': 'Chef', 'user_id': self.user_chef.id})
        dep = self.env['hr.department'].create({
            'name': 'Équipe', 'manager_id': chef_emp.id})
        moi = self._employe(200000, user=self.user_employe,
                            department_id=dep.id)
        autre = self._employe(250000, department_id=dep.id)
        mien = self._bulletin(moi)
        sien = self._bulletin(autre)
        Bulletin = self.env['rh.bulletin.paie']
        ids = (mien | sien).ids
        # Employé : rien tant que son bulletin n'est pas validé
        self.assertFalse(Bulletin.with_user(self.user_employe).search(
            [('id', 'in', ids)]))
        mien.action_valider()
        self.assertEqual(Bulletin.with_user(self.user_employe).search(
            [('id', 'in', ids)]), mien)
        self.assertEqual(mien.with_user(self.user_employe).net_a_payer,
                         172634)
        # Chef : aucun bulletin de son équipe
        self.assertFalse(Bulletin.with_user(self.user_chef).search(
            [('id', 'in', ids)]))
        # Gestionnaire, Recruteur, Formation : aucun accès à la paie
        for user in (self.user_gestionnaire, self.user_recruteur,
                     self.user_formation):
            self.assertFalse(Bulletin.with_user(user).search(
                [('id', 'in', ids)]), user.login)
            with self.assertRaises(AccessError, msg=user.login):
                self.env['rh.paie'].with_user(user).search([])
        # DG et Auditeur : lecture seule
        for user in (self.user_dg, self.user_auditeur):
            self.assertEqual(len(Bulletin.with_user(user).search(
                [('id', 'in', ids)])), 2)
            with self.assertRaises(AccessError, msg=user.login):
                sien.with_user(user).action_calculer()
        # Responsable Paie : calcule et valide
        sien.with_user(self.user_paie).action_calculer()
        sien.with_user(self.user_paie).action_valider()
        self.assertEqual(sien.state, 'valide')
        # Prêts : l'employé voit les siens uniquement
        pret = self.env['rh.pret'].create({
            'employee_id': autre.id, 'montant': 10000})
        self.assertFalse(self.env['rh.pret'].with_user(
            self.user_employe).search([('id', '=', pret.id)]))
        with self.assertRaises(AccessError):
            self.env['rh.prime'].with_user(self.user_gestionnaire).search([])
