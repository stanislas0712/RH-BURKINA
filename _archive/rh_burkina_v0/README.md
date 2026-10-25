# RH Burkina Faso — Module Odoo 18

**Auteur :** KONATÉ Faichal Ismaël Stanislas  
**Version :** 18.0.1.0.0  
**Licence :** LGPL-3  
**Dépendances :** `base`, `hr`

> Module de gestion des ressources humaines entièrement adapté aux spécificités du Burkina Faso : Code du travail burkinabè, CNSS (Caisse Nationale de Sécurité Sociale), IUTS (Impôt Unique sur les Traitements et Salaires).

---

## Table des matières

1. [Vue d'ensemble](#vue-densemble)
2. [Installation](#installation)
3. [Fonctionnalités](#fonctionnalités)
4. [Modèles de données](#modèles-de-données)
5. [Sécurité et rôles](#sécurité-et-rôles)
6. [Menus et navigation](#menus-et-navigation)
7. [Numérotation automatique](#numérotation-automatique)
8. [Spécificités Burkina Faso](#spécificités-burkina-faso)

---

## Vue d'ensemble

Le module `rh_burkina` couvre l'intégralité du cycle de vie RH :

```
Recrutement → Embauche → Gestion du personnel → Paie → Congés → Évaluation → Fin de contrat
```

**37 modèles** · **10 rôles de sécurité** · **40 règles d'accès aux enregistrements** · **191 lignes ACL**

---

## Installation

```bash
# Copier le module dans le dossier addons
cp -r rh_burkina /path/to/odoo/custom_addons/

# Installer via Odoo
python odoo-bin -c conf/odoo.conf -d ma_base -i rh_burkina

# Mettre à jour
python odoo-bin -c conf/odoo.conf -d ma_base -u rh_burkina
```

Activer le **mode développeur** → Paramètres → Applications → rechercher « RH Burkina Faso » → Installer.

---

## Fonctionnalités

### 1. Dossier Personnel Employé (`rh.employe`)
- Informations personnelles : nom, prénom, genre, date de naissance, nationalité, situation familiale, nombre d'enfants
- Photo de profil
- Coordonnées : téléphone, email personnel et professionnel, adresse
- Pièces d'identité : CNIB, CNSS, IFU (NIF)
- Informations professionnelles : poste, département, service, site, supérieur hiérarchique, catégorie/échelon
- Rémunération : salaire de base, mode de paiement, coordonnées bancaires
- Statut : Actif / Inactif / Suspendu / Démissionnaire / Licencié / Retraité
- Calcul automatique de l'ancienneté et de l'âge
- Matricule auto-généré (format `EMP-XXXX`)
- Lien vers le compte utilisateur Odoo (self-service RH)
- Onglets : Diplômes, Formations, Historique des postes, Documents, Contacts d'urgence, Contrats, Congés, Soldes congés, Primes, Retenues, Sanctions, Évaluations, Présences

### 2. Recrutement (`rh.recrutement`, `rh.candidat`, `rh.entretien`)
- Offres d'emploi avec référence auto (`REC-XXXX`)
- Informations : titre du poste, département, type de contrat, nombre de postes
- Workflow : Brouillon → Publié → En Cours → Clôturé / Annulé
- Description du poste et profil recherché (champs texte multi-lignes)
- Critères : niveau d'étude minimum, expérience minimum, fourchette salariale, lieu
- Gestion des candidatures : statut de chaque candidat (Reçu / Présélectionné / Entretien / Test / Sélectionné / Refusé)
- Entretiens : planification, évaluation (note /10), recommandation, compte-rendu, points forts/faibles
- Statistiques : nombre de candidatures et d'entretiens calculés automatiquement

### 3. Contrats (`rh.contrat`)
- Types : CDI, CDD, Stage, Consultant, Vacataire
- Référence auto (`CTR-XXXX`)
- Workflow : Brouillon → Actif → Suspendu → Résilié / Expiré
- Informations : poste, salaire, durée du travail, renouvellement possible
- Clauses contractuelles libres

### 4. Gestion des Congés (`rh.conge`, `rh.solde.conge`, `rh.type.conge`)
- Types de congé configurables
- Demandes avec référence auto (`CNG-XXXX`)
- Workflow : Brouillon → Soumis → Approuvé / Refusé / Annulé
- **Contrôle du solde** : vérification automatique du solde disponible avant approbation — erreur si solde insuffisant
- Soldes de congés par employé, par type et par année
- Calcul automatique des jours pris et jours restants

### 5. Présences & Retards (`rh.presence`, `rh.retard`)
- Enregistrement des présences (heure d'arrivée, heure de départ)
- Calcul automatique des heures travaillées
- Suivi des retards avec motif
- Heures supplémentaires (`rh.heure.sup`)

### 6. Paie (`rh.bulletin.paie`, `rh.ligne.bulletin`, `rh.paie`)
- Bulletins de paie avec référence auto (`BP-XXXXX`)
- **Calcul automatique complet** :
  1. Salaire de base
  2. Primes (avec gestion de l'imposabilité)
  3. CNSS salarié (5,5 %) avec plafond de 1 500 000 FCFA
  4. CNSS patronal (16 %) avec plafond de 1 500 000 FCFA
  5. IUTS calculé via le barème progressif (`rh.iuts`)
  6. Autres retenues
  7. Net à payer
- Lignes détaillées de bulletin (revenus, retenues salariales, charges patronales)
- Workflow : Brouillon → Calculé → Validé → Payé
- Périodes de paie (`rh.paie`) avec référence auto (`PAI-XXXX`)
- Données confidentielles : accès restreint aux rôles Paie, Responsable RH, Directeur Général

### 7. Primes & Retenues (`rh.prime`, `rh.retenue`)
- Primes liées à un employé avec type, montant ou taux
- Types de prime configurables : imposable/non imposable, montant fixe ou pourcentage
- Retenues diverses avec base de calcul (salaire brut, salaire de base, montant fixe)
- Types de retenue configurables

### 8. Évaluations (`rh.evaluation`)
- Évaluations périodiques des employés
- Note globale et commentaires
- Statut : Planifiée / En cours / Finalisée
- Objectifs liés (`rh.objectif`)
- Visible par l'employé (ses propres évaluations) et modifiable par le chef de département (son équipe)

### 9. Formations (`rh.formation`, `rh.inscription.formation`)
- Catalogue de formations avec type, formateur, durée, capacité
- Inscriptions des employés avec statut (Inscrit / Confirmé / Présent / Absent / Certifié)
- Suivi par le Responsable Formation

### 10. Sanctions Disciplinaires (`rh.sanction`)
- Types : Avertissement / Blâme / Mise en demeure / Suspension sans solde / Licenciement
- Référence auto (`SANC-XXXX`)
- Workflow : Brouillon → Notifié → Confirmé / Annulé
- Motif obligatoire
- Licenciement déclenche automatiquement le changement de statut de l'employé
- Données confidentielles : invisibles aux employés simples

### 11. Carrière & Historique (`rh.carriere`, `rh.historique.poste`)
- Historique complet des postes occupés
- Évolution de carrière avec dates de prise de poste

### 12. Documents RH (`rh.document`)
- Gestion des documents liés à chaque employé
- Types : contrat, attestation, certificat, etc.

### 13. Diplômes & Contacts d'urgence (`rh.diplome`, `rh.contact.urgence`)
- Diplômes avec établissement, date d'obtention, mention
- Contacts d'urgence avec lien de parenté et téléphone

### 14. Tableau de Bord (`rh.tableau.bord`)
- Vue consolidée des indicateurs RH

### 15. Configuration organisationnelle
| Modèle | Description |
|--------|-------------|
| `rh.departement` | Départements / Directions avec responsable |
| `rh.service` | Services rattachés aux départements |
| `rh.poste` | Postes / Emplois avec grille salariale |
| `rh.site` | Sites / Agences avec localisation |
| `rh.categorie` | Catégories / Échelons avec fourchettes de salaire |

### 16. Paramètres légaux (`rh.configuration`, `rh.cnss`, `rh.iuts`)
- SMIG, heures légales hebdomadaires et mensuelles
- Barème CNSS : taux salarié, taux patronal, plafond
- Barème IUTS : tranches progressives d'imposition

---

## Modèles de données

| Modèle | Nom technique | Description |
|--------|--------------|-------------|
| `rh.employe` | Employé | Dossier personnel complet |
| `rh.recrutement` | Recrutement | Offres d'emploi |
| `rh.candidat` | Candidat | Candidatures reçues |
| `rh.entretien` | Entretien | Entretiens de recrutement |
| `rh.contrat` | Contrat | Contrats de travail |
| `rh.conge` | Congé | Demandes de congé |
| `rh.solde.conge` | Solde Congé | Soldes par type et par année |
| `rh.type.conge` | Type de Congé | Types configurables |
| `rh.presence` | Présence | Pointage journalier |
| `rh.retard` | Retard | Retards enregistrés |
| `rh.heure.sup` | Heure Sup. | Heures supplémentaires |
| `rh.bulletin.paie` | Bulletin de Paie | Fiche de paie mensuelle |
| `rh.ligne.bulletin` | Ligne Bulletin | Détail des lignes de paie |
| `rh.paie` | Période de Paie | Clôture mensuelle de paie |
| `rh.prime` | Prime | Primes par employé |
| `rh.type.prime` | Type de Prime | Catalogue des primes |
| `rh.retenue` | Retenue | Retenues par employé |
| `rh.type.retenue` | Type de Retenue | Catalogue des retenues |
| `rh.evaluation` | Évaluation | Évaluations périodiques |
| `rh.objectif` | Objectif | Objectifs individuels |
| `rh.formation` | Formation | Catalogue de formations |
| `rh.inscription.formation` | Inscription | Inscriptions aux formations |
| `rh.sanction` | Sanction | Sanctions disciplinaires |
| `rh.carriere` | Carrière | Évolution de carrière |
| `rh.historique.poste` | Historique Poste | Postes antérieurs |
| `rh.document` | Document | Documents RH |
| `rh.diplome` | Diplôme | Diplômes et formations |
| `rh.contact.urgence` | Contact d'Urgence | Personnes à contacter |
| `rh.departement` | Département | Structure organisationnelle |
| `rh.service` | Service | Sous-unités des départements |
| `rh.poste` | Poste | Emplois / Fonctions |
| `rh.site` | Site / Agence | Lieux de travail |
| `rh.categorie` | Catégorie | Échelons salariaux |
| `rh.cnss` | Barème CNSS | Paramètres CNSS Burkina |
| `rh.iuts` | Barème IUTS | Tranches IUTS Burkina |
| `rh.configuration` | Configuration | Paramètres légaux |
| `rh.tableau.bord` | Tableau de Bord | Indicateurs RH |

---

## Sécurité et rôles

### Hiérarchie principale

```
Employé  ⊂  Gestionnaire RH  ⊂  Responsable RH  ⊂  Administrateur RH
```

### Rôles fonctionnels (transversaux)

```
Employé  ⊂  Chef de Département
Employé  ⊂  Recruteur
Gestionnaire RH  ⊂  Responsable Paie
Employé  ⊂  Responsable Formation
Employé  ⊂  Directeur Général
Employé  ⊂  Auditeur
```

### Tableau des droits

| Rôle | Employés | Contrats | Congés | Paie | Recrutement | Formations | Sanctions | Config |
|------|----------|----------|--------|------|-------------|------------|-----------|--------|
| **Employé** | ✅ (sien) | 👁 (sien) | ✅ (siens) | 👁 (sien) | ❌ | 👁 | ❌ | ❌ |
| **Gestionnaire RH** | ✅ (tous) | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ | ❌ |
| **Responsable RH** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 👁 |
| **Administrateur RH** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Chef de Département** | ✅ (équipe) | 👁 (équipe) | ✅ (équipe) | ❌ | ❌ | 👁 | ❌ | ❌ |
| **Recruteur** | 👁 | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |
| **Responsable Paie** | 👁 | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Responsable Formation** | 👁 | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| **Directeur Général** | 👁 | 👁 | 👁 | 👁 | 👁 | 👁 | 👁 | ❌ |
| **Auditeur** | 👁 | 👁 | 👁 | 👁 | 👁 | 👁 | 👁 | ❌ |

> ✅ Lecture + Écriture · 👁 Lecture seule · ❌ Aucun accès

### Règles d'accès aux enregistrements (Record Rules)

- **Employé self-service** : ne voit que ses propres données (fiche, congés, bulletins, présences, évaluations, contrats)
- **Chef de département** : filtrage par `departement_id.responsable_id.user_id = utilisateur connecté`
- **Bulletins de paie** : confidentiels — accessibles uniquement à la Paie, au Responsable RH et au Directeur
- **Sanctions** : invisibles aux employés simples

### Activer le self-service pour un employé

1. Créer un compte utilisateur Odoo (Configuration → Utilisateurs & Rôles)
2. Assigner le rôle **Employé** dans la section « RH Burkina Faso »
3. Dans la fiche employé, champ **Utilisateur Odoo** → sélectionner le compte

---

## Menus et navigation

```
RH Burkina Faso
├── Tableau de Bord              (tous les rôles RH)
├── Employés                     (Gestionnaire+, Chef dept, Directeur, Auditeur)
├── Contrats                     (Gestionnaire+, Directeur, Auditeur)
├── Recrutements                 (Gestionnaire+, Recruteur, Directeur, Auditeur)
├── Présences                    (tous — filtré sur ses propres données pour Employé)
├── Congés
│   ├── Demandes de Congé        (tous — filtré pour Employé)
│   └── Soldes de Congés         (tous — filtré pour Employé)
├── Paie
│   ├── Bulletins de Paie        (Responsable Paie, Responsable RH+, Directeur)
│   └── Périodes de Paie         (Responsable Paie, Responsable RH+, Directeur)
├── Sanctions Disciplinaires     (Gestionnaire+, Directeur, Auditeur)
└── Configuration                (Responsable RH+, Administrateur)
    ├── Utilisateurs & Rôles     (Administrateur uniquement)
    ├── Structure Organisationnelle
    │   ├── Départements / Directions
    │   ├── Services
    │   └── Postes / Emplois
    └── Paramètres RH
        ├── Sites / Agences
        ├── Catégories / Échelons
        ├── Types de Prime
        └── Types de Retenue
```

Toutes les vues supportent le **basculement liste ↔ kanban**.

---

## Numérotation automatique

| Séquence | Préfixe | Exemple | Modèle |
|----------|---------|---------|--------|
| Employé | `EMP-` | EMP-0001 | `rh.employe` |
| Recrutement | `REC-` | REC-0001 | `rh.recrutement` |
| Candidat | `CAND-` | CAND-0001 | `rh.candidat` |
| Contrat | `CTR-` | CTR-0001 | `rh.contrat` |
| Congé | `CNG-` | CNG-0001 | `rh.conge` |
| Bulletin de Paie | `BP-` | BP-00001 | `rh.bulletin.paie` |
| Période de Paie | `PAI-` | PAI-0001 | `rh.paie` |
| Sanction | `SANC-` | SANC-0001 | `rh.sanction` |

---

## Spécificités Burkina Faso

### CNSS (Caisse Nationale de Sécurité Sociale)
- **Part salariale** : 5,5 % du salaire brut
- **Part patronale** : 16 % du salaire brut
- **Plafond de cotisation** : 1 500 000 FCFA par mois
- Calcul automatique lors de la génération du bulletin

### IUTS (Impôt Unique sur les Traitements et Salaires)
- Calcul via le barème progressif par tranches (`rh.iuts`)
- Barème paramétrable par l'administrateur
- Intégré automatiquement dans le bulletin de paie

### Paramètres légaux configurables
- **SMIG** (Salaire Minimum Interprofessionnel Garanti)
- **Heures légales** hebdomadaires et mensuelles
- **Date d'application** des paramètres

### Code du travail burkinabè
- Types de contrats conformes : CDI, CDD, Stage, Consultant, Vacataire
- Gestion des indemnités de licenciement
- Suivi des sanctions disciplinaires conforme à la procédure légale
- Calcul de l'ancienneté

---

## Structure des fichiers

```
rh_burkina/
├── __manifest__.py
├── README.md
├── models/
│   ├── rh_employe.py
│   ├── rh_recrutement.py
│   ├── rh_candidat.py
│   ├── rh_entretien.py
│   ├── rh_contrat.py
│   ├── rh_conge.py
│   ├── rh_solde_conge.py
│   ├── rh_type_conge.py
│   ├── rh_presence.py
│   ├── rh_retard.py
│   ├── rh_heure_sup.py
│   ├── rh_bulletin_paie.py
│   ├── rh_ligne_bulletin.py
│   ├── rh_paie.py
│   ├── rh_prime.py
│   ├── rh_type_prime.py
│   ├── rh_retenue.py
│   ├── rh_type_retenue.py
│   ├── rh_evaluation.py
│   ├── rh_objectif.py
│   ├── rh_formation.py
│   ├── rh_inscription_formation.py
│   ├── rh_sanction.py
│   ├── rh_carriere.py
│   ├── rh_historique_poste.py
│   ├── rh_document.py
│   ├── rh_diplome.py
│   ├── rh_contact_urgence.py
│   ├── rh_departement.py
│   ├── rh_service.py
│   ├── rh_poste.py
│   ├── rh_site.py
│   ├── rh_categorie.py
│   ├── rh_cnss.py
│   ├── rh_iuts.py
│   ├── rh_configuration.py
│   └── rh_tableau_bord.py
├── security/
│   ├── res_groups_data.xml      # 10 rôles + catégorie personnalisée
│   ├── ir_rule.xml              # 40 règles d'accès aux enregistrements
│   └── ir.model.access.csv     # 191 lignes ACL
├── data/
│   └── ir_sequence_data.xml    # 8 séquences de numérotation
├── views/
│   └── rh_burkina_views.xml    # Toutes les vues, actions et menus
└── static/
    └── src/
        ├── css/
        │   └── rh_burkina.css
        └── img/
            └── logo_rh_burkina.png
```

---

*Module développé dans le cadre de la formation Odoo 18 — Burkina Faso*
