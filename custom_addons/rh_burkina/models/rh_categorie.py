from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Groupes professionnels servant de clé aux paramètres légaux
# (période d'essai, préavis, abattement IUTS cadre / non-cadre).
GROUPES_PROFESSIONNELS = [
    ('ouvrier', 'Ouvrier / Employé'),
    ('maitrise', 'Agent de maîtrise / Technicien'),
    ('cadre', 'Cadre'),
]


class RhCategorie(models.Model):
    """Catégorie / échelon de la grille de classification."""

    _name = 'rh.categorie'
    _description = 'Catégorie professionnelle'
    _inherit = ['mail.thread']
    _order = 'sequence, categorie, echelon'

    name = fields.Char(
        string='Libellé', compute='_compute_name', store=True,
        precompute=True, readonly=False, required=True)
    categorie = fields.Char(string='Catégorie', required=True, tracking=True)
    echelon = fields.Char(string='Échelon', tracking=True)
    sequence = fields.Integer(default=10)
    groupe_professionnel = fields.Selection(
        GROUPES_PROFESSIONNELS, string='Groupe professionnel',
        required=True, default='ouvrier', tracking=True,
        help="Sert à déterminer la période d'essai, le préavis et "
             "l'abattement IUTS (cadre / non-cadre).")
    est_cadre = fields.Boolean(
        string='Cadre', compute='_compute_est_cadre', store=True)
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
    description = fields.Text(string='Description')
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('categorie_echelon_uniq',
         'unique(categorie, echelon, company_id)',
         'Ce couple catégorie / échelon existe déjà pour cette société.'),
    ]

    @api.depends('categorie', 'echelon')
    def _compute_name(self):
        for rec in self:
            if rec.categorie and rec.echelon:
                rec.name = _('%(cat)s - Échelon %(ech)s',
                             cat=rec.categorie, ech=rec.echelon)
            else:
                rec.name = rec.categorie or rec.name

    @api.depends('groupe_professionnel')
    def _compute_est_cadre(self):
        for rec in self:
            rec.est_cadre = rec.groupe_professionnel == 'cadre'

    @api.constrains('salaire_min', 'salaire_max')
    def _check_fourchette(self):
        for rec in self.sudo():
            if rec.salaire_min < 0 or rec.salaire_max < 0:
                raise ValidationError(
                    _("Les salaires de la catégorie ne peuvent pas être "
                      "négatifs."))
            if rec.salaire_max and rec.salaire_min > rec.salaire_max:
                raise ValidationError(
                    _("Catégorie %s : le salaire minimum dépasse le "
                      "salaire maximum.", rec.name))
