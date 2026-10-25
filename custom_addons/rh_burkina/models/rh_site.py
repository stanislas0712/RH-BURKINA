from odoo import fields, models


class RhSite(models.Model):
    """Site géographique (siège, agence, chantier…)."""

    _name = 'rh.site'
    _description = 'Site'
    _inherit = ['mail.thread']
    _order = 'name'

    name = fields.Char(string='Nom', required=True, tracking=True)
    code = fields.Char(string='Code')
    ville = fields.Char(string='Ville', default='Ouagadougou')
    adresse = fields.Text(string='Adresse')
    telephone = fields.Char(string='Téléphone')
    company_id = fields.Many2one(
        'res.company', string='Société', required=True, index=True,
        default=lambda self: self.env.company)
    active = fields.Boolean(default=True)
    note = fields.Text(string='Notes')

    _sql_constraints = [
        ('code_company_uniq', 'unique(code, company_id)',
         'Le code du site doit être unique par société.'),
    ]
