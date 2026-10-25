from odoo.tests.common import TransactionCase, new_test_user


class RhBurkinaCommon(TransactionCase):
    """Données communes aux tests du module."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.xof = cls.env.ref('base.XOF')
        cls.config = cls.env.ref('rh_burkina.configuration_2024')
        cls.cnss = cls.env.ref('rh_burkina.cnss_2024')
        cls.iuts = cls.env.ref('rh_burkina.iuts_2024')
        cls.licenciement = cls.env.ref('rh_burkina.bareme_licenciement_2024')

        def user(login, group):
            return new_test_user(
                cls.env, login=login, groups='rh_burkina.%s' % group,
                company_id=cls.company.id)

        cls.user_employe = user('rh_employe', 'group_rh_employe')
        cls.user_gestionnaire = user('rh_gestionnaire', 'group_rh_gestionnaire')
        cls.user_responsable = user('rh_responsable', 'group_rh_responsable')
        cls.user_admin = user('rh_admin', 'group_rh_admin')
        cls.user_chef = user('rh_chef', 'group_rh_chef_departement')
        cls.user_recruteur = user('rh_recruteur', 'group_rh_recruteur')
        cls.user_paie = user('rh_paie', 'group_rh_paie')
        cls.user_formation = user('rh_formation', 'group_rh_formation')
        cls.user_dg = user('rh_dg', 'group_rh_dg')
        cls.user_auditeur = user('rh_auditeur', 'group_rh_auditeur')
