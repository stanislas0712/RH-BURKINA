from odoo import api, fields, models
from odoo.exceptions import ValidationError


class RhEvaluation(models.Model):
    _name = 'rh.evaluation'
    _description = 'Évaluation RH'
    _order = 'date_evaluation desc, id desc'

    employe_id = fields.Many2one(
        'rh.employe',
        string='Employé',
        required=True,
        ondelete='cascade',
    )
    date_evaluation = fields.Date(
        string="Date d'évaluation",
        required=True,
        default=fields.Date.today,
    )
    type_evaluation = fields.Selection(
        [
            ('annuelle', 'Annuelle'),
            ('periodique', 'Périodique'),
            ('probatoire', 'Période probatoire'),
            ('autre', 'Autre'),
        ],
        string='Type d’évaluation',
        default='annuelle',
    )
    note_globale = fields.Float(string='Note globale', digits=(5, 2))
    commentaire = fields.Text(string='Commentaire')
    responsable_id = fields.Many2one('res.users', string='Responsable')
    state = fields.Selection(
        [
            ('draft', 'Brouillon'),
            ('done', 'Validée'),
        ],
        string='État',
        default='draft',
    )
    active = fields.Boolean(string='Actif', default=True)

    @api.constrains('note_globale')
    def _check_note_globale(self):
        for rec in self:
            if rec.note_globale is not None and (rec.note_globale < 0 or rec.note_globale > 20):
                raise ValidationError('La note globale doit être comprise entre 0 et 20.')
