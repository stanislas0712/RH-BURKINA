from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class RhBaremeLicenciement(models.Model):
    """Barème daté de l'indemnité de licenciement par tranches."""

    _name = 'rh.bareme.licenciement'
    _description = "Barème de l'indemnité de licenciement"
    _inherit = ['rh.parametre.mixin']

    anciennete_minimum_mois = fields.Integer(
        string='Ancienneté minimum ouvrant droit (mois)', tracking=True)
    proratiser = fields.Boolean(
        string='Proratiser les années incomplètes', default=True,
        tracking=True,
        help="Les mois au-delà de la dernière année complète comptent "
             "au prorata.")
    ligne_ids = fields.One2many(
        'rh.bareme.licenciement.ligne', 'bareme_id', string='Tranches',
        copy=True)

    def _calculer_indemnite(self, salaire_reference, anciennete_mois):
        """Indemnité de licenciement.

        Pour chaque tranche d'ancienneté, les années comprises dans la
        tranche sont multipliées par le taux et le salaire de référence.
        """
        self.ensure_one()
        if anciennete_mois < self.anciennete_minimum_mois:
            return 0.0
        annees = anciennete_mois / 12.0
        if not self.proratiser:
            annees = float(int(annees))
        total = 0.0
        for ligne in self.ligne_ids.sorted('annees_debut'):
            if annees <= ligne.annees_debut:
                break
            fin = min(annees, ligne.annees_fin) if ligne.annees_fin \
                else annees
            total += (fin - ligne.annees_debut) * salaire_reference \
                * ligne.taux / 100.0
        return self._arrondi(total)


class RhBaremeLicenciementLigne(models.Model):
    _name = 'rh.bareme.licenciement.ligne'
    _description = "Tranche de l'indemnité de licenciement"
    _order = 'annees_debut'

    bareme_id = fields.Many2one(
        'rh.bareme.licenciement', string='Barème', required=True,
        ondelete='cascade', index=True)
    annees_debut = fields.Float(string='De (années)', required=True)
    annees_fin = fields.Float(string='À (années)', help="0 = sans limite.")
    taux = fields.Float(
        string='Taux (% du salaire de référence par année)', required=True)

    @api.constrains('annees_debut', 'annees_fin', 'taux')
    def _check_ligne(self):
        for l in self:
            if l.annees_debut < 0 or l.taux < 0:
                raise ValidationError(
                    _("Les tranches de licenciement doivent être "
                      "positives."))
            if l.annees_fin and l.annees_fin <= l.annees_debut:
                raise ValidationError(
                    _("La fin de tranche doit dépasser le début."))
