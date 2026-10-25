from odoo import _, fields, models
from odoo.exceptions import UserError

from ..models.rh_contrat import MOTIFS_FIN


class RhWizardFinContrat(models.TransientModel):
    """Résiliation d'un contrat ou rupture de la période d'essai.

    La procédure complète de sortie (préavis, solde de tout compte,
    certificat de travail) est gérée par le module de sortie.
    """

    _name = 'rh.wizard.fin.contrat'
    _description = 'Fin de contrat'

    contrat_id = fields.Many2one('rh.contrat', required=True, readonly=True)
    etat_contrat = fields.Selection(related='contrat_id.state')
    motif_fin = fields.Selection(MOTIFS_FIN, string='Motif', required=True)
    date_fin = fields.Date(string='Date de fin effective', required=True,
                           default=fields.Date.context_today)
    note = fields.Text(string='Commentaire')

    def action_valider(self):
        self.ensure_one()
        if self.motif_fin == 'rupture_essai' and \
                self.contrat_id.state != 'essai':
            raise UserError(_("Le contrat n'est pas en période d'essai."))
        self.contrat_id._terminer(self.motif_fin, self.date_fin, self.note)
        self.contrat_id.message_post(body=_(
            "Fin du contrat au %(date)s – motif : %(motif)s.",
            date=self.date_fin,
            motif=dict(MOTIFS_FIN).get(self.motif_fin)))
        return {'type': 'ir.actions.act_window_close'}
