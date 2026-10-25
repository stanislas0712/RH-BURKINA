from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class RhPresence(models.Model):
    """Pointage journalier : arrivée, départ, heures travaillées."""

    _name = 'rh.presence'
    _description = 'Présence'
    _order = 'date desc, employee_id'
    _check_company_auto = True

    employee_id = fields.Many2one(
        'hr.employee', string='Employé', required=True, index=True,
        ondelete='restrict', check_company=True)
    company_id = fields.Many2one(
        related='employee_id.company_id', store=True, index=True)
    department_id = fields.Many2one(
        related='employee_id.department_id', store=True, string='Département')
    date = fields.Date(string='Date', required=True, index=True,
                       default=fields.Date.context_today)
    heure_arrivee = fields.Float(string='Arrivée')
    heure_depart = fields.Float(string='Départ')
    duree_pause = fields.Float(string='Pause (h)')
    heures_travaillees = fields.Float(
        string='Heures travaillées', compute='_compute_heures', store=True)
    heure_prevue = fields.Float(
        string='Arrivée prévue', compute='_compute_heure_prevue', store=True,
        help="Première heure de travail du jour selon le calendrier de "
             "l'employé.")
    retard_minutes = fields.Integer(
        string='Retard (min)', compute='_compute_heure_prevue', store=True)
    retard_ids = fields.One2many('rh.retard', 'presence_id',
                                 string='Retards déclarés')
    note = fields.Char(string='Observations')

    _sql_constraints = [
        ('employee_date_uniq', 'unique(employee_id, date)',
         'Une seule présence par employé et par jour.'),
    ]

    @api.depends('heure_arrivee', 'heure_depart', 'duree_pause')
    def _compute_heures(self):
        for rec in self:
            if rec.heure_depart and rec.heure_depart > rec.heure_arrivee:
                rec.heures_travaillees = max(
                    rec.heure_depart - rec.heure_arrivee - rec.duree_pause,
                    0.0)
            else:
                rec.heures_travaillees = 0.0

    @api.depends('date', 'heure_arrivee', 'employee_id')
    def _compute_heure_prevue(self):
        for rec in self:
            prevue = 0.0
            if rec.date and rec.employee_id:
                emp = rec.employee_id.sudo()
                calendar = emp.resource_calendar_id \
                    or emp.company_id.resource_calendar_id
                lignes = calendar.attendance_ids.filtered(
                    lambda a: int(a.dayofweek) == rec.date.weekday()
                    and not a.date_from and a.day_period != 'lunch') \
                    if calendar else []
                if lignes:
                    prevue = min(lignes.mapped('hour_from'))
            rec.heure_prevue = prevue
            rec.retard_minutes = round((rec.heure_arrivee - prevue) * 60) \
                if prevue and rec.heure_arrivee > prevue else 0

    @api.constrains('heure_arrivee', 'heure_depart', 'duree_pause')
    def _check_heures(self):
        for rec in self:
            for valeur in (rec.heure_arrivee, rec.heure_depart):
                if valeur < 0 or valeur >= 24:
                    raise ValidationError(
                        _("Les heures doivent être comprises entre 00:00 et "
                          "23:59."))
            if rec.heure_depart and rec.heure_depart < rec.heure_arrivee:
                raise ValidationError(
                    _("L'heure de départ précède l'heure d'arrivée."))
            if rec.duree_pause < 0:
                raise ValidationError(_("La pause ne peut être négative."))

    def action_declarer_retard(self):
        """Crée la fiche de retard correspondant au pointage."""
        for rec in self.filtered(lambda p: p.retard_minutes
                                 and not p.retard_ids):
            self.env['rh.retard'].create({
                'employee_id': rec.employee_id.id,
                'date': rec.date,
                'duree_minutes': rec.retard_minutes,
                'presence_id': rec.id,
            })
        return True


class RhRetard(models.Model):
    _name = 'rh.retard'
    _description = 'Retard'
    _inherit = ['mail.thread']
    _order = 'date desc'
    _check_company_auto = True

    employee_id = fields.Many2one(
        'hr.employee', string='Employé', required=True, index=True,
        ondelete='restrict', check_company=True, tracking=True)
    company_id = fields.Many2one(
        related='employee_id.company_id', store=True, index=True)
    department_id = fields.Many2one(
        related='employee_id.department_id', store=True, string='Département')
    date = fields.Date(string='Date', required=True, index=True,
                       default=fields.Date.context_today, tracking=True)
    duree_minutes = fields.Integer(string='Durée (min)', required=True,
                                   tracking=True)
    motif = fields.Char(string='Motif', tracking=True)
    justifie = fields.Boolean(string='Justifié', tracking=True)
    justificatif = fields.Binary(string='Justificatif', attachment=True)
    nom_justificatif = fields.Char()
    presence_id = fields.Many2one('rh.presence', string='Pointage',
                                  ondelete='set null')

    @api.constrains('duree_minutes')
    def _check_duree(self):
        if any(r.duree_minutes <= 0 for r in self):
            raise ValidationError(_("La durée du retard doit être "
                                    "positive."))
