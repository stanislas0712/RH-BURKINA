# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class RhDiplome(models.Model):
    _name = 'rh.diplome'
    _description = 'Diplômes et Certifications'
    _order = 'date_obtention desc'

    employe_id = fields.Many2one('rh.employe', string='Employé',
                                  required=True, ondelete='cascade')
    type_diplome = fields.Selection([
        ('bepc', 'BEPC / Brevet'),
        ('bac', 'Baccalauréat'),
        ('bts', 'BTS / DUT'),
        ('licence', 'Licence / Bachelor'),
        ('master', 'Master / DEA / DESS'),
        ('doctorat', 'Doctorat / PhD'),
        ('ingenieur', 'Diplôme d\'Ingénieur'),
        ('certification', 'Certification Professionnelle'),
        ('formation', 'Attestation de Formation'),
        ('autre', 'Autre'),
    ], string='Type', required=True)
    intitule = fields.Char(string='Intitulé du Diplôme', required=True)
    specialite = fields.Char(string='Spécialité / Filière')
    etablissement = fields.Char(string='Établissement', required=True)
    pays_id = fields.Many2one('res.country', string='Pays d\'Obtention')
    date_obtention = fields.Date(string='Date d\'Obtention')
    mention = fields.Selection([
        ('passable', 'Passable'),
        ('assez_bien', 'Assez Bien'),
        ('bien', 'Bien'),
        ('tres_bien', 'Très Bien'),
        ('excellent', 'Excellent / Félicitations'),
    ], string='Mention')
    numero_diplome = fields.Char(string='N° du Diplôme')
    date_expiration = fields.Date(string='Date d\'Expiration',
                                   help='Pour les certifications renouvelables')
    expire = fields.Boolean(string='Expiré', compute='_compute_expire', store=True)
    piece_jointe = fields.Binary(string='Copie Scannée', attachment=True)
    nom_fichier = fields.Char(string='Nom du Fichier')
    notes = fields.Text(string='Notes')

    @api.depends('date_expiration')
    def _compute_expire(self):
        from datetime import date
        today = date.today()
        for rec in self:
            rec.expire = bool(rec.date_expiration and rec.date_expiration < today)

    @api.constrains('date_obtention')
    def _check_date(self):
        from datetime import date
        for rec in self:
            if rec.date_obtention and rec.date_obtention > date.today():
                raise ValidationError(
                    'La date d\'obtention ne peut pas être dans le futur.')