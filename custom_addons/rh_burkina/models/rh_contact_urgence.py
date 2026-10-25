from odoo import fields, models

LIENS_PARENTE = [
    ('conjoint', 'Conjoint(e)'),
    ('pere', 'Père'),
    ('mere', 'Mère'),
    ('enfant', 'Enfant'),
    ('frere_soeur', 'Frère / sœur'),
    ('autre_parent', 'Autre parent'),
    ('ami', 'Ami(e)'),
    ('autre', 'Autre'),
]


class RhContactUrgence(models.Model):
    _name = 'rh.contact.urgence'
    _description = "Contact d'urgence"
    _order = 'sequence, id'
    _check_company_auto = True

    employee_id = fields.Many2one(
        'hr.employee', string='Employé', required=True, index=True,
        ondelete='restrict', check_company=True)
    company_id = fields.Many2one(
        related='employee_id.company_id', store=True, index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Nom', required=True)
    lien_parente = fields.Selection(
        LIENS_PARENTE, string='Lien de parenté', required=True)
    telephone = fields.Char(string='Téléphone', required=True)
    telephone2 = fields.Char(string='Autre téléphone')
    adresse = fields.Char(string='Adresse')
    active = fields.Boolean(default=True)
