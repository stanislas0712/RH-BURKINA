from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class RhParametreMixin(models.AbstractModel):
    """Socle commun des paramètres légaux datés.

    Un jeu de paramètres s'applique à partir de ``date_debut`` jusqu'à la
    veille du jeu suivant ayant la même clé. Un jeu sans société
    s'applique à toutes les sociétés ; un jeu propre à une société
    prime sur le jeu commun.
    """

    _name = 'rh.parametre.mixin'
    _description = 'Paramètre légal daté'
    _inherit = ['mail.thread']
    _order = 'date_debut desc, id desc'

    # Champs supplémentaires formant la clé d'unicité (ex. : régime).
    _rh_cle_fields = []

    name = fields.Char(string='Libellé', required=True, tracking=True)
    date_debut = fields.Date(
        string="Date d'entrée en vigueur", required=True, tracking=True,
        default=fields.Date.context_today)
    date_fin = fields.Date(
        string='Valable jusqu’au', compute='_compute_date_fin',
        help="Veille de l'entrée en vigueur du jeu suivant.")
    company_id = fields.Many2one(
        'res.company', string='Société', index=True,
        help="Vide : s'applique à toutes les sociétés.")
    currency_id = fields.Many2one(
        'res.currency', string='Devise', required=True,
        default=lambda self: self.env.ref('base.XOF'))
    reference_legale = fields.Char(
        string='Référence légale',
        help="Texte de loi, décret ou convention justifiant ces valeurs.")
    note = fields.Text(string='Observations')
    a_verifier = fields.Boolean(
        string='À vérifier', default=True, tracking=True,
        help="Coché tant que les valeurs n'ont pas été confirmées "
             "auprès de l'administration compétente.")
    active = fields.Boolean(default=True)

    def _rh_cle_domain(self):
        self.ensure_one()
        domain = [('company_id', '=', self.company_id.id)]
        for fname in self._rh_cle_fields:
            domain.append((fname, '=', self[fname]))
        return domain

    @api.depends('date_debut', 'company_id')
    def _compute_date_fin(self):
        for rec in self:
            rec.date_fin = False
            if not rec.date_debut or not rec.id:
                continue
            suivant = self.search(
                rec._rh_cle_domain() + [('date_debut', '>', rec.date_debut)],
                order='date_debut asc', limit=1)
            if suivant:
                rec.date_fin = fields.Date.subtract(suivant.date_debut,
                                                    days=1)

    @api.constrains('date_debut', 'company_id', 'active')
    def _check_date_unique(self):
        for rec in self.filtered('active'):
            doublon = self.search_count(
                rec._rh_cle_domain() + [
                    ('date_debut', '=', rec.date_debut),
                    ('id', '!=', rec.id)])
            if doublon:
                raise ValidationError(_(
                    "Un jeu de paramètres « %(model)s » existe déjà à la "
                    "date du %(date)s pour ce périmètre.",
                    model=self._description, date=rec.date_debut))

    @api.model
    def _get_en_vigueur(self, date=None, company=None, raise_if_missing=True,
                        **cle):
        """Retourne le jeu de paramètres applicable à ``date``.

        Le jeu propre à la société est prioritaire sur le jeu commun.
        Lecture en sudo : les paramètres légaux sont des données de
        référence utilisées par les calculs, quel que soit l'utilisateur.
        """
        date = date or fields.Date.context_today(self)
        company = company or self.env.company
        base = [('date_debut', '<=', date)]
        base += [(fname, '=', value) for fname, value in cle.items()]
        model = self.sudo()
        for company_id in (company.id, False):
            rec = model.search(base + [('company_id', '=', company_id)],
                               order='date_debut desc, id desc', limit=1)
            if rec:
                return rec
        if raise_if_missing:
            raise UserError(_(
                "Aucun paramètre « %(model)s » en vigueur au %(date)s pour "
                "la société %(company)s. Renseignez-le dans Configuration "
                "> Paramètres légaux.",
                model=self._description, date=date, company=company.name))
        return model.browse()

    def _arrondi(self, montant):
        """Arrondit un montant selon la devise (à l'unité en XOF)."""
        self.ensure_one()
        return self.currency_id.round(montant)
