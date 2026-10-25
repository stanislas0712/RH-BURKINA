from odoo import fields, models


class RhService(models.Model):
    """Service rattaché à un département."""

    _name = 'rh.service'
    _description = 'Service'
    _inherit = ['mail.thread']
    _order = 'department_id, name'
    _check_company_auto = True

    name = fields.Char(string='Nom', required=True, tracking=True)
    code = fields.Char(string='Code')
    department_id = fields.Many2one(
        'hr.department', string='Département', required=True,
        ondelete='restrict', index=True, check_company=True, tracking=True)
    responsable_id = fields.Many2one(
        'hr.employee', string='Responsable', check_company=True,
        tracking=True)
    site_id = fields.Many2one('rh.site', string='Site', check_company=True)
    company_id = fields.Many2one(
        'res.company', string='Société', required=True, index=True,
        default=lambda self: self.env.company)
    active = fields.Boolean(default=True)
    description = fields.Text(string='Description')

    _sql_constraints = [
        ('code_company_uniq', 'unique(code, company_id)',
         'Le code du service doit être unique par société.'),
    ]
