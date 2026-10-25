from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .rh_iuts import TYPES_INDEMNITE

RECURRENCES = [('recurrent', 'Récurrent (chaque mois)'),
               ('ponctuel', 'Ponctuel (une seule fois)')]


class RhTypePrime(models.Model):
    """Type de prime ou d'indemnité et son traitement social et fiscal."""

    _name = 'rh.type.prime'
    _description = "Type de prime ou d'indemnité"
    _order = 'sequence, name'

    name = fields.Char(string='Libellé', required=True, translate=True)
    code = fields.Char(string='Code', required=True)
    sequence = fields.Integer(default=10)
    imposable = fields.Boolean(
        string='Imposable (IUTS)', default=True,
        help="Décoché : la prime est entièrement exclue de la base IUTS.")
    exoneration_iuts = fields.Selection(
        TYPES_INDEMNITE, string='Exonération IUTS plafonnée',
        help="Indemnité imposable exonérée dans la limite du plafond du "
             "barème IUTS en vigueur (logement, transport, fonction…).")
    soumis_cotisation = fields.Boolean(string='Soumis à cotisation sociale',
                                       default=True)
    mode_calcul = fields.Selection(
        [('fixe', 'Montant fixe'), ('pourcentage', '% du salaire de base')],
        string='Calcul', required=True, default='fixe')
    montant = fields.Monetary(string='Montant par défaut')
    taux = fields.Float(string='Taux par défaut (%)')
    recurrence = fields.Selection(RECURRENCES, string='Récurrence',
                                  required=True, default='recurrent')
    company_id = fields.Many2one('res.company', string='Société')
    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.ref('base.XOF'))
    description = fields.Text(string='Description / référence')
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('code_uniq', 'unique(code, company_id)',
         'Le code du type de prime doit être unique.'),
    ]

    @api.constrains('imposable', 'exoneration_iuts', 'taux', 'montant')
    def _check_type(self):
        for rec in self:
            if rec.exoneration_iuts and not rec.imposable:
                raise ValidationError(_(
                    "Une indemnité non imposable n'a pas besoin de plafond "
                    "d'exonération (%s).", rec.name))
            if rec.taux < 0 or rec.montant < 0:
                raise ValidationError(_("Montant ou taux négatif."))


class RhElementVariableMixin(models.AbstractModel):
    """Socle commun aux primes et retenues attribuées à un employé."""

    _name = 'rh.element.variable.mixin'
    _description = 'Élément variable de paie'
    _inherit = ['mail.thread']
    _order = 'date_debut desc, id desc'
    _check_company_auto = True

    employee_id = fields.Many2one(
        'hr.employee', string='Employé', required=True, index=True,
        ondelete='restrict', check_company=True, tracking=True)
    company_id = fields.Many2one(
        related='employee_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    montant = fields.Monetary(string='Montant', tracking=True)
    taux = fields.Float(string='Taux (%)', tracking=True)
    date_debut = fields.Date(
        string='À partir du', required=True, tracking=True,
        default=fields.Date.context_today,
        help="Ponctuel : la prime ou retenue s'applique au mois de cette "
             "date.")
    date_fin = fields.Date(string="Jusqu'au", tracking=True)
    bulletin_id = fields.Many2one(
        'rh.bulletin.paie', string='Payé sur le bulletin', readonly=True,
        copy=False, help="Élément ponctuel déjà intégré à un bulletin.")
    note = fields.Char(string='Observations')
    active = fields.Boolean(default=True)

    @api.constrains('date_debut', 'date_fin', 'montant', 'taux')
    def _check_element(self):
        for rec in self:
            if rec.date_fin and rec.date_fin < rec.date_debut:
                raise ValidationError(_("La date de fin précède la date de "
                                        "début."))
            if rec.montant < 0 or rec.taux < 0:
                raise ValidationError(_("Montant ou taux négatif."))

    def write(self, vals):
        if self.filtered('bulletin_id') and not self.env.su and \
                set(vals) - {'active', 'note'}:
            raise UserError(_("Cet élément a déjà été payé sur un bulletin "
                              "validé : il ne peut plus être modifié."))
        return super().write(vals)

    def unlink(self):
        if not self.env.su:
            raise UserError(_("Suppression interdite : archivez l'élément."))
        return super().unlink()

    @api.model
    def _domaine_periode(self, employee, date_debut, date_fin):
        """Éléments applicables à un employé sur une période."""
        return [
            ('employee_id', '=', employee.id),
            ('date_debut', '<=', date_fin),
            '|', ('date_fin', '=', False), ('date_fin', '>=', date_debut),
        ]

    def _filtrer_periode(self, date_debut, date_fin, bulletin):
        """Garde les récurrents actifs et les ponctuels du mois non payés."""
        return self.filtered(lambda e: (
            e._recurrence() == 'recurrent'
            or (date_debut <= e.date_debut <= date_fin
                and e.bulletin_id in (bulletin, self.env['rh.bulletin.paie'])
                )))

    def _recurrence(self):
        raise NotImplementedError


class RhPrime(models.Model):
    _name = 'rh.prime'
    _inherit = ['rh.element.variable.mixin']
    _description = "Prime ou indemnité d'un employé"

    type_prime_id = fields.Many2one('rh.type.prime', string='Type',
                                    required=True, tracking=True)
    mode_calcul = fields.Selection(related='type_prime_id.mode_calcul')
    recurrence = fields.Selection(related='type_prime_id.recurrence',
                                  store=True)

    def _recurrence(self):
        return self.recurrence

    @api.onchange('type_prime_id')
    def _onchange_type_prime_id(self):
        if self.type_prime_id:
            self.montant = self.type_prime_id.montant
            self.taux = self.type_prime_id.taux

    def _montant_pour(self, salaire_base):
        """Montant de la prime pour un salaire de base (déjà proratisé)."""
        self.ensure_one()
        type_p = self.type_prime_id
        if type_p.mode_calcul == 'pourcentage':
            taux = self.taux or type_p.taux
            return salaire_base * taux / 100.0
        return self.montant or type_p.montant
