from odoo.exceptions import AccessError, UserError
from odoo.tests import new_test_user, tagged

from .common import RhBurkinaCommon


@tagged('post_install', '-at_install', 'rh_burkina')
class TestSecuriteDossier(RhBurkinaCommon):
    """Qui voit quoi dans le dossier du personnel."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Employee = cls.env['hr.employee']
        cls.chef_emp = Employee.create({
            'name': 'Chef Finances', 'user_id': cls.user_chef.id})
        cls.dep = cls.env['hr.department'].create({
            'name': 'Finances', 'manager_id': cls.chef_emp.id})
        cls.dep_autre = cls.env['hr.department'].create({'name': 'Technique'})
        cls.moi = Employee.create({
            'name': 'Moi Employé', 'user_id': cls.user_employe.id,
            'department_id': cls.dep.id, 'birthday': '1990-05-01',
            'salaire_base': 250000, 'mode_paiement': 'orange_money',
            'numero_mobile_money': '70000000', 'private_phone': '25000000'})
        cls.collegue = Employee.create({
            'name': 'Collègue Finances', 'department_id': cls.dep.id,
            'salaire_base': 400000})
        cls.etranger = Employee.create({
            'name': 'Agent Technique', 'department_id': cls.dep_autre.id,
            'salaire_base': 500000})
        cls.collegue.salaire_base = 420000   # ligne d'historique salariale
        cls.env['rh.contact.urgence'].create({
            'employee_id': cls.moi.id, 'name': 'Maman',
            'lien_parente': 'mere', 'telephone': '76000000'})
        cls.doc_collegue = cls.env['rh.document'].create({
            'employee_id': cls.collegue.id, 'name': 'CNIB',
            'type_document_id': cls.env.ref(
                'rh_burkina.type_document_cnib').id})

    def _visibles(self, user):
        return self.env['hr.employee'].with_user(user).search(
            [('id', 'in', (self.moi | self.collegue | self.etranger).ids)])

    # ------------------------------------------------------------------
    # Employé (self-service)
    # ------------------------------------------------------------------
    def test_employe_ne_voit_que_sa_fiche(self):
        self.assertEqual(self._visibles(self.user_employe), self.moi)
        moi = self.moi.with_user(self.user_employe)
        self.assertEqual(str(moi.birthday), '1990-05-01')
        with self.assertRaises(AccessError):
            self.collegue.with_user(self.user_employe).read(['name'])

    def test_employe_voit_sa_remuneration_sans_droit_global(self):
        moi = self.moi.with_user(self.user_employe)
        self.assertEqual(moi.ma_remuneration, 250000)
        self.assertIn('70000000', moi.mon_paiement)
        with self.assertRaises(AccessError):
            moi.read(['salaire_base'])

    def test_employe_ne_peut_pas_modifier_sa_fiche(self):
        moi = self.moi.with_user(self.user_employe)
        for vals in ({'private_phone': '1'}, {'poste_id': False},
                     {'statut_rh': 'inactif'}):
            with self.assertRaises(AccessError):
                moi.write(vals)

    def test_assistant_coordonnees(self):
        action = self.moi.with_user(
            self.user_employe).action_rh_modifier_coordonnees()
        wizard = self.env['rh.wizard.coordonnees'].with_user(
            self.user_employe).browse(action['res_id'])
        self.assertEqual(wizard.private_phone, '25000000')
        self.assertEqual(len(wizard.contact_ids), 1)
        wizard.write({
            'private_phone': '25111111',
            'contact_ids': [(0, 0, {'name': 'Frère', 'lien_parente':
                                    'frere_soeur', 'telephone': '78000000'})],
        })
        wizard.contact_ids.filtered(lambda c: c.name == 'Maman').unlink()
        wizard.action_valider()
        self.assertEqual(self.moi.private_phone, '25111111')
        self.assertEqual(self.moi.contact_urgence_ids.mapped('name'),
                         ['Frère'])
        archive = self.env['rh.contact.urgence'].with_context(
            active_test=False).search([('employee_id', '=', self.moi.id),
                                       ('name', '=', 'Maman')])
        self.assertFalse(archive.active)   # archivé, pas supprimé

    def test_assistant_refuse_autre_employe(self):
        with self.assertRaises(AccessError):
            self.env['rh.wizard.coordonnees'].with_user(
                self.user_employe)._valeurs_initiales(self.collegue)

    def test_mon_dossier(self):
        action = self.env['hr.employee'].with_user(
            self.user_employe).action_rh_mon_dossier()
        self.assertEqual(action['res_id'], self.moi.id)
        with self.assertRaises(UserError):
            self.env['hr.employee'].with_user(
                self.user_recruteur).action_rh_mon_dossier()

    def test_employe_documents_contacts(self):
        Doc = self.env['rh.document'].with_user(self.user_employe)
        self.assertFalse(Doc.search([]))
        contacts = self.env['rh.contact.urgence'].with_user(
            self.user_employe).search([])
        self.assertEqual(contacts.employee_id, self.moi)

    # ------------------------------------------------------------------
    # Chef de département
    # ------------------------------------------------------------------
    def test_chef_voit_son_equipe(self):
        visibles = self._visibles(self.user_chef)
        self.assertIn(self.moi, visibles)
        self.assertIn(self.collegue, visibles)
        self.assertNotIn(self.etranger, visibles)
        collegue = self.collegue.with_user(self.user_chef)
        with self.assertRaises(AccessError):
            collegue.read(['salaire_base'])
        self.assertEqual(collegue.ma_remuneration, 0)
        with self.assertRaises(AccessError):
            collegue.write({'job_title': 'x'})

    def test_chef_sans_salaire_ni_documents_equipe(self):
        hist = self.env['rh.historique.poste'].with_user(
            self.user_chef).search([('employee_id', '=', self.collegue.id)])
        self.assertTrue(hist)
        self.assertNotIn('salaire', hist.mapped('type_changement'))
        self.assertFalse(self.env['rh.document'].with_user(
            self.user_chef).search([('id', '=', self.doc_collegue.id)]))

    # ------------------------------------------------------------------
    # Gestionnaire RH
    # ------------------------------------------------------------------
    def test_gestionnaire_gere_sans_salaires(self):
        visibles = self._visibles(self.user_gestionnaire)
        self.assertEqual(len(visibles), 3)
        collegue = self.collegue.with_user(self.user_gestionnaire)
        collegue.write({'job_title': 'Comptable principal',
                        'private_phone': '25222222'})
        with self.assertRaises(AccessError):
            collegue.read(['salaire_base'])
        with self.assertRaises(AccessError):
            collegue.write({'salaire_base': 1})
        nouveau = self.env['hr.employee'].with_user(
            self.user_gestionnaire).create({'nom': 'Zongo', 'prenom': 'Ali'})
        self.assertTrue(nouveau.matricule)
        hist = self.env['rh.historique.poste'].with_user(
            self.user_gestionnaire).search(
            [('employee_id', '=', self.collegue.id)])
        self.assertNotIn('salaire', hist.mapped('type_changement'))
        with self.assertRaises(UserError):
            collegue.unlink()

    # ------------------------------------------------------------------
    # Rôles en lecture
    # ------------------------------------------------------------------
    def test_roles_lecture_avec_salaires(self):
        for user in (self.user_paie, self.user_dg, self.user_auditeur,
                     self.user_responsable):
            collegue = self.collegue.with_user(user)
            self.assertEqual(collegue.salaire_base, 420000, user.login)
            hist = self.env['rh.historique.poste'].with_user(user).search(
                [('employee_id', '=', self.collegue.id)])
            self.assertIn('salaire', hist.mapped('type_changement'))
        for user in (self.user_paie, self.user_dg, self.user_auditeur):
            with self.assertRaises(AccessError, msg=user.login):
                self.collegue.with_user(user).write({'job_title': 'x'})

    def test_roles_lecture_sans_salaires(self):
        for user in (self.user_recruteur, self.user_formation):
            self.assertEqual(len(self._visibles(user)), 3, user.login)
            with self.assertRaises(AccessError, msg=user.login):
                self.collegue.with_user(user).read(['salaire_base'])
            with self.assertRaises(AccessError, msg=user.login):
                self.collegue.with_user(user).write({'job_title': 'x'})

    def test_utilisateur_interne_sans_role_rh(self):
        """Un utilisateur sans rôle RH garde l'annuaire public d'Odoo."""
        interne = new_test_user(self.env, login='interne_simple',
                                groups='base.group_user')
        emp = self.env['hr.employee'].with_user(interne).search(
            [('id', '=', self.collegue.id)])
        self.assertEqual(emp.name, 'Collègue Finances')
        with self.assertRaises(AccessError):
            emp.read(['birthday'])

    def test_vues_chargent_pour_chaque_role(self):
        """Les écrans s'ouvrent pour chaque rôle, sans fuite de salaire."""
        Employee = self.env['hr.employee']
        form = self.env.ref('rh_burkina.view_rh_employe_form').id
        liste = self.env.ref('rh_burkina.view_rh_employe_list').id
        kanban = self.env.ref('rh_burkina.view_rh_employe_kanban').id
        for user in (self.user_employe, self.user_chef,
                     self.user_gestionnaire, self.user_recruteur,
                     self.user_paie, self.user_auditeur, self.user_admin):
            res = Employee.with_user(user).get_views(
                [(liste, 'list'), (kanban, 'kanban'), (form, 'form')])
            champs = res['models']['hr.employee']['fields']
            voit_salaire = user.has_group('rh_burkina.group_rh_salaire')
            self.assertEqual('salaire_base' in champs, voit_salaire,
                             user.login)
        self_form = self.env.ref('rh_burkina.view_rh_employe_form_self').id
        res = Employee.with_user(self.user_employe).get_views(
            [(self_form, 'form')])
        self.assertIn('ma_remuneration', res['models']['hr.employee'][
            'fields'])
        moi = self.moi.with_user(self.user_employe)
        data = moi.web_read({'name': {}, 'ma_remuneration': {},
                             'parent_id': {'fields': {'display_name': {}}},
                             'contact_urgence_ids': {'fields': {
                                 'name': {}}}})
        self.assertEqual(data[0]['ma_remuneration'], 250000)

    def test_isolation_multi_societe(self):
        autre = self.env['res.company'].create({'name': 'Société B'})
        emp_b = self.env['hr.employee'].create({
            'name': 'Employé B', 'company_id': autre.id})
        self.assertNotIn(emp_b, self.env['hr.employee'].with_user(
            self.user_gestionnaire).search([]))
