from odoo import _, api, fields, models
from odoo.exceptions import UserError

# Modèles dont les demandes peuvent être refusées par cet assistant ;
# chacun expose une méthode _refuser(motif) qui contrôle les droits.
MODELES_REFUSABLES = ('rh.conge', 'rh.heure.sup')


class RhWizardRefus(models.TransientModel):
    _name = 'rh.wizard.refus'
    _description = 'Motif de refus'

    res_model = fields.Char(required=True, readonly=True)
    res_ids = fields.Char(required=True, readonly=True)
    motif = fields.Text(string='Motif du refus', required=True)

    @api.model
    def _ouvrir(self, records):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Motif du refus'),
            'res_model': self._name,
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_res_model': records._name,
                        'default_res_ids': ','.join(map(str, records.ids))},
        }

    def action_valider(self):
        self.ensure_one()
        if self.res_model not in MODELES_REFUSABLES:
            raise UserError(_("Modèle non pris en charge."))
        ids = [int(i) for i in self.res_ids.split(',') if i]
        self.env[self.res_model].browse(ids)._refuser(self.motif)
        return {'type': 'ir.actions.act_window_close'}
