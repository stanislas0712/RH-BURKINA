from odoo import models, fields, api
from odoo.exceptions import ValidationError

class RhCnss(models.Model):
    _name = 'rh.cnss'
    _description = 'Configuration CNSS Burkina Faso'
    _order = 'date_debut desc'

    name = fields.Char(
        string='Libellé',
        required=True,
    )
    date_debut = fields.Date(
        string='Date de début',
        required=True,
    )
    date_fin = fields.Date(
        string='Date de fin',
    )
    # Cotisations salariales
    taux_cnss_salarie = fields.Float(
        string='Taux salarié (%)',
        default=5.5,
        required=True,
        help='Part salariale CNSS (5.5% au Burkina Faso)',
    )
    # Cotisations patronales
    taux_cnss_patronal = fields.Float(
        string='Taux patronal (%)',
        default=16.0,
        required=True,
        help='Part patronale CNSS (16% au Burkina Faso)',
    )
    # Plafond mensuel
    plafond_mensuel = fields.Float(
        string='Plafond mensuel (FCFA)',
        default=1500000,
        required=True,
        help='Plafond de cotisation CNSS mensuel',
    )
    active = fields.Boolean(
        string='Actif',
        default=True,
    )
    notes = fields.Text(
        string='Notes',
    )

    @api.constrains('taux_cnss_salarie', 'taux_cnss_patronal')
    def _check_taux(self):
        for rec in self:
            if rec.taux_cnss_salarie <= 0 or rec.taux_cnss_salarie > 100:
                raise ValidationError("Le taux salarié CNSS doit être entre 0 et 100%.")
            if rec.taux_cnss_patronal <= 0 or rec.taux_cnss_patronal > 100:
                raise ValidationError("Le taux patronal CNSS doit être entre 0 et 100%.")

    def name_get(self):
        result = []
        for rec in self:
            name = f"{rec.name} - Salarié: {rec.taux_cnss_salarie}% / Patronal: {rec.taux_cnss_patronal}%"
            result.append((rec.id, name))
        return result