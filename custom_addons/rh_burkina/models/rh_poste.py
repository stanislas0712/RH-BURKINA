from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class RhPoste(models.Model):
    """Poste de travail avec sa grille salariale."""

    _name = 'rh.poste'
    _description = 'Poste'
    _inherit = ['mail.thread']
    _order = 'name'
    _check_company_auto = True

    name = fields.Char(string='Intitulé', required=True, tracking=True)
    code = fields.Char(string='Code')
    department_id = fields.Many2one(
        'hr.department', string='Département', check_company=True,
        tracking=True)
    service_id = fields.Many2one(
        'rh.service', string='Service', check_company=True,
        domain="[('department_id', '=?', department_id)]")
    categorie_id = fields.Many2one(
        'rh.categorie', string='Catégorie de référence', check_company=True,
        tracking=True)
    company_id = fields.Many2one(
        'res.company', string='Société', required=True, index=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    salaire_min = fields.Monetary(
        string='Salaire minimum', tracking=True,
        groups='rh_burkina.group_rh_salaire')
    salaire_max = fields.Monetary(
        string='Salaire maximum', tracking=True,
        groups='rh_burkina.group_rh_salaire')
    description = fields.Html(string='Description du poste')
    missions = fields.Text(string='Missions principales')
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('code_company_uniq', 'unique(code, company_id)',
         'Le code du poste doit être unique par société.'),
    ]

    @api.onchange('service_id')
    def _onchange_service_id(self):
        if self.service_id:
            self.department_id = self.service_id.department_id

    @api.constrains('service_id', 'department_id')
    def _check_service_department(self):
        for rec in self:
            if (rec.service_id and rec.department_id
                    and rec.service_id.department_id != rec.department_id):
                raise ValidationError(
                    _("Le service %(s)s n'appartient pas au département "
                      "%(d)s.", s=rec.service_id.name,
                      d=rec.department_id.name))

    @api.constrains('salaire_min', 'salaire_max')
    def _check_grille(self):
        for rec in self.sudo():
            if rec.salaire_min < 0 or rec.salaire_max < 0:
                raise ValidationError(
                    _("La grille salariale ne peut pas être négative."))
            if rec.salaire_max and rec.salaire_min > rec.salaire_max:
                raise ValidationError(
                    _("Poste %s : le salaire minimum dépasse le salaire "
                      "maximum.", rec.name))
