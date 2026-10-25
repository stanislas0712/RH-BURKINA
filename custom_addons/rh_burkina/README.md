# RH Burkina Faso (`rh_burkina`)

Module Odoo 18 de gestion des ressources humaines et de la paie adapté au
Burkina Faso (Code du travail – loi n°028-2008/AN, CNSS / CARFO, IUTS).

- Version : 18.0.1.0.0 – Licence LGPL-3
- Auteur : KONATÉ Faichal Ismaël Stanislas
- Dépendances : `base`, `mail`, `hr`
- Devise : XOF (FCFA), montants arrondis à l'unité

## ⚠️ Valeurs légales à vérifier

Toutes les valeurs légales sont **paramétrables et datées** (menu
*Configuration > Paramètres légaux*). Aucune n'est codée en dur dans le
Python. Les valeurs initiales (`data/rh_parametres_data.xml`) sont un point
de départ marqué « à vérifier » : elles doivent être confirmées auprès de la
CNSS, de la DGI, de l'Inspection du travail et de la convention collective
avant toute mise en production.

| Paramètre | Valeur initiale | Statut |
|---|---|---|
| SMIG mensuel | 45 000 FCFA | à vérifier |
| Durée légale | 40 h / semaine, 173,33 h / mois | à vérifier |
| Âge minimum d'embauche / retraite | 16 ans / 60 ans | à vérifier |
| CDD | 1 renouvellement, 24 mois cumulés | à vérifier |
| Mise à pied | 8 jours maximum | à vérifier |
| Heures sup. | plafond 20 h / semaine ; annuel non renseigné | à vérifier |
| Majorations HS | jour 15 % (8 premières h) puis 35 % ; nuit 50 % ; dimanche et férié 60 % | à vérifier |
| Congés | 2,5 jours ouvrables / mois | à vérifier |
| Périodes d'essai | ouvrier 1 mois, maîtrise 2 mois, cadre 3 mois | à vérifier |
| Préavis | ouvrier 1 mois, maîtrise 2 mois, cadre 3 mois | à vérifier |
| CNSS | plafond 1 500 000 FCFA ; salarié 5,5 % (pension) ; employeur 16 % (PF 7 %, RP 3,5 %, pension 5,5 %) | à vérifier |
| IUTS | 7 tranches de 0 % à 25 % ; base arrondie à la centaine inférieure | à vérifier |
| Abattement frais professionnels | cadre 20 %, non-cadre 25 % du salaire de base | à vérifier |
| Charges de famille | 1 : 8 %, 2 : 10 %, 3 : 12 %, 4 et plus : 14 % | à vérifier |
| Indemnités exonérées | logement 20 % du brut ≤ 75 000 ; fonction 5 % ≤ 50 000 ; transport 5 % ≤ 30 000 | à vérifier |
| Licenciement | 25 % (0–5 ans), 30 % (5–10 ans), 40 % (au-delà) ; 12 mois minimum | à vérifier |
| Conservation des dossiers | 5 ans après la sortie | à vérifier |
| SMIG et contrats | stage non soumis au SMIG ; temps partiel : SMIG × heures / durée légale ; SMIG horaire à défaut = SMIG mensuel / 173,33 ; consultant non soumis | à vérifier |
| Jours fériés 2026 | 1/01, 3/01, 8/03, 1/05, 5/08, 15/08, 1/11, 11/12, 25/12 ; fêtes à date variable à saisir chaque année ; 31/10 et 15/05 non saisis | à vérifier |
| Congés spéciaux | maternité 98 jours calendaires (justificatif) ; mariage, naissance, décès : durées à renseigner ; maladie : certificat | à vérifier |
| Acquisition des congés | prorata calendaire des jours sous contrat dans le mois ; suspensions non déduites ; solde rattaché à l'année de début du congé | à vérifier |
| Heures supplémentaires | rang de l'heure compté par semaine et par type d'heures | à vérifier |

**Laissés vides, à renseigner :** barème de la prime d'ancienneté, congés
supplémentaires pour ancienneté, quotité saisissable, barème CARFO. Tant que
la quotité saisissable n'est pas renseignée, le contrôle des retenues
signale une erreur au lieu de laisser passer.

Pour un changement légal, **créer un nouveau jeu de paramètres** à sa date
d'entrée en vigueur : l'ancien reste appliqué aux périodes passées. Un jeu
propre à une société prime sur le jeu commun (sans société).

## Rôles

| Rôle | Hérite de |
|---|---|
| Employé | Utilisateur interne |
| Gestionnaire RH | Employé |
| Responsable RH | Gestionnaire RH + accès salaires |
| Administrateur RH | Responsable RH |
| Chef de Département, Recruteur, Responsable Formation | Employé |
| Responsable Paie, Directeur Général, Auditeur | Employé + accès salaires |

Le groupe technique « accès aux salaires » protège les champs confidentiels
(salaires, coordonnées bancaires, montants des contrats, prêts).

## Avancement

| Phase | Contenu | État |
|---|---|---|
| 1 | Squelette, rôles, ACL, règles, structure, paramètres légaux, séquences | ✅ |
| 2 | Dossier du personnel (extension `hr.employee`), historique, documents, diplômes, contacts | ✅ |
| 3 | Contrats : période d'essai, CDD, préavis, SMIG | ✅ |
| 4 | Jours fériés, présences, retards, heures sup., congés | ✅ |
| 5 | Paie | à venir |
| 6 | Recrutement | à venir |
| 7 | Évaluations, formations, discipline | à venir |
| 8 | Sortie, rapports, tableau de bord, automatisations, démo | à venir |

## Installation et tests

```bash
python odoo/odoo-bin -c conf/odoo.conf -d <base> -i rh_burkina --stop-after-init
python odoo/odoo-bin -c conf/odoo.conf -d <base> -u rh_burkina \
    --test-enable --test-tags /rh_burkina --stop-after-init
```
