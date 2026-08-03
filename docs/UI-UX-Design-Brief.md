# UI/UX Design Brief - CBC Supervision Platform

**Version 1.0**  
**Date : 3 août 2026**  
**Document de référence pour la conception des interfaces**

---

## Table des matières

1. [Présentation du projet](#1-présentation-du-projet)
2. [Les utilisateurs](#2-les-utilisateurs)
3. [Architecture de navigation](#3-architecture-de-navigation)
4. [Tous les écrans](#4-tous-les-écrans)
5. [Dashboard](#5-dashboard)
6. [Gestion des agents](#6-gestion-des-agents)
7. [Détail d'un agent](#7-détail-dun-agent)
8. [Gestion des alertes](#8-gestion-des-alertes)
9. [Paramètres](#9-paramètres)
10. [Gestion des utilisateurs](#10-gestion-des-utilisateurs)
11. [Authentification](#11-authentification)
12. [Tous les composants UI](#12-tous-les-composants-ui)
13. [Toutes les couleurs](#13-toutes-les-couleurs)
14. [Typographie](#14-typographie)
15. [Iconographie](#15-iconographie)
16. [Espacements](#16-espacements)
17. [UX](#17-ux)
18. [États](#18-états)
19. [Animations](#19-animations)
20. [Design System](#20-design-system)
21. [Inspirations](#21-inspirations)
22. [Design Tokens](#22-design-tokens)
23. [Responsive Strategy](#23-responsive-strategy)
24. [Empty States](#24-empty-states)
25. [Loading States](#25-loading-states)
26. [Error States](#26-error-states)
27. [Success States](#27-success-states)
28. [Micro-interactions](#28-micro-interactions)
29. [Accessibilité](#29-accessibilité)
30. [Performance UX](#30-performance-ux)
31. [Bibliothèque d'icônes](#31-bibliothèque-dicônes)
32. [Layout System](#32-layout-system)
33. [Comportement des composants](#33-comportement-des-composants)
34. [Règles de cohérence UI](#34-règles-de-cohérence-ui)
35. [Principes UX](#35-principes-ux)
36. [Identité visuelle officielle de la CBC](#36-identité-visuelle-officielle-de-la-cbc)

---

## 1. Présentation du projet

### Le problème

La Commercial Bank Cameroun gère un parc informatique hétérogène (Windows, Linux, macOS) sans vision centralisée de son état de santé. Les équipes IT opèrent dans le noir, détectant les incidents de manière réactive plutôt que proactive. Les conséquences sont directes : temps d'arrêt prolongés, perte de productivité, et risque pour la continuité des activités bancaires.

### Pourquoi cette plateforme existe

CBC Supervision Platform apporte une réponse structurée à ces défis en offrant :

- **Visibilité unifiée** : Une seule source de vérité pour l'état de l'ensemble du parc informatique
- **Détection proactive** : Les anomalies sont identifiées avant qu'elles ne deviennent des incidents critiques
- **Réactivité accrue** : Les équipes sont informées immédiatement et peuvent intervenir plus rapidement
- **Maintenance simplifiée** : La configuration est centralisée, éliminant les interventions machine par machine
- **Historique et traçabilité** : Les données sont conservées, permettant l'analyse des tendances et l'amélioration continue

### Objectifs

- Fournir une vue en temps réel de l'état de tous les agents déployés
- Identifier automatiquement les anomalies de ressources (CPU, RAM, disque)
- Réduire le temps de détection et de résolution des incidents
- Centraliser la configuration et éliminer les scripts dispersés
- Supporter Windows, Linux et macOS avec une solution unifiée
- Garantir des communications authentifiées et chiffrées

### Bénéfices utilisateurs

- **Pour les administrateurs** : Vision globale du parc, configuration centralisée, gestion proactive des incidents
- **Pour les opérateurs** : Alertes ciblées, informations détaillées pour le diagnostic, actions rapides
- **Pour la direction** : Indicateurs de disponibilité, tendances des incidents, planification capacitaire

---

## 2. Les utilisateurs

### 2.1 Administrateur

**Objectifs**
- Maintenir une vision globale du parc informatique
- Configurer les seuils d'alerte selon les besoins de l'organisation
- Gérer les accès utilisateurs et les permissions
- Superviser le déploiement des agents
- Analyser les tendances et planifier les évolutions

**Responsabilités**
- Configuration des seuils globaux et par agent
- Gestion des comptes utilisateurs (création, modification, suppression)
- Génération des jetons d'enrôlement pour les nouveaux agents
- Révocation et suppression des agents
- Acquittement de toutes les alertes (Info, Warning, Critique)
- Export des données pour analyse

**Besoins**
- Vue d'ensemble avec KPIs de santé du parc
- Accès à tous les écrans de configuration
- Outils de gestion des utilisateurs et agents
- Capacité d'export des données
- Historique complet des alertes

**Permissions**
- Lecture : Tous les écrans
- Écriture : Paramètres, configuration agents, gestion utilisateurs
- Administration : Révocation/suppression agents, génération jetons
- Export : CSV agents et alertes

**Fréquence d'utilisation**
- Quotidienne : Consultation dashboard et alertes
- Hebdomadaire : Analyse des tendances, ajustement des seuils
- Mensuelle : Planification, gestion des utilisateurs

---

### 2.2 Opérateur

**Objectifs**
- Surveiller l'état du parc en temps réel
- Traiter les alertes de manière proactive
- Diagnostiquer les incidents et intervenir
- Acquitter les alertes après résolution

**Responsabilités**
- Surveillance du dashboard et des alertes
- Diagnostic des incidents via les détails d'agent
- Intervention sur les machines en anomalie
- Acquittement des alertes Info et Warning
- Export des données pour reporting

**Besoins**
- Vue d'ensemble avec alertes prioritaires
- Accès rapide aux détails des agents en anomalie
- Outils de filtrage et recherche des alertes
- Capacité d'acquittement des alertes
- Export des données pour reporting

**Permissions**
- Lecture : Dashboard, détails agent, liste alertes
- Écriture : Acquittement alertes Info et Warning uniquement
- Export : CSV agents et alertes
- Interdit : Paramètres, configuration agents, gestion utilisateurs

**Fréquence d'utilisation**
- Quotidienne : Surveillance continue du dashboard
- En cas d'alerte : Intervention immédiate

---

### 2.3 Lecture seule

**Objectifs**
- Consulter l'état du parc informatique
- Visualiser les métriques et alertes
- Accéder aux informations pour reporting

**Responsabilités**
- Consultation passive des données
- Aucune action d'écriture ou de modification

**Besoins**
- Vue d'ensemble du parc
- Accès aux détails des agents
- Consultation de la liste des alertes
- Aucune capacité d'action

**Permissions**
- Lecture : Dashboard, détails agent, liste alertes
- Interdit : Toute action d'écriture, export, configuration

**Fréquence d'utilisation**
- Hebdomadaire ou mensuelle : Consultation pour reporting
- Ponctuelle : Vérification de l'état du parc

---

## 3. Architecture de navigation

### Arborescence complète

```
Connexion
    ↓
Dashboard (Page d'accueil)
    ↓
├── Agents
│   ├── Liste des agents
│   ├── Détail d'un agent
│   └── Recherche / Filtres
│
├── Alertes
│   ├── Liste des alertes
│   ├── Détail d'une alerte
│   └── Filtres (gravité, type, statut)
│
├── Paramètres
│   ├── Seuils d'alerte
│   │   ├── Seuils globaux
│   │   └── Seuils par agent
│   ├── Notifications
│   │   └── Configuration email
│   ├── Rétention des données
│   └── Génération de jetons d'enrôlement
│
├── Utilisateurs
│   ├── Liste des utilisateurs
│   ├── Créer un utilisateur
│   ├── Modifier un utilisateur
│   └── Supprimer un utilisateur
│
└── Profil utilisateur
    ├── Informations personnelles
    └── Changer le mot de passe
```

### Navigation principale

**Sidebar fixe (gauche)**
- Logo CBC Supervision
- Navigation principale
- Informations utilisateur (bas)
- Bouton déconnexion

**Header (haut)**
- Breadcrumb de navigation
- Indicateur de statut système
- Notifications (alertes non acquittées)
- Profil utilisateur (dropdown)

**Zone de contenu (centre)**
- Contenu dynamique selon la page active

### Liens entre pages

**Depuis Dashboard**
- Clic sur un agent → Détail agent
- Clic sur une alerte → Liste alertes filtrée
- Clic sur KPI → Vue correspondante

**Depuis Liste agents**
- Clic sur une ligne → Détail agent
- Bouton recherche → Filtres appliqués
- Bouton configurer → Détail agent (onglet Configuration)

**Depuis Détail agent**
- Bouton retour → Liste agents
- Clic sur alerte active → Détail alerte
- Bouton révoquer → Modal de confirmation

**Depuis Liste alertes**
- Clic sur une alerte → Détail agent correspondant
- Filtres → Rafraîchissement de la liste
- Bouton acquitter → Action immédiate

**Depuis Paramètres**
- Navigation par onglets
- Sauvegarde → Feedback toast
- Retour → Dashboard

---

## 4. Tous les écrans

### 4.1 Écran de connexion

**Objectif**
Permettre l'authentification sécurisée des utilisateurs.

**Informations affichées**
- Logo CBC Supervision
- Formulaire de connexion (email, mot de passe)
- Lien "Mot de passe oublié"
- Message de copyright

**Actions disponibles**
- Saisie de l'email
- Saisie du mot de passe (masqué/visible)
- Bouton "Se connecter"
- Lien vers récupération mot de passe

**Composants**
- Input email avec validation
- Input mot de passe avec toggle visibilité
- Bouton principal "Se connecter"
- Lien secondaire "Mot de passe oublié"
- Logo centré

**États**
- **Initial** : Formulaire vide
- **Validation** : Feedback sur les champs
- **Chargement** : Spinner sur le bouton
- **Erreur** : Message d'erreur (identifiants invalides)
- **Succès** : Redirection vers Dashboard

**Responsive**
- Mobile : Formulaire centré, plein écran
- Desktop : Centré dans un card, fond décoratif

---

### 4.2 Écran Dashboard

**Objectif**
Fournir une vue d'ensemble en temps réel de l'état du parc informatique.

**Informations affichées**
- KPIs globaux (agents en ligne, hors ligne, alertes actives)
- Liste des agents avec métriques en temps réel
- Alertes récentes non acquittées
- Graphiques de tendance (si disponible en V1.1)

**Actions disponibles**
- Rafraîchissement automatique (30s)
- Clic sur un agent → Détail agent
- Clic sur une alerte → Liste alertes
- Filtres rapides (tous, en ligne, hors ligne, en anomalie)

**Composants**
- **KPI Cards** : 4 cartes avec métriques clés
- **Tableau agents** : Liste avec tri et pagination
- **Section alertes** : Liste compacte des alertes récentes
- **Filtres** : Barre de recherche et filtres rapides
- **Actions rapides** : Boutons d'action courante

**Filtres**
- Recherche par nom d'agent
- Filtre par statut (en ligne, hors ligne)
- Filtre par OS (Windows, Linux, macOS)
- Filtre par alerte active

**Tableaux**
- Colonnes : Nom, OS, Statut, CPU, RAM, Disque, Uptime, Alertes
- Tri sur toutes les colonnes
- Pagination (20/50/100 par page)
- Badges de statut colorés

**Navigation**
- Sidebar fixe
- Header avec breadcrumb
- Lien direct vers autres sections

**États vides**
- **Aucun agent** : Message illustré + CTA "Générer jeton d'enrôlement"
- **Aucune alerte** : Message "Tout va bien"

**États de chargement**
- Skeleton loaders pour les KPIs
- Skeleton rows pour le tableau
- Spinner global si chargement initial

**États d'erreur**
- Message d'erreur avec bouton "Réessayer"
- Indication de la nature de l'erreur

**Responsive attendu**
- Mobile : KPIs empilés, tableau en cards, sidebar hamburger
- Tablet : KPIs 2x2, tableau complet
- Desktop : KPIs 4x1, tableau complet

---

### 4.3 Écran Liste des agents

**Objectif**
Afficher la liste complète des agents avec leurs métriques et permettre la gestion.

**Informations affichées**
- Tableau complet des agents
- Métriques en temps réel (CPU, RAM, Disque, Uptime)
- Statut de connexion
- Nombre d'alertes actives
- OS et version de l'agent

**Actions disponibles**
- Recherche par nom
- Tri sur toutes les colonnes
- Filtres multiples (OS, statut, alertes)
- Pagination
- Clic sur ligne → Détail agent
- Export CSV (Admin/Opérateur)

**Composants**
- **Barre de recherche** : Input avec icône
- **Filtres avancés** : Dropdown avec checkboxes
- **Tableau** : Colonnes triables
- **Pagination** : Bas de page
- **Bouton export** : Header (Admin/Opérateur)

**Filtres**
- Recherche textuelle (nom, hostname)
- Filtre OS : Windows, Linux, macOS
- Filtre statut : En ligne, Hors ligne, Obsolète
- Filtre alertes : Aucune, Info, Warning, Critique
- Filtre seuils personnalisés : Oui/Non

**Tableaux**
- Colonnes : Nom, Hostname, OS, Statut, CPU, RAM, Disque, Uptime, Alertes, Actions
- Tri ascendant/descendant
- Pagination configurable
- Hover sur ligne → highlight

**Navigation**
- Breadcrumb : Dashboard > Agents
- Sidebar : Section Agents active
- Header : Titre + actions

**États vides**
- **Aucun agent** : Message + illustration + CTA vers enrôlement
- **Aucun résultat** : Message après filtre/recherche

**États de chargement**
- Skeleton rows pour le tableau
- Spinner sur les filtres

**États d'erreur**
- Message d'erreur avec réessai
- Détail de l'erreur technique

**Responsive attendu**
- Mobile : Tableau transformé en cards, filtres collapsibles
- Tablet : Tableau avec scroll horizontal
- Desktop : Tableau complet

---

### 4.4 Écran Détail d'un agent

**Objectif**
Afficher toutes les informations détaillées d'un agent et permettre sa configuration.

**Informations affichées**
- Informations système (hostname, OS, version agent, IP)
- Métriques en temps réel (CPU, RAM, Disque avec graphiques)
- Statut de connexion et uptime
- Alertes actives sur cet agent
- Configuration personnalisée (seuils)
- Historique des alertes

**Actions disponibles**
- Rafraîchissement manuel
- Acquitter les alertes (Admin/Opérateur)
- Configurer les seuils (Admin)
- Révoquer l'agent (Admin)
- Supprimer l'agent (Admin)
- Retour à la liste

**Composants**
- **Header agent** : Nom, statut, OS, uptime
- **Onglets** : Vue d'ensemble, Métriques, Alertes, Configuration
- **Cards métriques** : CPU, RAM, Disque avec jauges
- **Tableau alertes** : Alertes actives de cet agent
- **Formulaire configuration** : Seuils personnalisés
- **Boutons action** : Révoquer, Supprimer (Admin)

**Filtres**
- Filtre alertes par gravité (onglet Alertes)
- Filtre alertes par statut (actives, résolues)

**Tableaux**
- Onglet Alertes : Tableau des alertes de cet agent
- Colonnes : Type, Gravité, Date, Message, Statut, Actions

**Navigation**
- Breadcrumb : Dashboard > Agents > [Nom agent]
- Bouton retour : Liste agents
- Onglets : Navigation interne

**États vides**
- **Aucune alerte** : Message "Aucune alerte active"
- **Aucune configuration** : Message "Utilise les seuils globaux"

**États de chargement**
- Skeleton cards pour les métriques
- Skeleton rows pour les alertes

**États d'erreur**
- Message d'erreur avec réessai
- Indication agent hors ligne

**Responsive attendu**
- Mobile : Onglets scrollables, cards empilées
- Tablet : Onglets complets, layout 2 colonnes
- Desktop : Layout complet avec sidebar métriques

---

### 4.5 Écran Liste des alertes

**Objectif**
Afficher toutes les alertes avec filtrage avancé et permettre leur gestion.

**Informations affichées**
- Tableau complet des alertes
- Type d'alerte (CPU, RAM, Disque, Hors ligne)
- Gravité (Info, Warning, Critique)
- Agent concerné
- Date et heure
- Statut (ouverte, acquittée, résolue)
- Message descriptif

**Actions disponibles**
- Filtres multiples (gravité, type, statut, agent, période)
- Tri sur toutes les colonnes
- Acquitter une alerte (Admin/Opérateur selon gravité)
- Acquitter en lot (Admin)
- Clic sur alerte → Détail agent
- Export CSV (Admin/Opérateur)

**Composants**
- **Barre de filtres** : Filtres avancés collapsibles
- **Tableau alertes** : Colonnes triables
- **Pagination** : Bas de page
- **Bouton acquitter tout** : Header (Admin)
- **Bouton export** : Header (Admin/Opérateur)

**Filtres**
- Recherche textuelle (agent, message)
- Filtre gravité : Info, Warning, Critique
- Filtre type : Hors ligne, CPU, RAM, Disque
- Filtre statut : Ouverte, Acquittée, Résolue
- Filtre période : Dernières 24h, 7j, 30j, personnalisé
- Filtre agent : Dropdown avec recherche

**Badges**
- Gravité : Info (bleu), Warning (orange), Critique (rouge)
- Statut : Ouverte (rouge), Acquittée (gris), Résolue (vert)

**Couleurs**
- Fond ligne selon gravité (subtil)
- Badge gravité coloré
- Badge statut coloré

**Gravité**
- **Info** : Informationnel, pas d'action requise
- **Warning** : Attention requise, monitoring accru
- **Critique** : Action immédiate requise

**Acquittement**
- Modal de confirmation
- Champ commentaire optionnel
- Feedback toast après action

**Historique**
- Conservation 30 jours
- Archivage automatique
- Export disponible

**Détails**
- Clic sur alerte → Détail agent
- Affichage du message complet
- Contexte de l'alerte

**Actions possibles**
- Acquitter (selon permissions)
- Voir l'agent concerné
- Filtrer par agent

**Navigation**
- Breadcrumb : Dashboard > Alertes
- Sidebar : Section Alertes active
- Header : Titre + filtres + actions

**États vides**
- **Aucune alerte** : Message "Aucune alerte" + illustration positive
- **Aucun résultat** : Message après filtre

**États de chargement**
- Skeleton rows pour le tableau
- Spinner sur les filtres

**États d'erreur**
- Message d'erreur avec réessai
- Détail de l'erreur

**Responsive attendu**
- Mobile : Tableau en cards, filtres collapsibles
- Tablet : Tableau avec scroll horizontal
- Desktop : Tableau complet

---

### 4.6 Écran Paramètres

**Objectif**
Centraliser la configuration globale de la plateforme.

**Informations affichées**
- Onglets de navigation
- Formulaires de configuration
- Valeurs actuelles
- Messages d'aide contextuels

**Actions disponibles**
- Navigation par onglets
- Modification des seuils globaux
- Configuration des notifications email
- Configuration de la rétention des données
- Génération de jetons d'enrôlement
- Sauvegarde des modifications

**Composants**
- **Onglets** : Seuils, Notifications, Rétention, Enrôlement
- **Formulaires** : Inputs avec validation
- **Cards** : Groupement de paramètres
- **Boutons** : Sauvegarder, Annuler
- **Tooltips** : Aide contextuelle

**Organisation**
- Onglet 1 : Seuils d'alerte (CPU, RAM, Disque)
- Onglet 2 : Notifications email (destinataires, serveur SMTP)
- Onglet 3 : Rétention (alertes, heartbeats)
- Onglet 4 : Enrôlement (génération jetons)

**Navigation**
- Navigation par onglets
- Sauvegarde par onglet ou globale
- Breadcrumb : Dashboard > Paramètres

**Sections**
- **Seuils globaux** : CPU Warning/Critique, RAM Warning/Critique, Disque Warning/Critique
- **Notifications** : Email destinataires, configuration SMTP
- **Rétention** : Durée conservation alertes, durée conservation heartbeats
- **Enrôlement** : Liste des jetons générés, bouton générer

**Configuration**
- Inputs numériques avec validation
- Liste des destinataires (add/remove)
- Configuration SMTP (host, port, secure)
- Jetons avec date d'expiration

**Notifications**
- Liste des destinataires
- Bouton ajouter destinataire
- Bouton supprimer destinataire
- Test d'envoi email

**Seuils**
- Inputs CPU Warning/Critique (%)
- Inputs RAM Warning/Critique (%)
- Inputs Disque Warning/Critique (%)
- Validation des valeurs (Warning < Critique)

**Rétention**
- Input alertes (jours, max 365)
- Input heartbeats (jours, max 365)
- Message d'avertissement si modification

**Enrôlement**
- Liste des jetons actifs
- Date de génération
- Date d'expiration
- Bouton copier le jeton
- Bouton générer nouveau jeton

**Gestion globale**
- Sauvegarde avec feedback toast
- Annulation des modifications
- Validation avant sauvegarde

**États vides**
- **Aucun jeton** : Message "Aucun jeton actif"
- **Aucun destinataire** : Message "Aucun destinataire configuré"

**États de chargement**
- Spinner sur les boutons
- Skeleton des formulaires

**États d'erreur**
- Message d'erreur par champ
- Message d'erreur global

**Responsive attendu**
- Mobile : Onglets scrollables, formulaires empilés
- Tablet : Onglets complets, layout 2 colonnes
- Desktop : Layout complet

---

### 4.7 Écran Gestion des utilisateurs

**Objectif**
Gérer les comptes utilisateurs et leurs permissions.

**Informations affichées**
- Tableau des utilisateurs
- Nom, email, rôle, date de création
- Statut du compte

**Actions disponibles**
- Créer un nouvel utilisateur
- Modifier un utilisateur existant
- Supprimer un utilisateur
- Filtres et recherche

**Composants**
- **Tableau utilisateurs** : Colonnes triables
- **Bouton créer** : Header
- **Modal création** : Formulaire
- **Modal modification** : Formulaire
- **Modal suppression** : Confirmation

**Tableaux**
- Colonnes : Nom, Email, Rôle, Date création, Actions
- Tri sur nom, email, rôle
- Pagination

**Filtres**
- Recherche par nom ou email
- Filtre par rôle

**Actions**
- Créer : Bouton header
- Modifier : Icône par ligne
- Supprimer : Icône par ligne

**Profils**
- Administrateur
- Opérateur
- Lecture seule

**Responsive attendu**
- Mobile : Tableau en cards
- Desktop : Tableau complet

---

### 4.8 Écran Profil utilisateur

**Objectif**
Permettre à l'utilisateur de gérer ses informations personnelles.

**Informations affichées**
- Nom
- Email
- Rôle
- Date de création du compte

**Actions disponibles**
- Modifier le mot de passe
- Déconnexion

**Composants**
- Card informations
- Formulaire changement mot de passe
- Bouton déconnexion

**Responsive attendu**
- Mobile : Card centrée
- Desktop : Card avec fond décoratif

---

## 5. Dashboard

### KPIs

**KPI 1 : Agents en ligne**
- Nombre d'agents avec statut "En ligne"
- Badge vert si > 90%, orange si 70-90%, rouge si < 70%
- Tendance vs hier (flèche haut/bas)

**KPI 2 : Agents hors ligne**
- Nombre d'agents avec statut "Hors ligne"
- Badge rouge si > 10%, orange si 5-10%, vert si < 5%
- Clic → Liste filtrée agents hors ligne

**KPI 3 : Alertes actives**
- Nombre total d'alertes non acquittées
- Décomposé par gravité (Info/Warning/Critique)
- Clic → Liste alertes filtrée

**KPI 4 : Alertes critiques**
- Nombre d'alertes Critique non acquittées
- Badge rouge clignotant si > 0
- Clic → Liste alertes filtrée Critique

### Widgets

**Widget Liste des agents**
- Tableau compact des 10 derniers agents
- Colonnes : Nom, Statut, CPU, RAM, Alertes
- Badge statut coloré
- Progress bar CPU/RAM
- Clic → Détail agent

**Widget Alertes récentes**
- Liste des 5 dernières alertes
- Badge gravité
- Nom de l'agent
- Heure de l'alerte
- Clic → Détail agent

### Graphiques

**Note** : Les graphiques temporels sont prévus pour V1.1. En V1, utiliser des jauges et indicateurs statiques.

### Cartes

**Card Agent**
- Nom et hostname
- OS et version
- Statut (badge)
- Uptime
- Métriques (CPU, RAM, Disque en jauges)
- Alertes actives (badge avec nombre)

**Card Alerte**
- Type et gravité (badge)
- Agent concerné
- Message
- Heure
- Bouton acquitter

### Alertes

**Section Alertes du Dashboard**
- Titre "Alertes récentes"
- Liste compacte (5 items)
- Badge gravité
- Clic → Détail agent
- Bouton "Voir toutes" → Liste alertes

### Liste des agents

**Tableau principal**
- Colonnes : Nom, OS, Statut, CPU, RAM, Disque, Uptime, Alertes
- Tri sur toutes les colonnes
- Pagination
- Hover sur ligne → highlight

### Actions rapides

**Boutons rapides**
- "Générer jeton d'enrôlement" → Modal
- "Voir les alertes" → Liste alertes
- "Exporter les données" → Export CSV

### Disposition

**Layout Desktop**
- Header : Titre + actions rapides
- Row 1 : 4 KPIs côte à côte
- Row 2 : 2 colonnes
  - Col gauche : Liste des agents (70%)
  - Col droite : Alertes récentes (30%)

**Layout Tablet**
- Header : Titre + actions rapides
- Row 1 : 2x2 KPIs
- Row 2 : Liste des agents (pleine largeur)
- Row 3 : Alertes récentes (pleine largeur)

**Layout Mobile**
- Header : Titre + menu hamburger
- Row 1 : KPIs empilés
- Row 2 : Liste des agents (cards)
- Row 3 : Alertes récentes (cards)

### Priorités visuelles

**Hiérarchie**
1. KPIs (priorité haute)
2. Alertes critiques (priorité haute)
3. Liste des agents (priorité moyenne)
4. Alertes récentes (priorité basse)

**Couleurs**
- Vert : Tout va bien
- Orange : Attention requise
- Rouge : Action immédiate
- Bleu : Information

### Hiérarchie des informations

**Niveau 1**
- KPIs globaux
- Alertes critiques

**Niveau 2**
- Liste des agents
- Statut des agents

**Niveau 3**
- Métriques détaillées
- Alertes non critiques

---

## 6. Gestion des agents

### Liste

**Objectif**
Afficher tous les agents avec leurs métriques et permettre la navigation.

**Informations**
- Nom, hostname, OS
- Statut (en ligne, hors ligne, obsolète)
- CPU, RAM, Disque (pourcentages)
- Uptime
- Nombre d'alertes actives

**Actions**
- Clic sur ligne → Détail agent
- Tri sur toutes les colonnes
- Pagination

### Recherche

**Barre de recherche**
- Input text avec icône loupe
- Recherche en temps réel (debounce 300ms)
- Recherche sur nom et hostname
- Highlight des résultats

### Filtres

**Filtres avancés**
- OS : Windows, Linux, macOS (checkboxes)
- Statut : En ligne, Hors ligne, Obsolète (checkboxes)
- Alertes : Aucune, Info, Warning, Critique (checkboxes)
- Seuils personnalisés : Oui/Non (toggle)

**Application des filtres**
- Filtres cumulatifs (AND)
- Badge "X filtres actifs" si filtres appliqués
- Bouton "Réinitialiser" pour effacer

### Détail

Voir section 7 "Détail d'un agent"

### Configuration

**Accès**
- Bouton "Configurer" dans le détail agent
- Onglet "Configuration" dans le détail agent

**Champs**
- CPU Warning (%)
- CPU Critique (%)
- RAM Warning (%)
- RAM Critique (%)
- Disque Warning (%)
- Disque Critique (%)

**Validation**
- Warning < Critique
- Valeurs entre 0 et 100
- Message d'erreur si invalide

**Actions**
- Sauvegarder : Applique les seuils personnalisés
- Réinitialiser : Revient aux seuils globaux
- Annuler : Ferme sans sauvegarder

### Actions

**Actions rapides**
- Acquitter les alertes (Admin/Opérateur)
- Configurer les seuils (Admin)
- Révoquer l'agent (Admin)
- Supprimer l'agent (Admin)

### Suppression

**Modal de confirmation**
- Message d'avertissement
- Nom de l'agent concerné
- Bouton "Confirmer la suppression"
- Bouton "Annuler"

**Conséquences**
- L'agent est supprimé de la base de données
- L'agent reçoit un code 401
- L'agent doit être réinstallé pour se reconnecter

### Révocation

**Modal de confirmation**
- Message d'avertissement
- Nom de l'agent concerné
- Bouton "Confirmer la révocation"
- Bouton "Annuler"

**Conséquences**
- L'agent passe en statut "Révoqué"
- L'agent reçoit un code 401
- L'agent peut être réactivé par réenrôlement

### Enrôlement

**Génération du jeton**
- Accès via Paramètres > Enrôlement
- Bouton "Générer un jeton"
- Jeton affiché dans un modal
- Date d'expiration (24h)

**Modal de génération**
- Jeton généré (code)
- Date de génération
- Date d'expiration
- Bouton "Copier"
- Bouton "Fermer"

**Utilisation du jeton**
- Installation de l'agent avec le jeton
- L'agent s'enrôle automatiquement
- Le jeton est consommé (usage unique)

---

## 7. Détail d'un agent

### Organisation des informations

**Header**
- Nom de l'agent
- Hostname
- OS (badge)
- Statut (badge)
- Uptime
- Dernier heartbeat

**Onglets**
- Vue d'ensemble
- Métriques
- Alertes
- Configuration

### Sections

**Section Vue d'ensemble**
- Informations système
- Statut de connexion
- Alertes actives (résumé)

**Section Métriques**
- CPU (jauge + valeur)
- RAM (jauge + valeur)
- Disque (jauge + valeur)
- Uptime

**Section Alertes**
- Liste des alertes actives
- Historique des alertes

**Section Configuration**
- Seuils personnalisés
- Formulaire de modification

### Cartes

**Card Informations système**
- Hostname
- OS
- Version de l'agent
- Adresse IP
- Date d'enrôlement

**Card Statut**
- Statut actuel (badge)
- Dernier heartbeat
- Uptime
- Temps depuis dernier heartbeat

**Card Métriques**
- CPU : Jauge + pourcentage
- RAM : Jauge + pourcentage
- Disque : Jauge + pourcentage

### Affichage des télémétries

**CPU**
- Jauge circulaire (0-100%)
- Valeur numérique
- Badge si > seuil Warning/Critique
- Historique (si disponible en V1.1)

**RAM**
- Jauge circulaire (0-100%)
- Valeur numérique (Go utilisés / Go total)
- Badge si > seuil Warning/Critique
- Historique (si disponible en V1.1)

**Disque**
- Jauge linéaire (0-100%)
- Valeur numérique (Go utilisés / Go total)
- Badge si > seuil Warning/Critique
- Liste des partitions (si applicable)

### Organisation visuelle

**Layout Desktop**
- Header : Informations de base
- Row 1 : 3 colonnes (CPU, RAM, Disque)
- Row 2 : Onglets (contenu variable)

**Layout Mobile**
- Header : Informations de base
- Cards empilées (CPU, RAM, Disque)
- Onglets scrollables

### Actions disponibles

**Actions rapides**
- Acquitter les alertes (Admin/Opérateur)
- Configurer les seuils (Admin)
- Révoquer l'agent (Admin)
- Supprimer l'agent (Admin)
- Rafraîchir les données

### Historique

**Historique des alertes**
- Tableau dans l'onglet Alertes
- Colonnes : Type, Gravité, Date, Message, Statut
- Filtre par période
- Pagination

### Alertes

**Alertes actives**
- Liste dans l'onglet Alertes
- Badge gravité
- Message
- Bouton acquitter

### État

**Statut de l'agent**
- En ligne (vert)
- Hors ligne (rouge)
- Obsolète (gris)
- Révoqué (orange)

**Indicateurs**
- Badge de statut dans le header
- Dernier heartbeat
- Temps depuis dernier heartbeat

### Performance

**Métriques de performance**
- CPU : Pourcentage
- RAM : Pourcentage
- Disque : Pourcentage
- Uptime : Jours/heures

**Indicateurs visuels**
- Jauge colorée selon seuils
- Badge si anomalie détectée
- Tendance (si disponible)

---

## 8. Gestion des alertes

### Liste

**Objectif**
Afficher toutes les alertes avec filtrage avancé.

**Informations**
- Type d'alerte
- Gravité
- Agent concerné
- Date et heure
- Statut
- Message

**Actions**
- Acquitter (selon permissions)
- Voir l'agent
- Filtrer
- Exporter

### Filtres

**Filtres disponibles**
- Gravité : Info, Warning, Critique
- Type : Hors ligne, CPU, RAM, Disque
- Statut : Ouverte, Acquittée, Résolue
- Période : 24h, 7j, 30j, personnalisé
- Agent : Recherche par nom

**Interface des filtres**
- Barre de filtres collapsible
- Checkboxes pour les choix multiples
- Input texte pour la recherche
- Date picker pour la période personnalisée

### Badges

**Gravité**
- Info : Bleu (#3B82F6)
- Warning : Orange (#F59E0B)
- Critique : Rouge (#EF4444)

**Statut**
- Ouverte : Rouge (#EF4444)
- Acquittée : Gris (#6B7280)
- Résolue : Vert (#10B981)

**Type**
- Hors ligne : Violet (#8B5CF6)
- CPU : Jaune (#EAB308)
- RAM : Rose (#EC4899)
- Disque : Cyan (#06B6D4)

### Couleurs

**Fond des lignes**
- Aucune couleur par défaut
- Fond subtil selon gravité au hover
- Fond rouge clair pour Critique (optionnel)

**Texte**
- Noir par défaut
- Gris pour les métadonnées

### Gravité

**Info**
- Informationnel
- Pas d'action requise
- Peut être ignoré

**Warning**
- Attention requise
- Monitoring accru
- Intervention planifiée

**Critique**
- Action immédiate requise
- Notification email envoyée
- Priorité haute

### Acquittement

**Modal d'acquittement**
- Message de confirmation
- Champ commentaire (optionnel)
- Bouton "Confirmer"
- Bouton "Annuler"

**Permissions**
- Admin : Peut acquitter Info, Warning, Critique
- Opérateur : Peut acquitter Info, Warning uniquement
- Lecture seule : Ne peut rien acquitter

**Feedback**
- Toast de succès après acquittement
- Mise à jour de la liste
- Badge statut mis à jour

### Historique

**Conservation**
- 30 jours par défaut
- Archivage automatique
- Non modifiable en V1

**Affichage**
- Tableau avec toutes les alertes
- Filtre par période
- Export CSV

### Détails

**Détail d'une alerte**
- Type et gravité
- Agent concerné (clic → détail agent)
- Date et heure
- Message complet
- Statut
- Historique d'acquittement

### Actions possibles

**Sur une alerte**
- Acquitter (selon permissions)
- Voir l'agent concerné
- Filtrer par cet agent

**Sur la liste**
- Acquitter en lot (Admin)
- Exporter CSV
- Filtrer

---

## 9. Paramètres

### Organisation

**Navigation par onglets**
- Onglet 1 : Seuils d'alerte
- Onglet 2 : Notifications
- Onglet 3 : Rétention
- Onglet 4 : Enrôlement

**Layout**
- Sidebar d'onglets (gauche)
- Zone de contenu (droite)
- Boutons de sauvegarde (bas)

### Navigation

**Navigation interne**
- Clic sur onglet → changement de vue
- Sauvegarde par onglet
- Navigation sans perte de données non sauvegardées (confirmation)

### Sections

**Section Seuils**
- CPU Warning/Critique
- RAM Warning/Critique
- Disque Warning/Critique

**Section Notifications**
- Destinataires email
- Configuration SMTP

**Section Rétention**
- Conservation alertes
- Conservation heartbeats

**Section Enrôlement**
- Liste des jetons
- Génération de jetons

### Configuration

**Seuils d'alerte**
- Inputs numériques (0-100)
- Validation (Warning < Critique)
- Message d'aide contextuel

**Notifications**
- Liste des destinataires
- Configuration SMTP
- Bouton de test

**Rétention**
- Inputs numériques (jours)
- Validation (1-365)
- Message d'avertissement

**Enrôlement**
- Liste des jetons actifs
- Bouton générer
- Modal de génération

### Notifications

**Destinataires**
- Liste des emails
- Bouton ajouter
- Bouton supprimer
- Validation du format email

**Configuration SMTP**
- Host
- Port
- Secure (TLS/SSL)
- Authentification (username/password)
- Bouton de test d'envoi

### Seuils

**Seuils globaux**
- CPU Warning : 80%
- CPU Critique : 90%
- RAM Warning : 80%
- RAM Critique : 90%
- Disque Warning : 85%
- Disque Critique : 95%

**Seuils par agent**
- Surcharge des seuils globaux
- Configuration dans le détail agent
- Priorité sur les seuils globaux

### Rétention

**Alertes**
- Par défaut : 30 jours
- Modifiable : 1-365 jours
- Archivage automatique à 00h00 UTC

**Heartbeats**
- Par défaut : 7 jours
- Modifiable : 1-365 jours
- Suppression automatique à 01h00 UTC

### Enrôlement

**Génération de jetons**
- Bouton "Générer un jeton"
- Modal avec le jeton
- Date d'expiration (24h)
- Bouton copier

**Liste des jetons**
- Jeton (tronqué)
- Date de génération
- Date d'expiration
- Statut (actif/expiré)

### Gestion globale

**Sauvegarde**
- Bouton "Sauvegarder" par onglet
- Feedback toast de succès
- Validation avant sauvegarde

**Annulation**
- Bouton "Annuler" pour réinitialiser
- Confirmation si modifications non sauvegardées

**Validation**
- Validation des champs
- Messages d'erreur par champ
- Bouton sauvegarde désactivé si invalide

---

## 10. Gestion des utilisateurs

### Création

**Modal de création**
- Input Nom (texte)
- Input Email (email)
- Select Rôle (Admin, Opérateur, Lecture seule)
- Input Mot de passe (password)
- Input Confirmer mot de passe (password)
- Bouton "Créer"
- Bouton "Annuler"

**Validation**
- Nom : requis, min 2 caractères
- Email : requis, format valide
- Rôle : requis
- Mot de passe : min 8 caractères, 1 majuscule, 1 chiffre
- Confirmation : doit correspondre

### Modification

**Modal de modification**
- Input Nom (texte, pré-rempli)
- Input Email (email, pré-rempli)
- Select Rôle (pré-rempli)
- Bouton "Modifier"
- Bouton "Annuler"

**Note** : Le mot de passe ne peut être modifié que par l'utilisateur lui-même dans son profil.

### Suppression

**Modal de confirmation**
- Message d'avertissement
- Nom de l'utilisateur
- Bouton "Confirmer la suppression"
- Bouton "Annuler"

**Note** : La suppression est irréversible et tracée dans les logs.

### Permissions

**Tableau des permissions**
- Colonnes : Action, Admin, Opérateur, Lecture seule
- Lignes : Voir dashboard, Modifier paramètres, Acquitter alertes, etc.
- Checkmarks pour les permissions accordées

### Profils

**Administrateur**
- Tous les droits
- Gestion des utilisateurs
- Configuration globale

**Opérateur**
- Lecture sur tous les écrans
- Acquittement alertes Info/Warning
- Export CSV

**Lecture seule**
- Lecture uniquement
- Aucune action d'écriture

### Tableaux

**Tableau des utilisateurs**
- Colonnes : Nom, Email, Rôle, Date création, Actions
- Tri sur nom, email, rôle
- Pagination
- Actions : Modifier, Supprimer

### Filtres

**Filtres disponibles**
- Recherche par nom ou email
- Filtre par rôle

### Actions

**Actions disponibles**
- Créer un utilisateur (bouton header)
- Modifier un utilisateur (icône par ligne)
- Supprimer un utilisateur (icône par ligne)

---

## 11. Authentification

### Connexion

**Écran de connexion**
- Logo centré
- Input Email
- Input Mot de passe (avec toggle visibilité)
- Bouton "Se connecter"
- Lien "Mot de passe oublié"

**Validation**
- Email : format valide
- Mot de passe : requis

**États**
- Initial : Formulaire vide
- Validation : Feedback sur les champs
- Chargement : Spinner sur le bouton
- Erreur : Message d'erreur
- Succès : Redirection vers Dashboard

### Déconnexion

**Action**
- Bouton déconnexion dans le sidebar ou le header
- Modal de confirmation
- Redirection vers l'écran de connexion

**Feedback**
- Toast de succès
- Session terminée

### Écran oublié

**Note** : Non implémenté en V1. Afficher un message "Fonctionnalité non disponible" avec un lien vers l'administrateur.

### Messages

**Messages d'erreur**
- "Identifiants invalides"
- "Compte désactivé"
- "Erreur de connexion"

**Messages de succès**
- "Connexion réussie"
- "Déconnexion réussie"

### Validation

**Validation du formulaire**
- Email : format valide
- Mot de passe : requis
- Feedback en temps réel

### États

**États de l'écran**
- Initial
- Validation
- Chargement
- Erreur
- Succès

---

## 12. Tous les composants UI

### Buttons

**Primary Button**
- Utilisation : Action principale
- Style : Fond bleu, texte blanc
- États : Default, Hover, Active, Disabled, Loading

**Secondary Button**
- Utilisation : Action secondaire
- Style : Fond transparent, bordure bleue, texte bleu
- États : Default, Hover, Active, Disabled

**Danger Button**
- Utilisation : Action destructive
- Style : Fond rouge, texte blanc
- États : Default, Hover, Active, Disabled

**Ghost Button**
- Utilisation : Action tertiaire
- Style : Fond transparent, texte gris
- États : Default, Hover, Active, Disabled

**Icon Button**
- Utilisation : Action avec icône seule
- Style : Fond transparent, icône
- États : Default, Hover, Active, Disabled

### Cards

**Card standard**
- Fond blanc
- Bordure subtile
- Ombre légère
- Coins arrondis (8px)

**Card KPI**
- Fond blanc
- Bordure gauche colorée selon statut
- Ombre légère
- Coins arrondis (8px)

**Card agent**
- Fond blanc
- Bordure subtile
- Hover : ombre accentuée
- Coins arrondis (8px)

### Tables

**Table standard**
- Fond blanc
- Bordure subtile
- Header gris clair
- Lignes alternées (optionnel)
- Hover sur ligne

**Table compact**
- Hauteur de ligne réduite
- Padding réduit'
- Pour les listes denses

**Table avec actions**
- Colonne actions à droite
- Icônes d'action
- Hover sur ligne

### Charts

**Note** : Non implémenté en V1. Prévu pour V1.1.

### Badges

**Badge gravité**
- Info : Bleu (#3B82F6)
- Warning : Orange (#F59E0B)
- Critique : Rouge (#EF4444)
- Texte blanc
- Coins arrondis (12px)

**Badge statut**
- En ligne : Vert (#10B981)
- Hors ligne : Rouge (#EF4444)
- Obsolète : Gris (#6B7280)
- Texte blanc
- Coins arrondis (12px)

**Badge OS**
- Windows : Bleu (#3B82F6)
- Linux : Orange (#F59E0B)
- macOS : Violet (#8B5CF6)
- Texte blanc
- Coins arrondis (12px)

### Progress bars

**Progress bar standard**
- Fond gris clair
- Barre de progression colorée
- Coins arrondis (4px)
- Animation de remplissage

**Progress bar CPU**
- Vert si < 80%
- Orange si 80-90%
- Rouge si > 90%

**Progress bar RAM**
- Vert si < 80%
- Orange si 80-90%
- Rouge si > 90%

**Progress bar Disque**
- Vert si < 85%
- Orange si 85-95%
- Rouge si > 95%

### Dropdown

**Dropdown standard**
- Bouton avec flèche
- Liste déroulante
- Hover sur items
- Sélection highlight

**Dropdown multi-select**
- Checkboxes
- Bouton "Appliquer"
- Badge de comptage

### Sidebar

**Sidebar fixe**
- Fond gris foncé
- Logo en haut
- Navigation principale
- Profil utilisateur en bas
- Largeur : 250px

**Items de navigation**
- Icône + texte
- Hover : fond plus clair
- Actif : fond bleu, texte blanc
- Badge de notification si alertes

### Header

**Header standard**
- Fond blanc
- Breadcrumb
- Titre de page
- Actions à droite
- Hauteur : 64px

**Breadcrumbs**
- Fil d'ariane
- Séparateur : "/"
- Lien cliquable
- Dernier élément non cliquable

### Search

**Input recherche**
- Icône loupe
- Placeholder
- Debounce 300ms
- Clear button

### Modal

**Modal standard**
- Fond semi-transparent
- Card centrée
- Bouton fermer (X)
- Footer avec actions

**Modal confirmation**
- Titre d'avertissement
- Message
- Boutons Annuler / Confirmer

### Toast

**Toast succès**
- Fond vert
- Icône check
- Message
- Auto-dismiss 5s

**Toast erreur**
- Fond rouge
- Icône erreur
- Message
- Auto-dismiss 5s

**Toast info**
- Fond bleu
- Icône info
- Message
- Auto-dismiss 5s

### Notification

**Dropdown notification**
- Icône cloche dans header
- Badge rouge si non lu
- Liste des notifications
- Clic → dismiss

### Tabs

**Tabs standard**
- Onglets horizontaux
- Badge de comptage
- Contenu en dessous
- Active : fond bleu, texte blanc

### Pagination

**Pagination standard**
- Boutons Previous/Next
- Numéros de page
- Page active highlight
- Jump to page (input)

### Empty state

**Empty state standard**
- Illustration
- Titre
- Description
- CTA (optionnel)

### Loader

**Spinner standard**
- Cercle animé
- Couleur bleue
- Taille variable (sm, md, lg)

**Skeleton**
- Fond gris clair
- Animation shimmer
- Forme du contenu à charger

### Tooltip

**Tooltip standard**
- Fond noir
- Texte blanc
- Apparition au hover
- Délai 500ms

### Avatar

**Avatar standard**
- Cercle
- Initiales ou image
- Fond coloré
- Taille variable (sm, md, lg)

### Status

**Status indicator**
- Point coloré
- Vert : en ligne
- Rouge : hors ligne
- Gris : inconnu
- Animation pulse si en ligne

---

## 13. Toutes les couleurs

### Palette

**Primary**
- Bleu principal : #3B82F6
- Bleu clair : #60A5FA
- Bleu foncé : #2563EB

**Secondary**
- Gris clair : #F3F4F6
- Gris moyen : #9CA3AF
- Gris foncé : #4B5563

**Accent**
- Violet : #8B5CF6
- Rose : #EC4899
- Cyan : #06B6D4

### Couleurs système

**Succès**
- Vert : #10B981
- Vert clair : #34D399
- Vert foncé : #059669

**Erreur**
- Rouge : #EF4444
- Rouge clair : #F87171
- Rouge foncé : #DC2626

**Warning**
- Orange : #F59E0B
- Orange clair : #FBBF24
- Orange foncé : #D97706

**Info**
- Bleu : #3B82F6
- Bleu clair : #60A5FA
- Bleu foncé : #2563EB

**Critique**
- Rouge vif : #DC2626
- Fond rouge clair : #FEE2E2

### Dark Mode

**Note** : Non implémenté en V1. Prévu pour les versions futures.

---

## 14. Typographie

### Hiérarchie

**H1 - Titre principal**
- Taille : 32px
- Poids : 700 (Bold)
- Couleur : #111827

**H2 - Titre de section**
- Taille : 24px
- Poids : 600 (Semi-bold)
- Couleur : #111827

**H3 - Sous-titre**
- Taille : 20px
- Poids : 600 (Semi-bold)
- Couleur : #111827

**H4 - Titre de card**
- Taille : 16px
- Poids : 600 (Semi-bold)
- Couleur : #111827

**Body - Texte standard**
- Taille : 14px
- Poids : 400 (Regular)
- Couleur : #374151

**Small - Texte secondaire**
- Taille : 12px
- Poids : 400 (Regular)
- Couleur : #6B7280

**Caption - Légende**
- Taille : 11px
- Poids : 400 (Regular)
- Couleur : #9CA3AF

### Tailles

- Display : 48px (utilisé pour les KPIs)
- H1 : 32px
- H2 : 24px
- H3 : 20px
- H4 : 16px
- Body : 14px
- Small : 12px
- Caption : 11px

### Poids

- Light : 300
- Regular : 400
- Medium : 500
- Semi-bold : 600
- Bold : 700

### Espacements

**Line-height**
- Display : 1.2
- H1-H3 : 1.3
- H4 : 1.4
- Body : 1.5
- Small : 1.4
- Caption : 1.3

**Letter-spacing**
- H1-H3 : -0.02em
- Body : 0
- Small : 0.01em

---

## 15. Iconographie

### Famille d'icônes

**Librairie recommandée**
- Lucide React (pour React)
- Heroicons (alternative)
- Material Icons (alternative)

### Style

**Caractéristiques**
- Outline (contour) par défaut
- Taille : 16px, 20px, 24px
- Épaisseur : 2px
- Coins arrondis

**Variants**
- Solid (rempli) pour les actions principales
- Outline pour les actions secondaires

### Utilisation

**Navigation**
- Dashboard : LayoutDashboard
- Agents : Server
- Alertes : Bell
- Paramètres : Settings
- Utilisateurs : Users
- ProfilUser : User

**Actions**
- Ajouter : Plus
- Modifier : Pencil
- Supprimer : Trash
- Sauvegarder : Save
- Annuler : X
- Rafraîchir : Refresh
- Exporter : Download
- Rechercher : Search
- Filtrer : Filter

**Statuts**
- Succès : CheckCircle
- Erreur : XCircle
- Warning : AlertTriangle
- Info : Info
- En ligne : Wifi
- Hors ligne : WifiOff

**OS**
- Windows : Monitor
- Linux : Terminal
- macOS : Apple

---

## 16. Espacements

### Grille

**Grid system**
- Base : 8px
- Multiples : 8, 16, 24, 32, 48, 64, 96

**Utilisation**
- xs : 4px
- sm : 8px
- md : 16px
- lg : 24px
- xl : 32px
- 2xl : 48px
- 3xl : 64px

### Marges

**Composants**
- Card : 16px
- Card interne : 12px
- Section : 24px
- Page : 32px

### Padding

**Composants**
- Button : 12px 24px
- Input : 12px 16px
- Card : 16px
- Table cell : 12px 16px

### Rayons

**Border radius**
- sm : 4px
- md : 8px
- lg : 12px
- xl : 16px
- full : 9999px

**Utilisation**
- Button : 8px
- Card : 8px
- Input : 8px
- Badge : 12px
- Avatar : full

### Ombres

**Shadows**
- sm : 0 1px 2px rgba(0,0,0,0.05)
- md : 0 4px 6px rgba(0,0,0,0.1)
- lg : 0 10px 15px rgba(0,0,0,0.1)
- xl : 0 20px 25px rgba(0,0,0,0.15)

**Utilisation**
- Card : sm
- Modal : lg
- Dropdown : md
- Tooltip : sm

### Élévation

**Niveaux d'élévation**
- Base : 0 (pas d'ombre)
- Elevé 1 : sm
- Elevé 2 : md
- Elevé 3 : lg
- Elevé 4 : xl

**Utilisation**
- Page : 0
- Card : 1
- Modal : 3
- Dropdown : 2

---

## 17. UX

### Navigation

**Principes**
- Navigation claire et prévisible
- Breadcrumb pour le contexte
- Raccourcis clavier (optionnel)
- Liens visibles et identifiables

**Feedback**
- Highlight de l'élément actif
- Hover sur les éléments interactifs
- Transition fluide entre les pages

### Feedback

**Actions**
- Toast après chaque action
- Spinner pendant le chargement
- Message d'erreur clair
- Confirmation pour les actions destructives

**Validation**
- Validation en temps réel
- Messages d'erreur par champ
- Bouton désactivé si invalide

### Confirmation

**Actions destructives**
- Modal de confirmation
- Message d'avertissement clair
- Nom de l'élément concerné
- Bouton "Annuler" prominent

**Actions irréversibles**
- Double confirmation (optionnel)
- Message "Cette action est irréversible"
- Délai avant confirmation (optionnel)

### Prévention des erreurs

**Validation**
- Validation des entrées
- Messages d'erreur clairs
- Suggestions de correction

**Guidance**
- Tooltips d'aide
- Messages d'aide contextuels
- Exemples de format

### Accessibilité

**Contraste**
- Ratio de contraste minimum 4.5:1
- Texte sur fond clair
- Texte sur fond foncé

**Navigation clavier**
- Tab pour naviguer
- Enter pour valider
- Escape pour annuler
- Focus visible

**Screen readers**
- Labels sur les inputs
- Alt text sur les images
- ARIA labels sur les icônes

**Taille des cibles**
- Minimum 44x44px pour les boutons
- Espacement suffisant entre les éléments

### Clarté

**Langage**
- Terminologie cohérente
- Phrases courtes et simples
- Éviter le jargon technique

**Hiérarchie**
- Information importante en premier
- Regroupement logique
- Espacement pour la séparation

### Performance perçue

**Chargement**
- Skeleton loaders
- Spinners pour les actions
- Indication de progression

**Transitions**
- Animations fluides
- Durée < 300ms
- Easing naturel

### Hiérarchie visuelle

**Taille**
- Éléments importants plus grands
- Titres hiérarchiques
- Échelle cohérente

**Couleur**
- Couleur pour l'accentuation
- Utilisation modérée
- Signification cohérente

**Position**
- Éléments importants en haut
- Actions principales à gauche
- Contenu centré

---

## 18. États

### Loading

**Spinner**
- Cercle animé
- Couleur bleue
- Taille variable

**Skeleton**
- Fond gris clair
- Animation shimmer
- Forme du contenu

**Progress bar**
- Barre de progression
- Pourcentage affiché
- Animation de remplissage

### Erreur

**Message d'erreur**
- Fond rouge clair
- Icône erreur
- Message descriptif
- Bouton "Réessayer"

**État d'erreur**
- Illustration d'erreur
- Titre "Une erreur est survenue"
- Description
- Bouton "Réessayer"

### Vide

**Empty state**
- Illustration
- Titre
- Description
- CTA (optionnel)

**Exemples**
- Aucun agent : Illustration + "Aucun agent déployé"
- Aucune alerte : Illustration + "Tout va bien"
- Aucun résultat : "Aucun résultat pour votre recherche"

### Succès

**Toast de succès**
- Fond vert
- Icône check
- Message
- Auto-dismiss

**État de succès**
- Illustration de succès
- Titre
- Description
- Bouton "Continuer"

### Aucune donnée

**Indicateur**
- Tiret (-)
- Texte "N/A"
- Gris clair

**Utilisation**
- Tableau sans donnée
- Métrique non disponible

### Agent hors ligne

**Indicateur**
- Badge rouge "Hors ligne"
- Icône WifiOff
- Temps depuis dernier heartbeat

**Actions**
- Message d'avertissement
- Pas de métriques disponibles
- Bouton "Rafraîchir"

### Serveur inaccessible

**Indicateur**
- Message d'erreur
- Illustration
- Bouton "Réessayer"

**Actions**
- Retry automatique (optionnel)
- Notification à l'utilisateur

---

## 19. Animations

### Transitions

**Page transitions**
- Fade in/out
- Durée : 200ms
- Easing : ease-in-out

**Component transitions**
- Slide up/down
- Durée : 150ms
- Easing : ease-out

### Hover

**Button hover**
- Fond plus clair/sombre
- Durée : 150ms
- Easing : ease-out

**Card hover**
- Ombre accentuée
- Durée : 200ms
- Easing : ease-out

**Link hover**
- Soulignement
- Changement de couleur
- Durée : 150ms

### Focus

**Input focus**
- Bordure bleue
- Ombre légère
- Durée : 150ms

**Button focus**
- Bordure bleue
- Ombre légère
- Durée : 150ms

### Feedback

**Toast appearance**
- Slide in from right
- Durée : 300ms
- Easing : ease-out

**Modal appearance**
- Fade in + scale
- Durée : 200ms
- Easing : ease-out

### Micro-interactions

**Button click**
- Scale down (0.95)
- Durée : 100ms
- Easing : ease-out

**Checkbox toggle**
- Animation de coche
- Durée : 150ms
- Easing : ease-out

**Switch toggle**
- Animation de glissement
- Durée : 200ms
- Easing : ease-out

### Animations autorisées

- Transitions de page (fade, slide)
- Hover effects (fond, ombre)
- Focus states (bordure, ombre)
- Toast notifications (slide in)
- Modal appearance (fade, scale)
- Button click (scale)
- Loading spinners
- Skeleton loaders
- Progress bars

### Animations interdites

- Animations de texte (typing, bouncing)
- Animations de fond (gradient, pattern)
- Animations d'icônes (rotation, bounce)
- Animations de layout (shuffle, reordering)
- Animations de scroll (parallax)
- Animations de particules

---

## 20. Design System

### Naming

**Convention de nommage**
- Components : PascalCase (Button, Card)
- Variants : camelCase (primary, secondary)
- Modifiers : camelCase (disabled, loading)
- States : PascalCase (Error, Success)

**Exemples**
- ButtonPrimary
- ButtonSecondary
- ButtonDanger
- CardKPI
- CardAgent

### Tokens

**Color tokens**
- color-primary-500
- color-success-500
- color-error-500
- color-warning-500
- color-info-500

**Spacing tokens**
- spacing-xs (4px)
- spacing-sm (8px)
- spacing-md (16px)
- spacing-lg (24px)
- spacing-xl (32px)

**Typography tokens**
- font-size-h1 (32px)
- font-size-body (14px)
- font-weight-bold (700)
- line-height-body (1.5)

**Border radius tokens**
- radius-sm (4px)
- radius-md (8px)
- radius-lg (12px)
- radius-full (9999px)

**Shadow tokens**
- shadow-sm
- shadow-md
- shadow-lg
- shadow-xl

### Composants

**Structure des composants**
- Props documentées
- Variants exposées
- Slots pour le contenu
- Events pour les interactions

**Exemple : Button**
```jsx
<Button
  variant="primary"
  size="medium"
  disabled={false}
  loading={false}
  onClick={handleClick}
>
  Label
</Button>
```

### Règles

**Composition**
- Composants réutilisables
- Props cohérentes
- Slots flexibles

**Accessibilité**
- Keyboard navigation
- Screen reader support
- Focus management

**Performance**
- Lazy loading (optionnel)
- Code splitting (optionnel)
- Tree shaking (optionnel)

### Réutilisabilité

**Principes**
- DRY (Don't Repeat Yourself)
- Composants génériques
- Props flexibles
- Slots pour la personnalisation

**Exemples**
- Card : Contenu générique
- Table : Colonnes configurables
- Modal : Contenu via slot

---

## 21. Inspirations

### Datadog

**Points intéressants**
- Dashboard dense mais organisé
- Utilisation efficace de l'espace
- Graphiques clairs et lisibles
- Navigation par onglets intuitive
- Filtres puissants mais accessibles

**Pourquoi pertinent**
- Plateforme de monitoring similaire
- Gestion d'alertes efficace
- Interface dense mais claire

**À ne pas copier**
- Complexité excessive des graphiques
- Nombreux menus déroulants

### Grafana

**Points intéressants**
- Personnalisation du dashboard
- Widgets variés et flexibles
- Exploration des données intuitive
- Mode dark bien conçu

**Pourquoi pertinent**
- Plateforme de supervision
- Visualisation de métriques
- Gestion de dashboards

**À ne pas copier**
- Complexité de configuration
- Courbe d'apprentissage élevée

### Linear

**Points intéressants**
- Interface minimaliste et épurée
- Navigation fluide et rapide
- Utilisation de l'espace blanc
- Typographie cohérente

**Pourquoi pertinent**
- Expérience utilisateur moderne
- Navigation intuitive
- Design system cohérent

**À ne pas copier**
- Minimalisme excessif (manque d'informations)

### Atlassian

**Points intéressants**
- Navigation par produits claire
- Gestion des permissions intuitive
- Interface cohérente entre produits
- Documentation intégrée

**Pourquoi pertinent**
- Gestion d'utilisateurs et permissions
- Navigation multi-produits
- Cohérence de l'interface

**À ne pas copier**
- Navigation parfois complexe
- Trop de menus

### Microsoft Azure

**Points intéressants**
- Dashboard avec widgets configurables
- Gestion des ressources claire
- Filtres puissants
- Documentation contextuelle

**Pourquoi pertinent**
- Gestion d'infrastructure
- Dashboard de ressources
- Filtres avancés

**À ne pas copier**
- Interface parfois lourde
- Trop d'informations

### GitHub

**Points intéressants**
- Navigation simple et efficace
- Utilisation de badges
- Actions rapides accessibles
- Interface cohérente

**Pourquoi pertinent**
- Gestion d'utilisateurs
- Navigation simple
- Actions rapides

**À ne pas copier**
- Fonctionnalités trop spécifiques

### Stripe Dashboard

**Points intéressants**
- Interface moderne et épurée
- Utilisation de l'espace
- Actions rapides bien placées
- Feedback utilisateur clair

**Pourquoi pertinent**
- Dashboard moderne
- Actions rapides
- Feedback utilisateur

**À ne pas copier**
- Spécificités métier

---

## 22. Design Tokens

Les Design Tokens sont les variables fondamentales qui constituent la base du Design System. Ils garantissent la cohérence visuelle et facilitent la maintenance et l'évolutivité de l'interface.

### Border Radius

**XS - 2px**
- Utilisation : Badges, tags, petits éléments
- Utilité : Coins très légèrement arrondis pour les éléments compacts

**SM - 4px**
- Utilisation : Inputs, boutons small, tooltips
- Utilité : Arrondi subtil pour les éléments interactifs

**MD - 8px**
- Utilisation : Cards, boutons standard, modals
- Utilité : Arrondi standard pour les composants principaux

**LG - 12px**
- Utilisation : Badges de statut, avatars, boutons large
- Utilité : Arrondi prononcé pour les éléments importants

**XL - 16px**
- Utilisation : Cards hero, sections importantes
- Utilité : Arrondi très prononcé pour les éléments de mise en valeur

**Full - 9999px**
- Utilisation : Avatars, badges circulaires, pills
- Utilité : Création de formes parfaitement circulaires

### Espacements

**4px - spacing-xs**
- Utilisation : Espacement entre éléments très proches (icon + texte)
- Utilité : Création de relations visuelles étroites

**8px - spacing-sm**
- Utilisation : Padding interne des inputs, buttons small
- Utilité : Espacement minimal pour les éléments compacts

**12px - spacing-md**
- Utilisation : Padding standard des composants, gap entre items
- Utilité : Espacement de base pour la plupart des composants

**16px - spacing-lg**
- Utilisation : Padding des cards, gap entre sections
- Utilité : Espacement confortable pour les conteneurs

**24px - spacing-xl**
- Utilisation : Marges entre sections, gap entre cards
- Utilité : Séparation visuelle claire des sections

**32px - spacing-2xl**
- Utilisation : Marges des pages, gap entre blocs majeurs
- Utilité : Séparation importante des zones de contenu

**48px - spacing-3xl**
- Utilisation : Marges des sections hero, espacements verticaux majeurs
- Utilité : Création de respiration visuelle dans les layouts

**64px - spacing-4xl**
- Utilisation : Marges des containers principaux, espacements exceptionnels
- Utilité : Séparation maximale pour les éléments isolés

### Ombres

**Small - shadow-sm**
- Valeur : `0 1px 2px rgba(0, 0, 0, 0.05)`
- Utilisation : Cards au repos, tooltips, dropdowns
- Utilité : Élévation subtile pour les éléments proches de la surface

**Medium - shadow-md**
- Valeur : `0 4px 6px rgba(0, 0, 0, 0.1)`
- Utilisation : Cards au hover, modals, menus déroulants
- Utilité : Élévation moyenne pour les éléments interactifs

**Large - shadow-lg**
- Valeur : `0 10px 15px rgba(0, 0, 0, 0.1)`
- Utilisation : Modals, dropdowns ouverts, cards actives
- Utilité : Élévation prononcée pour les éléments superposés

**Extra Large - shadow-xl**
- Valeur : `0 20px 25px rgba(0, 0, 0, 0.15)`
- Utilisation : Modals de confirmation, tooltips persistants
- Utilité : Élévation maximale pour les éléments les plus importants

### Durées des transitions

**Fast - 150ms**
- Utilisation : Hover states, focus states, micro-interactions
- Utilité : Réactivité immédiate pour les interactions légères

**Normal - 200ms**
- Utilisation : Transitions de composants, ouvertures de dropdowns
- Utilité : Durée standard pour les transitions courantes

**Slow - 300ms**
- Utilisation : Apparition de modals, transitions de page, toasts
- Utilité : Durée confortable pour les transitions majeures

**Extra Slow - 500ms**
- Utilisation : Animations complexes, transitions de layout
- Utilité : Durée prolongée pour les animations sophistiquées

**Easing**
- ease-out : Pour les transitions d'apparition
- ease-in : Pour les transitions de disparition
- ease-in-out : Pour les transitions bidirectionnelles

### Z-index principaux

**0 - z-base**
- Utilisation : Contenu de base, éléments non superposés
- Utilité : Niveau par défaut du contenu

**10 - z-dropdown**
- Utilisation : Dropdowns, tooltips, popovers
- Utilité : Éléments superposés au contenu

**20 - z-sticky**
- Utilisation : Headers sticky, sidebar fixe
- Utilité : Éléments fixes au défilement

**30 - z-modal**
- Utilisation : Modals, dialogues, overlays
- Utilité : Éléments modaux superposés

**40 - z-modal-backdrop**
- Utilisation : Fond des modals, overlays
- Utilité : Arrière-plan des éléments modaux

**50 - z-toast**
- Utilisation : Toasts, notifications, snackbar
- Utilité : Éléments de notification au-dessus de tout

**100 - z-max**
- Utilisation : Éléments d'urgence, alerts critiques
- Utilité : Niveau maximum pour les éléments prioritaires

### Opacités

**0% - opacity-0**
- Utilisation : État invisible, éléments masqués
- Utilité : Disparition complète des éléments

**25% - opacity-25**
- Utilisation : État désactivé, placeholders
- Utilité : Indication de non-disponibilité

**50% - opacity-50**
- Utilisation : État de chargement, éléments secondaires
- Utilité : Atténuation modérée

**75% - opacity-75**
- Utilisation : Hover states, éléments semi-actifs
- Utilité : Atténuation légère

**100% - opacity-100**
- Utilisation : État normal, éléments actifs
- Utilité : Opacité par défaut

### Largeurs maximales des conteneurs

**sm - 640px**
- Utilisation : Conteneurs mobiles, small cards
- Utilité : Largeur maximale pour les contenus compacts

**md - 768px**
- Utilisation : Conteneurs tablet, cards standard
- Utilité : Largeur maximale pour les contenus moyens

**lg - 1024px**
- Utilisation : Conteneurs desktop, layouts standard
- Utilité : Largeur maximale pour les contenus principaux

**xl - 1280px**
- Utilisation : Conteneurs wide desktop, layouts larges
- Utilité : Largeur maximale pour les contenus étendus

**2xl - 1536px**
- Utilisation : Conteneurs extra wide, hero sections
- Utilité : Largeur maximale pour les contenus exceptionnels

**full - 100%**
- Utilisation : Conteneurs pleine largeur, backgrounds
- Utilité : Largeur maximale pour les contenus full-width

---

## 23. Responsive Strategy

La stratégie responsive définit comment l'interface s'adapte aux différentes tailles d'écran. Même si la V1 est principalement orientée Desktop, il est essentiel de définir les règles pour les futures versions.

### Résolutions supportées

**Résolution minimale supportée**
- Largeur : 1024px
- Utilisation : Desktop standard
- Justification : Expérience optimale pour les administrateurs et opérateurs

**Résolution recommandée**
- Largeur : 1280px
- Utilisation : Desktop large
- Justification : Expérience confortable avec tous les éléments visibles

**Résolution maximale**
- Largeur : 1920px
- Utilisation : Desktop extra large
- Justification : Support des écrans haute résolution sans dégradation

**Résolutions mobiles (futures versions)**
- Small : 320px (mobile portrait)
- Medium : 375px (mobile standard)
- Large : 414px (mobile large)
- Tablet : 768px (tablet portrait)

### Comportement de la Sidebar

**Desktop (≥ 1280px)**
- État : Fixe, toujours visible
- Largeur : 250px
- Comportement : Navigation permanente

**Tablet (768px - 1279px)**
- État : Collapsible
- Largeur : 250px (ouverte) / 64px (fermée)
- Comportement : Toggle via bouton hamburger

**Mobile (< 768px)**
- État : Overlay (future version)
- Largeur : 100% de l'écran
- Comportement : Slide-in depuis la gauche

### Comportement des tableaux

**Desktop (≥ 1280px)**
- Affichage : Tableau complet avec toutes les colonnes
- Pagination : 20/50/100 items par page
- Tri : Sur toutes les colonnes

**Tablet (768px - 1279px)**
- Affichage : Tableau avec scroll horizontal si nécessaire
- Pagination : 20 items par page par défaut
- Tri : Sur les colonnes principales

**Mobile (< 768px)**
- Affichage : Transformation en cards (future version)
- Pagination : 10 items par page
- Tri : Limité aux colonnes essentielles

### Comportement des cartes

**Desktop (≥ 1280px)**
- Layout : Grille 3-4 colonnes
- Espacement : 24px entre les cartes
- Hover : Ombre accentuée

**Tablet (768px - 1279px)**
- Layout : Grille 2 colonnes
- Espacement : 16px entre les cartes
- Hover : Ombre accentuée

**Mobile (< 768px)**
- Layout : 1 colonne (future version)
- Espacement : 12px entre les cartes
- Hover : Pas d'effet (touch)

### Comportement des graphiques

**Desktop (≥ 1280px)**
- Taille : Largeur complète du conteneur
- Hauteur : 300-400px
- Interactivité : Tooltips au hover, zoom

**Tablet (768px - 1279px)**
- Taille : Largeur complète du conteneur
- Hauteur : 250-300px
- Interactivité : Tooltips au touch

**Mobile (< 768px)**
- Taille : Largeur complète du conteneur (future version)
- Hauteur : 200-250px
- Interactivité : Tooltips au touch, swipe

### Règles responsive pour les futures versions

**Mobile-first approach**
- Concevoir d'abord pour mobile
- Progressively enhance pour desktop
- Optimiser les performances sur mobile

**Touch targets**
- Taille minimale : 44x44px
- Espacement : 8px entre les targets
- Feedback visuel au touch

**Typography scaling**
- Base : 16px sur mobile
- Desktop : 14-16px selon le contexte
- Line-height : 1.5 sur mobile, 1.4-1.5 sur desktop

**Content prioritization**
- Mobile : Contenu essentiel uniquement
- Tablet : Contenu essentiel + secondaire
- Desktop : Contenu complet

**Performance**
- Mobile : Optimisation agressive (lazy loading, code splitting)
- Tablet : Optimisation modérée
- Desktop : Performance standard

---

## 24. Empty States

Les Empty States décrivent l'interface lorsqu'il n'existe aucune donnée. Ils doivent être informatifs, engageants et orienter l'utilisateur vers l'action appropriée.

### Aucun agent

**Illustration**
- Icône : Server ou Monitor
- Style : Outline, taille 64px
- Couleur : Gris CBC (#777777)

**Titre**
- Texte : "Aucun agent déployé"
- Style : H3, Gris CBC (#777777)

**Description**
- Texte : "Commencez par générer un jeton d'enrôlement pour installer votre premier agent."
- Style : Body, Gris moyen (#9CA3AF)

**Action principale**
- Bouton : "Générer un jeton d'enrôlement"
- Style : Primary (Or CBC #D0B335)
- Action : Ouvre le modal de génération de jeton

### Aucune alerte

**Illustration**
- Icône : CheckCircle ou Shield
- Style : Outline, taille 64px
- Couleur : Vert succès (#10B981)

**Titre**
- Texte : "Tout va bien"
- Style : H3, Vert succès (#10B981)

**Description**
- Texte : "Aucune alerte active. Votre parc informatique fonctionne normalement."
- Style : Body, Gris moyen (#9CA3AF)

**Action principale**
- Aucune (état positif)

### Aucune notification

**Illustration**
- Icône : BellOff
- Style : Outline, taille 64px
- Couleur : Gris CBC (#777777)

**Titre**
- Texte : "Aucune notification"
- Style : H3, Gris CBC (#777777)

**Description**
- Texte : "Vous n'avez aucune notification pour le moment."
- Style : Body, Gris moyen (#9CA3AF)

**Action principale**
- Aucune

### Aucune recherche

**Illustration**
- Icône : SearchX
- Style : Outline, taille 64px
- Couleur : Gris CBC (#777777)

**Titre**
- Texte : "Aucun résultat"
- Style : H3, Gris CBC (#777777)

**Description**
- Texte : "Aucun résultat ne correspond à votre recherche. Essayez avec d'autres critères."
- Style : Body, Gris moyen (#9CA3AF)

**Action principale**
- Bouton : "Effacer les filtres"
- Style : Secondary
- Action : Réinitialise les filtres et la recherche

### Aucun utilisateur

**Illustration**
- Icône : Users
- Style : Outline, taille 64px
- Couleur : Gris CBC (#777777)

**Titre**
- Texte : "Aucun utilisateur"
- Style : H3, Gris CBC (#777777)

**Description**
- Texte : "Aucun utilisateur n'est enregistré. Créez le premier utilisateur pour commencer."
- Style : Body, Gris moyen (#9CA3AF)

**Action principale**
- Bouton : "Créer un utilisateur"
- Style : Primary (Or CBC #D0B335)
- Action : Ouvre le modal de création d'utilisateur

### Aucun résultat

**Illustration**
- Icône : FileX ou SearchX
- Style : Outline, taille 64px
- Couleur : Gris CBC (#777777)

**Titre**
- Texte : "Aucun résultat trouvé"
- Style : H3, Gris CBC (#777777)

**Description**
- Texte : "Aucun résultat ne correspond à vos critères de recherche."
- Style : Body, Gris moyen (#9CA3AF)

**Action principale**
- Bouton : "Réinitialiser les filtres"
- Style : Secondary
- Action : Efface tous les filtres actifs

---

## 25. Loading States

Les Loading States indiquent à l'utilisateur que l'application est en train de charger des données. Ils doivent être clairs, cohérents et donner une perception de performance.

### Skeleton Loading

**Utilisation**
- Tableaux avec beaucoup de données
- Listes d'agents ou d'alertes
- Cards avec contenu variable
- Pages avec chargement initial

**Comportement**
- Fond gris clair (#F3F4F6)
- Animation shimmer (gradient animé)
- Forme approximative du contenu final
- Disparition progressive lors du chargement

**Exemples**
- Skeleton rows pour les tableaux
- Skeleton cards pour les KPIs
- Skeleton text pour les titres et descriptions

**Durée**
- Apparition immédiate (< 100ms)
- Remplacement par le contenu réel dès disponibilité
- Maximum 3 secondes avant message d'erreur

### Spinner

**Utilisation**
- Actions ponctuelles (boutons, formulaires)
- Chargement de modals
- Opérations asynchrones courtes
- États de chargement globaux

**Comportement**
- Cercle animé
- Couleur Or CBC (#D0B335)
- Taille variable (sm: 16px, md: 24px, lg: 32px)
- Rotation continue

**Exemples**
- Spinner dans les boutons lors de la soumission
- Spinner centré pour le chargement global
- Spinner inline pour les actions rapides

**Durée**
- Apparition immédiate
- Disparition à la fin de l'opération
- Maximum 10 secondes avant timeout

### Progress Bar

**Utilisation**
- Opérations longues avec progression connue
- Téléchargements
- Imports/exports
- Traitements par lots

**Comportement**
- Barre de progression linéaire
- Fond gris clair (#F3F4F6)
- Barre colorée (Or CBC #D0B335)
- Pourcentage affiché
- Animation fluide

**Exemples**
- Progress bar pour l'export CSV
- Progress bar pour l'import de données
- Progress bar pour les traitements par lots

**Durée**
- Mise à jour en temps réel
- Indication du pourcentage
- Estimation du temps restant (si disponible)

### Règles d'utilisation

**Skeleton vs Spinner**
- Skeleton : Contenu structurel (tableaux, listes)
- Spinner : Actions ponctuelles (boutons, formulaires)
- Progress Bar : Opérations longues avec progression

**Priorité**
- Skeleton > Progress Bar > Spinner
- Utiliser le plus informatif pour le contexte
- Éviter les spinners pour les chargements initiaux

**Feedback**
- Toujours indiquer le chargement
- Jamais de blanc sans indicateur
- Message d'erreur après timeout

---

## 26. Error States

Les Error States gèrent les situations où l'application rencontre une erreur. Ils doivent être clairs, informatifs et orienter l'utilisateur vers la résolution.

### Serveur indisponible

**Message utilisateur**
- Titre : "Serveur indisponible"
- Description : "Le serveur est temporairement inaccessible. Veuillez réessayer dans quelques instants."

**Illustration**
- Icône : ServerOff ou WifiOff
- Style : Outline, taille 64px
- Couleur : Rouge erreur (#EF4444)

**Bouton d'action**
- Texte : "Réessayer"
- Style : Primary (Or CBC #D0B335)
- Action : Recharge la page ou relance la requête

**Stratégie de récupération**
- Retry automatique après 5 secondes (optionnel)
- Indication du nombre de tentatives
- Message de contact si échec persistant

### Erreur réseau

**Message utilisateur**
- Titre : "Erreur de connexion"
- Description : "Une erreur de réseau est survenue. Vérifiez votre connexion internet et réessayez."

**Illustration**
- Icône : WifiOff
- Style : Outline, taille 64px
- Couleur : Orange warning (#F59E0B)

**Bouton d'action**
- Texte : "Réessayer"
- Style : Primary (Or CBC #D0B335)
- Action : Relance la requête

**Stratégie de récupération**
- Détection automatique de la connexion
- Retry automatique lorsque la connexion revient
- Indication du statut de la connexion

### API inaccessible

**Message utilisateur**
- Titre : "Service indisponible"
- Description : "Le service est temporairement indisponible pour maintenance. Veuillez réessayer ultérieurement."

**Illustration**
- Icône : AlertTriangle
- Style : Outline, taille 64px
- Couleur : Orange warning (#F59E0B)

**Bouton d'action**
- Texte : "Réessayer"
- Style : Primary (Or CBC #D0B335)
- Action : Recharge la page

**Stratégie de récupération**
- Retry automatique après 30 secondes
- Indication du temps de maintenance estimé
- Message de contact si maintenance prolongée

### Erreur 404

**Message utilisateur**
- Titre : "Page non trouvée"
- Description : "La page que vous recherchez n'existe pas ou a été déplacée."

**Illustration**
- Icône : FileX
- Style : Outline, taille 64px
- Couleur : Gris CBC (#777777)

**Bouton d'action**
- Texte : "Retour au Dashboard"
- Style : Primary (Or CBC #D0B335)
- Action : Redirection vers le Dashboard

**Stratégie de récupération**
- Redirection automatique après 10 secondes
- Suggestion de pages similaires (si disponible)
- Lien vers la page d'accueil

### Erreur 500

**Message utilisateur**
- Titre : "Erreur interne"
- Description : "Une erreur inattendue est survenue. Nos équipes ont été notifiées."

**Illustration**
- Icône : AlertOctagon
- Style : Outline, taille 64px
- Couleur : Rouge erreur (#EF4444)

**Bouton d'action**
- Texte : "Réessayer"
- Style : Primary (Or CBC #D0B335)
- Action : Recharge la page

**Stratégie de récupération**
- Logging automatique de l'erreur
- Retry automatique après 5 secondes
- Message de contact si échec persistant

### Authentification expirée

**Message utilisateur**
- Titre : "Session expirée"
- Description : "Votre session a expiré. Veuillez vous reconnecter pour continuer."

**Illustration**
- Icône : Lock
- Style : Outline, taille 64px
- Couleur : Orange warning (#F59E0B)

**Bouton d'action**
- Texte : "Se reconnecter"
- Style : Primary (Or CBC #D0B335)
- Action : Redirection vers la page de connexion

**Stratégie de récupération**
- Redirection automatique vers la connexion
- Conservation de l'URL demandée (redirect après login)
- Message d'information sur la durée de session

---

## 27. Success States

Les Success States fournissent un retour positif à l'utilisateur après une action réussie. Ils doivent être clairs, encourageants et confirmer l'action effectuée.

### Agent installé

**Message**
- Titre : "Agent installé avec succès"
- Description : "L'agent [Nom] est maintenant en ligne et envoie ses métriques."

**Illustration**
- Icône : CheckCircle
- Style : Solid, taille 48px
- Couleur : Vert succès (#10B981)

**Action**
- Bouton : "Voir l'agent"
- Style : Secondary
- Action : Redirection vers le détail de l'agent

### Paramètres enregistrés

**Message**
- Titre : "Paramètres enregistrés"
- Description : "Vos modifications ont été appliquées avec succès."

**Illustration**
- Icône : CheckCircle
- Style : Solid, taille 48px
- Couleur : Vert succès (#10B981)

**Action**
- Aucune (fermeture automatique du toast)

### Utilisateur créé

**Message**
- Titre : "Utilisateur créé"
- Description : "L'utilisateur [Nom] a été créé avec succès."

**Illustration**
- Icône : UserCheck
- Style : Solid, taille 48px
- Couleur : Vert succès (#10B981)

**Action**
- Bouton : "Voir les utilisateurs"
- Style : Secondary
- Action : Redirection vers la liste des utilisateurs

### Alerte acquittée

**Message**
- Titre : "Alerte acquittée"
- Description : "L'alerte a été marquée comme acquittée."

**Illustration**
- Icône : CheckCircle
- Style : Solid, taille 48px
- Couleur : Vert succès (#10B981)

**Action**
- Aucune (fermeture automatique du toast)

### Export terminé

**Message**
- Titre : "Export terminé"
- Description : "Le fichier [Nom] a été téléchargé avec succès."

**Illustration**
- Icône : DownloadCheck
- Style : Solid, taille 48px
- Couleur : Vert succès (#10B981)

**Action**
- Aucune (téléchargement automatique)

### Toast

**Utilisation**
- Actions rapides (sauvegarde, acquittement)
- Feedback immédiat
- Notifications non critiques

**Comportement**
- Apparition : Slide-in depuis la droite
- Durée : 5 secondes auto-dismiss
- Position : Top-right ou Bottom-right
- Fermeture manuelle : Bouton X

**Style**
- Fond : Vert succès (#10B981)
- Texte : Blanc
- Icône : CheckCircle
- Ombre : Medium

### Snackbar

**Utilisation**
- Actions importantes nécessitant une confirmation
- Feedback persistant
- Actions avec possibilité d'annulation

**Comportement**
- Apparition : Slide-in depuis le bas
- Durée : Persistante (jusqu'à action)
- Position : Bottom-center
- Bouton d'action : "Annuler" ou "OK"

**Style**
- Fond : Blanc
- Bordure : Vert succès (#10B981)
- Texte : Noir
- Ombre : Large

### Notifications visuelles

**Utilisation**
- Alertes critiques
- Notifications importantes
- Événements système

**Comportement**
- Badge sur l'icône de notification
- Couleur : Rouge critique (#EF4444)
- Nombre : Comptage des notifications non lues
- Animation : Pulse si critique

**Style**
- Badge : Circulaire, fond rouge
- Icône : Bell
- Position : Header, à droite

---

## 28. Micro-interactions

Les Micro-interactions sont les animations subtiles qui améliorent l'expérience utilisateur en fournissant un feedback visuel et en rendant l'interface plus vivante.

### Hover

**Boutons**
- Fond : Plus clair ou plus foncé selon l'état
- Durée : 150ms
- Easing : ease-out
- Ombre : Accentuée

**Cards**
- Ombre : Medium → Large
- Transform : TranslateY(-2px)
- Durée : 200ms
- Easing : ease-out

**Links**
- Soulignement : Apparition
- Couleur : Plus intense
- Durée : 150ms
- Easing : ease-out

**Table rows**
- Fond : Gris très clair (#F9FAFB)
- Durée : 100ms
- Easing : ease-out

### Focus

**Inputs**
- Bordure : Or CBC (#D0B335)
- Ombre : Small (couleur Or CBC)
- Durée : 150ms
- Easing : ease-out

**Boutons**
- Bordure : Or CBC (#D0B335)
- Ombre : Small (couleur Or CBC)
- Durée : 150ms
- Easing : ease-out

**Links**
- Soulignement : Or CBC (#D0B335)
- Durée : 150ms
- Easing : ease-out

### Active

**Boutons**
- Transform : Scale(0.95)
- Fond : Plus foncé
- Durée : 100ms
- Easing : ease-in

**Toggles**
- Animation de glissement
- Durée : 200ms
- Easing : ease-in-out

**Checkboxes**
- Animation de coche
- Durée : 150ms
- Easing : ease-out

### Disabled

**Boutons**
- Opacité : 50%
- Curseur : not-allowed
- Aucune interaction
- Aucune animation

**Inputs**
- Fond : Gris clair (#F3F4F6)
- Curseur : not-allowed
- Aucune interaction
- Aucune animation

**Links**
- Couleur : Gris CBC (#777777)
- Curseur : not-allowed
- Aucune interaction
- Text-decoration : none

### Sélection

**Table rows**
- Fond : Or CBC très clair (rgba(208, 179, 53, 0.1))
- Bordure gauche : Or CBC (#D0B335)
- Durée : 150ms
- Easing : ease-out

**List items**
- Fond : Or CBC très clair (rgba(208, 179, 53, 0.1))
- Durée : 150ms
- Easing : ease-out

**Tabs**
- Fond : Or CBC (#D0B335)
- Texte : Blanc
- Durée : 200ms
- Easing : ease-out

### Ouverture de Modal

**Backdrop**
- Opacité : 0 → 50%
- Durée : 200ms
- Easing : ease-out

**Modal**
- Transform : Scale(0.9) → Scale(1)
- Opacité : 0 → 100%
- Durée : 200ms
- Easing : ease-out

### Fermeture

**Backdrop**
- Opacité : 50% → 0
- Durée : 150ms
- Easing : ease-in

**Modal**
- Transform : Scale(1) → Scale(0.9)
- Opacité : 100% → 0%
- Durée : 150ms
- Easing : ease-in

### Tooltip

**Apparition**
- Opacité : 0 → 100%
- Transform : TranslateY(4px) → TranslateY(0)
- Durée : 150ms
- Easing : ease-out
- Délai : 500ms avant apparition

**Disparition**
- Opacité : 100% → 0%
- Durée : 100ms
- Easing : ease-in

### Menu déroulant

**Apparition**
- Opacité : 0 → 100%
- Transform : TranslateY(-8px) → TranslateY(0)
- Durée : 200ms
- Easing : ease-out

**Disparition**
- Opacité : 100% → 0%
- Durée : 150ms
- Easing : ease-in

### Animation des boutons

**Click**
- Transform : Scale(0.95)
- Durée : 100ms
- Easing : ease-in
- Retour : Scale(1) en 100ms

**Loading**
- Spinner : Rotation continue
- Durée : Indéterminée
- Couleur : Or CBC (#D0B335)

### Animation des cartes

**Hover**
- Ombre : Small → Medium
- Transform : TranslateY(-2px)
- Durée : 200ms
- Easing : ease-out

**Loading**
- Skeleton : Shimmer animation
- Durée : Indéterminée
- Couleur : Gris clair (#F3F4F6)

### Animation des graphiques

**Apparition**
- Progression : 0 → 100%
- Durée : 1000ms
- Easing : ease-out

**Hover**
- Tooltip : Apparition
- Durée : 150ms
- Easing : ease-out

### Règles générales

**Discrétion**
- Animations subtiles et professionnelles
- Jamais distrayantes
- Toujours au service de l'UX

**Performance**
- Durée < 300ms pour les interactions
- Utilisation de transform et opacity (GPU)
- Éviter les animations coûteuses

**Cohérence**
- Mêmes durées pour les mêmes types d'interactions
- Même easing pour les mêmes types d'animations
- Patterns réutilisables

---

## 29. Accessibilité

L'accessibilité garantit que l'interface est utilisable par tous les utilisateurs, indépendamment de leurs capacités ou de leurs technologies d'assistance.

### WCAG

**Niveau de conformité**
- Cible : WCAG 2.1 AA
- Priorité : Haute
- Vérification : Tests automatiques + manuels

**Critères clés**
- Contraste des couleurs (minimum 4.5:1)
- Navigation au clavier
- Texte alternatif pour les images
- Labels pour les formulaires
- Focus visible
- ARIA pour les composants dynamiques

### Contraste

**Ratios minimum**
- Texte normal : 4.5:1
- Texte large (18px+) : 3:1
- Composants d'interface : 3:1
- Graphiques : 3:1

**Vérification**
- Outils : WebAIM Contrast Checker, axe DevTools
- Tests manuels sur tous les textes
- Tests sur les états hover, focus, disabled

**Couleurs validées**
- Or CBC (#D0B335) sur blanc : 3.2:1 (OK pour texte large)
- Noir (#000000) sur blanc : 21:1 (Excellent)
- Gris CBC (#777777) sur blanc : 4.5:1 (OK pour texte normal)

### Navigation clavier

**Tab order**
- Ordre logique de gauche à droite, haut en bas
- Focus visible sur tous les éléments interactifs
- Skip links pour le contenu principal

**Raccourcis clavier**
- Escape : Fermer les modals, dropdowns
- Enter : Valider les formulaires, boutons
- Space : Activer les boutons, checkboxes
- Arrow keys : Navigation dans les listes, menus

**Focus management**
- Focus trap dans les modals
- Focus return après fermeture de modal
- Focus visible sur tous les éléments

### Focus visible

**Style**
- Bordure : Or CBC (#D0B335), 2px
- Ombre : Small (couleur Or CBC)
- Offset : 2px
- Toujours visible, jamais hidden

**États**
- Default : Focus visible
- Hover : Focus visible + hover
- Active : Focus visible + active

**Exceptions**
- Aucune exception
- Toujours visible sur tous les éléments interactifs

### ARIA

**Rôles**
- button : role="button"
- link : role="link"
- modal : role="dialog"
- alert : role="alert"
- navigation : role="navigation"

**Labels**
- aria-label pour les icônes sans texte
- aria-labelledby pour les formulaires
- aria-describedby pour les messages d'aide
- aria-expanded pour les dropdowns

**States**
- aria-disabled pour les éléments désactivés
- aria-selected pour les éléments sélectionnés
- aria-checked pour les checkboxes
- aria-pressed pour les toggles

**Live regions**
- aria-live="polite" pour les notifications
- aria-live="assertive" pour les erreurs critiques
- aria-atomic pour les mises à jour complètes

### Taille minimale des boutons

**Dimensions**
- Minimum : 44x44px
- Recommandé : 48x48px
- Espace : 8px entre les boutons

**Justification**
- Confort d'utilisation sur mobile
- Conformité WCAG 2.1 AAA
- Réduction des erreurs de clic

### Taille minimale des zones cliquables

**Dimensions**
- Minimum : 44x44px
- Recommandé : 48x48px
- Espace : 8px entre les zones

**Justification**
- Touch targets sur mobile
- Confort d'utilisation
- Réduction des erreurs

### Accessibilité des couleurs

**Indépendance de la couleur**
- L'information ne doit pas dépendre uniquement de la couleur
- Utiliser des icônes, textes ou patterns en complément
- Tests en noir et blanc

**Daltonisme**
- Tester avec des simulateurs de daltonisme
- Éviter les combinaisons rouge/vert
- Utiliser des patterns en plus des couleurs

**Mode sombre**
- Contraste vérifié en mode sombre
- Pas de perte d'information
- Tests manuels requis

### Lisibilité

**Taille du texte**
- Minimum : 14px pour le texte normal
- Recommandé : 16px pour le corps du texte
- Large : 18px+ pour les titres

**Line-height**
- Minimum : 1.5 pour le texte normal
- Recommandé : 1.5-1.6
- Maximum : 2 pour les textes longs

**Letter-spacing**
- Normal : 0
- Titres : -0.02em
- Texte en majuscules : 0.05em

**Justification**
- Éviter le texte justifié (problèmes de lisibilité)
- Alignement gauche recommandé
- Espacement cohérent entre les mots

---

## 30. Performance UX

La Performance UX définit les objectifs de performance perçue et mesurable pour garantir une expérience utilisateur fluide et réactive.

### Ouverture d'une page

**Objectif**
- Time to Interactive (TTI) : < 2 secondes
- First Contentful Paint (FCP) : < 1 seconde
- Largest Contentful Paint (LCP) : < 2.5 secondes

**Mesures**
- Lighthouse Performance Score : > 90
- Core Web Vitals : Good
- Tests sur connexion 3G

**Stratégies**
- Code splitting
- Lazy loading des composants
- Optimisation des images
- Minification CSS/JS

### Temps de chargement

**Objectif**
- Chargement initial : < 3 secondes
- Chargement des données : < 1 seconde
- Mise à jour des données : < 500ms

**Mesures**
- Network latency : < 100ms
- API response time : < 200ms
- Rendering time : < 100ms

**Stratégies**
- Pagination pour les listes
- Infinite scroll (optionnel)
- Cache des données
- Optimisation des requêtes

### Recherche

**Objectif**
- Réponse : < 300ms
- Affichage des résultats : < 500ms
- Highlight : < 100ms

**Mesures**
- Debounce : 300ms
- Index côté serveur
- Recherche floue (fuzzy search)

**Stratégies**
- Recherche côté serveur
- Pagination des résultats
- Highlight des termes recherchés
- Suggestions automatiques

### Pagination

**Objectif**
- Changement de page : < 500ms
- Affichage : < 300ms
- Navigation : < 200ms

**Mesures**
- Nombre d'items par page : 20/50/100
- Cache des pages visitées
- Préchargement de la page suivante

**Stratégies**
- Pagination côté serveur
- Cache des résultats
- Indicateur de chargement
- Skeleton loaders

### Navigation

**Objectif**
- Transition entre pages : < 200ms
- Apparition du contenu : < 300ms
- Navigation au clavier : < 100ms

**Mesures**
- Route transition time
- Component mount time
- First paint time

**Stratégies**
- Transitions CSS (GPU)
- Préchargement des routes
- Optimisation des composants
- Code splitting

### Rafraîchissement des données

**Objectif**
- Rafraîchissement automatique : 30 secondes
- Rafraîchissement manuel : < 500ms
- Mise à jour de l'UI : < 100ms

**Mesures**
- WebSocket latency : < 100ms
- Polling interval : 30 secondes
- Update time : < 100ms

**Stratégies**
- WebSocket pour les mises à jour en temps réel
- Polling fallback
- Optimistic UI updates
- Cache des données

### Perception utilisateur

**Objectifs**
- Feedback immédiat : < 100ms
- Chargement perçu : < 1 seconde
- Attente acceptable : < 3 secondes

**Mesures**
- Time to First Byte (TTFB) : < 600ms
- First Input Delay (FID) : < 100ms
- Cumulative Layout Shift (CLS) : < 0.1

**Stratégies**
- Skeleton loaders
- Spinners pour les actions
- Progress bars pour les opérations longues
- Toasts pour le feedback

---

## 31. Bibliothèque d'icônes

La bibliothèque d'icônes définit les standards pour l'utilisation des icônes dans l'interface.

### Bibliothèque recommandée

**Lucide React**
- Justification : Moderne, cohérente, open-source
- Taille : ~1KB par icône (tree-shakeable)
- Style : Outline par défaut
- Licence : ISC (open-source)

**Alternative : Heroicons**
- Justification : Créée par Tailwind Labs, très populaire
- Taille : ~1KB par icône
- Style : Outline et Solid
- Licence : MIT (open-source)

### Style des icônes

**Outline (par défaut)**
- Utilisation : Navigation, actions secondaires
- Épaisseur : 2px
- Coins : Arrondis (2px)
- Remplissage : Aucun

**Solid**
- Utilisation : Actions principales, badges
- Épaisseur : N/A (rempli)
- Coins : Arrondis (2px)
- Remplissage : Couleur unie

### Tailles

**XS - 12px**
- Utilisation : Badges, tags, inline icons
- Contexte : Texte small

**SM - 16px**
- Utilisation : Boutons small, inputs, inline
- Contexte : Texte normal

**MD - 20px**
- Utilisation : Boutons standard, navigation
- Contexte : Texte body

**LG - 24px**
- Utilisation : Boutons large, cards, sections
- Contexte : Titres H4

**XL - 32px**
- Utilisation : Hero sections, empty states
- Contexte : Titres H3-H2

**2XL - 48px**
- Utilisation : Empty states, illustrations
- Contexte : Titres H1

**3XL - 64px**
- Utilisation : Empty states, hero illustrations
- Contexte : Display

### Épaisseurs

**Thin - 1px**
- Utilisation : Icônes délicates, decorative
- Contexte : Rare, usage spécifique

**Regular - 2px (par défaut)**
- Utilisation : Standard pour toutes les icônes
- Contexte : Majorité des cas

**Bold - 3px**
- Utilisation : Icônes importantes, emphase
- Contexte : Rare, usage spécifique

### Cohérence visuelle

**Utilisation cohérente**
- Même style pour les icônes de même fonction
- Même taille pour les icônes de même contexte
- Même épaisseur pour les icônes de même niveau

**Exemples**
- Navigation : Outline, 20px, 2px
- Actions principales : Solid, 20px, 2px
- Badges : Solid, 12px, 2px
- Empty states : Outline, 64px, 2px

**Règles**
- Toujours utiliser la même bibliothèque
- Ne pas mixer les styles (outline/solid)
- Respecter les tailles définies
- Éviter les icônes personnalisées

---

## 32. Layout System

Le Layout System définit la structure de base des pages et des composants.

### Grille

**Base**
- Colonnes : 12
- Gutter : 24px
- Margin : 24px
- Max-width : 1280px

**Breakpoints**
- Mobile : < 768px (1 colonne)
- Tablet : 768px - 1279px (2-3 colonnes)
- Desktop : ≥ 1280px (3-4 colonnes)

**Utilisation**
- Dashboard : Grille 12 colonnes
- Cards : Grille 3-4 colonnes
- Formulaires : Grille 2 colonnes

### Colonnes

**Desktop (≥ 1280px)**
- Full : 12 colonnes
- Half : 6 colonnes
- Third : 4 colonnes
- Quarter : 3 colonnes

**Tablet (768px - 1279px)**
- Full : 2 colonnes
- Half : 1 colonne

**Mobile (< 768px)**
- Full : 1 colonne

### Gutters

**Standard**
- Desktop : 24px
- Tablet : 16px
- Mobile : 12px

**Compact**
- Desktop : 16px
- Tablet : 12px
- Mobile : 8px

**Spacious**
- Desktop : 32px
- Tablet : 24px
- Mobile : 16px

### Marges

**Page margins**
- Desktop : 32px
- Tablet : 24px
- Mobile : 16px

**Section margins**
- Desktop : 48px
- Tablet : 32px
- Mobile : 24px

**Component margins**
- Desktop : 24px
- Tablet : 16px
- Mobile : 12px

### Largeur maximale

**Container**
- Max-width : 1280px
- Center : Horizontalement
- Margin : Auto

**Content**
- Text : 800px (lisibilité optimale)
- Table : 100% (scroll horizontal)
- Card : Variable selon grille

### Organisation des pages

**Structure standard**
- Header (fixe) : 64px
- Sidebar (fixe) : 250px
- Content (scroll) : Restant
- Footer (optionnel) : Variable

**Dashboard**
- Header : 64px
- Sidebar : 250px
- Content : Calcul automatique
- KPIs : Grille 4 colonnes
- Main : Grille 2 colonnes

**Détail agent**
- Header : 64px
- Sidebar : 250px
- Content : Calcul automatique
- Onglets : Horizontal
- Cards : Grille 3 colonnes

### Alignements

**Horizontal**
- Left : Alignement par défaut
- Center : Titres, KPIs, modals
- Right : Actions, badges, dates

**Vertical**
- Top : Alignement par défaut
- Center : KPIs, badges, cellules de tableau
- Bottom : Actions, footers

**Justification**
- Space-between : Headers, cards
- Space-around : KPIs, badges
- Flex-start : Navigation, listes

---

## 33. Comportement des composants

Cette section définit le comportement détaillé de chaque composant important de l'interface.

### Table

**États**
- Default : Fond blanc, bordure subtile
- Hover : Fond gris clair, highlight
- Selected : Fond Or CBC très clair, bordure gauche
- Disabled : Fond gris, opacité 50%

**Interactions**
- Click : Sélection de la ligne
- Double-click : Action détaillée
- Sort : Click sur l'en-tête
- Filter : Application des filtres

**Comportement**
- Tri : Ascendant/descendant
- Pagination : 20/50/100 par page
- Scroll : Horizontal si nécessaire
- Selection : Single ou multiple

**Variantes**
- Standard : Tableau complet
- Compact : Hauteur de ligne réduite
- Dense : Padding minimal

### Card

**États**
- Default : Fond blanc, ombre small
- Hover : Ombre medium, translateY(-2px)
- Active : Ombre large
- Disabled : Fond gris, opacité 50%

**Interactions**
- Click : Action principale
- Hover : Feedback visuel
- Focus : Bordure Or CBC

**Comportement**
- Responsive : Adaptation à la grille
- Collapse : Expansion/réduction (optionnel)
- Drag : Drag & drop (optionnel)

**Variantes**
- Standard : Card simple
- KPI : Card avec bordure colorée
- Interactive : Card cliquable

### Modal

**États**
- Closed : Opacité 0, scale 0.9
- Opening : Opacité 0 → 100%, scale 0.9 → 1
- Open : Opacité 100%, scale 1
- Closing : Opacité 100% → 0%, scale 1 → 0.9

**Interactions**
- Open : Trigger (bouton, lien)
- Close : Bouton X, backdrop click, Escape
- Submit : Formulaire interne
- Cancel : Bouton annuler

**Comportement**
- Backdrop : Fond semi-transparent
- Focus trap : Focus restreint au modal
- Scroll lock : Désactivation du scroll body
- Animation : 200ms ease-out

**Variantes**
- Standard : Modal simple
- Confirmation : Modal avec avertissement
- Form : Modal avec formulaire
- Large : Modal pleine largeur

### Formulaire

**États**
- Default : Champs vides ou pré-remplis
- Valid : Tous les champs valides
- Invalid : Au moins un champ invalide
- Submitting : En cours de soumission
- Submitted : Soumis avec succès

**Interactions**
- Input : Saisie dans les champs
- Validate : Validation en temps réel
- Submit : Soumission du formulaire
- Reset : Réinitialisation

**Comportement**
- Validation : En temps réel (debounce 300ms)
- Error : Message par champ
- Success : Toast de confirmation
- Required : Indication visuelle

**Variantes**
- Standard : Formulaire vertical
- Inline : Formulaire horizontal
- Multi-step : Formulaire par étapes

### Bouton

**États**
- Default : Fond normal
- Hover : Fond plus clair/sombre
- Active : Scale 0.95
- Disabled : Opacité 50%, curseur not-allowed
- Loading : Spinner à la place du texte

**Interactions**
- Click : Action principale
- Hover : Feedback visuel
- Focus : Bordure Or CBC
- Keyboard : Enter/Space pour activer

**Comportement**
- Ripple : Effet d'onde (optionnel)
- Loading : Désactivation pendant le chargement
- Auto-disable : Désactivation si formulaire invalide

**Variantes**
- Primary : Or CBC, texte blanc
- Secondary : Transparent, bordure Or CBC
- Danger : Rouge, texte blanc
- Ghost : Transparent, texte gris
- Icon : Icône seule

### Input

**États**
- Default : Fond blanc, bordure grise
- Focus : Bordure Or CBC, ombre small
- Valid : Bordure verte
- Invalid : Bordure rouge, message d'erreur
- Disabled : Fond gris, curseur not-allowed

**Interactions**
- Input : Saisie de texte
- Focus : Activation du focus
- Blur : Perte du focus
- Clear : Effacement du contenu

**Comportement**
- Validation : En temps réel ou au blur
- Placeholder : Texte indicatif
- Clear button : Apparaît si contenu
- Password toggle : Affichage/masquage

**Variantes**
- Standard : Input texte
- Password : Input mot de passe
- Email : Input email avec validation
- Number : Input numérique
- Search : Input avec icône loupe

### Dropdown

**États**
- Closed : Liste masquée
- Opening : Animation d'apparition
- Open : Liste visible
- Closing : Animation de disparition

**Interactions**
- Click : Ouverture/fermeture
- Select : Sélection d'un item
- Outside click : Fermeture
- Escape : Fermeture

**Comportement**
- Position : Absolute ou fixed
- Scroll : Vertical si nécessaire
- Search : Recherche dans la liste (optionnel)
- Multi-select : Sélection multiple (optionnel)

**Variantes**
- Standard : Dropdown simple
- Multi-select : Avec checkboxes
- Search : Avec barre de recherche
- Filter : Filtre avancé

### Tooltip

**États**
- Hidden : Invisible
- Appearing : Animation d'apparition
- Visible : Visible
- Disappearing : Animation de disparition

**Interactions**
- Hover : Apparition après délai
- Focus : Apparition au focus
- Leave : Disparition
- Keyboard : Apparition au focus clavier

**Comportement**
- Délai : 500ms avant apparition
- Position : Auto (top, right, bottom, left)
- Duration : Persistante tant que hover
- Z-index : Au-dessus de tout

**Variantes**
- Standard : Tooltip simple
- Rich : Tooltip avec HTML
- Interactive : Tooltip interactif

### Badge

**États**
- Default : Couleur normale
- Hover : Fond plus clair
- Active : Fond plus foncé
- Disabled : Gris, opacité 50%

**Interactions**
- Click : Action (si cliquable)
- Hover : Badge de comptage

**Comportement**
- Position : Absolute ou inline
- Count : Nombre affiché
- Pulse : Animation si critique

**Variantes**
- Standard : Badge simple
- Count : Badge avec nombre
- Dot : Badge point
- Status : Badge de statut

### Alert

**États**
- Default : Visible
- Closing : Animation de disparition
- Closed : Invisible

**Interactions**
- Close : Bouton X
- Click : Action (si cliquable)

**Comportement**
- Auto-dismiss : Après délai (optionnel)
- Icon : Icône selon le type
- Progress bar : Indicateur de temps (optionnel)

**Variantes**
- Info : Bleu
- Success : Vert
- Warning : Orange
- Error : Rouge

### Toast

**États**
- Hidden : Invisible
- Appearing : Slide-in depuis la droite
- Visible : Visible
- Disappearing : Slide-out vers la droite
- Closed : Invisible

**Interactions**
- Close : Bouton X
- Click : Action (si cliquable)
- Hover : Pause auto-dismiss

**Comportement**
- Auto-dismiss : 5 secondes
- Position : Top-right ou Bottom-right
- Stack : Empilement si multiples
- Z-index : Au-dessus de tout

**Variantes**
- Success : Vert
- Error : Rouge
- Warning : Orange
- Info : Bleu

### Pagination

**États**
- Default : Boutons normaux
- Disabled : Boutons désactivés (première/dernière page)
- Active : Page courante highlight

**Interactions**
- Click : Changement de page
- Keyboard : Navigation flèches

**Comportement**
- Items : Numéros de page
- Jump : Input pour saut à une page
- Per page : Sélection du nombre d'items

**Variantes**
- Standard : Numéros de page
- Simple : Previous/Next uniquement
- Compact : Version réduite

### Sidebar

**États**
- Expanded : Largeur 250px
- Collapsed : Largeur 64px
- Mobile : Overlay 100% (future version)

**Interactions**
- Click : Navigation
- Toggle : Expansion/réduction
- Hover : Highlight des items

**Comportement**
- Fixed : Position fixe
- Scroll : Vertical si nécessaire
- Active : Item actif highlight
- Badge : Notification badge

**Variantes**
- Standard : Sidebar fixe
- Collapsible : Avec toggle
- Overlay : Mobile (future version)

### Navbar

**États**
- Default : Visible
- Scrolled : Fond opaque (si transparent)
- Mobile : Menu hamburger (future version)

**Interactions**
- Click : Navigation
- Search : Barre de recherche
- Profile : Dropdown utilisateur

**Comportement**
- Fixed : Position fixe en haut
- Breadcrumb : Fil d'ariane
- Actions : Actions rapides

**Variantes**
- Standard : Navbar opaque
- Transparent : Navbar transparent
- Compact : Navbar réduite

---

## 34. Règles de cohérence UI

Les règles de cohérence UI garantissent que l'interface est uniforme et prévisible dans tous les écrans et composants.

### Cohérence des espacements

**Règle**
- Utiliser uniquement les espacements définis dans les Design Tokens
- Ne jamais utiliser de valeurs arbitraires
- Appliquer le même espacement pour les mêmes types d'éléments

**Exemples**
- Padding des cards : 16px (spacing-lg)
- Margin entre sections : 24px (spacing-xl)
- Gap entre items : 12px (spacing-md)

**Vérification**
- Audit du code pour les valeurs arbitraires
- Linting CSS/JS pour les espacements
- Review design pour la cohérence

### Cohérence des couleurs

**Règle**
- Utiliser uniquement les couleurs définies dans la palette
- Ne jamais utiliser de couleurs hexadécimales arbitraires
- Appliquer la même couleur pour les mêmes types d'éléments

**Exemples**
- Primary : Or CBC (#D0B335)
- Success : Vert (#10B981)
- Error : Rouge (#EF4444)
- Warning : Orange (#F59E0B)

**Vérification**
- Audit du code pour les couleurs arbitraires
- Linting CSS/JS pour les couleurs
- Review design pour la cohérence

### Cohérence des actions

**Règle**
- Même action = même bouton
- Même feedback = même toast
- Même confirmation = même modal

**Exemples**
- Sauvegarder : Bouton Primary
- Annuler : Bouton Secondary
- Supprimer : Bouton Danger
- Succès : Toast vert

**Vérification**
- Audit des actions dans tous les écrans
- Review des feedbacks utilisateur
- Tests de cohérence

### Cohérence des boutons

**Règle**
- Primary : Actions principales
- Secondary : Actions secondaires
- Danger : Actions destructives
- Ghost : Actions tertiaires

**Exemples**
- Créer : Primary
- Modifier : Secondary
- Supprimer : Danger
- Annuler : Ghost

**Vérification**
- Audit des boutons dans tous les écrans
- Review de la hiérarchie des actions
- Tests de cohérence

### Cohérence des icônes

**Règle**
- Même fonction = même icône
- Même taille pour le même contexte
- Même style (outline/solid)

**Exemples**
- Supprimer : Trash
- Modifier : Pencil
- Sauvegarder : Save
- Rechercher : Search

**Vérification**
- Audit des icônes dans tous les écrans
- Review de la cohérence visuelle
- Tests de cohérence

### Cohérence des formulaires

**Règle**
- Même structure pour tous les formulaires
- Même validation
- Même feedback

**Exemples**
- Labels : Au-dessus des inputs
- Validation : En temps réel
- Error : Message sous l'input
- Success : Toast de confirmation

**Vérification**
- Audit des formulaires dans tous les écrans
- Review de la cohérence
- Tests de cohérence

### Cohérence des messages

**Règle**
- Même ton (professionnel, clair)
- Même terminologie
- Même structure

**Exemples**
- Succès : "X a été créé avec succès"
- Erreur : "Une erreur est survenue"
- Confirmation : "Êtes-vous sûr de vouloir X ?"

**Vérification**
- Audit des messages dans tous les écrans
- Review de la terminologie
- Tests de cohérence

---

## 35. Principes UX

Les Principes UX sont les grands principes qui guident toutes les décisions de conception de l'interface.

### Simplicité

**Définition**
- L'interface doit être simple et intuitive
- Éviter la complexité inutile
- Réduire le nombre d'étapes pour accomplir une tâche

**Application**
- Moins de clics pour les actions courantes
- Interface épurée sans éléments superflus
- Navigation claire et prévisible

**Exemples**
- Dashboard comme point d'entrée unique
- Actions rapides accessibles en un clic
- Filtres intuitifs

### Clarté

**Définition**
- L'information doit être claire et compréhensible
- Éviter l'ambiguïté
- Utiliser un langage simple

**Application**
- Terminologie cohérente
- Titres et descriptions clairs
- Messages d'erreur explicites

**Exemples**
- "Aucun agent" au lieu de "Liste vide"
- "Réessayer" au lieu de "Recommencer"
- Messages d'erreur avec contexte

### Lisibilité

**Définition**
- Le texte doit être facile à lire
- Contraste suffisant
- Taille de police appropriée

**Application**
- Contraste minimum 4.5:1
- Taille de police minimum 14px
- Line-height 1.5 minimum

**Exemples**
- Texte noir sur fond blanc
- Titres hiérarchiques
- Espacement suffisant entre les paragraphes

### Rapidité

**Définition**
- L'interface doit être rapide et réactive
- Feedback immédiat
- Performance perçue élevée

**Application**
- Feedback visuel immédiat (< 100ms)
- Chargement des données < 2 secondes
- Skeleton loaders pour le chargement

**Exemples**
- Spinner sur les boutons
- Skeleton loaders pour les tableaux
- Toasts pour le feedback

### Cohérence

**Définition**
- L'interface doit être cohérente dans tous les écrans
- Même comportement pour les mêmes éléments
- Même style visuel

**Application**
- Design system cohérent
- Composants réutilisables
- Patterns répétitifs

**Exemples**
- Même bouton pour les mêmes actions
- Même icône pour les mêmes fonctions
- Même espacement pour les mêmes éléments

### Faible charge cognitive

**Définition**
- Réduire la charge mentale de l'utilisateur
- Éviter la surcharge d'information
- Faciliter la prise de décision

**Application**
- Information hiérarchisée
- Éléments regroupés logiquement
- Actions claires et évidentes

**Exemples**
- KPIs en premier sur le dashboard
- Alertes critiques highlightées
- Actions principales mises en avant

### Réduction du nombre de clics

**Définition**
- Minimiser le nombre d'interactions pour accomplir une tâche
- Raccourcis pour les actions courantes
- Automatiser quand possible

**Application**
- Actions rapides sur le dashboard
- Clic direct sur les éléments
- Raccourcis clavier (optionnel)

**Exemples**
- Clic sur KPI → vue filtrée
- Clic sur agent → détail
- Clic sur alerte → détail agent

### Feedback immédiat

**Définition**
- Fournir un feedback immédiat pour chaque action
- Confirmer les actions importantes
- Indiquer les erreurs clairement

**Application**
- Toasts pour les actions rapides
- Modals pour les confirmations
- Messages d'erreur explicites

**Exemples**
- Toast "Paramètres enregistrés"
- Modal "Confirmer la suppression"
- Message d'erreur avec contexte

### Hiérarchie visuelle

**Définition**
- Organiser l'information par importance
- Utiliser la taille, la couleur et la position
- Guider l'œil de l'utilisateur

**Application**
- Titres plus grands que le corps
- Couleur pour l'accentuation
- Position pour la priorité

**Exemples**
- KPIs en premier sur le dashboard
- Alertes critiques en rouge
- Actions principales à gauche

### Design orienté efficacité

**Définition**
- Concevoir pour l'efficacité de l'utilisateur
- Optimiser les tâches courantes
- Réduire le temps d'exécution

**Application**
- Actions rapides accessibles
- Filtres puissants
- Recherche efficace

**Exemples**
- Filtres avancés sur les listes
- Recherche en temps réel
- Export CSV en un clic

---

## 36. Identité visuelle officielle de la CBC

L'identité visuelle de la Commercial Bank Cameroun (CBC) doit être intégrée de manière cohérente dans toute l'interface pour renforcer la confiance et la reconnaissance de marque.

### Palette de couleurs officielle

La palette officielle de la CBC sert de base au Design System et doit être utilisée de manière cohérente dans toute l'interface.

#### Or CBC (Couleur primaire)

**#D0B335**

**À utiliser pour :**
- Boutons principaux
- Liens importants
- Éléments actifs (navigation, onglets)
- Indicateurs positifs
- Highlights visuels
- Badges principaux
- Éléments de navigation actifs
- Accents visuels
- Bordures de focus
- Progress bars
- Spinners de chargement

**Variantes :**
- Hover : #B89C2C (plus foncé de 10%)
- Active : #A68523 (plus foncé de 20%)
- Focus : #D0B335 avec ombre
- Disabled : #D0B335 avec opacité 50%
- Background léger : rgba(208, 179, 53, 0.1)
- Border léger : rgba(208, 179, 53, 0.3)

#### Gris CBC (Couleur secondaire)

**#777777**

**À utiliser pour :**
- Textes secondaires
- Icônes secondaires
- Bordures discrètes
- Informations complémentaires
- Placeholders
- Éléments désactivés lorsque cela est pertinent
- Métadonnées
- Labels de formulaire
- Texte de description

**Variantes :**
- Hover : #6B6B6B (plus foncé de 10%)
- Active : #5F5F5F (plus foncé de 20%)
- Disabled : #777777 avec opacité 50%
- Background léger : rgba(119, 119, 119, 0.1)
- Border léger : rgba(119, 119, 119, 0.3)

#### Noir (Couleur neutre principale)

**#000000**

**À utiliser pour :**
- Titres principaux
- Textes principaux
- Icônes principales
- Navigation
- Éléments nécessitant un contraste élevé
- Texte de corps
- En-têtes de tableau
- Labels importants

**Variantes :**
- Hover : #1A1A1A (plus clair de 10%)
- Active : #333333 (plus clair de 20%)
- Disabled : #000000 avec opacité 50%
- Background léger : rgba(0, 0, 0, 0.05)
- Border léger : rgba(0, 0, 0, 0.1)

### Couleurs dérivées

À partir de la palette officielle, des variantes sont créées pour les différents états et utilisations.

#### Variantes Or CBC

**Background léger**
- Valeur : rgba(208, 179, 53, 0.1)
- Utilisation : Fond des éléments sélectionnés, hover states
- Contraste : Suffisant avec texte noir

**Border léger**
- Valeur : rgba(208, 179, 53, 0.3)
- Utilisation : Bordures des inputs au focus, éléments actifs
- Contraste : Suffisant avec fond blanc

**Hover**
- Valeur : #B89C2C
- Utilisation : Boutons au hover, liens au hover
- Contraste : Suffisant avec texte blanc

**Active**
- Valeur : #A68523
- Utilisation : Boutons actifs, éléments pressés
- Contraste : Suffisant avec texte blanc

**Focus**
- Valeur : #D0B335
- Utilisation : Bordures de focus, ombres de focus
- Contraste : Suffisant avec fond blanc

**Disabled**
- Valeur : rgba(208, 179, 53, 0.5)
- Utilisation : Boutons désactivés, éléments inactifs
- Contraste : Suffisant pour la lisibilité

#### Variantes Gris CBC

**Background léger**
- Valeur : rgba(119, 119, 119, 0.1)
- Utilisation : Fond des éléments secondaires
- Contraste : Suffisant avec texte noir

**Border léger**
- Valeur : rgba(119, 119, 119, 0.3)
- Utilisation : Bordures des inputs, séparateurs
- Contraste : Suffisant avec fond blanc

**Hover**
- Valeur : #6B6B6B
- Utilisation : Éléments secondaires au hover
- Contraste : Suffisant avec fond blanc

**Active**
- Valeur : #5F5F5F
- Utilisation : Éléments secondaires actifs
- Contraste : Suffisant avec fond blanc

**Disabled**
- Valeur : rgba(119, 119, 119, 0.5)
- Utilisation : Éléments secondaires désactivés
- Contraste : Suffisant pour la lisibilité

#### Variantes Noir

**Background léger**
- Valeur : rgba(0, 0, 0, 0.05)
- Utilisation : Fond des éléments neutres
- Contraste : Suffisant avec texte noir

**Border léger**
- Valeur : rgba(0, 0, 0, 0.1)
- Utilisation : Bordures subtiles, séparateurs
- Contraste : Suffisant avec fond blanc

**Hover**
- Valeur : #1A1A1A
- Utilisation : Éléments neutres au hover
- Contraste : Suffisant avec fond blanc

**Active**
- Valeur : #333333
- Utilisation : Éléments neutres actifs
- Contraste : Suffisant avec fond blanc

**Disabled**
- Valeur : rgba(0, 0, 0, 0.5)
- Utilisation : Éléments neutres désactivés
- Contraste : Suffisant pour la lisibilité

### Règles d'utilisation

#### Règle 1 : Pas de couleurs arbitraires
- **Principe** : N'utiliser jamais de couleurs hexadécimales arbitraires
- **Application** : Toujours utiliser les couleurs définies dans la palette
- **Vérification** : Audit du code pour les couleurs arbitraires
- **Exception** : Aucune exception

#### Règle 2 : Hiérarchie visuelle
- **Principe** : Respecter la hiérarchie visuelle définie
- **Application** : Or CBC pour les éléments primaires, Gris CBC pour les secondaires, Noir pour les neutres
- **Vérification** : Review design pour la cohérence
- **Exception** : Couleurs sémantiques (succès, erreur, warning)

#### Règle 3 : Contraste élevé
- **Principe** : Maintenir un contraste élevé pour l'accessibilité
- **Application** : Ratio minimum 4.5:1 pour le texte normal
- **Vérification** : Tests de contraste avec WebAIM Contrast Checker
- **Exception** : Texte large (18px+) avec ratio 3:1

#### Règle 4 : Interface sobre
- **Principe** : Privilégier une interface sobre, professionnelle et bancaire
- **Application** : Utiliser modérément l'Or CBC, éviter les couleurs saturées
- **Vérification** : Review design pour la sobriété
- **Exception** : Alertes critiques (rouge)

#### Règle 5 : Éviter les couleurs "startup flashy"
- **Principe** : Éviter les couleurs trop saturées ou trop "startup flashy"
- **Application** : Utiliser des couleurs subtiles et professionnelles
- **Vérification** : Review design pour le professionnalisme
- **Exception** : Aucune exception

#### Règle 6 : Cohérence avec l'identité CBC
- **Principe** : Conserver une identité visuelle homogène avec la CBC
- **Application** : Utiliser l'Or CBC comme couleur primaire dans tout l'interface
- **Vérification** : Audit de l'interface pour la cohérence
- **Exception** : Aucune exception

### Style visuel attendu

L'interface doit transmettre les valeurs suivantes à travers son style visuel :

#### Confiance
- **Expression** : Couleurs sobres et professionnelles
- **Application** : Utilisation modérée de l'Or CBC, fond blanc dominant
- **Exemple** : Dashboard épuré avec KPIs clairs

#### Stabilité
- **Expression** : Interface cohérente et prévisible
- **Application** : Design system cohérent, composants réutilisables
- **Exemple** : Même bouton pour les mêmes actions

#### Sécurité
- **Expression** : Contraste élevé, lisibilité optimale
- **Application** : Texte noir sur fond blanc, ratio de contraste 4.5:1 minimum
- **Exemple** : Texte clair et lisible dans tous les écrans

#### Professionnalisme
- **Expression** : Interface soignée et raffinée
- **Application** : Espacements cohérents, typographie hiérarchique
- **Exemple** : Cards avec ombres subtiles et bordures discrètes

#### Modernité
- **Expression** : Interface contemporaine sans être "trendy"
- **Application** : Design system moderne, composants actualisés
- **Exemple** : Micro-interactions subtiles et professionnelles

#### Simplicité
- **Expression** : Interface épurée sans éléments superflus
- **Application** : Information hiérarchisée, éléments regroupés logiquement
- **Exemple** : Dashboard avec KPIs en premier

#### Élégance
- **Expression** : Interface raffinée et harmonieuse
- **Application** : Couleurs subtiles, typographie soignée, espacements précis
- **Exemple** : Cards avec ombres légères et coins arrondis

### Inspiration et références

L'apparence générale doit s'inspirer des plateformes SaaS haut de gamme tout en respectant l'identité visuelle de la CBC :

**Références SaaS haut de gamme**
- Stripe Dashboard : Modernité et élégance
- Linear : Simplicité et fluidité
- Datadog : Densité organisée
- Microsoft Azure : Professionnalisme

**Adaptation CBC**
- Remplacer les couleurs primaires par l'Or CBC
- Conserver la sobriété et le professionnalisme
- Maintenir la cohérence avec l'identité bancaire
- Éviter les éléments trop "startup"

### Application dans les composants

#### Écrans
- Dashboard : Or CBC pour les KPIs, Noir pour les titres
- Liste agents : Or CBC pour les badges, Gris CBC pour les métadonnées
- Détail agent : Or CBC pour les jauges, Noir pour les valeurs
- Liste alertes : Or CBC pour les actions, Noir pour le texte

#### Composants
- Boutons : Primary (Or CBC), Secondary (Ghost Gris CBC), Danger (Rouge)
- Cards : Fond blanc, bordure Gris CBC, ombre subtile
- Tableaux : Noir pour le texte, Gris CBC pour les bordures
- Inputs : Noir pour le texte, Gris CBC pour les placeholders
- Badges : Or CBC pour les badges principaux, couleurs sémantiques pour les alertes

#### Navigation
- Sidebar : Fond gris foncé, Or CBC pour l'item actif
- Header : Fond blanc, Noir pour le titre
- Breadcrumb : Gris CBC pour les séparateurs
- Tabs : Or CBC pour l'onglet actif

#### Graphiques
- Lignes : Or CBC pour la ligne principale
- Aires : Or CBC transparent pour l'aire
- Axes : Gris CBC pour les axes
- Labels : Noir pour les labels

#### Formulaires
- Labels : Gris CBC pour les labels
- Inputs : Noir pour le texte, Gris CBC pour les placeholders
- Boutons : Primary (Or CBC), Secondary (Ghost Gris CBC)
- Messages : Vert pour succès, Rouge pour erreur

#### Notifications
- Toasts : Vert pour succès, Rouge pour erreur, Orange pour warning
- Badges : Or CBC pour les badges principaux
- Alerts : Couleurs sémantiques (succès, erreur, warning)

Cette identité visuelle officielle de la CBC doit être appliquée de manière cohérente dans l'ensemble des écrans, composants, graphiques, tableaux, cartes, boutons, formulaires, badges, notifications et éléments interactifs de l'application.

---

## Conclusion

Ce document UI/UX Design Brief sert de référence absolue pour la conception des interfaces de CBC Supervision Platform. Il couvre l'ensemble des aspects nécessaires à la création d'une expérience utilisateur cohérente, intuitive et efficace.

**Points clés à retenir**
- 3 profils utilisateurs avec des permissions distinctes
- Navigation claire avec sidebar et breadcrumb
- Dashboard comme point d'entrée principal
- Gestion des agents et des alertes centralisée
- Design system cohérent avec tokens réutilisables
- Accessibilité et performance prioritaires

**Prochaines étapes**
- Création des maquettes dans Figma ou Google AI Studio
- Développement des composants UI
- Implémentation du dashboard
- Tests utilisateurs et itérations

---

**Document approuvé pour la conception des interfaces**
**Version 1.0 - 3 août 2026**
