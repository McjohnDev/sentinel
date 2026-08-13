# CBC Supervision Platform

**Plateforme de supervision centralisée multiplateforme pour le parc informatique d'entreprise**

[![Version](https://img.shields.io/badge/version-v1.1.0--developing-blue.svg)](https://github.com/cbc-cameroun/supervision-platform)
[![Build Status](https://img.shields.io/badge/build-pending-yellow.svg)](https://github.com/cbc-cameroun/supervision-platform/actions)
[![License](https://img.shields.io/badge/license-proprietary-red.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)](https://github.com/cbc-cameroun/supervision-platform)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![Status](https://img.shields.io/badge/status-active-success.svg)](https://github.com/cbc-cameroun/supervision-platform)

---

## Table des matières

- [Pourquoi ce projet ?](#pourquoi-ce-projet)
- [Présentation du projet](#présentation-du-projet)
- [Objectifs](#objectifs)
- [Fonctionnalités principales](#fonctionnalités-principales)
- [Aperçu](#aperçu)
- [Fonctionnement général](#fonctionnement-général)
- [Cas d'utilisation](#cas-dutilisation)
- [Principes du projet](#principes-du-projet)
- [Exigences non fonctionnelles](#exigences-non-fonctionnelles)
- [Périmètre](#périmètre)
- [Roadmap](#roadmap)
- [Technologies](#technologies)
- [Structure du dépôt](#structure-du-dépôt)
- [Structure générale du système](#structure-générale-du-système)
- [Sécurité](#sécurité)
- [Journal des versions](#journal-des-versions)
- [Licence](#licence)
- [Contribution](#contribution)
- [Auteur](#auteur)

---

## Pourquoi ce projet ?

### Le problème de la supervision informatique

La supervision informatique est un défi majeur pour toute organisation gérant un parc de machines hétérogène. Sans une vision centralisée, les équipes IT opèrent dans le noir, détectant les incidents de manière réactive plutôt que proactive. Les conséquences sont directes : temps d'arrêt prolongés, perte de productivité, et risque pour la continuité des activités.

### Pourquoi une supervision centralisée ?

Une supervision centralisée apporte une réponse structurée à ces défis :

- **Visibilité unifiée** : Une seule source de vérité pour l'état de l'ensemble du parc
- **Détection proactive** : Les anomalies sont identifiées avant qu'elles ne deviennent des incidents critiques
- **Réactivité accrue** : Les équipes sont informées immédiatement et peuvent intervenir plus rapidement
- **Maintenance simplifiée** : La configuration est centralisée, éliminant les interventions machine par machine
- **Historique et traçabilité** : Les données sont conservées, permettant l'analyse des tendances et l'amélioration continue

### La valeur métier de CBC Supervision Platform

Pour la Commercial Bank Cameroun, cette plateforme représente un investissement stratégique dans la résilience de son infrastructure informatique. Elle permet de :

- Garantir la disponibilité des services critiques de la banque
- Réduire le MTTR (Mean Time To Recovery) des incidents
- Optimiser l'utilisation des ressources serveurs
- Fournir des indicateurs pour la planification capacitaire
- Renforcer la conformité et la sécurité du parc informatique

---

## Présentation du projet

### Résumé

CBC Supervision Platform est une solution de supervision centralisée permettant de surveiller en temps réel l'état de santé du parc informatique de la Commercial Bank Cameroun. Elle remplace l'architecture fragmentée de scripts PowerShell par une plateforme unifiée, multiplateforme et sécurisée.

### Contexte

La Commercial Bank Cameroun gère un parc informatique hétérogène composé de serveurs et postes de travail sous Windows, Linux et macOS. La supervision actuelle repose sur des scripts PowerShell décentralisés, difficiles à maintenir et ne fournissant pas une vision globale du parc.

### Problème rencontré

L'architecture actuelle présente plusieurs limitations majeures :

- **Absence de vision centralisée** : Pas de vue d'ensemble en temps réel de l'état du parc
- **Maintenance complexe** : Scripts PowerShell dispersés sur chaque machine
- **Détection réactive** : Les incidents sont détectés tardivement, souvent après signalement utilisateur
- **Configuration manuelle** : Chaque modification de configuration doit être appliquée machine par machine
- **Absence d'historique** : Pas de traçabilité des incidents et des métriques
- **Alertes manuelles** : Pas de notification automatique en cas d'anomalie

### Solution proposée

CBC Supervision Platform propose une architecture agent-serveur moderne :

- **Agent léger multiplateforme** : Déployé sur chaque machine, il collecte les métriques système en temps réel
- **Plateforme centralisée** : Serveur unique qui agrège et traite toutes les données
- **Dashboard web** : Interface unique pour consulter l'état du parc et gérer les alertes
- **Alertes automatiques** : Détection proactive des anomalies et notification par email
- **Configuration centralisée** : Gestion unifiée des seuils et paramètres depuis une interface web

---

## Aperçu

### Dashboard principal

<!-- Placeholder pour capture d'écran du dashboard principal -->

*Vue d'ensemble du parc avec KPIs et liste des agents*

### Liste des agents

<!-- Placeholder pour capture d'écran de la liste des agents -->

*Liste filtrable et triable de tous les agents avec leurs métriques en temps réel*

### Vue détaillée d'un serveur

<!-- Placeholder pour capture d'écran des détails d'un serveur -->

*Métriques détaillées, alertes actives et informations système d'une machine spécifique*

### Gestion des alertes

<!-- Placeholder pour capture d'écran de la gestion des alertes -->

*Interface de gestion des alertes avec filtrage, tri et acquittement*

---

## Objectifs

La plateforme vise à atteindre les objectifs suivants :

- **Visibilité permanente** : Fournir une vue en temps réel de l'état de tous les agents déployés
- **Détection proactive** : Identifier automatiquement les anomalies de ressources (CPU, RAM, disque)
- **Réactivité améliorée** : Réduire le temps de détection et de résolution des incidents
- **Maintenance simplifiée** : Centraliser la configuration et éliminer les scripts dispersés
- **Multiplateforme** : Supporter Windows, Linux et macOS avec une solution unifiée
- **Sécurité** : Garantir des communications authentifiées et chiffrées entre agents et serveur

---

## Fonctionnalités principales

### Supervision en temps réel

- Collecte automatique des métriques système (CPU, RAM, disque, uptime)
- Détection automatique des agents hors ligne
- Dashboard web avec vue d'ensemble et détails par machine
- Rafraîchissement automatique des données (30 secondes)

### Alertes intelligentes

- Détection automatique des anomalies basée sur des seuils configurables
- 3 niveaux de gravité : Info, Warning, Critique
- 4 types d'alertes : Agent hors ligne, CPU élevé, RAM élevée, Disque plein
- Hystérésis pour éviter les alertes oscillantes
- Historique des alertes sur 30 jours

### Notifications par email

- Envoi automatique d'emails pour les alertes Warning et Critique
- Configuration des destinataires via l'interface web
- Contenu détaillé de l'alerte avec lien vers le dashboard

### Gestion centralisée

- Configuration des seuils d'alerte (globaux ou par agent)
- Gestion des utilisateurs avec 3 profils (Administrateur, Opérateur, Lecture seule)
- Génération de jetons d'enrôlement pour les nouveaux agents
- Export CSV des listes d'agents et d'alertes

### Multiplateforme

- Support complet de Windows, Linux et macOS
- Agent Python unique pour tous les systèmes d'exploitation
- Collecte de métriques standardisées indépendamment de l'OS

---

## Fonctionnement général

### L'agent

L'agent est un logiciel léger installé sur chaque machine du parc. Son rôle est de :

- Collecter les métriques système (CPU, RAM, disque, etc.) toutes les 30 secondes
- Envoyer ces métriques au serveur central via une connexion HTTPS sécurisée
- Recevoir et appliquer automatiquement les configurations envoyées par le serveur
- Gérer automatiquement les reconnexions en cas de perte de réseau

L'agent s'installe facilement via un package standard (MSI, DEB, RPM, PKG) et se configure avec un jeton d'enrôlement unique.

### La plateforme centrale

Le serveur central est le cœur du système. Son rôle est de :

- Recevoir et traiter les heartbeats de tous les agents
- Stocker les métriques et calculer les informations dérivées (statut en ligne/hors ligne)
- Générer automatiquement les alertes lorsque les seuils sont dépassés
- Envoyer les notifications par email
- Fournir l'API pour le dashboard web
- Gérer la configuration centralisée

### Le dashboard

Le dashboard est l'interface web accessible aux utilisateurs. Il permet de :

- Consulter la vue d'ensemble du parc (KPIs, liste des agents)
- Voir les détails d'une machine spécifique (métriques, alertes actives)
- Gérer la liste des alertes (filtrage, acquittement)
- Configurer les seuils et paramètres globaux
- Gérer les utilisateurs et les agents

### Les alertes

Les alertes sont des notifications automatiques générées par le serveur lorsqu'une anomalie est détectée :

- Elles sont basées sur des seuils configurables (CPU, RAM, disque, temps hors ligne)
- Elles ont 3 niveaux de gravité (Info, Warning, Critique)
- Elles peuvent être acquittées manuellement par les utilisateurs
- Elles sont résolues automatiquement lorsque la condition disparaît
- Elles sont conservées dans l'historique pendant 30 jours

### Les notifications

Les notifications sont les messages envoyés aux équipes pour les informer des alertes :

- En V1, seul le canal email est implémenté
- Les alertes Info ne déclenchent pas de notification
- Les alertes Warning et Critique déclenchent un email immédiat
- Les destinataires sont configurés globalement dans les paramètres

---

## Principes du projet

La conception de CBC Supervision Platform est guidée par les principes suivants :

### Simplicité

L'interface et l'installation doivent être accessibles sans nécessiter une expertise approfondie. L'agent s'installe en quelques minutes avec un package standard, et le dashboard est intuitif pour tous les profils utilisateurs.

### Fiabilité

Le système doit fonctionner de manière prévisible et cohérente. Les agents gèrent automatiquement les reconnexions, et le serveur continue d'opérer même en cas de défaillance partielle.

### Sécurité

La sécurité est intégrée par design : communications chiffrées, authentification forte, gestion des accès basée sur les rôles, et protection des données sensibles.

### Performance

La plateforme doit supporter des milliers d'agents sans dégradation des performances. Les heartbeats sont légers et le traitement est optimisé pour minimiser la latence.

### Maintenabilité

Le code est structuré pour faciliter les évolutions futures. La séparation des responsabilités entre agent, serveur et dashboard permet des modifications indépendantes.

### Extensibilité

L'architecture est conçue pour accueillir de nouvelles fonctionnalités sans refondre le système. De nouveaux types de télémétries, de canaux de notification ou d'intégrations peuvent être ajoutés progressivement.

### Scalabilité

Le système peut évoluer horizontalement pour accompagner la croissance du parc. Le serveur central peut être déployé en cluster pour gérer une charge accrue.

### Multiplateforme

La solution fonctionne de manière identique sur Windows, Linux et macOS, offrant une expérience unifiée quel que soit l'environnement.

---

## Exigences non fonctionnelles

### Disponibilité

- Le serveur central doit être disponible 99.5% du temps en production
- Le dashboard doit être accessible en permanence pendant les heures ouvrées
- Les agents doivent continuer de fonctionner en cas d'indisponibilité temporaire du serveur

### Performance

- Le temps de traitement d'un heartbeat doit être inférieur à 100ms
- Le dashboard doit afficher les données en moins de 2 secondes
- L'agent doit consommer moins de 1% de CPU et 50 Mo de RAM

### Sécurité

- Toutes les communications doivent être chiffrées en TLS 1.3 minimum
- Les mots de passe doivent être hachés avec un algorithme moderne (bcrypt ou argon2)
- Les jetons d'authentification doivent expirer après une durée configurable
- Les actions sensibles doivent être tracées dans les logs d'audit

### Maintenabilité

- Le code doit respecter les standards de qualité (linting, tests unitaires)
- La documentation doit être maintenue à jour avec les évolutions
- Les erreurs doivent être journalisées avec un niveau de détail suffisant pour le diagnostic

### Évolutivité

- Le système doit supporter jusqu'à 10 000 agents en V1
- L'ajout de nouveaux agents ne doit pas dégrader les performances existantes
- La base de données doit pouvoir être migrée vers un cluster si nécessaire

### Observabilité

- Les métriques internes du système doivent être exposées (CPU, mémoire, latence)
- Les erreurs doivent être visibles dans un système de monitoring centralisé
- Les logs doivent être structurés et facilement analysables

### Résilience

- Le système doit tolérer la perte de connexions temporaires des agents
- Le serveur doit pouvoir redémarrer sans perte de données critiques
- Les opérations en échec doivent pouvoir être réessayées automatiquement

### Volumétrie

**À DÉFINIR / À VALIDER**

- **Nombre d'agents** : Cible de plusieurs centaines de machines (serveurs + postes de travail)
- **Fréquence des heartbeats** : 30 secondes par agent
- **Volume de données par heartbeat** : ~1 KB par heartbeat
- **Volume de données quotidien** : À calculer selon le nombre d'agents et la fréquence
- **Volume d'alertes** : Variable selon l'activité du parc, estimation à fournir par CBC
- **Croissance prévue** : À définir selon la stratégie de déploiement de CBC

### Dimensionnement

**À DÉFINIR / À VALIDER**

- **Ressources serveur central** :
  - CPU : À dimensionner selon le nombre d'agents
  - RAM : À dimensionner selon le nombre d'agents et la charge
  - Stockage : À dimensionner selon la rétention des données
- **Base de données** :
  - PostgreSQL : Capacité cible pour plusieurs centaines de machines
  - Redis : Cache pour les données fréquemment accédées
- **Capacité cible** : Plusieurs centaines de machines (serveurs + postes de travail)

### Sauvegarde

**À DÉFINIR / À VALIDER**

- **Stratégie de sauvegarde** :
  - Sauvegarde complète de la base de données
  - Sauvegarde des fichiers de configuration
  - Sauvegarde des logs d'audit
- **Fréquence** : À définir selon les exigences de CBC
- **Rétention** : À définir selon les exigences de CBC
- **Restauration** : Procédure de restauration à documenter
- **Paramètres RPO/RTO** : À définir selon les exigences de CBC

---

## Cas d'utilisation

### Cas 1 - Surveillance quotidienne du parc

Un administrateur système consulte le dashboard chaque matin pour vérifier l'état global du parc. Il identifie rapidement les machines hors ligne ou en anomalie grâce aux indicateurs visuels (badges de couleur, barres de progression). Il peut alors prioriser ses interventions en fonction de la gravité des alertes.

### Cas 2 - Traitement d'une alerte critique

Un opérateur reçoit un email l'informant que le disque d'un serveur critique est à 96% d'utilisation. Il clique sur le lien dans l'email pour accéder directement au dashboard, consulte les métriques de la machine, identifie les fichiers volumineux à supprimer, effectue le nettoyage, puis acquitte l'alerte depuis l'interface web.

### Cas 3 - Installation d'un nouvel agent

Un technicien doit déployer l'agent sur un nouveau serveur. Il se connecte au dashboard, génère un jeton d'enrôlement à usage unique, installe l'agent sur le serveur avec ce jeton, et vérifie quelques secondes plus tard que le nouveau serveur apparaît dans la liste des agents avec le statut "En ligne".

### Cas 4 - Ajustement des seuils

Après avoir observé que certains serveurs génèrent fréquemment des alertes CPU Warning à 80% alors que cette charge est normale pour eux, un administrateur configure des seuils personnalisés pour ces machines spécifiques (CPU Warning à 90%, Critique à 95%). Les alertes cessent d'être générées pour ces serveurs, tandis que les seuils globaux s'appliquent toujours aux autres machines.

### Cas 5 - Consultation de l'historique

Un responsable infrastructure souhaite analyser les tendances des incidents sur le dernier mois. Il accède à la liste des alertes, filtre par la période des 30 derniers jours, exporte le résultat en CSV, et utilise un tableur pour identifier les machines les plus problématiques et planifier les actions de maintenance préventives.

---

## Périmètre

### Inclus dans la V1.1

**Supervision**
- ✅ Collecte de métriques système (CPU, RAM, disque, uptime)
- ✅ Détection automatique des agents hors ligne (seuils différenciés par type de machine)
- ✅ Détection automatique des anomalies (CPU, RAM, disque)
- ✅ Agent multiplateforme (Windows, Linux, macOS)
- ✅ Différenciation serveurs/postes de travail (machine_type)
- ✅ Supervision des services système (préparée, liste officielle à définir)
- ✅ Supervision des fichiers (préparée, liste officielle à définir)

**Alertes**
- ✅ 3 niveaux de gravité (Info, Warning, Critique)
- ✅ Types d'alertes (hors ligne, CPU, RAM, disque, services, fichiers)
- ✅ Seuils configurables (globaux et par agent)
- ✅ Acquittement manuel des alertes
- ✅ Historique des alertes (30 jours)
- ✅ Règle R11 : Détection des pannes du canal de notification

**Notifications**
- ✅ Notifications via API Mail Service CBC (implémentation conforme documentation v1.0)
- ✅ Configuration des destinataires
- ✅ Indicateur visuel de l'état du canal de notification (R11)
- ✅ Contenu détaillé avec lien vers le dashboard
- ✅ Health check automatique via endpoint /health
- ✅ Sécurisation de la clé API via variables d'environnement

**Dashboard**
- ✅ Vue d'ensemble du parc (KPIs, liste des agents)
- ✅ Détails par machine (métriques, alertes actives)
- ✅ Liste des alertes avec filtrage
- ✅ Gestion des agents (configuration, révocation, suppression)
- ✅ Paramètres globaux (seuils, notifications API CBC, rétention)
- ✅ Indicateur visuel du canal de notification (Opérationnel/Dégradé/Erreur)
- ✅ Configuration paramétrable de supervision des services système
- ✅ Configuration paramétrable de supervision des fichiers

**Gestion**
- ✅ 3 profils utilisateurs (Admin, Opérateur, Lecture seule)
- ✅ Génération de jetons d'enrôlement
- ✅ Export CSV (agents, alertes)
- ✅ Configuration centralisée

**Sécurité**
- ✅ Communications HTTPS authentifiées
- ✅ Jetons d'enrôlement à usage unique
- ✅ Gestion des rôles et permissions

**Documentation**
- ✅ Exigences non fonctionnelles (Volumétrie, Dimensionnement, Sauvegarde)

### Prévu pour les versions futures

**Supervision avancée**
- ✅ Supervision des services système (mécanisme paramétrable prêt, liste officielle à définir par CBC)
- ✅ Supervision des fichiers (mécanisme paramétrable prêt, liste officielle à définir par CBC)
- ⏳ Supervision des logs applicatifs
- ⏳ Supervision réseau avancée (bande passante, connexions)
- ⏳ Historique des télémétries (time-series)

**Notifications**
- ✅ API Mail Service CBC (implémenté selon documentation v1.0)
- ⏳ SMS
- ⏳ Slack
- ⏳ Microsoft Teams
- ⏳ Telegram
- ⏳ Webhook

**Dashboard**
- ⏳ Graphiques temporels et tendances
- ⏳ Statistiques globales agrégées
- ⏳ Personnalisation de l'affichage
- ⏳ Rapports automatisés planifiés

**Gestion des agents**
- ⏳ Mise à jour automatique des agents
- ⏳ Gestion de groupes d'agents
- ⏳ Désactivation d'agents
- ⏳ Suppression automatique après désinstallation

**Sécurité**
- ⏳ MFA (Multi-Factor Authentication)
- ⏳ Intégration LDAP/Active Directory

**Données**
- ⏳ Persistance locale des données hors ligne
- ⏳ Synchronisation différée

**Internationalisation**
- ⏳ Support multilingue
- ⏳ Conversion de fuseau horaire

---

## Roadmap

### V1.0 - Fondation

*Objectif : Supervision basique du parc avec alertes par email*

- ✅ Agent multiplateforme (Windows, Linux, macOS)
- ✅ Collecte de 21 télémétries système
- ✅ Détection automatique des agents hors ligne
- ✅ Alertes avec 3 niveaux de gravité
- ✅ Notifications par email
- ✅ Dashboard web avec vue d'ensemble et détails
- ✅ Gestion des utilisateurs avec 3 profils
- ✅ Configuration centralisée

### V1.1 - Amélioration de l'expérience

*Objectif : Renforcer l'UX et la fiabilité*

- ⏳ Graphiques temporels basiques
- ⏳ Amélioration des filtres et de la recherche
- ⏳ Mode maintenance pour les agents
- ⏳ Amélioration de la gestion des erreurs
- ⏳ Documentation utilisateur complète

### V1.2 - Extensions de supervision

*Objectif : Étendre les capacités de supervision*

- ⏳ Supervision des processus et services
- ⏳ Supervision réseau basique
- ⏳ Historique des télémétries (7 jours)
- ⏳ Rapports CSV avancés
- ⏳ Canaux de notification additionnels (Slack, Teams)

### V2.0 - Plateforme d'entreprise

*Objectif : Transformation en plateforme de supervision complète*

- ⏳ Mise à jour automatique des agents
- ⏳ Gestion de groupes d'agents
- ⏳ Intégration LDAP/Active Directory
- ⏳ MFA (Multi-Factor Authentication)
- ⏳ API publique pour intégrations tierces
- ⏳ Historique des télémétries complet (time-series)
- ⏳ Dashboard avancé avec tendances et prédictions

---

## Technologies

| Composant | Technologie | Description |
|-----------|-------------|-------------|
| **Agent** | Python 3.9+ | Langage principal pour la multiplateforme |
| **Backend** | Python 3.9+ | Framework web et API REST |
| **Frontend** | JavaScript moderne | Framework SPA pour le dashboard |
| **Base de données** | PostgreSQL | Stockage relationnel des données |
| **API** | REST HTTPS | Interface de communication standard |
| **Communications** | HTTPS/TLS | Chiffrement des communications agent-serveur |
| **Déploiement** | Docker | Conteneurisation pour simplifier le déploiement |

---

## Configuration des fenêtres horaires

Les fenêtres horaires permettent de définir les périodes pendant lesquelles les postes de travail sont censés être disponibles. En dehors de ces périodes, l'absence d'un poste ne générera pas d'alerte offline.

### Configuration par défaut

Les fenêtres horaires sont désactivées par défaut. Elles doivent être activées explicitement dans la configuration.

### Configuration YAML (Agent)

```yaml
availability:
  enabled: false  # Activer pour utiliser les fenêtres horaires
  time_windows:
    monday:
      - start: "08:00"
        end: "12:00"
      - start: "14:00"
        end: "18:00"
    tuesday:
      - start: "08:00"
        end: "12:00"
      - start: "14:00"
        end: "18:00"
    # ... autres jours
  offline_threshold_seconds: null  # null = utiliser le seuil par défaut
```

### Configuration Frontend

Dans le dashboard, naviguez vers **Paramètres > Fenêtres Horaires** pour configurer :

- Activation/désactivation des fenêtres horaires
- Plages horaires par jour (support de plages multiples)
- Seuil offline personnalisé (optionnel)

### Comportement

- **Serveurs** : Toujours supervisés 24/7, les fenêtres horaires ne s'appliquent pas
- **Postes de travail** : Supervisés uniquement pendant les fenêtres horaires configurées
- **Hors fenêtres** : L'absence d'un poste ne génère pas d'alerte offline
- **Dans fenêtres** : L'absence d'un poste génère une alerte selon le seuil configuré

### Politiques

- **Politique globale** : S'applique à tous les agents sans configuration spécifique
- **Politique par agent** : Remplace la politique globale pour un agent spécifique

---

## Mode dégradé de l'agent

L'agent implémente un mode dégradé pour garantir la continuité de la supervision même en cas d'indisponibilité du serveur central.

### Fonctionnement

Lorsque le serveur central est inaccessible, l'agent:
- Stocke les heartbeats localement dans un buffer en mémoire
- Continue de collecter les métriques système à intervalle régulier
- Tente de se reconnecter au serveur avec un mécanisme de retry
- Envoie automatiquement les heartbeats bufferisés lorsque la connexion est rétablie

### Configuration

Le mode dégradé peut être configuré via le fichier `config.yaml` de l'agent:

```yaml
degraded_mode:
  enabled: true  # Activer le mode dégradé
  buffer_size: 100  # Nombre maximum de heartbeats à stocker
  retry_on_recovery: true  # Envoyer les heartbeats bufferisés lors de la reconnexion
```

### Paramètres

- **enabled** : Active ou désactive le mode dégradé (défaut: true)
- **buffer_size** : Nombre maximum de heartbeats stockés en mémoire (défaut: 100)
- **retry_on_recovery** : Envoie automatiquement les heartbeats bufferisés quand la connexion revient (défaut: true)

### Limites

- Les heartbeats sont stockés en mémoire volatile et sont perdus si l'agent redémarre
- Le buffer circulaire supprime automatiquement les heartbeats les plus anciens quand la limite est atteinte
- La synchronisation différée peut créer un délai dans l'affichage des métriques

---

## Logging structuré et rotation des logs

La plateforme utilise un système de logging structuré pour faciliter le diagnostic et le monitoring.

### Logging du serveur

Le serveur implémente un logging structuré en format JSON avec les caractéristiques suivantes:

- **Format JSON** : Tous les logs sont en format JSON structuré pour une analyse facile
- **Double sortie** : Logs envoyés à la fois vers un fichier et la console
- **Rotation automatique** : Les fichiers de logs sont gérés avec rotation pour éviter la saturation disque
- **Métadonnées enrichies** : Chaque log inclut timestamp, niveau, module, fonction, et ligne de code

### Configuration du logging serveur

Le logging est configuré dans `server/src/main.py`:

```python
# Handler fichier avec rotation
file_handler = logging.FileHandler("logs/application.log")
file_handler.setFormatter(JSONFormatter())

# Handler console
console_handler = logging.StreamHandler()
console_handler.setFormatter(JSONFormatter())
```

### Logging de l'agent

L'agent implémente également un système de logging avec rotation configurable:

```yaml
logging:
  level: INFO  # Niveau de log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
  file: agent.log  # Nom du fichier de log
  rotation:
    enabled: true  # Activer la rotation
    max_size_mb: 10  # Taille max avant rotation
    backup_count: 5  # Nombre de fichiers de backup à conserver
```

### Logs d'audit

Toutes les actions sensibles sont tracées dans les logs d'audit:
- Connexions utilisateurs
- Enrôlement d'agents
- Acquittement et résolution d'alertes
- Modifications de configuration

---

## Métriques Prometheus et Monitoring

Le serveur expose des métriques Prometheus pour le monitoring de la plateforme elle-même.

### Endpoint de métriques

Les métriques sont disponibles via l'endpoint `/metrics`:

```bash
curl http://localhost:8000/metrics
```

### Métriques exposées

| Métrique | Type | Description |
|----------|------|-------------|
| `http_requests_total` | Counter | Nombre total de requêtes HTTP (par méthode, endpoint, status) |
| `http_request_duration_seconds` | Histogram | Durée des requêtes HTTP |
| `active_agents` | Gauge | Nombre d'agents actifs |
| `total_alerts` | Gauge | Nombre total d'alertes (par gravité) |
| `websocket_connections` | Gauge | Nombre de connexions WebSocket actives |

### Intégration Prometheus

Pour intégrer avec Prometheus, ajoutez ceci à votre configuration `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'cbc-supervision'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
```

---

## Cache Redis

La plateforme utilise Redis pour mettre en cache les données fréquemment accédées afin d'améliorer les performances et réduire la charge sur la base de données.

### Utilisation du cache

Le cache est utilisé pour:
- **Liste des agents** : Cache des résultats paginés (TTL: 30 secondes)
- **Liste des alertes** : Cache des résultats paginés (TTL: 30 secondes)
- **Données de configuration** : Cache des paramètres globaux

### Configuration du cache

Le service de cache est configuré dans `server/src/cache_service.py`:

```python
# Stocker dans le cache (TTL: 30 secondes)
cache_service.set(cache_key, result, ttl=30)

# Récupérer depuis le cache
cached_data = cache_service.get(cache_key)

# Invalider un pattern de cache
cache_service.delete_pattern("agents:*")
```

### Invalidation du cache

Le cache est automatiquement invalidé lors:
- De la mise à jour d'un agent
- De la création d'une nouvelle alerte
- De la modification de la configuration

### Avantages

- Réduction de la charge base de données
- Temps de réponse amélioré pour les endpoints fréquents
- Scalabilité accrue pour les requêtes de lecture

---

## WebSocket et Notifications en temps réel

La plateforme utilise WebSocket pour envoyer des notifications en temps réel aux clients connectés.

### Fonctionnalités WebSocket

- **Notifications d'alertes** : Les nouvelles alertes sont poussées en temps réel
- **Mises à jour d'agents** : Les changements de statut sont immédiatement visibles
- **Connexions multiples** : Support de plusieurs clients simultanés

### Endpoint WebSocket

```javascript
// Connexion WebSocket
const ws = new WebSocket('ws://localhost:8000/ws');

// Écouter les messages
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Notification:', data);
};
```

### Gestion des connexions

Le gestionnaire WebSocket (`server/src/websocket_manager.py`) gère:
- L'inscription des clients
- La diffusion des messages
- La gestion des déconnexions
- Le nettoyage des connexions inactives

### Types de notifications

- `alert_created` : Nouvelle alerte créée
- `alert_acknowledged` : Alerte acquittée
- `alert_resolved` : Alerte résolue
- `agent_online` : Agent revenu en ligne
- `agent_offline` : Agent passé hors ligne

---

## Health Checks

La plateforme fournit plusieurs endpoints de health check pour le monitoring de l'état du système.

### Endpoints disponibles

| Endpoint | Description |
|----------|-------------|
| `/` | Informations de base (nom, version, statut) |
| `/health` | Health check général du service |
| `/health/db` | Health check de la connexion base de données |
| `/metrics` | Métriques Prometheus |

### Exemples de réponses

```bash
# Health check général
curl http://localhost:8000/health
# {"status":"healthy","service":"CBC Supervision Platform","version":"1.1.0"}

# Health check base de données
curl http://localhost:8000/health/db
# {"status":"healthy","database":"connected"}
```

### Utilisation

Ces endpoints peuvent être utilisés par:
- **Load balancers** : Pour vérifier la disponibilité du service
- **Orchestrateurs** : Kubernetes, Docker Swarm pour les health checks
- **Moniteurs** : Nagios, Zabbix pour le monitoring

---

## Configuration par environnement

La plateforme supporte la configuration par environnement via des fichiers `.env` et des variables d'environnement.

### Fichier .env.example

Un fichier exemple est fourni dans `server/.env.example`:

```bash
# Base de données
DATABASE_URL=postgresql://cbc_user:cbc_password@localhost:5432/cbc_supervision

# Sécurité
SECRET_KEY=your-secret-key-change-in-production

# API Mail Service CBC
CBC_MAIL_API_ENDPOINT=http://lumen-mail-service.test
CBC_MAIL_API_KEY=your-api-key

# Fréquences
HEARTBEAT_INTERVAL_SECONDS=30
HEARTBEAT_TIMEOUT_SECONDS=90
```

### Chargement de la configuration

La configuration est chargée via `pydantic-settings` dans `server/src/config.py`:

```python
class Settings(BaseSettings):
    database_url: str = "postgresql://..."
    secret_key: str = "your-secret-key"
    
    class Config:
        env_file = ".env"
        case_sensitive = False
```

### Environnements typiques

- **Développement** : Configuration locale avec SQLite ou PostgreSQL local
- **Staging** : Configuration de pré-production avec données de test
- **Production** : Configuration optimisée avec secrets sécurisés

---

## Rate Limiting et Protection

La plateforme implémente un rate limiting pour protéger contre les abus et les attaques par force brute.

### Configuration du rate limiting

Le rate limiting est implémenté avec `slowapi` et configuré par endpoint:

```python
@limiter.limit("20/minute")  # 20 enrôlements par minute
def enroll_agent(...)

@limiter.limit("5/minute")  # 5 tentatives de login par minute
def login(...)

@limiter.limit("100/minute")  # 100 requêtes par minute pour les listes
def list_agents(...)
```

### Protection contre force brute

- **Login** : Limité à 5 tentatives par minute par adresse IP
- **Enrôlement** : Limité à 20 enrôlements par minute
- **API endpoints** : Limités à 100 requêtes par minute par adresse IP

### Comportement en cas de dépassement

Lorsque la limite est dépassée, le serveur retourne:
- Status HTTP 429 (Too Many Requests)
- Message d'erreur explicite
- Header `Retry-After` indiquant le temps d'attente

---

## Configuration des fréquences

Toutes les fréquences sont centralisées dans `server/src/config.py` et peuvent être configurées via variables d'environnement.

### Fréquences configurables

| Paramètre | Valeur par défaut | Description |
|-----------|------------------|-------------|
| `heartbeat_interval_seconds` | 30 | Intervalle d'envoi des heartbeats par l'agent |
| `heartbeat_timeout_seconds` | 90 | Timeout de réception des heartbeats côté serveur |
| `offline_check_interval_seconds` | 60 | Fréquence de vérification des agents offline |
| `services_check_interval_seconds` | 60 | Intervalle de vérification des services |
| `files_check_interval_seconds` | 300 | Intervalle de vérification des fichiers |
| `notification_channel_health_check_interval_seconds` | 60 | Fréquence du health check du canal de notification |

### Variables d'environnement

```bash
# Fréquences
HEARTBEAT_INTERVAL_SECONDS=30
HEARTBEAT_TIMEOUT_SECONDS=90
OFFLINE_CHECK_INTERVAL_SECONDS=60
SERVICES_CHECK_INTERVAL_SECONDS=60
FILES_CHECK_INTERVAL_SECONDS=300
NOTIFICATION_CHANNEL_HEALTH_CHECK_INTERVAL_SECONDS=60
```

---

## Déploiement avec Docker

La plateforme CBC Supervision Platform peut être déployée facilement avec Docker et Docker Compose pour simplifier l'installation et la gestion des dépendances.

### Prérequis

- Docker 20.10+
- Docker Compose 2.0+

### Structure Docker

Le projet inclut les fichiers Docker suivants dans le répertoire `docker/`:

- `Dockerfile.server` : Image Docker pour le serveur central (FastAPI + PostgreSQL)
- `docker-compose.yml` : Configuration Docker Compose pour l'orchestration des services

### Démarrage rapide avec Docker Compose

1. **Cloner le dépôt et naviguer vers le répertoire racine**

```bash
cd /path/to/CBC-Supervision-Platform
```

2. **Lancer les services avec Docker Compose**

```bash
docker-compose -f docker/docker-compose.yml up -d
```

Cette commande démarre:
- **PostgreSQL 15** : Base de données pour le stockage des agents, alertes et métriques
- **Serveur FastAPI** : API REST sur le port 8000

3. **Vérifier que les services sont en cours d'exécution**

```bash
docker-compose -f docker/docker-compose.yml ps
```

4. **Accéder à l'API**

- API Documentation (Swagger) : http://localhost:8000/docs
- API Documentation (ReDoc) : http://localhost:8000/redoc
- Health Check : http://localhost:8000/health

### Configuration

Les variables d'environnement peuvent être configurées dans le fichier `docker-compose.yml` ou via un fichier `.env`:

```yaml
environment:
  DATABASE_URL: postgresql://cbc_user:cbc_password@postgres:5432/cbc_supervision
  SECRET_KEY: your-secret-key-change-in-production
  CBC_MAIL_API_ENDPOINT: http://lumen-mail-service.test
  CBC_MAIL_API_KEY: your-api-key
```

### Commandes utiles

```bash
# Démarrer les services
docker-compose -f docker/docker-compose.yml up -d

# Arrêter les services
docker-compose -f docker/docker-compose.yml down

# Voir les logs
docker-compose -f docker/docker-compose.yml logs -f

# Redémarrer un service spécifique
docker-compose -f docker/docker-compose.yml restart server

# Reconstruire les images après modification
docker-compose -f docker/docker-compose.yml up -d --build
```

### Persistance des données

Les données PostgreSQL sont persistées dans un volume Docker nommé `postgres_data`. Les données sont conservées même après l'arrêt des conteneurs.

### Sécurité en production

Pour un déploiement en production, assurez-vous de:

1. **Modifier les mots de passe par défaut** dans `docker-compose.yml`
2. **Utiliser des secrets Docker** ou un gestionnaire de secrets pour les clés sensibles
3. **Configurer HTTPS/TLS** pour les communications
4. **Limiter l'accès réseau** avec des réseaux Docker privés
5. **Utiliser des images Docker signées et vérifiées**

### Déploiement du frontend

Le frontend React peut être construit et servi via un conteneur nginx séparé. Consultez la documentation d'installation pour plus de détails.

---

## Structure du dépôt

```
cbc-supervision-platform/
├── src/                       # Source du frontend React
│   ├── components/            # Composants React réutilisables
│   │   ├── common/           # Composants communs (Badge, Modal, etc.)
│   │   └── layout/           # Composants de layout (Header, Sidebar)
│   ├── context/              # Contexte global React (AppContext)
│   ├── services/             # Services API
│   │   ├── api/              # Services d'appel API (auth, agents, alerts, etc.)
│   │   ├── types/            # Types TypeScript pour les DTOs API
│   │   └── mappers/          # Mappers backend → frontend
│   ├── views/                # Vues principales (Dashboard, Agents, Alerts, etc.)
│   ├── types.ts              # Types TypeScript globaux
│   ├── App.tsx               # Composant principal React
│   └── main.tsx              # Point d'entrée React
├── server/                    # Code source du serveur central
│   ├── src/                   # Source principal
│   │   ├── models.py          # Modèles SQLAlchemy ORM
│   │   ├── main.py            # Application FastAPI principale
│   │   ├── database.py        # Configuration base de données
│   │   ├── auth_service.py    # Service d'authentification
│   │   ├── alert_service.py   # Service de gestion des alertes
│   │   ├── permissions.py     # Gestion des permissions RBAC
│   │   ├── audit_logger.py    # Logger d'audit
│   │   ├── websocket_manager.py # Gestion WebSocket
│   │   └── cache_service.py   # Service de cache Redis
│   ├── tests/                 # Tests unitaires et intégration
│   ├── alembic/               # Migrations de base de données
│   ├── logs/                  # Logs d'application
│   ├── ssl/                   # Certificats SSL
│   └── requirements.txt       # Dépendances Python
├── docs/                      # Documentation du projet
│   ├── specification/         # Spécification fonctionnelle
│   ├── architecture/          # Documentation technique
│   └── api/                   # Documentation de l'API
├── scripts/                   # Scripts utilitaires
│   ├── deploy/                # Scripts de déploiement
│   ├── setup/                 # Scripts d'installation
│   └── maintenance/          # Scripts de maintenance
├── tests/                     # Tests d'intégration E2E
│   ├── docker-compose.yml     # Environnement de test
│   └── fixtures/              # Données de test
├── docker/                    # Configuration Docker
│   ├── Dockerfile.agent       # Image Docker de l'agent (tests)
│   ├── Dockerfile.server      # Image Docker du serveur
│   └── Dockerfile.dashboard   # Image Docker du dashboard
├── .github/                   # Configuration GitHub
│   ├── workflows/             # Actions GitHub (CI/CD)
│   └── ISSUE_TEMPLATE/        # Modèles d'issues
├── package.json               # Dépendances JavaScript (frontend)
├── tsconfig.json              # Configuration TypeScript
├── vite.config.ts             # Configuration Vite
├── tailwind.config.js         # Configuration TailwindCSS
├── README.md                  # Documentation principale
├── LICENSE                    # Licence du projet
├── CONTRIBUTING.md            # Guide de contribution
└── .gitignore                 # Fichiers ignorés par Git
```

---

## Structure générale du système

Le système CBC Supervision Platform repose sur une architecture à trois composants principaux :

```
┌─────────────────────────────────────────────────────────────────┐
│                        Parc informatique                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │  Agent   │  │  Agent   │  │  Agent   │  │  Agent   │  ... │
│  │ Windows  │  │  Linux   │  │   macOS  │  │ Windows  │      │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘      │
│       │             │             │             │              │
│       └─────────────┴─────────────┴─────────────┘              │
│                     HTTPS (Heartbeats)                         │
└──────────────────────┬──────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────┐
│                    Serveur central                               │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  - Réception des heartbeats                              │  │
│  │  - Stockage des métriques                                │  │
│  │  - Génération des alertes                                │  │
│  │  - Envoi des notifications email                         │  │
│  │  - API pour le dashboard                                 │  │
│  │  - Gestion de la configuration                           │  │
│  └──────────────────────────────────────────────────────────┘  │
└──────────────────────┬──────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────┐
│                    Dashboard web                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  - Vue d'ensemble du parc                                 │  │
│  │  - Détails par machine                                     │  │
│  │  - Liste des alertes                                      │  │
│  │  - Gestion des agents et utilisateurs                     │  │
│  │  - Paramètres globaux                                      │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

**Flux de données :**

1. Les agents collectent les métriques système localement
2. Les agents envoient les métriques au serveur central via HTTPS (toutes les 30 secondes)
3. Le serveur central traite les données, calcule les informations dérivées et génère les alertes
4. Le serveur envoie les notifications email si nécessaire
5. Le dashboard web interroge le serveur via API pour afficher les données aux utilisateurs

---

## Sécurité

### Communications

- **HTTPS obligatoire** : Toutes les communications entre agents et serveur utilisent le protocole HTTPS avec validation du certificat SSL
- **Authentification par jeton** : Chaque agent possède une clé d'authentification unique générée lors de l'enrôlement
- **Jeton d'enrôlement à usage unique** : L'enrôlement d'un nouvel agent nécessite un jeton généré depuis le dashboard, valide 24 heures et utilisable une seule fois

### Gestion des accès

- **3 profils utilisateurs** : Administrateur, Opérateur, Lecture seule
- **Permissions granulaires** : Chaque profil dispose de droits spécifiques (lecture, écriture, administration)
- **Authentification requise** : L'accès au dashboard nécessite une authentification par identifiant et mot de passe
- **Politique de mot de passe** : Minimum 8 caractères, 1 majuscule, 1 chiffre

### Protection des données

- **Secrets jamais en clair** : Les mots de passe et clés d'authentification sont stockés de manière sécurisée (hash)
- **Pas de données sensibles dans les logs** : Les logs ne contiennent pas d'informations d'authentification ou de données sensibles
- **Rétention configurable** : La durée de conservation des données est configurable et automatiquement purgée

### Audit

- **Traçabilité des actions** : Les actions des utilisateurs (connexion, modification) sont loggées
- **Historique des alertes** : Toutes les alertes sont conservées avec leur historique d'acquittement

---

## Journal des versions

### [V1.1.0] - Version actuelle (en développement)

**Changements majeurs**

- ✅ **Fenêtres horaires configurables** : Implémentation complète pour les postes de travail
  - Modèle AvailabilityPolicy avec support de plages horaires multiples par jour
  - Service AvailabilityService pour vérification des fenêtres horaires
  - Intégration dans AlertService pour éviter les faux positifs offline
  - Configuration par agent ou politique globale
  - Frontend : Onglet "Fenêtres Horaires" dans SettingsView
  - **⚠️ ATTENTION** : Valeurs par défaut techniques, à définir par CBC

- ✅ **Centralisation des fréquences configurables** : Toutes les fréquences dans config.py
  - heartbeat_interval_seconds : 30s (agent)
  - heartbeat_timeout_seconds : 90s (serveur)
  - offline_check_interval_seconds : 60s
  - services_check_interval_seconds : 60s
  - files_check_interval_seconds : 300s
  - notification_channel_health_check_interval_seconds : 60s

- ✅ **Configuration paramétrable services/fichiers** : Modèles dédiés
  - ServiceMonitoringConfig : enabled, expected_status, check_interval_seconds
  - FileMonitoringConfig : enabled, max_size_mb, check_interval_seconds
  - Support de politiques globales et par agent

- ✅ **Remplacement SMTP par API Mail Service CBC** : Implémentation conforme documentation v1.0
  - Endpoint /mail pour l'envoi de notifications
  - Endpoint /health pour le health check du canal de notification (R11)
  - Authentification via header X-API-Key
  - Sécurisation de la clé API via variables d'environnement (CBC_MAIL_API_KEY)
  - Support des envois HTML avec emojis pour les alertes

- ✅ **Différenciation serveurs/postes de travail** : Ajout du champ machine_type
  - Enum MachineType (SERVER, WORKSTATION)
  - Seuils offline différenciés (90s pour serveurs, 7200s pour postes de travail)
  - Configuration paramétrable dans l'agent (config.yaml)

- ✅ **Suppression des télémétries obsolètes** : Suppression de 3 télémétries
  - Suppression de la température CPU
  - Suppression de la latence réseau
  - Suppression de l'architecture CPU

- ✅ **Mécanisme paramétrable de supervision services/fichiers** : Infrastructure prête
  - Backend : Modèles ServiceMonitoring et FileMonitoring créés
  - Backend : Méthodes check_service_alerts() et check_file_alerts() dans AlertService
  - Agent : Méthodes collect_services() et collect_files() préparées
  - Configuration : Paramètres activables via variables d'environnement
  - Frontend : Onglets de configuration dans SettingsView
  - API : Endpoints /api/settings/services-monitoring et /api/settings/files-monitoring
  - **⚠️ ATTENTION** : Liste officielle des services/fichiers à définir par CBC

- ✅ **Règle R11 - Indicateur visuel du canal de notification** : Implémentation complète
  - Backend : Modèle NotificationChannelStatus créé
  - Backend : Endpoint /api/system/notification-channel-status
  - Frontend : Indicateur visuel dans DashboardView avec polling automatique
  - États : Opérationnel (vert), Dégradé (orange), Erreur (rouge), Désactivé (gris)

- ✅ **Exigences non fonctionnelles** : Documentation étendue
  - Section Volumétrie ajoutée (placeholders pour valeurs à définir)
  - Section Dimensionnement ajoutée (placeholders pour ressources serveur)
  - Section Sauvegarde ajoutée (placeholders pour stratégie de sauvegarde)

**Changements techniques**

- ✅ Migration Alembic v1_1_0_migration.py créée pour les changements de schéma
- ✅ Mise à jour des tests backend pour V1.1
- ✅ Mise à jour des types TypeScript (BackendAgent, BackendMessagingConfig, BackendNotificationChannelStatus)
- ✅ Mise à jour de AppContext pour inclure les nouvelles configurations
- ✅ Mise à jour de SettingsView avec les onglets services/fichiers

**Informations requises de CBC**

Pour finaliser la V1.1, les informations suivantes sont nécessaires :
- Liste officielle des services système à superviser (ex: SWIFT AutoClient)
- Liste officielle des fichiers à superviser (ex: fichiers de logs SWIFT)
- Seuil offline officiel pour les postes de travail (placeholder actuel: 7200s)
- Valeurs de dimensionnement serveur (CPU, RAM, stockage)
- Stratégie de sauvegarde (fréquence, rétention, RPO/RTO)

---

### [V1.0.0] - Version précédente

**Fonctionnalités initiales**

- ✅ Agent multiplateforme (Windows, Linux, macOS)
- ✅ Collecte de 21 télémétries système
- ✅ Détection automatique des agents hors ligne
- ✅ Alertes avec 3 niveaux de gravité
- ✅ Notifications par email
- ✅ Dashboard web avec vue d'ensemble et détails
- ✅ Gestion des utilisateurs avec 3 profils
- ✅ Configuration centralisée
- ✅ Export CSV

**Fonctionnalités supplémentaires implémentées**

- ✅ Authentification JWT avec refresh tokens
- ✅ Rate limiting et protection contre force brute
- ✅ Validation stricte des entrées
- ✅ Logs d'audit et traçabilité
- ✅ Historique des métriques et stockage temporel
- ✅ Acquittement et résolution des alertes
- ✅ Gestion des seuils par agent
- ✅ Permissions par rôle (RBAC)
- ✅ Notifications push WebSocket en temps réel
- ✅ Graphiques d'évolution et visualisation des métriques
- ✅ Health check endpoints
- ✅ Configuration par environnement (.env)
- ✅ Logs structurés et centralisation
- ✅ Monitoring avec Prometheus
- ✅ Backup automatique PostgreSQL
- ✅ Migrations de base de données (Alembic)
mobile
- ✅ Dark mode et thèmes
- ✅ Configuration de l'agent par fichier YAML/JSON
- ✅ Mode dégradé et gestion pannes réseau
- ✅ Logs détaillés avec rotation
- ✅ Pagination des listes
- ✅ Cache Redis pour requêtes fréquentes
- ✅ Indexation optimisée PostgreSQL
- ✅ Documentation API Swagger/OpenAPI

---

## Licence

Ce projet est propriété de la Commercial Bank Cameroun. Tous droits réservés.

---

## Contribution

Ce projet est développé en interne pour la Commercial Bank Cameroun. Les contributions externes ne sont pas acceptées à ce stade.

Pour toute question ou suggestion, veuillez contacter l'équipe en charge du projet.

---

## Auteur

**Commercial Bank Cameroun**
- Direction des Systèmes d'Information
- Équipe Infrastructure et Sécurité

*Année 2026*
