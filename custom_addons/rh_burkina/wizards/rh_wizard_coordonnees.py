from odoo import _, api, fields, models
from odoo.exceptions import AccessError

from ..models.rh_contact_urgence import LIENS_PARENTE

# Seuls champs du dossier que l'employé peut modifier lui-même.
CHAMPS_COORDONNEES = [
    'private_phone', 'mobile_phone', 'private_email',
    'private_street', 'private_street2', 'private_city', 'private_zip',
    'private_country_id',
]


class RhWizardCoordonnees(models.TransientModel):
    """Mise à jour par l'employé de ses coordonnées et contacts d'urgence.

    L'employé n'a aucun droit d'écriture sur sa fiche : cet assistant
    vérifie l'identité puis n'écrit (en sudo) que la liste blanche
    CHAMPS_COORDONNEES et ses contacts d'urgence.
    """

    _name = 'rh.wizard.coordonnees'
    _description = 'Modification des coordonnées'

    employee_id = fields.Many2one('hr.employee', required=True,
                                  readonly=True)
    private_phone = fields.Char(string='Téléphone personnel')
    mobile_phone = fields.Char(string='Téléphone mobile')
    private_email = fields.Char(string='Email personnel')
    private_street = fields.Char(string='Adresse')
    private_street2 = fields.Char(string='Complément')
    private_city = fields.Char(string='Ville')
    private_zip = fields.Char(string='Code postal')
    private_country_id = fields.Many2one('res.country', string='Pays')
    contact_ids = fields.One2many(
        'rh.wizard.coordonnees.contact', 'wizard_id',
        string="Contacts d'urgence")

    @api.model
    def _verifier_droit(self, employee):
        user = self.env.user
        est_rh = user.has_group('rh_burkina.group_rh_gestionnaire')
        if not est_rh and employee.sudo().user_id != user:
            raise AccessError(_(
                "Vous ne pouvez modifier que vos propres coordonnées."))

    @api.model
    def _valeurs_initiales(self, employee):
        self._verifier_droit(employee)
        emp = employee.sudo()
        vals = {'employee_id': emp.id}
        for fname in CHAMPS_COORDONNEES:
            value = emp[fname]
            vals[fname] = value.id if isinstance(value, models.BaseModel) \
                else value
        vals['contact_ids'] = [(0, 0, {
            'contact_id': c.id, 'name': c.name,
            'lien_parente': c.lien_parente, 'telephone': c.telephone,
            'telephone2': c.telephone2, 'adresse': c.adresse,
        }) for c in emp.contact_urgence_ids]
        return vals

    def action_valider(self):
        self.ensure_one()
        self._verifier_droit(self.employee_id)
        emp = self.employee_id.sudo()
        vals = {}
        for fname in CHAMPS_COORDONNEES:
            value = self[fname]
            value = value.id if isinstance(value, models.BaseModel) else value
            ancien = emp[fname]
            ancien = ancien.id if isinstance(ancien, models.BaseModel) \
                else ancien
            if (value or False) != (ancien or False):
                vals[fname] = value
        if vals:
            emp.write(vals)

        Contact = self.env['rh.contact.urgence'].sudo()
        gardes = Contact
        for ligne in self.contact_ids:
            data = {
                'name': ligne.name, 'lien_parente': ligne.lien_parente,
                'telephone': ligne.telephone, 'telephone2': ligne.telephone2,
                'adresse': ligne.adresse,
            }
            if ligne.contact_id and ligne.contact_id.employee_id == emp:
                ligne.contact_id.sudo().write(data)
                gardes |= ligne.contact_id.sudo()
            else:
                gardes |= Contact.create(dict(data, employee_id=emp.id))
        # Contacts retirés : archivés, jamais supprimés
        (emp.contact_urgence_ids - gardes).write({'active': False})

        emp.message_post(body=_(
            "Coordonnées et contacts d'urgence mis à jour par %s.",
            self.env.user.name))
        return {'type': 'ir.actions.act_window_close'}


class RhWizardCoordonneesContact(models.TransientModel):
    _name = 'rh.wizard.coordonnees.contact'
    _description = "Contact d'urgence (assistant)"

    wizard_id = fields.Many2one('rh.wizard.coordonnees', required=True,
                                ondelete='cascade')
    contact_id = fields.Many2one('rh.contact.urgence')
    name = fields.Char(string='Nom', required=True)
    lien_parente = fields.Selection(LIENS_PARENTE, string='Lien de parenté',
                                    required=True)
    telephone = fields.Char(string='Téléphone', required=True)
    telephone2 = fields.Char(string='Autre téléphone')
    adresse = fields.Char(string='Adresse')
