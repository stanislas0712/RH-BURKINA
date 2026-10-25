from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

REGIMES_SOCIAUX = [
    ('cnss', 'CNSS (régime général)'),
    ('carfo', 'CARFO (agents publics détachés)'),
]

BRANCHES = [
    ('pf', 'Prestations familiales'),
    ('rp', 'Risques professionnels'),
    ('pension', 'Pension (vieillesse, invalidité, décès)'),
    ('autre', 'Autre'),
]


class RhCnss(models.Model):
    """Barème daté des cotisations sociales d'un régime (CNSS, CARFO)."""

    _name = 'rh.cnss'
    _description = 'Barème des cotisations sociales'
    _inherit = ['rh.parametre.mixin']
    _rh_cle_fields = ['regime']

    regime = fields.Selection(
        REGIMES_SOCIAUX, string='Régime', required=True, default='cnss',
        tracking=True)
    plafond_mensuel = fields.Monetary(
        string='Plafond mensuel de cotisation', tracking=True,
        help="0 = pas de plafond.")
    branche_ids = fields.One2many(
        'rh.cnss.branche', 'cnss_id', string='Branches', copy=True)
    taux_salarial_total = fields.Float(
        string='Total part salariale (%)', compute='_compute_totaux')
    taux_patronal_total = fields.Float(
        string='Total part patronale (%)', compute='_compute_totaux')

    @api.depends('branche_ids.taux_salarial', 'branche_ids.taux_patronal')
    def _compute_totaux(self):
        for rec in self:
            rec.taux_salarial_total = sum(rec.branche_ids.mapped(
                'taux_salarial'))
            rec.taux_patronal_total = sum(rec.branche_ids.mapped(
                'taux_patronal'))

    @api.constrains('plafond_mensuel')
    def _check_plafond(self):
        if any(r.plafond_mensuel < 0 for r in self):
            raise ValidationError(_("Le plafond ne peut pas être négatif."))

    @api.model
    def _get_bareme(self, regime, date=None, company=None):
        """Barème en vigueur pour un régime donné."""
        return self._get_en_vigueur(date=date, company=company, regime=regime)

    def _calculer_cotisations(self, brut_soumis):
        """Calcule les cotisations sur le brut soumis à cotisation.

        Retourne un dict : base plafonnée, base non plafonnée, détail par
        branche (base, part salariale, part patronale) et totaux, chaque
        montant arrondi à l'unité.
        """
        self.ensure_one()
        brut_soumis = max(brut_soumis, 0.0)
        base_plafonnee = brut_soumis
        if self.plafond_mensuel:
            base_plafonnee = min(brut_soumis, self.plafond_mensuel)
        detail = []
        for branche in self.branche_ids.sorted('sequence'):
            base = base_plafonnee if branche.plafonnee else brut_soumis
            detail.append({
                'branche': branche,
                'code': branche.code,
                'name': branche.name,
                'base': self._arrondi(base),
                'taux_salarial': branche.taux_salarial,
                'taux_patronal': branche.taux_patronal,
                'salarial': self._arrondi(
                    base * branche.taux_salarial / 100.0),
                'patronal': self._arrondi(
                    base * branche.taux_patronal / 100.0),
            })
        return {
            'base': self._arrondi(base_plafonnee),
            'base_non_plafonnee': self._arrondi(brut_soumis),
            'detail': detail,
            'total_salarial': sum(d['salarial'] for d in detail),
            'total_patronal': sum(d['patronal'] for d in detail),
        }


class RhCnssBranche(models.Model):
    _name = 'rh.cnss.branche'
    _description = 'Branche de cotisation sociale'
    _order = 'sequence, id'

    cnss_id = fields.Many2one(
        'rh.cnss', string='Barème', required=True, ondelete='cascade',
        index=True)
    sequence = fields.Integer(default=10)
    code = fields.Selection(BRANCHES, string='Branche', required=True)
    name = fields.Char(string='Libellé', required=True)
    taux_salarial = fields.Float(string='Part salariale (%)')
    taux_patronal = fields.Float(string='Part patronale (%)')
    plafonnee = fields.Boolean(
        string='Assiette plafonnée', default=True,
        help="Décoché : la branche cotise sur la totalité du brut soumis.")

    _sql_constraints = [
        ('code_uniq', 'unique(cnss_id, code)',
         'Chaque branche ne peut figurer qu’une fois par barème.'),
        ('taux_positifs',
         'CHECK(taux_salarial >= 0 AND taux_patronal >= 0 '
         'AND taux_salarial <= 100 AND taux_patronal <= 100)',
         'Les taux doivent être compris entre 0 et 100 %.'),
    ]
