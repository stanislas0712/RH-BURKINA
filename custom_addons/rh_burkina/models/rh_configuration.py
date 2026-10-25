from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .rh_categorie import GROUPES_PROFESSIONNELS

UNITES_DUREE = [('jour', 'Jour(s)'), ('mois', 'Mois')]

TYPES_HEURE_SUP = [
    ('jour', 'Heures de jour (jours ouvrables)'),
    ('nuit', 'Heures de nuit'),
    ('dimanche', 'Dimanche'),
    ('ferie', 'Jour férié'),
]


class RhConfiguration(models.Model):
    """Paramètres légaux généraux, datés et historisés."""

    _name = 'rh.configuration'
    _description = 'Paramètres légaux généraux'
    _inherit = ['rh.parametre.mixin', 'mail.activity.mixin']

    # Salaire minimum et durée du travail
    smig_mensuel = fields.Monetary(
        string='SMIG mensuel', required=True, tracking=True)
    smig_horaire = fields.Monetary(string='SMIG horaire', tracking=True)
    heures_legales_hebdo = fields.Float(
        string='Durée légale hebdomadaire (h)', required=True, tracking=True)
    heures_legales_mensuelles = fields.Float(
        string='Durée légale mensuelle (h)', required=True, tracking=True)
    jours_base_prorata = fields.Float(
        string='Jours de base du prorata', required=True, default=30.0,
        tracking=True,
        help="Nombre de jours d'un mois complet pour le calcul du salaire "
             "au prorata (entrée / sortie en cours de mois).")

    # Embauche, carrière, retraite
    age_minimum_embauche = fields.Integer(
        string="Âge minimum à l'embauche", required=True, tracking=True)
    age_retraite = fields.Integer(
        string='Âge légal de départ à la retraite', required=True,
        tracking=True)
    cdd_renouvellements_max = fields.Integer(
        string='CDD : renouvellements maximum', tracking=True)
    cdd_duree_max_mois = fields.Integer(
        string='CDD : durée cumulée maximum (mois)', tracking=True)
    mise_a_pied_max_jours = fields.Integer(
        string='Mise à pied : durée maximum (jours)', tracking=True)

    # Heures supplémentaires
    hs_plafond_hebdo = fields.Float(
        string='Heures sup. : plafond hebdomadaire (h)', tracking=True,
        help="0 = aucun plafond renseigné.")
    hs_plafond_annuel = fields.Float(
        string='Heures sup. : plafond annuel (h)', tracking=True,
        help="0 = aucun plafond renseigné.")

    # Congés
    conge_jours_par_mois = fields.Float(
        string='Congés acquis par mois de service (jours)', required=True,
        tracking=True)
    conge_type_jours = fields.Selection(
        [('ouvrable', 'Jours ouvrables'), ('ouvre', 'Jours ouvrés'),
         ('calendaire', 'Jours calendaires')],
        string='Nature des jours de congé', required=True,
        default='ouvrable', tracking=True)

    # Protection des données
    # Application du SMIG selon le contrat (à vérifier)
    smig_stage = fields.Boolean(
        string='SMIG applicable aux stages', tracking=True,
        help="Décoché : la gratification de stage n'est pas comparée au "
             "SMIG (à vérifier).")
    smig_prorata_temps_partiel = fields.Boolean(
        string='SMIG proratisé pour le temps partiel', default=True,
        tracking=True,
        help="Le minimum exigé est le SMIG × heures du contrat / durée "
             "légale (à vérifier).")

    duree_conservation_annees = fields.Integer(
        string='Conservation des dossiers après sortie (années)',
        tracking=True)

    # Barèmes détaillés
    essai_ids = fields.One2many(
        'rh.configuration.essai', 'configuration_id',
        string="Périodes d'essai", copy=True)
    preavis_ids = fields.One2many(
        'rh.configuration.preavis', 'configuration_id',
        string='Préavis', copy=True)
    majoration_hs_ids = fields.One2many(
        'rh.configuration.majoration.hs', 'configuration_id',
        string='Majorations heures supplémentaires', copy=True)
    anciennete_ids = fields.One2many(
        'rh.configuration.anciennete', 'configuration_id',
        string="Prime d'ancienneté", copy=True)
    conge_anciennete_ids = fields.One2many(
        'rh.configuration.conge.anciennete', 'configuration_id',
        string='Congés supplémentaires pour ancienneté', copy=True)
    quotite_ids = fields.One2many(
        'rh.configuration.quotite', 'configuration_id',
        string='Quotité saisissable', copy=True)

    @api.constrains('smig_mensuel', 'heures_legales_hebdo',
                    'heures_legales_mensuelles', 'jours_base_prorata',
                    'age_minimum_embauche', 'age_retraite',
                    'conge_jours_par_mois')
    def _check_valeurs(self):
        for rec in self:
            if rec.smig_mensuel <= 0:
                raise ValidationError(_("Le SMIG doit être positif."))
            if rec.heures_legales_hebdo <= 0 or \
                    rec.heures_legales_mensuelles <= 0:
                raise ValidationError(
                    _("La durée légale du travail doit être positive."))
            if rec.jours_base_prorata <= 0:
                raise ValidationError(
                    _("Le nombre de jours de base du prorata doit être "
                      "positif."))
            if rec.age_minimum_embauche <= 0 or \
                    rec.age_retraite <= rec.age_minimum_embauche:
                raise ValidationError(
                    _("L'âge de retraite doit être supérieur à l'âge "
                      "minimum d'embauche."))
            if rec.conge_jours_par_mois < 0:
                raise ValidationError(
                    _("L'acquisition de congés ne peut pas être négative."))

    # ------------------------------------------------------------------
    # Lecture des barèmes
    # ------------------------------------------------------------------
    def _get_periode_essai(self, categorie):
        """Retourne (durée, unité) de la période d'essai d'une catégorie.

        Une ligne propre à la catégorie prime sur la ligne du groupe.
        """
        self.ensure_one()
        lignes = self.essai_ids.filtered(
            lambda l: l.categorie_id == categorie) or self.essai_ids.filtered(
            lambda l: not l.categorie_id
            and l.groupe_professionnel == categorie.groupe_professionnel)
        if not lignes:
            raise UserError(_(
                "Aucune durée de période d'essai paramétrée pour la "
                "catégorie %s.", categorie.display_name))
        ligne = lignes[0]
        return ligne.duree, ligne.unite

    def _get_preavis(self, categorie, anciennete_mois):
        """Retourne (durée, unité) du préavis selon catégorie et ancienneté."""
        self.ensure_one()
        lignes = self.preavis_ids.filtered(
            lambda l: l.categorie_id == categorie) or self.preavis_ids.filtered(
            lambda l: not l.categorie_id
            and l.groupe_professionnel == categorie.groupe_professionnel)
        lignes = lignes.filtered(
            lambda l: l.anciennete_min_mois <= anciennete_mois).sorted(
            'anciennete_min_mois', reverse=True)
        if not lignes:
            raise UserError(_(
                "Aucune durée de préavis paramétrée pour la catégorie %s.",
                categorie.display_name))
        return lignes[0].duree, lignes[0].unite

    def _get_taux_anciennete(self, annees):
        """Taux (%) de prime d'ancienneté pour ``annees`` de service."""
        self.ensure_one()
        lignes = self.anciennete_ids.filtered(
            lambda l: l.annees_min <= annees).sorted(
            'annees_min', reverse=True)
        return lignes[0].taux if lignes else 0.0

    def _get_conge_supplementaire(self, annees):
        """Jours de congé supplémentaires par an pour ``annees`` de service."""
        self.ensure_one()
        lignes = self.conge_anciennete_ids.filtered(
            lambda l: l.annees_min <= annees).sorted(
            'annees_min', reverse=True)
        return lignes[0].jours_supplementaires if lignes else 0.0

    def _get_taux_majoration_hs(self, type_heure, rang_heure):
        """Taux (%) de majoration pour la ``rang_heure``-ième heure sup."""
        self.ensure_one()
        lignes = self.majoration_hs_ids.filtered(
            lambda l: l.type_heure == type_heure
            and l.heure_debut < rang_heure
            and (not l.heure_fin or rang_heure <= l.heure_fin))
        if not lignes:
            raise UserError(_(
                "Aucun taux de majoration paramétré pour ce type d'heures "
                "supplémentaires (%s).",
                dict(TYPES_HEURE_SUP).get(type_heure)))
        return lignes[0].taux

    def _get_quotite_saisissable(self, salaire):
        """Montant maximal saisissable (retenues) sur ``salaire``.

        Barème progressif : chaque tranche de salaire est saisissable à
        hauteur de son taux. Lève une erreur si le barème est vide.
        """
        self.ensure_one()
        if not self.quotite_ids:
            raise UserError(_(
                "Le barème de la quotité saisissable n'est pas renseigné "
                "(Configuration > Paramètres légaux > Général)."))
        total = 0.0
        for tranche in self.quotite_ids.sorted('borne_inf'):
            haut = tranche.borne_sup or salaire
            if salaire <= tranche.borne_inf:
                break
            total += (min(salaire, haut) - tranche.borne_inf) \
                * tranche.taux / 100.0
        return self._arrondi(total)


class RhConfigurationLigneMixin(models.AbstractModel):
    _name = 'rh.configuration.ligne.mixin'
    _description = 'Ligne de barème des paramètres généraux'

    configuration_id = fields.Many2one(
        'rh.configuration', string='Paramètres', required=True,
        ondelete='cascade', index=True)
    currency_id = fields.Many2one(related='configuration_id.currency_id')


class RhConfigurationEssai(models.Model):
    _name = 'rh.configuration.essai'
    _inherit = ['rh.configuration.ligne.mixin']
    _description = "Durée de la période d'essai"
    _order = 'groupe_professionnel, categorie_id'

    groupe_professionnel = fields.Selection(
        GROUPES_PROFESSIONNELS, string='Groupe professionnel', required=True)
    categorie_id = fields.Many2one(
        'rh.categorie', string='Catégorie (facultatif)',
        help="Renseigner pour une durée propre à une catégorie.")
    duree = fields.Integer(string='Durée', required=True)
    unite = fields.Selection(UNITES_DUREE, string='Unité', required=True,
                             default='mois')
    renouvelable = fields.Boolean(string='Renouvelable une fois')

    @api.constrains('duree')
    def _check_duree(self):
        if any(l.duree <= 0 for l in self):
            raise ValidationError(
                _("La durée de la période d'essai doit être positive."))


class RhConfigurationPreavis(models.Model):
    _name = 'rh.configuration.preavis'
    _inherit = ['rh.configuration.ligne.mixin']
    _description = 'Durée du préavis'
    _order = 'groupe_professionnel, anciennete_min_mois'

    groupe_professionnel = fields.Selection(
        GROUPES_PROFESSIONNELS, string='Groupe professionnel', required=True)
    categorie_id = fields.Many2one(
        'rh.categorie', string='Catégorie (facultatif)')
    anciennete_min_mois = fields.Integer(
        string='Ancienneté minimum (mois)', default=0)
    duree = fields.Integer(string='Durée', required=True)
    unite = fields.Selection(UNITES_DUREE, string='Unité', required=True,
                             default='mois')

    @api.constrains('duree', 'anciennete_min_mois')
    def _check_duree(self):
        if any(l.duree <= 0 or l.anciennete_min_mois < 0 for l in self):
            raise ValidationError(
                _("La durée du préavis doit être positive."))


class RhConfigurationMajorationHs(models.Model):
    _name = 'rh.configuration.majoration.hs'
    _inherit = ['rh.configuration.ligne.mixin']
    _description = 'Majoration des heures supplémentaires'
    _order = 'type_heure, heure_debut'

    type_heure = fields.Selection(
        TYPES_HEURE_SUP, string="Type d'heures", required=True)
    heure_debut = fields.Float(
        string='À partir de (h sup. hebdo)', default=0.0,
        help="La tranche s'applique au-delà de ce nombre d'heures "
             "supplémentaires dans la semaine.")
    heure_fin = fields.Float(
        string='Jusqu’à (h sup. hebdo)', help="0 = sans limite.")
    taux = fields.Float(string='Majoration (%)', required=True)

    @api.constrains('heure_debut', 'heure_fin', 'taux')
    def _check_tranche(self):
        for l in self:
            if l.taux < 0 or l.heure_debut < 0:
                raise ValidationError(
                    _("Le taux et les bornes doivent être positifs."))
            if l.heure_fin and l.heure_fin <= l.heure_debut:
                raise ValidationError(
                    _("La fin de tranche doit dépasser le début."))


class RhConfigurationAnciennete(models.Model):
    _name = 'rh.configuration.anciennete'
    _inherit = ['rh.configuration.ligne.mixin']
    _description = "Barème de la prime d'ancienneté"
    _order = 'annees_min'

    annees_min = fields.Integer(
        string="À partir de (années d'ancienneté)", required=True)
    taux = fields.Float(string='Taux (% du salaire de base)', required=True)

    _sql_constraints = [
        ('annees_uniq', 'unique(configuration_id, annees_min)',
         "Une seule ligne par seuil d'ancienneté."),
        ('taux_positif', 'CHECK(taux >= 0 AND annees_min >= 0)',
         'Le taux et le seuil doivent être positifs.'),
    ]


class RhConfigurationCongeAnciennete(models.Model):
    _name = 'rh.configuration.conge.anciennete'
    _inherit = ['rh.configuration.ligne.mixin']
    _description = 'Congés supplémentaires pour ancienneté'
    _order = 'annees_min'

    annees_min = fields.Integer(
        string="À partir de (années d'ancienneté)", required=True)
    jours_supplementaires = fields.Float(
        string='Jours supplémentaires par an', required=True)

    _sql_constraints = [
        ('annees_uniq', 'unique(configuration_id, annees_min)',
         "Une seule ligne par seuil d'ancienneté."),
    ]


class RhConfigurationQuotite(models.Model):
    _name = 'rh.configuration.quotite'
    _inherit = ['rh.configuration.ligne.mixin']
    _description = 'Tranche de quotité saisissable'
    _order = 'borne_inf'

    borne_inf = fields.Monetary(string='Salaire de', required=True)
    borne_sup = fields.Monetary(string='à', help="0 = sans limite.")
    taux = fields.Float(string='Part saisissable (%)', required=True)

    @api.constrains('borne_inf', 'borne_sup', 'taux')
    def _check_tranche(self):
        for l in self:
            if l.borne_inf < 0 or not 0 <= l.taux <= 100:
                raise ValidationError(
                    _("Tranche de quotité invalide (borne ou taux)."))
            if l.borne_sup and l.borne_sup <= l.borne_inf:
                raise ValidationError(
                    _("La borne supérieure doit dépasser la borne "
                      "inférieure."))
