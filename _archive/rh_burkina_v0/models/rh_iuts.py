from odoo import models, fields, api
from odoo.exceptions import ValidationError

class RhIuts(models.Model):
    _name = 'rh.iuts'
    _description = 'Barème IUTS Burkina Faso'
    _order = 'revenu_min asc'

    name = fields.Char(
        string='Libellé',
        required=True,
    )
    revenu_min = fields.Float(
        string='Revenu minimum (FCFA)',
        required=True,
    )
    revenu_max = fields.Float(
        string='Revenu maximum (FCFA)',
        required=True,
    )
    taux = fields.Float(
        string='Taux (%)',
        required=True,
    )
    deduction_fixe = fields.Float(
        string='Déduction fixe (FCFA)',
        default=0.0,
    )
    active = fields.Boolean(
        string='Actif',
        default=True,
    )

    @api.constrains('revenu_min', 'revenu_max')
    def _check_revenus(self):
        for rec in self:
            if rec.revenu_min < 0:
                raise ValidationError("Le revenu minimum ne peut pas être négatif.")
            if rec.revenu_max <= rec.revenu_min:
                raise ValidationError("Le revenu maximum doit être supérieur au minimum.")

    @api.model
    def calculer_iuts(self, salaire_imposable):
        """Calcule l'IUTS selon le barème burkinabè"""
        tranche = self.search([
            ('revenu_min', '<=', salaire_imposable),
            ('revenu_max', '>=', salaire_imposable),
            ('active', '=', True),
        ], limit=1)
        if tranche:
            return (salaire_imposable * tranche.taux / 100) - tranche.deduction_fixe
        return 0.0