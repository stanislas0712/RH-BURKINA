import math

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

TYPES_INDEMNITE = [
    ('logement', 'Indemnité de logement'),
    ('transport', 'Indemnité de transport'),
    ('fonction', 'Indemnité de fonction'),
    ('autre', 'Autre indemnité exonérée'),
]


class RhIuts(models.Model):
    """Barème daté de l'Impôt Unique sur les Traitements et Salaires."""

    _name = 'rh.iuts'
    _description = 'Barème IUTS'
    _inherit = ['rh.parametre.mixin']

    tranche_ids = fields.One2many(
        'rh.iuts.tranche', 'iuts_id', string='Tranches', copy=True)
    charge_famille_ids = fields.One2many(
        'rh.iuts.charge.famille', 'iuts_id',
        string='Réductions pour charges de famille', copy=True)
    exoneration_ids = fields.One2many(
        'rh.iuts.exoneration', 'iuts_id',
        string="Plafonds d'exonération des indemnités", copy=True)
    abattement_cadre = fields.Float(
        string='Abattement frais professionnels – cadre (%)', tracking=True)
    abattement_non_cadre = fields.Float(
        string='Abattement frais professionnels – non-cadre (%)',
        tracking=True)
    abattement_assiette = fields.Selection(
        [('base', 'Salaire de base'),
         ('imposable', 'Brut imposable après cotisations')],
        string="Assiette de l'abattement", required=True, default='base',
        tracking=True)
    arrondi_base = fields.Integer(
        string='Arrondi de la base imposable (à la centaine inférieure…)',
        default=100, tracking=True,
        help="La base imposable est arrondie au multiple inférieur de "
             "cette valeur. 1 = pas d'arrondi.")

    @api.constrains('abattement_cadre', 'abattement_non_cadre',
                    'arrondi_base')
    def _check_abattements(self):
        for rec in self:
            if not (0 <= rec.abattement_cadre <= 100
                    and 0 <= rec.abattement_non_cadre <= 100):
                raise ValidationError(
                    _("Les taux d'abattement doivent être compris entre 0 "
                      "et 100 %."))
            if rec.arrondi_base < 1:
                raise ValidationError(
                    _("L'arrondi de la base doit être au moins 1."))

    def _arrondir_base(self, base):
        self.ensure_one()
        pas = self.arrondi_base or 1
        return max(math.floor(base / pas) * pas, 0)

    def _get_abattement(self, est_cadre):
        """Taux d'abattement forfaitaire pour frais professionnels."""
        self.ensure_one()
        return self.abattement_cadre if est_cadre else \
            self.abattement_non_cadre

    def _get_exoneration(self, type_indemnite, montant, assiettes):
        """Part exonérée d'une indemnité dans la limite de son plafond.

        ``assiettes`` : dict {'brut': …, 'base': …} servant au plafond en %.
        """
        self.ensure_one()
        regle = self.exoneration_ids.filtered(
            lambda e: e.type_indemnite == type_indemnite)[:1]
        if not regle:
            return 0.0
        plafonds = []
        if regle.taux_max:
            plafonds.append(
                assiettes.get(regle.assiette, 0.0) * regle.taux_max / 100.0)
        if regle.plafond_montant:
            plafonds.append(regle.plafond_montant)
        exonere = min([montant] + plafonds)
        return self._arrondi(max(exonere, 0.0))

    def _calculer_impot_brut(self, base):
        """Applique le barème progressif à la base (déjà arrondie)."""
        self.ensure_one()
        if not self.tranche_ids:
            raise UserError(_("Le barème IUTS « %s » ne comporte aucune "
                              "tranche.", self.name))
        impot = 0.0
        for tranche in self.tranche_ids.sorted('borne_inf'):
            if base <= tranche.borne_inf:
                break
            haut = min(base, tranche.borne_sup) if tranche.borne_sup \
                else base
            impot += (haut - tranche.borne_inf) * tranche.taux / 100.0
        return impot

    def _get_taux_reduction(self, nb_charges):
        """Taux de réduction pour ``nb_charges`` personnes à charge.

        La ligne au plus grand nombre de charges inférieur ou égal
        s'applique (le dernier palier vaut pour les nombres supérieurs).
        """
        self.ensure_one()
        lignes = self.charge_famille_ids.filtered(
            lambda c: c.nb_charges <= nb_charges).sorted(
            'nb_charges', reverse=True)
        return lignes[0].taux_reduction if lignes else 0.0

    def _calculer_iuts(self, base_imposable, nb_charges=0):
        """Calcule l'IUTS dû.

        Retourne un dict : base arrondie, impôt brut, taux et montant de
        la réduction pour charges de famille, impôt net (arrondis à
        l'unité).
        """
        self.ensure_one()
        base = self._arrondir_base(base_imposable)
        impot_brut = self._arrondi(self._calculer_impot_brut(base))
        taux_reduction = self._get_taux_reduction(nb_charges)
        reduction = self._arrondi(impot_brut * taux_reduction / 100.0)
        return {
            'base': base,
            'impot_brut': impot_brut,
            'taux_reduction': taux_reduction,
            'reduction': reduction,
            'impot_net': max(impot_brut - reduction, 0),
        }


class RhIutsTranche(models.Model):
    _name = 'rh.iuts.tranche'
    _description = 'Tranche du barème IUTS'
    _order = 'borne_inf'

    iuts_id = fields.Many2one(
        'rh.iuts', string='Barème', required=True, ondelete='cascade',
        index=True)
    currency_id = fields.Many2one(related='iuts_id.currency_id')
    borne_inf = fields.Monetary(string='Au-delà de', required=True)
    borne_sup = fields.Monetary(string='Jusqu’à', help="0 = sans limite.")
    taux = fields.Float(string='Taux (%)', required=True)

    @api.constrains('borne_inf', 'borne_sup', 'taux')
    def _check_tranche(self):
        for t in self:
            if t.borne_inf < 0 or not 0 <= t.taux <= 100:
                raise ValidationError(_("Tranche IUTS invalide."))
            if t.borne_sup and t.borne_sup <= t.borne_inf:
                raise ValidationError(
                    _("La borne supérieure d'une tranche IUTS doit dépasser "
                      "sa borne inférieure."))

    @api.constrains('borne_inf', 'borne_sup', 'iuts_id')
    def _check_chevauchement(self):
        for bareme in self.mapped('iuts_id'):
            tranches = bareme.tranche_ids.sorted('borne_inf')
            for prec, suiv in zip(tranches, tranches[1:]):
                if not prec.borne_sup or prec.borne_sup > suiv.borne_inf:
                    raise ValidationError(_(
                        "Les tranches du barème IUTS « %s » se "
                        "chevauchent.", bareme.name))


class RhIutsChargeFamille(models.Model):
    _name = 'rh.iuts.charge.famille'
    _description = 'Réduction IUTS pour charges de famille'
    _order = 'nb_charges'

    iuts_id = fields.Many2one(
        'rh.iuts', string='Barème', required=True, ondelete='cascade',
        index=True)
    nb_charges = fields.Integer(string='Personnes à charge', required=True)
    taux_reduction = fields.Float(
        string="Réduction (% de l'impôt)", required=True)

    _sql_constraints = [
        ('nb_uniq', 'unique(iuts_id, nb_charges)',
         'Une seule ligne par nombre de personnes à charge.'),
        ('taux_ok',
         'CHECK(nb_charges >= 0 AND taux_reduction >= 0 '
         'AND taux_reduction <= 100)',
         'Valeurs de réduction invalides.'),
    ]


class RhIutsExoneration(models.Model):
    _name = 'rh.iuts.exoneration'
    _description = "Plafond d'exonération d'une indemnité"
    _order = 'type_indemnite'

    iuts_id = fields.Many2one(
        'rh.iuts', string='Barème', required=True, ondelete='cascade',
        index=True)
    currency_id = fields.Many2one(related='iuts_id.currency_id')
    type_indemnite = fields.Selection(
        TYPES_INDEMNITE, string="Type d'indemnité", required=True)
    taux_max = fields.Float(
        string='Plafond (% de l’assiette)', help="0 = pas de plafond en %.")
    assiette = fields.Selection(
        [('brut', 'Salaire brut'), ('base', 'Salaire de base')],
        string='Assiette du plafond', default='brut', required=True)
    plafond_montant = fields.Monetary(
        string='Plafond en montant', help="0 = pas de plafond en montant.")

    _sql_constraints = [
        ('type_uniq', 'unique(iuts_id, type_indemnite)',
         "Une seule règle d'exonération par type d'indemnité."),
    ]
