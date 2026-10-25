from odoo import fields, models


class HrDepartment(models.Model):
    """Extension des départements : code, site et services."""

    _inherit = 'hr.department'

    code = fields.Char(string='Code')
    site_id = fields.Many2one(
        'rh.site', string='Site', check_company=True, tracking=True)
    service_ids = fields.One2many(
        'rh.service', 'department_id', string='Services')
    service_count = fields.Integer(
        string='Nombre de services', compute='_compute_service_count')

    _sql_constraints = [
        ('rh_code_company_uniq', 'unique(code, company_id)',
         'Le code du département doit être unique par société.'),
    ]

    def _compute_service_count(self):
        data = self.env['rh.service']._read_group(
            [('department_id', 'in', self.ids)],
            ['department_id'], ['__count'])
        counts = {dept.id: count for dept, count in data}
        for dept in self:
            dept.service_count = counts.get(dept.id, 0)
