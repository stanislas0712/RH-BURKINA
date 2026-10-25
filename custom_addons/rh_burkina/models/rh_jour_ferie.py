from datetime import date, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class RhJourFerie(models.Model):
    """Jour férié chômé et payé.

    Les fêtes fixes peuvent être recopiées d'une année sur l'autre ; les
    fêtes religieuses à date variable sont saisies chaque année.
    """

    _name = 'rh.jour.ferie'
    _description = 'Jour férié'
    _order = 'date'

    name = fields.Char(string='Libellé', required=True, translate=True)
    date = fields.Date(string='Date', required=True, index=True)
    annee = fields.Integer(string='Année', compute='_compute_annee',
                           store=True, index=True)
    type_fete = fields.Selection(
        [('fixe', 'Fête fixe'), ('variable', 'Fête à date variable')],
        string='Type', required=True, default='fixe')
    company_id = fields.Many2one(
        'res.company', string='Société',
        help="Vide : jour férié commun à toutes les sociétés.")
    note = fields.Char(string='Observations')
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('date_company_uniq', 'unique(date, company_id)',
         'Ce jour férié existe déjà pour ce périmètre.'),
    ]

    @api.depends('date')
    def _compute_annee(self):
        for rec in self:
            rec.annee = rec.date.year if rec.date else 0

    @api.constrains('date', 'company_id')
    def _check_doublon_commun(self):
        # unique() ne protège pas les lignes sans société (NULL)
        for rec in self.filtered(lambda r: not r.company_id):
            if self.search_count([('date', '=', rec.date),
                                  ('company_id', '=', False),
                                  ('id', '!=', rec.id)]):
                raise ValidationError(_(
                    "Le %s est déjà déclaré férié.", rec.date))

    # ------------------------------------------------------------------
    # Outils de calcul
    # ------------------------------------------------------------------
    @api.model
    def _get_dates_feriees(self, date_debut, date_fin, company=None):
        """Ensemble des dates fériées entre deux dates (incluses)."""
        company = company or self.env.company
        feries = self.sudo().search([
            ('date', '>=', date_debut), ('date', '<=', date_fin),
            ('company_id', 'in', [company.id, False])])
        return set(feries.mapped('date'))

    @api.model
    def _jours_travailles_semaine(self, employee):
        """Numéros de jours travaillés (lundi = 0) selon le calendrier."""
        calendar = employee.sudo().resource_calendar_id \
            or employee.sudo().company_id.resource_calendar_id
        jours = {int(a.dayofweek) for a in calendar.attendance_ids} \
            if calendar else set()
        return jours or {0, 1, 2, 3, 4}

    @api.model
    def _compter_jours(self, date_debut, date_fin, mode, employee):
        """Nombre de jours de congé entre deux dates incluses.

        - ``calendaire`` : tous les jours ;
        - ``ouvrable`` : tous les jours sauf le dimanche et les fériés ;
        - ``ouvre`` : jours travaillés selon le calendrier de l'employé,
          hors fériés.
        """
        if not date_debut or not date_fin or date_fin < date_debut:
            return 0
        if mode == 'calendaire':
            return (date_fin - date_debut).days + 1
        feries = self._get_dates_feriees(date_debut, date_fin,
                                         employee.sudo().company_id)
        travailles = self._jours_travailles_semaine(employee) \
            if mode == 'ouvre' else {0, 1, 2, 3, 4, 5}
        total = 0
        jour = date_debut
        while jour <= date_fin:
            if jour.weekday() in travailles and jour not in feries:
                total += 1
            jour += timedelta(days=1)
        return total

    # ------------------------------------------------------------------
    # Report des fêtes fixes
    # ------------------------------------------------------------------
    def action_recopier_fetes_fixes(self):
        """Recopie les fêtes fixes de l'année la plus récente sur l'année
        suivante (sans doublon)."""
        derniere = self.search([('type_fete', '=', 'fixe')],
                               order='date desc', limit=1)
        if not derniere:
            return True
        annee = derniere.date.year
        return self._recopier_fetes_fixes(annee, annee + 1)

    @api.model
    def _recopier_fetes_fixes(self, annee_source, annee_cible):
        sources = self.search([('type_fete', '=', 'fixe'),
                               ('annee', '=', annee_source)])
        crees = self.browse()
        for src in sources:
            try:
                cible = date(annee_cible, src.date.month, src.date.day)
            except ValueError:      # 29 février
                continue
            if not self.search_count([('date', '=', cible),
                                      ('company_id', '=',
                                       src.company_id.id)]):
                crees |= src.copy({'date': cible})
        return crees
