from odoo import _, api, fields, models
from odoo.exceptions import UserError

TYPES_CHANGEMENT = [
    ('embauche', 'Embauche'),
    ('poste', 'Changement de poste'),
    ('departement', 'Changement de département'),
    ('categorie', 'Changement de catégorie'),
    ('salaire', 'Changement de salaire'),
]


class RhHistoriquePoste(models.Model):
    """Historique de carrière, alimenté automatiquement.

    Les lignes sont créées par le système (sudo) et ne sont jamais
    modifiées ni supprimées : c'est une piste d'audit.
    """

    _name = 'rh.historique.poste'
    _description = 'Historique des postes'
    _order = 'date desc, id desc'

    employee_id = fields.Many2one(
        'hr.employee', string='Employé', required=True, index=True,
        ondelete='restrict')
    company_id = fields.Many2one(
        related='employee_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    date = fields.Date(string='Date', required=True, index=True)
    type_changement = fields.Selection(
        TYPES_CHANGEMENT, string='Type', required=True, index=True)
    ancien_poste_id = fields.Many2one('rh.poste', string='Ancien poste')
    nouveau_poste_id = fields.Many2one('rh.poste', string='Nouveau poste')
    ancien_department_id = fields.Many2one(
        'hr.department', string='Ancien département')
    nouveau_department_id = fields.Many2one(
        'hr.department', string='Nouveau département')
    ancienne_categorie_id = fields.Many2one(
        'rh.categorie', string='Ancienne catégorie')
    nouvelle_categorie_id = fields.Many2one(
        'rh.categorie', string='Nouvelle catégorie')
    ancien_salaire = fields.Monetary(
        string='Ancien salaire', groups='rh_burkina.group_rh_salaire')
    nouveau_salaire = fields.Monetary(
        string='Nouveau salaire', groups='rh_burkina.group_rh_salaire')
    motif = fields.Char(string='Motif / référence')
    auteur_id = fields.Many2one(
        'res.users', string='Modifié par', default=lambda self: self.env.user,
        readonly=True)
    description = fields.Char(
        string='Changement', compute='_compute_description')

    @api.depends('type_changement', 'nouveau_poste_id',
                 'nouveau_department_id', 'nouvelle_categorie_id')
    def _compute_description(self):
        for rec in self:
            if rec.type_changement == 'poste':
                rec.description = '%s → %s' % (
                    rec.ancien_poste_id.name or '—',
                    rec.nouveau_poste_id.name or '—')
            elif rec.type_changement == 'departement':
                rec.description = '%s → %s' % (
                    rec.ancien_department_id.name or '—',
                    rec.nouveau_department_id.name or '—')
            elif rec.type_changement == 'categorie':
                rec.description = '%s → %s' % (
                    rec.ancienne_categorie_id.name or '—',
                    rec.nouvelle_categorie_id.name or '—')
            elif rec.type_changement == 'salaire':
                rec.description = _('Révision de la rémunération')
            else:
                rec.description = rec.nouveau_poste_id.name \
                    or _('Entrée dans l’entreprise')

    def write(self, vals):
        if not self.env.su:
            raise UserError(_("L'historique des postes ne peut pas être "
                              "modifié."))
        return super().write(vals)

    def unlink(self):
        if not self.env.su:
            raise UserError(_("L'historique des postes ne peut pas être "
                              "supprimé."))
        return super().unlink()
