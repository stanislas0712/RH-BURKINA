# -*- coding: utf-8 -*-
from odoo import models, fields, api


class RhBulletinPaie(models.Model):
    _name = 'rh.bulletin.paie'
    _description = 'Bulletin de Paie'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_bulletin desc'

    employe_id = fields.Many2one(
        'rh.employe', string='Employé', required=True,
        ondelete='cascade', tracking=True
    )
    paie_id = fields.Many2one('rh.paie', string='Lot de Paie', ondelete='cascade')
    reference = fields.Char(
        string='Référence', required=True, copy=False,
        readonly=True, default='Nouveau'
    )
    date_bulletin = fields.Date(
        string='Date du Bulletin', required=True,
        default=fields.Date.today, tracking=True
    )
    periode_debut = fields.Date(string='Période début')
    periode_fin = fields.Date(string='Période fin')

    # ── Salaires & Base ──────────────────────────────────────────────
    salaire_base = fields.Float(
        string='Salaire de Base (FCFA)', digits=(16, 0),
        tracking=True,
        help='Récupéré automatiquement du dossier employé si vide'
    )

    # ── Lignes détaillées ────────────────────────────────────────────
    ligne_ids = fields.One2many(
        'rh.ligne.bulletin', 'bulletin_id', string='Lignes de Paie'
    )

    # ── Totaux calculés ──────────────────────────────────────────────
    total_revenus = fields.Float(
        string='Total Revenus Bruts', digits=(16, 0),
        compute='_compute_totaux', store=True
    )
    total_retenues_sal = fields.Float(
        string='Total Retenues Salariales', digits=(16, 0),
        compute='_compute_totaux', store=True
    )
    total_charges_pat = fields.Float(
        string='Total Charges Patronales', digits=(16, 0),
        compute='_compute_totaux', store=True
    )
    net_a_payer = fields.Float(
        string='Net à Payer (FCFA)', digits=(16, 0),
        compute='_compute_totaux', store=True
    )

    # ── Détail fiscal ────────────────────────────────────────────────
    cnss_salarie = fields.Float(string='CNSS Salarié', digits=(16, 0))
    cnss_patronal = fields.Float(string='CNSS Patronal', digits=(16, 0))
    iuts = fields.Float(string='IUTS', digits=(16, 0))

    statut = fields.Selection([
        ('brouillon', 'Brouillon'),
        ('calcule', 'Calculé'),
        ('valide', 'Validé'),
        ('paye', 'Payé'),
    ], string='Statut', default='brouillon', tracking=True)
    notes = fields.Text(string='Notes')

    @api.depends('ligne_ids.montant', 'ligne_ids.categorie')
    def _compute_totaux(self):
        for rec in self:
            revenus = sum(
                l.montant for l in rec.ligne_ids if l.categorie == 'revenu'
            )
            retenues = sum(
                l.montant for l in rec.ligne_ids if l.categorie == 'retenue_sal'
            )
            charges = sum(
                l.montant for l in rec.ligne_ids if l.categorie == 'charge_pat'
            )
            rec.total_revenus = revenus
            rec.total_retenues_sal = retenues
            rec.total_charges_pat = charges
            rec.net_a_payer = revenus - retenues

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', 'Nouveau') == 'Nouveau':
                vals['reference'] = (
                    self.env['ir.sequence'].next_by_code('rh.bulletin.paie')
                    or 'BUL-0001'
                )
        return super().create(vals_list)

    def action_calculer(self):
        """Calcul automatique : salaire + primes + CNSS + IUTS + retenues."""
        for rec in self:
            rec.ligne_ids.unlink()
            lignes = []
            seq = 10

            # 1. Salaire de base
            salaire = rec.salaire_base or rec.employe_id.salaire_base or 0.0
            if not rec.salaire_base:
                rec.salaire_base = salaire

            lignes.append({
                'sequence': seq, 'code': 'SB',
                'libelle': 'Salaire de Base',
                'categorie': 'revenu',
                'base': salaire, 'taux': 0, 'montant': salaire,
                'is_imposable': True,
            })
            seq += 10

            # 2. Primes actives de l'employé
            salaire_brut = salaire
            for prime in rec.employe_id.prime_ids.filtered(lambda p: p.active):
                lignes.append({
                    'sequence': seq, 'code': prime.type_prime.code or 'PRM',
                    'libelle': prime.name,
                    'categorie': 'revenu',
                    'base': 0, 'taux': 0, 'montant': prime.montant,
                    'is_imposable': prime.type_prime.est_imposable if prime.type_prime else True,
                })
                salaire_brut += prime.montant
                seq += 10

            # 3. CNSS salarié (5.5% plafonné)
            cnss_config = self.env['rh.cnss'].search(
                [('active', '=', True)], limit=1, order='date_debut desc'
            )
            taux_cnss_sal = cnss_config.taux_cnss_salarie / 100 if cnss_config else 0.055
            taux_cnss_pat = cnss_config.taux_cnss_patronal / 100 if cnss_config else 0.16
            plafond = cnss_config.plafond_mensuel if cnss_config else 1500000.0

            base_cnss = min(salaire_brut, plafond)
            cnss_sal = round(base_cnss * taux_cnss_sal)
            cnss_pat = round(base_cnss * taux_cnss_pat)

            lignes.append({
                'sequence': seq, 'code': 'CNSS',
                'libelle': f'CNSS Salarié ({cnss_config.taux_cnss_salarie if cnss_config else 5.5}%)',
                'categorie': 'retenue_sal',
                'base': base_cnss, 'taux': taux_cnss_sal * 100, 'montant': cnss_sal,
                'is_imposable': False,
            })
            seq += 10

            lignes.append({
                'sequence': seq, 'code': 'CNSS_PAT',
                'libelle': f'CNSS Patronal ({cnss_config.taux_cnss_patronal if cnss_config else 16}%)',
                'categorie': 'charge_pat',
                'base': base_cnss, 'taux': taux_cnss_pat * 100, 'montant': cnss_pat,
                'is_imposable': False,
            })
            seq += 10

            # 4. IUTS — sur salaire brut imposable - CNSS salarié
            brut_imposable = sum(
                l['montant'] for l in lignes
                if l['categorie'] == 'revenu' and l.get('is_imposable')
            )
            base_iuts = max(brut_imposable - cnss_sal, 0)
            iuts = self.env['rh.iuts'].calculer_iuts(base_iuts) if base_iuts else 0.0
            iuts = round(iuts)

            if iuts > 0:
                lignes.append({
                    'sequence': seq, 'code': 'IUTS',
                    'libelle': 'IUTS (Impôt sur Traitements et Salaires)',
                    'categorie': 'retenue_sal',
                    'base': base_iuts, 'taux': 0, 'montant': iuts,
                    'is_imposable': False,
                })
                seq += 10

            # 5. Autres retenues actives de l'employé
            for retenue in rec.employe_id.retenue_ids.filtered(lambda r: r.active):
                lignes.append({
                    'sequence': seq, 'code': retenue.type_retenue.code or 'RET',
                    'libelle': retenue.name,
                    'categorie': 'retenue_sal',
                    'base': 0, 'taux': 0, 'montant': retenue.montant,
                    'is_imposable': False,
                })
                seq += 10

            # Création des lignes
            for vals in lignes:
                vals['bulletin_id'] = rec.id
                self.env['rh.ligne.bulletin'].create(vals)

            rec.cnss_salarie = cnss_sal
            rec.cnss_patronal = cnss_pat
            rec.iuts = iuts
            rec.statut = 'calcule'

    def action_valider(self):
        self.write({'statut': 'valide'})

    def action_payer(self):
        self.write({'statut': 'paye'})

    def action_reinitialiser(self):
        self.write({'statut': 'brouillon'})
        self.ligne_ids.unlink()
