from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class RhPret(models.Model):
    """Prêt ou avance sur salaire remboursé par retenue mensuelle."""

    _name = 'rh.pret'
    _description = 'Prêt / avance sur salaire'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_octroi desc, id desc'
    _check_company_auto = True

    name = fields.Char(string='Référence', readonly=True, copy=False,
                       default='/')
    employee_id = fields.Many2one(
        'hr.employee', string='Employé', required=True, index=True,
        ondelete='restrict', check_company=True, tracking=True)
    company_id = fields.Many2one(
        related='employee_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    type_pret = fields.Selection(
        [('pret', 'Prêt'), ('avance', 'Avance sur salaire')],
        string='Type', required=True, default='pret', tracking=True)
    montant = fields.Monetary(string='Montant accordé', required=True,
                              tracking=True)
    date_octroi = fields.Date(string="Date d'octroi", required=True,
                              default=fields.Date.context_today,
                              tracking=True)
    nb_echeances = fields.Integer(string="Nombre d'échéances", required=True,
                                  default=1, tracking=True)
    date_premiere_echeance = fields.Date(
        string='Première échéance (mois)', required=True, tracking=True,
        default=lambda self: fields.Date.context_today(self).replace(day=1))
    echeance_ids = fields.One2many('rh.echeance.pret', 'pret_id',
                                   string='Échéancier', readonly=True)
    montant_rembourse = fields.Monetary(
        string='Remboursé', compute='_compute_remboursement', store=True)
    solde_restant = fields.Monetary(
        string='Restant dû', compute='_compute_remboursement', store=True)
    state = fields.Selection(
        [('brouillon', 'Brouillon'), ('en_cours', 'En cours'),
         ('solde', 'Soldé'), ('annule', 'Annulé')],
        string='État', default='brouillon', required=True, tracking=True,
        copy=False)
    motif = fields.Text(string='Objet')

    @api.depends('montant', 'echeance_ids.state', 'echeance_ids.montant')
    def _compute_remboursement(self):
        for rec in self:
            rec.montant_rembourse = sum(rec.echeance_ids.filtered(
                lambda e: e.state == 'paye').mapped('montant'))
            rec.solde_restant = rec.montant - rec.montant_rembourse \
                if rec.state != 'annule' else 0.0

    @api.constrains('montant', 'nb_echeances')
    def _check_pret(self):
        for rec in self:
            if rec.montant <= 0:
                raise ValidationError(_("Le montant doit être positif."))
            if rec.nb_echeances < 1:
                raise ValidationError(_("Au moins une échéance."))
            if rec.type_pret == 'avance' and rec.nb_echeances > 12:
                raise ValidationError(_(
                    "Une avance sur salaire se rembourse en 12 échéances "
                    "au plus ; utilisez un prêt."))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if rec.name == '/':
                rec.name = self.env['ir.sequence'].with_company(
                    rec.company_id).next_by_code('rh.pret') or '/'
        return records

    def write(self, vals):
        figes = {'montant', 'nb_echeances', 'date_premiere_echeance',
                 'employee_id', 'type_pret'}
        if figes & set(vals) and self.filtered(
                lambda p: p.state != 'brouillon'):
            raise UserError(_("Un prêt confirmé ne peut plus être modifié."))
        return super().write(vals)

    def unlink(self):
        if not self.env.su:
            raise UserError(_("Un prêt ne peut pas être supprimé : "
                              "annulez-le."))
        return super().unlink()

    def _generer_echeancier(self):
        """Échéances égales arrondies à l'unité ; la dernière ajuste."""
        for rec in self:
            rec.echeance_ids.sudo().unlink()
            mensualite = rec.currency_id.round(rec.montant / rec.nb_echeances)
            premier = rec.date_premiere_echeance.replace(day=1)
            vals = []
            for i in range(rec.nb_echeances):
                montant = mensualite if i < rec.nb_echeances - 1 \
                    else rec.montant - mensualite * (rec.nb_echeances - 1)
                vals.append({'pret_id': rec.id, 'numero': i + 1,
                             'date': premier + relativedelta(months=i),
                             'montant': montant})
            self.env['rh.echeance.pret'].create(vals)

    def action_confirmer(self):
        for rec in self:
            if rec.state != 'brouillon':
                raise UserError(_("Prêt déjà confirmé."))
            rec._generer_echeancier()
            rec.state = 'en_cours'

    def action_annuler(self):
        for rec in self:
            if rec.echeance_ids.filtered(lambda e: e.state == 'paye'):
                raise UserError(_(
                    "Des échéances du prêt %s ont déjà été retenues : il ne "
                    "peut plus être annulé.", rec.name))
            rec.state = 'annule'

    def _maj_etat(self):
        for rec in self.filtered(lambda p: p.state in ('en_cours', 'solde')):
            rec.state = 'solde' if all(
                e.state == 'paye' for e in rec.echeance_ids) else 'en_cours'


class RhEcheancePret(models.Model):
    _name = 'rh.echeance.pret'
    _description = 'Échéance de prêt'
    _order = 'pret_id, numero'

    pret_id = fields.Many2one('rh.pret', required=True, ondelete='cascade',
                              index=True)
    employee_id = fields.Many2one(related='pret_id.employee_id', store=True)
    company_id = fields.Many2one(related='pret_id.company_id', store=True)
    currency_id = fields.Many2one(related='pret_id.currency_id')
    numero = fields.Integer(string='N°')
    date = fields.Date(string='Mois', required=True, index=True)
    montant = fields.Monetary(string='Montant')
    state = fields.Selection([('a_payer', 'À retenir'), ('paye', 'Retenue')],
                             string='État', default='a_payer', required=True)
    bulletin_id = fields.Many2one('rh.bulletin.paie', string='Bulletin',
                                  readonly=True)
