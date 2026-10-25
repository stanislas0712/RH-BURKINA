from odoo import models, fields

class RhConfiguration(models.Model):
    _name = 'rh.configuration'
    _description = 'Configuration générale RH Burkina Faso'
    _order = 'type_config, name'

    name = fields.Char(
        string='Libellé',
        required=True,
    )
    type_config = fields.Selection(
        [
            ('poste', 'Poste'),
            ('departement', 'Département'),
            ('service', 'Service'),
            ('site', 'Site / Agence'),
            ('categorie', 'Catégorie / Échelon'),
            ('type_prime', 'Type de Prime'),
            ('type_retenue', 'Type de Retenue'),
        ],
        string='Type de configuration',
        required=True,
        default='poste',
        help='Type d’élément utilisé dans les autres modèles RH',
    )
    # Salaire minimum
    smig = fields.Float(
        string='SMIG (FCFA)',
        default=45000,
        help='Salaire Minimum Interprofessionnel Garanti au Burkina Faso',
    )
    # Durée légale du travail
    heures_semaine = fields.Float(
        string='Heures légales/semaine',
        default=40.0,
    )
    heures_mois = fields.Float(
        string='Heures légales/mois',
        default=173.33,
    )
    # Congés annuels
    jours_conge_annuel = fields.Integer(
        string='Jours de congé annuel',
        default=30,
        help='30 jours ouvrables par an selon le code du travail BF',
    )
    # Heures supplémentaires
    taux_hs_25 = fields.Float(
        string='Majoration HS 25%',
        default=25.0,
        help='Majoration pour heures supplémentaires normales',
    )
    taux_hs_50 = fields.Float(
        string='Majoration HS 50%',
        default=50.0,
        help='Majoration pour HS de nuit, dimanche et jours fériés',
    )
    active = fields.Boolean(
        string='Actif',
        default=True,
    )
    date_application = fields.Date(
        string="Date d'application",
        required=True,
    )