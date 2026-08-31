# Plan de reprise — CBC Supervision

**Ouvert le :** 31 août 2026
**Objet :** reconstruire le produit point par point à partir d'une base réduite.
**Règle :** un point livré = code + test + UI qui reflète réellement l'état. Pas d'écran qui affirme ce qui n'existe pas.

---

## Comment lire ce fichier

Une ligne par point du périmètre. `État` décrit ce qui est **vérifié**, pas ce qui est espéré.

| Marque | Sens |
|---|---|
| `vide` | rien en place, tout à écrire |
| `serveur seul` | l'API existe et est testée ; l'agent et/ou l'UI manquent |
| `à revoir` | du code existe mais n'a pas été validé sur ce périmètre |
| `livré` | code + test + UI cohérents, démontrable |

---

## Point 0 — Repartir d'un parc vide

**Demande :** « Delete every agent, let's start implementation at fresh. »

| Action | État |
|---|---|
| Implémentation de l'agent supprimée (`agent/src`, 24 modules + 9 collecteurs) | fait |
| Tests d'agent supprimés (15 fichiers) | fait |
| État local supprimé : `.machine_id`, `data/agent-buffer`, journaux, `test.db` | fait |
| Artefacts PyInstaller périmés supprimés (124 Mo, non suivis) | fait |
| Purge du parc en base | **à exécuter** — voir ci-dessous |

Docker n'était pas démarré : la base PostgreSQL n'a pas pu être vidée depuis ici.
Le script est écrit et vérifié (3 agents semés, comptés, puis effacés) :

```bash
python scripts/ops/purge_agents.py --dry-run     # compte, n'écrit rien
python scripts/ops/purge_agents.py --yes         # exécute
```

Il efface l'inventaire et ce qui en dépend. Il **conserve** les comptes, les
groupes d'administration, les réglages, les gabarits de courriel et le
**journal d'audit** : effacer la trace de ce qui a été fait au parc précédent
n'est pas le but d'une remise à zéro d'inventaire.

Ce qui reste dans `agent/` : `requirements.txt`, `packaging/`, `config.yaml`,
`config.lab.yaml`, `src/__init__.py`. Le paquet `shared/` (contrats
`metric.v1`, `event.v1`, `task.v1`) est conservé — c'est le contrat entre les
deux moitiés, à rouvrir seulement si le point 6 le rend faux.

---

## Points 1 à 10 — état vérifié

| # | Point | Serveur | Agent | UI | État |
|---|---|---|---|---|---|
| 1 | Enrôlement après installation | `POST /api/agents/enroll` + `enrollment_tokens` | **réécrit** | jetons dans Paramètres | **livré** |
| 2 | Champs modifiables / non modifiables | `AGENT_EDITABLE_FIELDS`, `PUT .../name`, `.../location` | constats déclarés | détail hôte | à revoir |
| 3 | Attribution d'un administrateur ou groupe | `admin_groups`, `admin_group_members` | — | Utilisateurs | à revoir |
| 4 | Désinstallation + signalement | `POST /api/agents/deregister`, `PUT .../revoke` | supprimé | détail hôte | serveur seul |
| 5 | Resynchronisation après coupure | `POST /api/agents/heartbeat`, `POST /api/agents/ping` | supprimé | bandeau hors ligne | serveur seul |
| 6 | Métriques paramétrables par hôte | `PUT/GET .../monitoring`, `service_monitoring`, `file_monitoring` | supprimé | onglet Configuration | serveur seul |
| 7 | Prise en charge des métriques par l'agent | — | **vide** | — | vide |
| 8 | Alerte mail + n8n, gabarit par vérification | `mail_templates`, `messaging_service`, `webhook_service` | — | Intégrations | à revoir |
| 9 | Workflow de vérification, validation, prise en charge | `action_approvals`, `/api/approvals` | — | **retirée** | à revoir |
| 10 | Voir où et comment l'agent tourne sur l'OS | colonne `runtime_json` | supprimé | — | vide |
| 11 | Mettre l'UI en accord avec le livré | — | — | — | continu |

> Les points 9 et 10 portent ici les deux entrées numérotées « 8 » et « 9 » de
> la demande initiale, qui comportait deux fois le chiffre 7.

### Point 1 — livré le 31 août 2026

L'agent est réécrit à partir de rien, réduit à ce que le point 1 demande.
Six modules dans `agent/src` :

| Module | Rôle |
|---|---|
| `agent_paths.py` | où l'état vit sur l'hôte (ProgramData / /var/lib), repli sur le profil utilisateur si les droits manquent |
| `identity.py` | `machine_id` stable, tiré une fois puis relu |
| `config.py` | configuration ; priorité ligne de commande > environnement > fichier |
| `facts.py` | ce qui est **constaté** de l'hôte, sans aucune métrique |
| `enrollment.py` | appel d'enrôlement et conservation des jetons |
| `cli.py` | `enroll`, `status`, `version` |

```bash
python agent/src/cli.py enroll --token <jeton> --server-url https://plateforme:8443
python agent/src/cli.py status
```

**40 tests passent**, dont 4 d'intégration qui enrôlent contre
`POST /api/agents/enroll` réellement montée — le seul moyen de prouver que la
charge utile satisfait les contraintes de la plateforme plutôt que ma lecture
de celles-ci. Ce sont eux qui échoueront si les deux moitiés dérivent.

Ce qui est garanti par test :

- l'identité survit à un redémarrage, et une identité corrompue est retirée
  plutôt que propagée vers un enrôlement voué au rejet ;
- le même hôte réenrôlé **met à jour** sa ligne au lieu d'en créer une
  seconde — c'est la reprise après réinstallation ;
- un jeton déjà consommé est refusé, et un refus **n'écrit rien** sur le
  disque de l'hôte ;
- un nom de poste accentué (« PC-Comptabilité ») est ramené à ce que la
  plateforme accepte, au lieu de partir en 422 devant l'installateur ;
- le matériel non mesuré est **omis**, jamais mis à zéro : un 0 dans
  l'inventaire se lirait comme une mesure ;
- le fichier de configuration livré ne porte aucun jeton — il est embarqué
  dans chaque installation.

Restent hors périmètre du point 1, donc absents : heartbeat, collecte,
service système, mise à jour. Le service `agent` de Compose reste commenté
tant qu'il n'y a pas de boucle d'exécution (points 5 et 7).

### Déjà acquis, à ne pas réécrire

- **Identifiant d'hôte** — `server/src/agent_identity.py` produit déjà
  **6 caractères hexadécimaux majuscules** (`A3F09C`), avec contrôle
  d'unicité en base et normalisation de la casse. Conforme au point 2.
- **Séparation constaté / attribué** — le modèle `Agent` distingue déjà les
  champs déclarés par la machine (`hostname`, `ip_address`, `os`, matériel),
  refusés en écriture depuis l'interface, des champs posés par
  l'exploitation (`name`, `location`, responsable, seuils). C'est exactement
  la règle du point 2.

---

## Interface — ce qui a été retiré

Dix écrans hors périmètre, avec leurs routes, entrées de navigation et clés
i18n : Actions, Approbations, Automatisation, Tableaux personnalisés,
Journaux, Réseau, Pilote/UAT, Rapports, Règles, Tendances. Les groupes
« Analyser » et « Automatiser » disparaissent, devenus vides.

Sur le détail d'hôte : onglets réduits à Vue / Métriques / Alertes /
Configuration. L'onglet Actions et le bloc Journaux-Événements-Audit sont
partis.

**Conservé :** Tableau de bord, Parc, Alertes, Intégrations, Utilisateurs,
Audit, Paramètres, Profil, Connexion.

**Primitives disponibles pour la reconstruction :** `PlannedCapability`
(annoncer une capacité non livrée sans simuler son fonctionnement),
`EmptyState`, `GaugeChart`, `SkeletonLoader`.

---

## Points ouverts

1. ~~**Longueur de l'identifiant.**~~ **Tranché le 31 août : 6 caractères
   hexadécimaux majuscules** (`A3F09C`), comme déjà implémenté. Aucun
   changement. Le « 12 » de la demande initiale venait probablement de
   `MAX_GENERATION_ATTEMPTS = 12`, voisin dans le même fichier. Le format est
   désormais vérifié de bout en bout par les tests d'intégration du point 1.
2. **Point 9 sans écran.** Le workflow de validation existe côté serveur
   (`action_approvals`) mais l'écran Approbations a été retiré. Il faudra le
   réécrire au moment du point 9.
3. **n8n (point 8).** Rien n'est câblé. À décider : webhook signé sortant
   seulement, ou intégration bidirectionnelle.
4. **Périmètre du point 10.** « Voir comment et où l'agent tourne » —
   service ou processus, chemin d'installation, utilisateur, version ? À cadrer.

---

## Ce qui bloque

### 1. La suite de tests serveur se fige — bloque la CI

`pytest server/tests` s'arrête invariablement après **33 tests**, sur
`test_agent_uninstall.py::test_deregister_marks_instead_of_deleting`, et
n'avance plus.

Établi : le processus consomme environ 0,1 s de CPU pendant que le temps
s'écoule — il est **bloqué sur une entrée-sortie**, pas en calcul. Les trois
fichiers concernés passent ensemble en 13 s ; le blocage n'apparaît qu'avec la
suite complète. `--timeout=30 --timeout-method=thread` ne se déclenche jamais :
le blocage est donc **hors du corps d'un test**. `test_api.py` — dernier
fichier sur le `test.db` partagé — a été écarté sans effet.

Non reproduit sous Linux à ce jour. La CI tourne sous Linux et tranchera.

> Piège de diagnostic : la sortie de pytest est bufferisée par bloc. Sans
> `python -u`, une suite en bonne santé ressemble à un blocage. Toujours
> `python -u -m pytest`.

### 2. Workflow CI invalide — corrigé

`.github/workflows/ci.yml` ne se lisait pas : ligne 26,
`DATABASE_URL: sqlite:///:memory:` — un scalaire non quoté terminé par un
deux-points, que YAML refuse. Le fichier était donc **invalide depuis son
ajout et n'a jamais pu s'exécuter**, malgré son envoi sur le dépôt. Corrigé
par mise entre guillemets ; le document se lit désormais et expose trois
tâches : `linux-tests`, `lint`, `dashboard`.

Le job `agent-os-matrix` est retiré avec l'implémentation de l'agent : il
lançait `agent/tests/test_os_smoke.py` et construisait un bundle PyInstaller
à partir de modules supprimés. Il revient avec le point 7.

Le service `agent` de `docker/docker-compose.yml` est commenté pour la même
raison : `docker compose up` démarre la plateforme sans agent.

### 3. Dette pré-existante

`ruff` signale 3 erreurs dans `server/src/main.py` (lignes ~1829 et
2349-2352) : clés de dictionnaire dupliquées, dont `disk_total_gb` écrite
deux fois. Antérieures à cette reprise, mais la tâche `lint` de la CI
échouera dessus.

---

## Publication

Le dépôt local est propre. La publication vers
`https://github.com/McjohnDev/sentinel.git` reste **à faire** : `git remote
add` et `git push` ont été refusés par le garde-fou de l'environnement.

```bash
git remote add mcjohn https://github.com/McjohnDev/sentinel.git
git push -u mcjohn main
```

Le dépôt doit exister et être vide. Ce push emporte **tout l'historique**, y
compris le commit `a3dc085` de BRYAN-1-C. Si `McjohnDev/sentinel` doit être
un dépôt neuf plutôt qu'une reprise de ce travail, le dire avant de pousser.
