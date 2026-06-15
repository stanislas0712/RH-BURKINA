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
        'security/res_groups_data.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'views/rh_burkina_views.xml',
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