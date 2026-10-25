import base64
import io
from collections import OrderedDict, defaultdict

import xlsxwriter

from odoo import _, api, fields, models
from odoo.exceptions import UserError

ETATS_EXPORTES = ('valide', 'paye')
OPERATEURS = {'orange_money': 'Orange Money', 'moov_money': 'Moov Money'}


class _ClasseurXlsx:
    """Petit utilitaire d'écriture de classeurs Excel."""

    def __init__(self, libelle_total='TOTAL'):
        self.libelle_total = libelle_total
        self.buffer = io.BytesIO()
        self.wb = xlsxwriter.Workbook(self.buffer, {'in_memory': True})
        self.f_titre = self.wb.add_format({'bold': True, 'font_size': 13})
        self.f_entete = self.wb.add_format({
            'bold': True, 'bg_color': '#D9E1F2', 'border': 1,
            'text_wrap': True, 'valign': 'vcenter'})
        self.f_texte = self.wb.add_format({'border': 1})
        self.f_montant = self.wb.add_format({'border': 1,
                                             'num_format': '#,##0'})
        self.f_total = self.wb.add_format({'bold': True, 'border': 1,
                                           'num_format': '#,##0',
                                           'bg_color': '#F2F2F2'})

    def feuille(self, nom, titre, entetes, lignes, colonnes_montant,
                sous_titre=None):
        ws = self.wb.add_worksheet(nom[:31].replace('/', '-'))
        ws.write(0, 0, titre, self.f_titre)
        if sous_titre:
            ws.write(1, 0, sous_titre)
        ligne0 = 3
        for col, entete in enumerate(entetes):
            ws.write(ligne0, col, entete, self.f_entete)
            ws.set_column(col, col, 14 if col in colonnes_montant else 24)
        for i, valeurs in enumerate(lignes, start=ligne0 + 1):
            for col, valeur in enumerate(valeurs):
                fmt = self.f_montant if col in colonnes_montant \
                    else self.f_texte
                ws.write(i, col, valeur if valeur is not None else '', fmt)
        total = ligne0 + 1 + len(lignes)
        ws.write(total, 0, self.libelle_total, self.f_total)
        for col in colonnes_montant:
            ws.write(total, col, sum((l[col] or 0) for l in lignes),
                     self.f_total)
        ws.freeze_panes(ligne0 + 1, 0)
        return ws

    def contenu(self):
        self.wb.close()
        return base64.b64encode(self.buffer.getvalue())


class RhWizardExportPaiement(models.TransientModel):
    """Fichier de virement par banque ou liste de paiement mobile money."""

    _name = 'rh.wizard.export.paiement'
    _description = 'Export des paiements'

    paie_id = fields.Many2one('rh.paie', string='Période', required=True)
    mode = fields.Selection(
        [('virement', 'Virements bancaires'),
         ('mobile', 'Mobile money'), ('especes', 'Espèces')],
        string='Mode', required=True, default='virement')
    banque_id = fields.Many2one(
        'res.bank', string='Banque',
        help="Vide : un onglet par banque.")
    fichier = fields.Binary(string='Fichier', readonly=True)
    nom_fichier = fields.Char(readonly=True)

    def _bulletins(self):
        bulletins = self.paie_id.bulletin_ids.filtered(
            lambda b: b.state in ETATS_EXPORTES)
        if self.mode == 'virement':
            bulletins = bulletins.filtered(
                lambda b: b.mode_paiement == 'virement')
            if self.banque_id:
                bulletins = bulletins.filtered(
                    lambda b: b.banque_id == self.banque_id)
        elif self.mode == 'mobile':
            bulletins = bulletins.filtered(
                lambda b: b.mode_paiement in OPERATEURS)
        else:
            bulletins = bulletins.filtered(
                lambda b: b.mode_paiement == 'especes')
        return bulletins.sorted(lambda b: b.employee_id.name or '')

    def action_generer(self):
        self.ensure_one()
        bulletins = self._bulletins()
        if not bulletins:
            raise UserError(_("Aucun bulletin validé ne correspond à ce mode "
                              "de paiement."))
        groupes = OrderedDict()
        for b in bulletins:
            if self.mode == 'virement':
                cle = b.banque_id.name or _('Banque non renseignée')
            elif self.mode == 'mobile':
                cle = OPERATEURS[b.mode_paiement]
            else:
                cle = _('Espèces')
            groupes.setdefault(cle, []).append(b)
        classeur = _ClasseurXlsx(_('TOTAL'))
        periode = self.paie_id.display_name
        for cle, liste in groupes.items():
            if self.mode == 'virement':
                entetes = [_('Matricule'), _('Bénéficiaire'), _('Banque'),
                           _('N° de compte / RIB'), _('Montant'),
                           _('Libellé')]
                lignes = [[b.employee_id.matricule, b.employee_id.name,
                           b.banque_id.name, b.numero_compte, b.net_a_payer,
                           _('Salaire %s', self.paie_id.libelle)]
                          for b in liste]
            elif self.mode == 'mobile':
                entetes = [_('Matricule'), _('Bénéficiaire'), _('Opérateur'),
                           _('Numéro'), _('Montant')]
                lignes = [[b.employee_id.matricule, b.employee_id.name, cle,
                           b.numero_mobile_money, b.net_a_payer]
                          for b in liste]
            else:
                entetes = [_('Matricule'), _('Bénéficiaire'), _('Montant'),
                           _('Émargement')]
                lignes = [[b.employee_id.matricule, b.employee_id.name,
                           b.net_a_payer, ''] for b in liste]
            colonnes = {entetes.index(_('Montant'))}
            classeur.feuille(cle, _('Paiement des salaires – %s', cle),
                             entetes, lignes, colonnes, sous_titre=periode)
        suffixe = {'virement': 'virements', 'mobile': 'mobile_money',
                   'especes': 'especes'}[self.mode]
        if self.banque_id:
            suffixe += '_%s' % (self.banque_id.bic or self.banque_id.name)
        self.write({
            'fichier': classeur.contenu(),
            'nom_fichier': '%s_%s.xlsx' % (self.paie_id.name, suffixe),
        })
        return {
            'type': 'ir.actions.act_window', 'res_model': self._name,
            'res_id': self.id, 'view_mode': 'form', 'target': 'new',
        }


class RhWizardDeclaration(models.TransientModel):
    """États mensuels CNSS et IUTS, récapitulatif annuel des salaires.

    Format interne : le format exact des déclarations officielles est à
    vérifier auprès de la CNSS et de la DGI.
    """

    _name = 'rh.wizard.declaration'
    _description = 'Déclarations sociales et fiscales'

    type_etat = fields.Selection(
        [('cnss', 'État mensuel des cotisations sociales'),
         ('iuts', "État mensuel de l'IUTS"),
         ('annuel', 'Récapitulatif annuel des salaires')],
        string='État', required=True, default='cnss')
    paie_id = fields.Many2one('rh.paie', string='Période')
    annee = fields.Integer(string='Année',
                           default=lambda self: fields.Date.context_today(
                               self).year)
    company_id = fields.Many2one('res.company', required=True,
                                 default=lambda self: self.env.company)
    fichier = fields.Binary(readonly=True)
    nom_fichier = fields.Char(readonly=True)

    def _bulletins(self):
        Bulletin = self.env['rh.bulletin.paie']
        if self.type_etat == 'annuel':
            domain = [('company_id', '=', self.company_id.id),
                      ('state', 'in', ETATS_EXPORTES),
                      ('date_debut', '>=', '%s-01-01' % self.annee),
                      ('date_debut', '<=', '%s-12-31' % self.annee)]
        else:
            if not self.paie_id:
                raise UserError(_("Choisissez la période."))
            domain = [('paie_id', '=', self.paie_id.id),
                      ('state', 'in', ETATS_EXPORTES)]
        bulletins = Bulletin.search(domain)
        if not bulletins:
            raise UserError(_("Aucun bulletin validé sur la période "
                              "demandée."))
        return bulletins

    @staticmethod
    def _montant_ligne(bulletin, code):
        return sum(bulletin.ligne_ids.filtered(
            lambda l: l.code == code).mapped('montant'))

    def _etat_cnss(self, classeur, bulletins):
        branches = OrderedDict()
        for l in bulletins.ligne_ids.filtered(
                lambda l: l.code and l.code.startswith(('COT_SAL_',
                                                        'COT_PAT_'))):
            branches.setdefault(l.code, l.name)
        codes = list(branches)
        entetes = [_('Matricule'), _('Nom'), _('N° CNSS / CARFO'),
                   _('Régime'), _('Brut soumis'), _('Base plafonnée')] \
            + [branches[c] for c in codes] \
            + [_('Total salarial'), _('Total patronal'), _('Total')]
        lignes = []
        for b in bulletins.sorted(lambda b: b.employee_id.name or ''):
            emp = b.employee_id.sudo()
            lignes.append([emp.matricule, emp.name, emp.ssnid,
                           b.regime_social, b.brut_soumis, b.base_cotisation]
                          + [self._montant_ligne(b, c) for c in codes]
                          + [b.cotisation_salariale, b.charges_patronales,
                             b.cotisation_salariale + b.charges_patronales])
        colonnes = set(range(4, len(entetes)))
        classeur.feuille(_('Cotisations'),
                         _('État des cotisations sociales – %s',
                           self.paie_id.display_name),
                         entetes, lignes, colonnes,
                         sous_titre=self.company_id.name)

    def _etat_iuts(self, classeur, bulletins):
        entetes = [_('Matricule'), _('Nom'), _('N° IFU'), _('Brut imposable'),
                   _('Cotisations salariales'), _('Indemnités exonérées'),
                   _('Abattement'), _('Base IUTS'), _('IUTS brut'),
                   _('Charges'), _('Réduction'), _('IUTS dû')]
        lignes = []
        for b in bulletins.sorted(lambda b: b.employee_id.name or ''):
            emp = b.employee_id.sudo()
            lignes.append([emp.matricule, emp.name, emp.numero_ifu,
                           b.brut_imposable, b.cotisation_salariale,
                           b.exonerations, b.abattement, b.base_iuts,
                           b.iuts_brut, b.nb_charges, b.reduction_iuts,
                           b.iuts])
        colonnes = {3, 4, 5, 6, 7, 8, 10, 11}
        classeur.feuille(_('IUTS'),
                         _("État de l'IUTS à reverser – %s",
                           self.paie_id.display_name),
                         entetes, lignes, colonnes,
                         sous_titre=self.company_id.name)

    def _etat_annuel(self, classeur, bulletins):
        cumul = defaultdict(lambda: defaultdict(float))
        employes = OrderedDict()
        for b in bulletins.sorted(lambda b: (b.employee_id.name or '',
                                             b.date_debut)):
            emp = b.employee_id.sudo()
            employes[emp.id] = emp
            c = cumul[emp.id]
            c['mois'] += 1
            for champ in ('brut', 'brut_soumis', 'cotisation_salariale',
                          'charges_patronales', 'brut_imposable', 'iuts',
                          'total_retenues', 'net_a_payer'):
                c[champ] += b[champ]
        entetes = [_('Matricule'), _('Nom'), _('N° CNSS'), _('N° IFU'),
                   _('Mois payés'), _('Brut'), _('Brut soumis'),
                   _('Cotisations salariales'), _('Charges patronales'),
                   _('Brut imposable'), _('IUTS'), _('Autres retenues'),
                   _('Net payé')]
        lignes = []
        for emp_id, emp in employes.items():
            c = cumul[emp_id]
            lignes.append([emp.matricule, emp.name, emp.ssnid,
                           emp.numero_ifu, c['mois'], c['brut'],
                           c['brut_soumis'], c['cotisation_salariale'],
                           c['charges_patronales'], c['brut_imposable'],
                           c['iuts'], c['total_retenues'], c['net_a_payer']])
        classeur.feuille(str(self.annee),
                         _('Récapitulatif annuel des salaires %s', self.annee),
                         entetes, lignes, set(range(5, 13)),
                         sous_titre=self.company_id.name)

    def action_generer(self):
        self.ensure_one()
        bulletins = self._bulletins()
        classeur = _ClasseurXlsx(_('TOTAL'))
        getattr(self, '_etat_%s' % self.type_etat)(classeur, bulletins)
        reference = str(self.annee) if self.type_etat == 'annuel' \
            else self.paie_id.name
        self.write({'fichier': classeur.contenu(),
                    'nom_fichier': '%s_%s.xlsx' % (self.type_etat.upper(),
                                                   reference)})
        return {
            'type': 'ir.actions.act_window', 'res_model': self._name,
            'res_id': self.id, 'view_mode': 'form', 'target': 'new',
        }

    @api.onchange('type_etat')
    def _onchange_type_etat(self):
        if self.type_etat != 'annuel' and not self.paie_id:
            self.paie_id = self.env['rh.paie'].search(
                [('company_id', '=', self.company_id.id)], limit=1)
