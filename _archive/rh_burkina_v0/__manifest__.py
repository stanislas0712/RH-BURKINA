{
    'name': 'RH Burkina Faso',
    'version': '18.0.1.0.0',
    'summary': 'Gestion RH conforme au droit du travail burkinabè',
    'description': """
        Module de gestion des ressources humaines adapté aux spécificités
        du Burkina Faso : CNSS, IUTS, Code du travail burkinabè.
    """,
    'author': 'KONATÉ Faichal Ismaël Stanislas',
    'website': 'https://rh_burkina.bf',
    'license': 'LGPL-3',  # Correction : 'license' avec un 's'
    'category': 'Human Resources',  # Correction : Doublon supprimé, anglais recommandé
    'depends': [
        'base',
        'hr',  # Suggestion : Souvent indispensable pour les modules RH
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'views/rh_tableau_bord_views.xml',
        'views/rh_employe_views.xml',
        'views/rh_contrat_views.xml',
        'views/rh_conge_views.xml',
        'views/rh_recrutement_views.xml',
        'views/rh_presence_views.xml',
        'views/rh_paie_views.xml',
        'views/rh_sanction_views.xml',
        'views/rh_formation_views.xml',
        'views/rh_config_views.xml',
        'views/rh_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'rh_burkina/static/src/css/rh_burkina.css',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': True,
}