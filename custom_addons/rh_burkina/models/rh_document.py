from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class RhTypeDocument(models.Model):
    _name = 'rh.type.document'
    _description = 'Type de document RH'
    _order = 'sequence, name'

    name = fields.Char(string='Type', required=True, translate=True)
    code = fields.Char(string='Code')
    sequence = fields.Integer(default=10)
    a_expiration = fields.Boolean(
        string="Soumis à expiration",
        help="Le document a une date d'expiration à surveiller.")
    delai_alerte_jours = fields.Integer(
        string="Alerte avant expiration (jours)", default=30)
    company_id = fields.Many2one(
        'res.company', string='Société',
        help="Vide : type commun à toutes les sociétés.")
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('code_uniq', 'unique(code, company_id)',
         'Le code du type de document doit être unique.'),
    ]


class RhDocument(models.Model):
    """Pièce du dossier du personnel."""

    _name = 'rh.document'
    _description = 'Document du personnel'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_expiration, id desc'
    _check_company_auto = True

    name = fields.Char(string='Intitulé', required=True, tracking=True)
    employee_id = fields.Many2one(
        'hr.employee', string='Employé', required=True, index=True,
        ondelete='restrict', check_company=True, tracking=True)
    company_id = fields.Many2one(
        related='employee_id.company_id', store=True, index=True)
    type_document_id = fields.Many2one(
        'rh.type.document', string='Type', required=True, tracking=True)
    fichier = fields.Binary(string='Fichier', attachment=True)
    nom_fichier = fields.Char(string='Nom du fichier')
    reference = fields.Char(string='Référence / numéro')
    date_emission = fields.Date(string="Date d'émission", tracking=True)
    date_expiration = fields.Date(string="Date d'expiration", tracking=True)
    etat = fields.Selection(
        [('valide', 'Valide'), ('bientot', 'Expire bientôt'),
         ('expire', 'Expiré'), ('sans', 'Sans expiration')],
        string='État', compute='_compute_etat', search='_search_etat')
    note = fields.Text(string='Observations')
    active = fields.Boolean(default=True)

    @api.depends('date_expiration', 'type_document_id.delai_alerte_jours')
    @api.depends_context('date')
    def _compute_etat(self):
        today = fields.Date.context_today(self)
        for doc in self:
            if not doc.date_expiration:
                doc.etat = 'sans'
            elif doc.date_expiration < today:
                doc.etat = 'expire'
            elif doc.date_expiration <= today + relativedelta(
                    days=doc.type_document_id.delai_alerte_jours or 0):
                doc.etat = 'bientot'
            else:
                doc.etat = 'valide'

    def _search_etat(self, operator, value):
        if operator not in ('=', 'in'):
            raise NotImplementedError(_("Opérateur non pris en charge."))
        valeurs = [value] if operator == '=' else value
        today = fields.Date.context_today(self)
        domains = []
        if 'expire' in valeurs:
            domains.append([('date_expiration', '<', today)])
        if 'bientot' in valeurs:
            # Approximation : délai standard de 30 jours pour la recherche
            domains.append([('date_expiration', '>=', today),
                            ('date_expiration', '<=',
                             today + relativedelta(days=30))])
        if 'valide' in valeurs:
            domains.append([('date_expiration', '>',
                             today + relativedelta(days=30))])
        if 'sans' in valeurs:
            domains.append([('date_expiration', '=', False)])
        if not domains:
            return [('id', '=', 0)]
        result = domains[0]
        for dom in domains[1:]:
            result = ['|'] + result + dom
        return result

    @api.constrains('date_emission', 'date_expiration')
    def _check_dates(self):
        for doc in self:
            if doc.date_emission and doc.date_expiration \
                    and doc.date_expiration < doc.date_emission:
                raise ValidationError(_(
                    "Document %s : la date d'expiration précède la date "
                    "d'émission.", doc.name))
