import calendar
from collections import defaultdict

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .hr_employee import MODES_PAIEMENT
from .rh_cnss import REGIMES_SOCIAUX

ETATS_BULLETIN = [
    ('brouillon', 'Brouillon'),
    ('calcule', 'Calculé'),
    ('valide', 'Validé'),
    ('paye', 'Payé'),
    ('annule', 'Annulé'),
]

CATEGORIES_LIGNE = [
    ('gain', 'Gain'),
    ('info', 'Information'),
    ('cotisation', 'Cotisation salariale'),
    ('impot', 'Impôt'),
    ('retenue', 'Retenue'),
    ('net', 'Net'),
    ('patronal', 'Charge patronale'),
]

# Statut des contrats pris en compte dans un mois de paie
ETATS_CONTRAT_PAYES = ('essai', 'actif', 'suspendu', 'resilie', 'expire')


class RhBulletinPaie(models.Model):
    """Bulletin de paie mensuel d'un employé."""

    _name = 'rh.bulletin.paie'
    _description = 'Bulletin de paie'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_debut desc, employee_id'
    _check_company_auto = True

    name = fields.Char(string='Référence', readonly=True, copy=False,
                       default='/', index=True)
    paie_id = fields.Many2one('rh.paie', string='Période de paie',
                              required=True, ondelete='restrict', index=True,
                              check_company=True)
    employee_id = fields.Many2one(
        'hr.employee', string='Employé', required=True, index=True,
        ondelete='restrict', check_company=True, tracking=True)
    contrat_id = fields.Many2one('rh.contrat', string='Contrat',
                                 readonly=True, check_company=True)
    company_id = fields.Many2one(related='paie_id.company_id', store=True,
                                 index=True)
    currency_id = fields.Many2one(related='paie_id.currency_id')
    date_debut = fields.Date(related='paie_id.date_debut', store=True)
    date_fin = fields.Date(related='paie_id.date_fin', store=True)
    state = fields.Selection(ETATS_BULLETIN, string='État',
                             default='brouillon', required=True,
                             tracking=True, copy=False, index=True)
    # Unicité « un bulletin actif par employé et par période » : vidé à
    # l'annulation pour permettre un nouveau bulletin.
    cle_unicite = fields.Char(copy=False, readonly=True)
    ligne_ids = fields.One2many('rh.ligne.bulletin', 'bulletin_id',
                                string='Lignes', readonly=True)
    erreur_calcul = fields.Text(string='Erreur de calcul', readonly=True,
                                copy=False)
    motif_annulation = fields.Char(string="Motif d'annulation",
                                   readonly=True, copy=False)

    # Données figées au calcul
    poste_id = fields.Many2one('rh.poste', string='Poste', readonly=True)
    categorie_id = fields.Many2one('rh.categorie', string='Catégorie',
                                   readonly=True)
    regime_social = fields.Selection(REGIMES_SOCIAUX, readonly=True)
    nb_charges = fields.Integer(string='Charges de famille', readonly=True)
    mode_paiement = fields.Selection(MODES_PAIEMENT, readonly=True,
                                     string='Mode de paiement')
    banque_id = fields.Many2one('res.bank', readonly=True, string='Banque')
    numero_compte = fields.Char(readonly=True, string='N° de compte')
    numero_mobile_money = fields.Char(readonly=True,
                                      string='N° mobile money')

    # Totaux (montants arrondis à l'unité)
    salaire_base = fields.Monetary(string='Salaire de base', readonly=True)
    jours_payes = fields.Float(string='Jours payés', readonly=True)
    brut = fields.Monetary(string='Salaire brut', readonly=True)
    brut_soumis = fields.Monetary(string='Brut soumis à cotisation',
                                  readonly=True)
    base_cotisation = fields.Monetary(string='Base de cotisation (plafonnée)',
                                      readonly=True)
    cotisation_salariale = fields.Monetary(readonly=True,
                                           string='Cotisations salariales')
    charges_patronales = fields.Monetary(readonly=True,
                                         string='Charges patronales')
    brut_imposable = fields.Monetary(readonly=True, string='Brut imposable')
    exonerations = fields.Monetary(readonly=True,
                                   string='Indemnités exonérées')
    abattement = fields.Monetary(readonly=True,
                                 string='Abattement frais professionnels')
    base_iuts = fields.Monetary(readonly=True, string='Base IUTS')
    iuts_brut = fields.Monetary(readonly=True, string='IUTS avant réduction')
    reduction_iuts = fields.Monetary(readonly=True,
                                     string='Réduction charges de famille')
    iuts = fields.Monetary(readonly=True, string='IUTS')
    total_retenues = fields.Monetary(readonly=True, string='Autres retenues')
    net_a_payer = fields.Monetary(readonly=True, string='Net à payer',
                                  tracking=True)
    cout_employeur = fields.Monetary(readonly=True, string='Coût employeur')

    _sql_constraints = [
        ('un_bulletin_par_periode', 'unique(cle_unicite)',
         'Un seul bulletin par employé et par période de paie.'),
    ]

    # ------------------------------------------------------------------
    # CRUD et verrouillage
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            rec.cle_unicite = '%s-%s' % (rec.employee_id.id, rec.paie_id.id)
            if rec.name == '/':
                rec.name = self.env['ir.sequence'].with_company(
                    rec.company_id).next_by_code('rh.bulletin.paie') or '/'
        records.paie_id._verifier_ouverte()
        return records

    def write(self, vals):
        champs_libres = {'message_main_attachment_id'}
        if not self.env.context.get('rh_paie_interne') and \
                set(vals) - champs_libres:
            bloques = self.filtered(
                lambda b: b.state not in ('brouillon', 'calcule'))
            if bloques:
                raise UserError(_(
                    "Le bulletin %s est verrouillé. Pour le corriger, "
                    "annulez-le puis établissez un nouveau bulletin.",
                    bloques[0].name))
            self.paie_id._verifier_ouverte()
        return super().write(vals)

    def unlink(self):
        if not self.env.su:
            raise UserError(_("Un bulletin ne peut pas être supprimé : "
                              "annulez-le."))
        return super().unlink()

    def _ecrire(self, vals):
        """Écriture interne (workflow, calcul) contournant le verrou."""
        return self.with_context(rh_paie_interne=True).write(vals)

    # ------------------------------------------------------------------
    # Collecte des éléments
    # ------------------------------------------------------------------
    def _contrats_periode(self):
        self.ensure_one()
        return self.env['rh.contrat'].sudo().search([
            ('employee_id', '=', self.employee_id.id),
            ('state', 'in', ETATS_CONTRAT_PAYES),
            ('date_debut', '<=', self.date_fin),
            '|', ('date_resiliation', '=', False),
            ('date_resiliation', '>=', self.date_debut),
            '|', ('date_fin', '=', False),
            ('date_fin', '>=', self.date_debut),
        ], order='date_debut')

    @staticmethod
    def _intersection(d1, f1, d2, f2):
        debut, fin = max(d1, d2), min(f1, f2)
        return (debut, fin) if debut <= fin else (None, None)

    def _taux_horaire(self, contrat):
        """Taux horaire de référence pour les heures supplémentaires."""
        if contrat.remuneration_type == 'horaire':
            return contrat.taux_horaire
        heures_mois = (contrat.heures_hebdo or 40.0) * 52.0 / 12.0
        return contrat.salaire_base / heures_mois if heures_mois else 0.0

    # ------------------------------------------------------------------
    # Moteur de calcul
    # ------------------------------------------------------------------
    def action_calculer(self):
        for rec in self:
            if rec.state not in ('brouillon', 'calcule'):
                raise UserError(_("Seul un bulletin brouillon ou calculé "
                                  "peut être recalculé."))
            rec.paie_id._verifier_ouverte()
            lignes, totaux = rec.sudo()._calculer()
            rec.ligne_ids.sudo().unlink()
            vals = dict(totaux, state='calcule', erreur_calcul=False,
                        ligne_ids=[(0, 0, l) for l in lignes])
            rec._ecrire(vals)
        return True

    def _calculer(self):
        """Calcule le bulletin et retourne (lignes, totaux).

        Ordre : base proratisée, ancienneté, heures sup., primes = brut ;
        cotisations ; IUTS ; retenues et prêts (quotité saisissable) ;
        net arrondi à l'unité. Aucune valeur légale n'est codée ici : tout
        provient des barèmes en vigueur à la fin de la période.
        """
        self.ensure_one()
        emp = self.employee_id
        cur = self.currency_id
        arrondi = cur.round
        date_ref = self.date_fin
        company = self.company_id
        config = self.env['rh.configuration']._get_en_vigueur(
            date_ref, company)
        contrats = self._contrats_periode()
        if not contrats:
            raise UserError(_("%s n'a aucun contrat sur la période.",
                              emp.name))
        contrat = contrats[-1]
        lignes = []
        seq = [0]

        def ligne(code, name, categorie, montant, base=0.0, taux=0.0,
                  quantite=0.0, imposable=False, soumis=False,
                  exoneration=False):
            seq[0] += 10
            lignes.append({
                'sequence': seq[0], 'code': code, 'name': name,
                'categorie': categorie, 'base': base, 'taux': taux,
                'quantite': quantite, 'montant': arrondi(montant),
                'imposable': imposable, 'soumis_cotisation': soumis,
                'exoneration_iuts': exoneration or False,
            })
            return lignes[-1]['montant']

        # 1. Salaire de base au prorata des jours sous contrat ---------------
        jours_mois = calendar.monthrange(date_ref.year, date_ref.month)[1]
        base_jours = config.jours_base_prorata
        salaire_base_total = 0.0
        jours_payes = 0
        presences = self.env['rh.presence'].sudo()
        for c in contrats:
            fin_c = min(filter(None, [c.date_resiliation, c.date_fin,
                                      self.date_fin]))
            debut, fin = self._intersection(c.date_debut, fin_c,
                                            self.date_debut, self.date_fin)
            if not debut:
                continue
            jours = (fin - debut).days + 1
            jours_payes += jours
            if c.remuneration_type == 'horaire':
                heures = sum(presences.search([
                    ('employee_id', '=', emp.id), ('date', '>=', debut),
                    ('date', '<=', fin)]).mapped('heures_travaillees'))
                montant = c.taux_horaire * heures
                ligne('BASE', _('Salaire (%s h)', round(heures, 2)), 'gain',
                      montant, base=c.taux_horaire, quantite=heures,
                      imposable=True, soumis=True)
            else:
                if jours >= jours_mois:
                    montant = c.salaire_base
                else:
                    montant = min(c.salaire_base * jours / base_jours,
                                  c.salaire_base)
                ligne('BASE', _('Salaire de base'), 'gain', montant,
                      base=c.salaire_base,
                      quantite=min(jours, base_jours) if jours < jours_mois
                      else base_jours, imposable=True, soumis=True)
            salaire_base_total += arrondi(montant)

        # Absences non rémunérées (jours calendaires × salaire / base)
        absences = self.env['rh.conge'].sudo().search([
            ('employee_id', '=', emp.id), ('state', '=', 'approuve'),
            ('paye', '=', False), ('date_debut', '<=', self.date_fin),
            ('date_fin', '>=', self.date_debut)])
        jours_absence = 0
        for a in absences:
            debut, fin = self._intersection(a.date_debut, a.date_fin,
                                            self.date_debut, self.date_fin)
            jours_absence += (fin - debut).days + 1
        if jours_absence and contrat.remuneration_type != 'horaire':
            retenue_abs = min(contrat.salaire_base * jours_absence / base_jours,
                              salaire_base_total)
            # ligne() renvoie le montant signé (négatif ici)
            salaire_base_total += ligne(
                'ABS', _('Absences non rémunérées'), 'gain', -retenue_abs,
                base=contrat.salaire_base, quantite=jours_absence,
                imposable=True, soumis=True)
            jours_payes = max(jours_payes - jours_absence, 0)
        salaire_base_total = max(salaire_base_total, 0.0)

        # 2. Prime d'ancienneté ----------------------------------------------
        if emp.date_embauche:
            annees = relativedelta(date_ref, emp.date_embauche).years
            taux_anc = config._get_taux_anciennete(annees)
            if taux_anc:
                ligne('ANC', _("Prime d'ancienneté (%s ans)", annees), 'gain',
                      salaire_base_total * taux_anc / 100.0,
                      base=salaire_base_total, taux=taux_anc,
                      imposable=True, soumis=True)

        # 3. Heures supplémentaires validées ---------------------------------
        heures_sup = self.env['rh.heure.sup'].sudo().search([
            ('employee_id', '=', emp.id), ('state', '=', 'valide'),
            ('date', '>=', self.date_debut), ('date', '<=', self.date_fin),
            '|', ('bulletin_id', '=', False), ('bulletin_id', '=', self.id)])
        if heures_sup:
            taux_h = self._taux_horaire(contrat)
            par_taux = defaultdict(float)
            for hs in heures_sup:
                for heures, taux in hs._calculer_repartition():
                    par_taux[taux] += heures
            for taux in sorted(par_taux):
                heures = par_taux[taux]
                ligne('HS', _('Heures supplémentaires majorées à %s %%', taux),
                      'gain', taux_h * heures * (1 + taux / 100.0),
                      base=taux_h, taux=taux, quantite=heures,
                      imposable=True, soumis=True)

        # 4. Primes et indemnités --------------------------------------------
        Prime = self.env['rh.prime'].sudo()
        primes = Prime.search(Prime._domaine_periode(
            emp, self.date_debut, self.date_fin))._filtrer_periode(
            self.date_debut, self.date_fin, self)
        for p in primes:
            t = p.type_prime_id
            ligne('PRIME_%s' % t.code, t.name, 'gain',
                  p._montant_pour(salaire_base_total),
                  base=salaire_base_total if t.mode_calcul == 'pourcentage'
                  else 0.0, taux=(p.taux or t.taux)
                  if t.mode_calcul == 'pourcentage' else 0.0,
                  imposable=t.imposable, soumis=t.soumis_cotisation,
                  exoneration=t.exoneration_iuts)

        gains = [l for l in lignes if l['categorie'] == 'gain']
        brut = sum(l['montant'] for l in gains)
        brut_soumis = sum(l['montant'] for l in gains
                          if l['soumis_cotisation'])
        brut_imposable = sum(l['montant'] for l in gains if l['imposable'])
        ligne('BRUT', _('Salaire brut'), 'info', brut)

        # 5. Cotisations sociales --------------------------------------------
        bareme = self.env['rh.cnss']._get_bareme(emp.regime_social, date_ref,
                                                 company)
        cot = bareme._calculer_cotisations(brut_soumis)
        for d in cot['detail']:
            if d['salarial']:
                ligne('COT_SAL_%s' % d['code'].upper(),
                      _('%(regime)s – %(branche)s (part salariale)',
                        regime=dict(REGIMES_SOCIAUX)[emp.regime_social]
                        .split(' ')[0], branche=d['name']),
                      'cotisation', d['salarial'], base=d['base'],
                      taux=d['taux_salarial'])
        cot_sal = cot['total_salarial']

        # 6. IUTS ------------------------------------------------------------
        iuts_bareme = self.env['rh.iuts']._get_en_vigueur(date_ref, company)
        assiettes = {'brut': brut, 'base': salaire_base_total}
        par_type = defaultdict(float)
        for l in gains:
            if l['imposable'] and l['exoneration_iuts']:
                par_type[l['exoneration_iuts']] += l['montant']
        exonerations = sum(
            iuts_bareme._get_exoneration(type_i, montant, assiettes)
            for type_i, montant in par_type.items())
        taux_abat = iuts_bareme._get_abattement(contrat.categorie_id.est_cadre)
        assiette_abat = salaire_base_total \
            if iuts_bareme.abattement_assiette == 'base' \
            else brut_imposable - cot_sal - exonerations
        abattement = arrondi(max(assiette_abat, 0.0) * taux_abat / 100.0)
        base_iuts = max(brut_imposable - cot_sal - exonerations - abattement,
                        0.0)
        res_iuts = iuts_bareme._calculer_iuts(base_iuts, emp.nb_charges_iuts)
        if res_iuts['impot_net']:
            ligne('IUTS', _('IUTS'), 'impot', res_iuts['impot_net'],
                  base=res_iuts['base'], taux=res_iuts['taux_reduction'])
        iuts = res_iuts['impot_net']

        # 7. Retenues, prêts et quotité saisissable ---------------------------
        net_avant_retenues = brut - cot_sal - iuts
        Retenue = self.env['rh.retenue'].sudo()
        retenues = Retenue.search(Retenue._domaine_periode(
            emp, self.date_debut, self.date_fin))._filtrer_periode(
            self.date_debut, self.date_fin, self)
        total_retenues = 0.0
        total_saisissable = 0.0
        for r in retenues:
            montant = ligne('RET_%s' % r.type_retenue_id.code,
                            r.type_retenue_id.name, 'retenue',
                            r._montant_pour(brut, salaire_base_total))
            total_retenues += montant
            if r.type_retenue_id.inclus_quotite:
                total_saisissable += montant
        echeances = self.env['rh.echeance.pret'].sudo().search([
            ('employee_id', '=', emp.id), ('pret_id.state', '=', 'en_cours'),
            ('date', '>=', self.date_debut), ('date', '<=', self.date_fin),
            '|', ('state', '=', 'a_payer'), ('bulletin_id', '=', self.id)])
        for e in echeances:
            libelle = _('Remboursement %(ref)s (%(n)s/%(total)s)',
                        ref=e.pret_id.name, n=e.numero,
                        total=e.pret_id.nb_echeances)
            montant = ligne('PRET', libelle, 'retenue', e.montant)
            total_retenues += montant
            total_saisissable += montant
        if total_saisissable:
            quotite = config._get_quotite_saisissable(
                max(net_avant_retenues, 0.0))
            if total_saisissable > quotite:
                raise UserError(_(
                    "%(emp)s : les retenues du mois (%(ret)s) dépassent la "
                    "quotité saisissable (%(q)s) calculée sur un net de "
                    "%(net)s. Réduisez ou étalez les retenues.",
                    emp=emp.name, ret=cur.format(total_saisissable),
                    q=cur.format(quotite), net=cur.format(net_avant_retenues)))

        net = arrondi(net_avant_retenues - total_retenues)
        if net < 0:
            raise UserError(_("%s : le net à payer serait négatif.",
                              emp.name))
        ligne('NET', _('Net à payer'), 'net', net)

        # 8. Charges patronales ----------------------------------------------
        for d in cot['detail']:
            if d['patronal']:
                ligne('COT_PAT_%s' % d['code'].upper(),
                      _('%s (part patronale)', d['name']), 'patronal',
                      d['patronal'], base=d['base'], taux=d['taux_patronal'])

        totaux = {
            'contrat_id': contrat.id,
            'poste_id': contrat.poste_id.id or emp.poste_id.id,
            'categorie_id': contrat.categorie_id.id,
            'regime_social': emp.regime_social,
            'nb_charges': emp.nb_charges_iuts,
            'mode_paiement': emp.mode_paiement,
            'banque_id': emp.banque_id.id,
            'numero_compte': emp.numero_compte,
            'numero_mobile_money': emp.numero_mobile_money,
            'salaire_base': salaire_base_total,
            'jours_payes': jours_payes,
            'brut': brut,
            'brut_soumis': brut_soumis,
            'base_cotisation': cot['base'],
            'cotisation_salariale': cot_sal,
            'charges_patronales': cot['total_patronal'],
            'brut_imposable': brut_imposable,
            'exonerations': exonerations,
            'abattement': abattement,
            'base_iuts': res_iuts['base'],
            'iuts_brut': res_iuts['impot_brut'],
            'reduction_iuts': res_iuts['reduction'],
            'iuts': iuts,
            'total_retenues': total_retenues,
            'net_a_payer': net,
            'cout_employeur': brut + cot['total_patronal'],
        }
        return lignes, totaux

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def _elements_consommes(self):
        """Éléments ponctuels, heures sup. et échéances repris par le
        bulletin (à marquer à la validation)."""
        self.ensure_one()
        sudo = self.sudo()
        emp = self.employee_id
        Prime = self.env['rh.prime'].sudo()
        Retenue = self.env['rh.retenue'].sudo()
        primes = Prime.search(Prime._domaine_periode(
            emp, self.date_debut, self.date_fin))._filtrer_periode(
            self.date_debut, self.date_fin, sudo).filtered(
            lambda p: p.recurrence == 'ponctuel')
        retenues = Retenue.search(Retenue._domaine_periode(
            emp, self.date_debut, self.date_fin))._filtrer_periode(
            self.date_debut, self.date_fin, sudo).filtered(
            lambda r: r.recurrence == 'ponctuel')
        heures = self.env['rh.heure.sup'].sudo().search([
            ('employee_id', '=', emp.id), ('state', '=', 'valide'),
            ('date', '>=', self.date_debut), ('date', '<=', self.date_fin),
            ('bulletin_id', '=', False)])
        echeances = self.env['rh.echeance.pret'].sudo().search([
            ('employee_id', '=', emp.id), ('pret_id.state', '=', 'en_cours'),
            ('date', '>=', self.date_debut), ('date', '<=', self.date_fin),
            ('state', '=', 'a_payer')])
        return primes, retenues, heures, echeances

    def action_valider(self):
        for rec in self:
            if rec.state != 'calcule':
                raise UserError(_("Le bulletin %s doit être calculé avant "
                                  "d'être validé.", rec.name))
            rec.paie_id._verifier_ouverte()
            # Recalcul de contrôle : les éléments n'ont pas changé depuis
            lignes, totaux = rec.sudo()._calculer()
            if rec.currency_id.compare_amounts(totaux['net_a_payer'],
                                               rec.net_a_payer):
                raise UserError(_(
                    "Les éléments de paie de %s ont changé depuis le calcul : "
                    "recalculez le bulletin avant de le valider.",
                    rec.employee_id.name))
            primes, retenues, heures, echeances = rec._elements_consommes()
            primes.write({'bulletin_id': rec.id})
            retenues.write({'bulletin_id': rec.id})
            heures.write({'bulletin_id': rec.id})
            echeances.write({'state': 'paye', 'bulletin_id': rec.id})
            echeances.pret_id._maj_etat()
            rec._ecrire({'state': 'valide'})
        return True

    def action_payer(self):
        for rec in self:
            if rec.state != 'valide':
                raise UserError(_("Seul un bulletin validé peut être marqué "
                                  "payé."))
            rec._ecrire({'state': 'paye'})
        return True

    def action_annuler(self, motif=None):
        """Annule un bulletin (même validé) tant que la période est ouverte.

        Les éléments consommés sont libérés ; un nouveau bulletin peut
        ensuite être établi.
        """
        for rec in self:
            if rec.state == 'annule':
                continue
            rec.paie_id._verifier_ouverte()
            sudo_id = rec.id
            self.env['rh.prime'].sudo().search(
                [('bulletin_id', '=', sudo_id)]).write({'bulletin_id': False})
            self.env['rh.retenue'].sudo().search(
                [('bulletin_id', '=', sudo_id)]).write({'bulletin_id': False})
            self.env['rh.heure.sup'].sudo().search(
                [('bulletin_id', '=', sudo_id)]).write({'bulletin_id': False})
            echeances = self.env['rh.echeance.pret'].sudo().search(
                [('bulletin_id', '=', sudo_id)])
            echeances.write({'state': 'a_payer', 'bulletin_id': False})
            echeances.pret_id._maj_etat()
            motif = motif or self.env.context.get('motif_annulation') \
                or _('Annulation')
            rec._ecrire({'state': 'annule', 'cle_unicite': False,
                         'motif_annulation': motif})
            rec.message_post(body=_("Bulletin annulé : %s", motif))
        return True

    def action_remettre_brouillon(self):
        for rec in self:
            if rec.state != 'calcule':
                raise UserError(_("Seul un bulletin calculé peut revenir en "
                                  "brouillon."))
            rec._ecrire({'state': 'brouillon'})


class RhLigneBulletin(models.Model):
    _name = 'rh.ligne.bulletin'
    _description = 'Ligne de bulletin de paie'
    _order = 'bulletin_id, sequence, id'

    bulletin_id = fields.Many2one('rh.bulletin.paie', required=True,
                                  ondelete='cascade', index=True)
    employee_id = fields.Many2one(related='bulletin_id.employee_id',
                                  store=True)
    company_id = fields.Many2one(related='bulletin_id.company_id',
                                 store=True)
    currency_id = fields.Many2one(related='bulletin_id.currency_id')
    date_debut = fields.Date(related='bulletin_id.date_debut', store=True)
    sequence = fields.Integer()
    code = fields.Char(string='Code', index=True)
    name = fields.Char(string='Libellé')
    categorie = fields.Selection(CATEGORIES_LIGNE, string='Catégorie')
    base = fields.Float(string='Base')
    taux = fields.Float(string='Taux (%)')
    quantite = fields.Float(string='Quantité')
    montant = fields.Monetary(string='Montant')
    imposable = fields.Boolean()
    soumis_cotisation = fields.Boolean()
    exoneration_iuts = fields.Char()

    def write(self, vals):
        if not self.env.su:
            raise UserError(_("Les lignes de bulletin ne se modifient pas : "
                              "recalculez le bulletin."))
        return super().write(vals)
