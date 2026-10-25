from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .rh_prime import RECURRENCES


class RhTypeRetenue(models.Model):
    _name = 'rh.type.retenue'
    _description = 'Type de retenue'
    _order = 'sequence, name'

    name = fields.Char(string='Libellé', required=True, translate=True)
    code = fields.Char(string='Code', required=True)
    sequence = fields.Integer(default=10)
    base_calcul = fields.Selection(
        [('fixe', 'Montant fixe'), ('brut', '% du salaire brut'),
         ('base', '% du salaire de base')],
        string='Base de calcul', required=True, default='fixe')
    montant = fields.Monetary(string='Montant par défaut')
    taux = fields.Float(string='Taux par défaut (%)')
    recurrence = fields.Selection(RECURRENCES, string='Récurrence',
                                  required=True, default='recurrent')
    inclus_quotite = fields.Boolean(
        string='Compte dans la quotité saisissable', default=True,
        help="Les retenues volontaires et saisies sont limitées par la "
             "quotité saisissable (à vérifier).")
    company_id = fields.Many2one('res.company', string='Société')
    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.ref('base.XOF'))
    description = fields.Text(string='Description / référence')
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('code_uniq', 'unique(code, company_id)',
         'Le code du type de retenue doit être unique.'),
    ]

    @api.constrains('taux', 'montant')
    def _check_type(self):
        if any(r.taux < 0 or r.montant < 0 for r in self):
            raise ValidationError(_("Montant ou taux négatif."))


class RhRetenue(models.Model):
    _name = 'rh.retenue'
    _inherit = ['rh.element.variable.mixin']
    _description = "Retenue sur salaire d'un employé"

    type_retenue_id = fields.Many2one('rh.type.retenue', string='Type',
                                      required=True, tracking=True)
    base_calcul = fields.Selection(related='type_retenue_id.base_calcul')
    recurrence = fields.Selection(related='type_retenue_id.recurrence',
                                  store=True)

    def _recurrence(self):
        return self.recurrence

    @api.onchange('type_retenue_id')
    def _onchange_type_retenue_id(self):
        if self.type_retenue_id:
            self.montant = self.type_retenue_id.montant
            self.taux = self.type_retenue_id.taux

    def _montant_pour(self, brut, salaire_base):
        self.ensure_one()
        type_r = self.type_retenue_id
        taux = self.taux or type_r.taux
        if type_r.base_calcul == 'brut':
            return brut * taux / 100.0
        if type_r.base_calcul == 'base':
            return salaire_base * taux / 100.0
        return self.montant or type_r.montant
