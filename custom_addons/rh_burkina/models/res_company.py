import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

# Codes des séquences RH ; les modèles de séquence sont définis
# dans data/ir_sequence_data.xml (rattachés à la société principale).
RH_SEQUENCE_CODES = [
    'rh.employe',
    'rh.recrutement',
    'rh.candidat',
    'rh.contrat',
    'rh.conge',
    'rh.bulletin.paie',
    'rh.paie',
    'rh.sanction',
    'rh.pret',
    'rh.sortie',
]


class ResCompany(models.Model):
    _inherit = 'res.company'

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        companies._rh_create_sequences()
        return companies

    def _rh_create_sequences(self):
        """Duplique les séquences RH pour chaque société qui n'en a pas.

        Chaque société dispose de sa propre numérotation (EMP-, CTR-, …).
        """
        Sequence = self.env['ir.sequence'].sudo()
        for code in RH_SEQUENCE_CODES:
            template = Sequence.search(
                [('code', '=', code)], order='company_id, id', limit=1)
            if not template:
                _logger.warning("Séquence modèle RH introuvable : %s", code)
                continue
            for company in self:
                exists = Sequence.search_count([
                    ('code', '=', code), ('company_id', '=', company.id)])
                if not exists:
                    template.copy({
                        'company_id': company.id,
                        'number_next': 1,
                        'name': template.name,
                    })
