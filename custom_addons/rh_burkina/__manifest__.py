{
    'name': 'RH Burkina Faso',
    'version': '18.0.1.0.0',
    'summary': 'Gestion RH et paie conforme au droit burkinabè (CNSS, IUTS)',
    'description': """
Gestion des ressources humaines adaptée au Burkina Faso
=======================================================
Recrutement, dossier du personnel, contrats, temps et absences, paie
(CNSS / CARFO, IUTS), évaluations, formations, discipline et sortie.

Toutes les valeurs légales sont paramétrables et datées. Les valeurs
initiales fournies sont marquées « à vérifier » et doivent être
confirmées avant la mise en production.
    """,
    'author': 'KONATÉ Faichal Ismaël Stanislas',
    'license': 'LGPL-3',
    'category': 'Human Resources',
    'depends': ['base', 'mail', 'hr'],
    'external_dependencies': {'python': ['xlsxwriter']},
    'data': [
        # Sécurité
        'security/res_groups_data.xml',
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        # Données
        'data/res_currency_data.xml',
        'data/ir_sequence_data.xml',
        'data/rh_parametres_data.xml',
        'data/rh_type_document_data.xml',
        'data/ir_cron_data.xml',
        'data/rh_jour_ferie_data.xml',
        'data/rh_type_conge_data.xml',
        'data/rh_paie_data.xml',
        # Vues
        'views/rh_structure_views.xml',
        'views/rh_parametres_views.xml',
        'views/rh_employe_views.xml',
        'views/rh_document_views.xml',
        'views/rh_contrat_views.xml',
        'views/rh_temps_views.xml',
        'views/rh_conge_views.xml',
        'views/rh_paie_views.xml',
        'views/menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'rh_burkina/static/src/css/rh_burkina.css',
        ],
    },
    'post_init_hook': '_post_init_hook',
    'installable': True,
    'application': True,
}
