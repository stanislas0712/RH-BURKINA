from odoo import fields, models

NIVEAUX_ETUDE = [
    ('cep', 'CEP'),
    ('bepc', 'BEPC'),
    ('cap', 'CAP / BEP'),
    ('bac', 'Baccalauréat'),
    ('bac2', 'Bac + 2 (BTS, DUT, DEUG)'),
    ('licence', 'Licence'),
    ('master', 'Master / Ingénieur'),
    ('doctorat', 'Doctorat'),
    ('autre', 'Autre'),
]


class RhDiplome(models.Model):
    _name = 'rh.diplome'
    _description = 'Diplôme'
    _order = 'date_obtention desc, id desc'
    _check_company_auto = True

    employee_id = fields.Many2one(
        'hr.employee', string='Employé', required=True, index=True,
        ondelete='restrict', check_company=True)
    company_id = fields.Many2one(
        related='employee_id.company_id', store=True, index=True)
    name = fields.Char(string='Intitulé', required=True)
    niveau = fields.Selection(NIVEAUX_ETUDE, string='Niveau')
    domaine = fields.Char(string='Domaine / spécialité')
    etablissement = fields.Char(string='Établissement')
    date_obtention = fields.Date(string="Date d'obtention")
    mention = fields.Selection(
        [('passable', 'Passable'), ('assez_bien', 'Assez bien'),
         ('bien', 'Bien'), ('tres_bien', 'Très bien'),
         ('excellent', 'Excellent')], string='Mention')
    fichier = fields.Binary(string='Copie', attachment=True)
    nom_fichier = fields.Char(string='Nom du fichier')
    active = fields.Boolean(default=True)
