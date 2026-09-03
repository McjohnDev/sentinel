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
| 2 | Champs modifiables / non modifiables | `PATCH /api/agents/{id}` + `AGENT_EDITABLE_FIELDS` | constats déclarés à l'enrôlement | `EditableAgentField` | **livré** |
| 3 | Attribution d'un administrateur ou groupe | `PATCH` + `admin_groups`, `admin_group_members` | — | `AgentOwnerField` | **livré** |
| 4 | Désinstallation + signalement | `POST /api/agents/deregister` | `uninstall` | détail hôte | **livré** |
| 5 | Resynchronisation après coupure | `POST /api/agents/heartbeat` + écho | `run` | bandeau hors ligne | **livré** (voir réserve) |
| 6 | Métriques paramétrables par hôte | plan d'hôte + poussée au battement | réception + accusé | onglet Configuration | **livré** |
| 7 | Prise en charge des métriques par l'agent | ingestion + alertes | `collectors` + inventaire | onglet Inventaire | **livré** |
| 8 | Alerte mail + n8n, gabarit par vérification | gabarits + webhook signé | — | Courriels par vérification | **livré** |
| 9 | Workflow de vérification, validation, prise en charge | verdict + attribution sur l'alerte | — | tiroir d'alerte | **livré** |
| 10 | Voir où et comment l'agent tourne sur l'OS | `runtime_json` + colonnes indexées | `runtime_info` | `AgentRuntimePanel` | **livré** |
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

### Points 2 et 3 — livrés le 1er septembre 2026

**Point 2 — champs modifiables.** Trouvé déjà en place, et vérifié plutôt que
réécrit. `PATCH /api/agents/{id}` refuse toute écriture sur un champ constaté
**en le nommant**, au lieu de l'ignorer en silence — sans quoi l'utilisateur
croit avoir renommé la machine. Côté interface, `EditableAgentField` tire sa
liste de champs modifiables de `editable_fields`, servi par le serveur avec la
fiche : l'interface ne peut donc ni proposer une modification que l'API
refusera, ni verrouiller un champ qu'elle accepte. 20 tests.

Une note de méthode : le premier relevé d'API avait manqué cette route, faute
d'avoir cherché `@app.patch`. Point 2 était classé « à revoir » alors qu'il
était complet.

**Point 3 — attribution.** Le serveur savait déjà attribuer ; **aucun écran ne
le faisait**. Le détail d'hôte se contentait d'afficher « Non attribué » en
lecture seule. Ajout de `AgentOwnerField` : choix d'un responsable nommé et/ou
d'une équipe d'administration, réservé aux administrateurs.

Les deux voies sont proposées **ensemble**, pas en exclusion : le serveur les
traite en union (`user_administers_agent`), donc un choix exclusif dans
l'interface décrirait faussement qui a la main. L'écran dit aussi ce que
signifie l'absence d'attribution — l'hôte n'est pas « à tout le monde », il ne
reste accessible qu'aux administrateurs globaux.

8 tests couvrent le chemin d'attribution lui-même, qui n'était pas testé : les
tests existants posaient `owner_user_id` à la main sur le modèle. Ils vérifient
qu'attribuer donne effectivement la main au destinataire, qu'un responsable ou
une équipe inconnus sont refusés sans rien écrire, qu'un opérateur hors
périmètre ne peut pas s'attribuer une machine, et que retirer l'attribution
rend l'hôte aux seuls administrateurs.

### Point 4 — livré le 1er septembre 2026

`cbc-agent uninstall` prévient la plateforme avant de partir.

```bash
python agent/src/cli.py uninstall --reason "poste réformé"
```

Ce signalement sépare un retrait *voulu* d'une *panne*. Sans lui, une machine
désinstallée reste « hors ligne » au parc et continue d'alerter pour une
absence décidée — un bruit qu'on ne distingue pas d'un vrai incident.

Deux décisions, tenues par des tests :

- **Les jetons ne sont pas effacés tant que la plateforme n'a pas été
  prévenue.** Si le signalement échoue, l'agent garde ses jetons et le dit,
  pour qu'on puisse réessayer. `--force` passe outre — une machine mise au
  rebut ne rejoindra jamais le réseau — et sort en code non nul même en cas de
  succès, parce que la plateforme reste sur une fausse idée de l'hôte.
- **L'identité machine est conservée.** La plateforme reconnaît un hôte par
  `machine_id` : l'effacer ferait d'une réinstallation un *second* hôte, avec
  un historique coupé en deux.

44 tests d'agent. Trois rejouent le cycle complet contre les vraies routes —
enrôler, désenrôler, réinstaller — et vérifient que l'hôte est *marqué* et non
effacé, que sa ligne et son historique survivent, et qu'une réinstallation
retombe sur le même identifiant. C'est la promesse que la CLI affiche à la
désinstallation : elle méritait un test plutôt qu'une phrase.

### Point 5 — livré le 1er septembre 2026, avec une réserve

C'est ce qui fait qu'un hôte enrôlé cesse d'être « hors ligne » : la
plateforme dérive la présence de la fraîcheur de `last_communication`, que
seul un appel de l'agent rafraîchit.

```bash
python agent/src/cli.py run --interval 30      # bat jusqu'à interruption
python agent/src/cli.py run --once             # un seul battement
python agent/src/cli.py status                 # état de la liaison vu de l'hôte
```

#### Réserve — l'énoncé ne peut pas être tenu littéralement

Le point 5 dit « **la plateforme qui envoie un echo ping** ». Elle ne le peut
pas. Toutes les routes qui s'authentifient en tant qu'agent sont des `POST`
que l'agent émet ; il n'existe ni écoute ni socket côté agent, et
`server/src/main.py` le dit lui-même :

> « La plateforme ne peut pas ouvrir une connexion vers un hôte derrière NAT :
> la réponse au battement est donc le seul canal descendant réel. »

Deux pièges de nom entretiennent la confusion : `POST /api/agents/ping` n'est
pas un ping de la plateforme — c'est l'agent qui l'émet, avec sa propre clé ;
et `network_probe.icmp_ping` vise bien depuis la plateforme, mais des
équipements réseau SNMP, jamais un agent.

**L'écho existe pourtant** — il voyage *dans la réponse* au battement, et
porte ce que l'agent ne peut pas savoir seul : l'identifiant que la plateforme
lui reconnaît, l'écart entre les deux horloges, et la durée du silence qui
vient de s'achever. C'est ce qui est implémenté : l'agent frappe, la
plateforme répond en se faisant connaître.

Un véritable ping plateforme → agent demanderait un transport qui n'existe pas
dans ce produit (écoute sur l'hôte, WebSocket sortante maintenue, MQTT). Ce
n'est pas une reconstruction du point 5 : **à arbitrer avant de le bâtir.**

#### Décisions tenues par des tests

- **Pourcentages ramenés dans 0..100.** psutil peut dépasser 100 brièvement ;
  la plateforme valide la borne et répond 422. Sans ce garde-fou, un pic de
  mesure fait rejeter le battement et l'hôte bascule hors ligne pour une
  raison purement arithmétique.
- **Seul 401 vaut perte d'identité.** L'agent précédent y ajoutait 403 et
  404. Or 403 est ce que rend le serveur pour un hôte *révoqué par un
  administrateur* : s'en servir pour se réenrôler fait rentrer par la fenêtre
  une machine qu'on venait de sortir. Et 404 est ce que rend une URL de base
  fautive — une faute de frappe devenait une boucle de réenrôlement perpétuelle.
- **La perte d'identité arrête la boucle** au lieu de réenrôler seule : un
  réenrôlement automatique consomme un jeton et défait une décision d'admin.
- **Recul progressif** (5 s, 10 s, 20 s… plafonné), cadence nominale rétablie
  au premier succès. Un parc entier qui réessaie à la seconde après une
  coupure suffit à empêcher la plateforme de redémarrer.
- **`last_success_at` survit aux échecs.** C'est la réponse à « hors ligne
  depuis quand ? », posée devant la machine.
- **Les faits d'hôte repartent à chaque battement**, sinon une montée de
  version reste invisible jusqu'à un réenrôlement qui n'arrive jamais.

84 tests d'agent. Quatre contre les vraies routes, dont celui qui énonce la
raison d'être : vieillir un hôte jusqu'au hors-ligne, envoyer **un** battement,
vérifier qu'il se relit « actif ». L'écrire a fait apparaître `ENROLLMENT_GRACE` :
`is_agent_live` garde vivant un hôte fraîchement enrôlé pendant deux minutes
quoi que dise `last_communication` — le test doit donc vieillir `enrolled_at`
aussi.

#### Hors périmètre, assumé

Pas de tampon disque ni de rejeu du retard accumulé. L'énoncé du point 5
demande la *reprise de contact*, pas le rattrapage de l'historique — et
l'analyse de l'agent supprimé montre que le rejeu est précisément là où
étaient ses défauts (perte d'enregistrements sur interruption, rejeu sans
limite ni cadence, ordre inversé écrasant les faits frais par des faits
vieux de 24 h). À reprendre proprement, avec une route d'ingestion par lots.

### Revue des points 1 à 5 — 1er septembre 2026

Deux défauts réels, tous deux dans le code écrit pendant cette reprise.

**Les faits d'hôte étaient figés au démarrage de l'agent.** `cli.py` les
relevait une fois et la boucle réutilisait cet objet indéfiniment.
L'affirmation portée par le code lui-même — les faits repartent à chaque
battement *pour qu'une montée de version soit visible sans réenrôlement* —
n'était vraie qu'à moitié : ils étaient dans chaque envoi, jamais relus. Un
agent installé en service tourne des mois : un poste en DHCP annonçait donc à
jamais l'adresse qu'il avait au lancement. Le test s'appelait
`test_host_facts_ride_on_every_beat` et ne vérifiait que la *présence* des
champs — il passait depuis le début.

Corrigé par `facts.refreshed()`. Le matériel est délibérément repris tel
quel : l'énumération des partitions interroge chaque volume monté, et un
partage réseau figé y bloque. Le refaire à chaque battement mettrait la
liaison à la merci d'un montage bloqué — ce que la supervision doit signaler,
pas subir.

**Le premier battement annonçait une charge processeur inventée.**
`psutil.cpu_percent(interval=None)` compare deux relevés successifs ; au
premier appel il n'y a pas de relevé précédent. Mesuré ici : **100 %**. Chaque
démarrage d'agent envoyait donc un pic de charge fictif, capable de déclencher
une alerte processeur critique sur un hôte fraîchement installé. La première
mesure est désormais réelle et bloquante une seconde.

### VLAN — ajouté le 1er septembre 2026, en deux champs

Un seul champ aurait menti. Une machine sur **port d'accès ne peut pas
connaître son VLAN** : le commutateur pose et retire l'étiquette de façon
transparente.

| Champ | Nature | Source | Vide signifie |
|---|---|---|---|
| `vlan_observed` | constaté, non modifiable | l'agent, si l'hôte étiquette | *non déterminable depuis l'hôte* |
| `vlan` | attribué, modifiable | l'exploitation | non renseigné |

L'agent lit `/proc/net/vlan/config`, à défaut les noms d'interfaces
(`eth0.100`). Un hôte sur trunk peut en porter plusieurs : ils sont tous
rendus, plutôt que d'en choisir un arbitrairement. Détection solide sous
Linux, au mieux sous Windows — où les postes sont de toute façon presque
toujours sur port d'accès.

La fiche d'hôte affiche les deux et **signale la divergence** au lieu de
trancher : un hôte rebranché sur un autre port étiquette un VLAN que la fiche
ignore encore, et c'est précisément cet écart qui est utile.

### Piste — le fichier VLAN de l'équipe réseau

L'équipe réseau peut effectivement fournir la donnée qui manque, mais la
**clé de jointure** décide de tout :

| Clé fournie | Verdict |
|---|---|
| **sous-réseau → VLAN** | **le bon choix** — l'agent remonte déjà `ip_address` à chaque battement ; le VLAN se déduit, se met à jour tout seul quand l'hôte change d'adresse, et le fichier ne vieillit pas quand le parc bouge |
| nom d'hôte → VLAN | exploitable, mais périme dès qu'une machine est rebranchée |
| adresse MAC → VLAN | l'agent ne remonte pas encore la MAC |
| port de commutateur → VLAN | inexploitable sans une table port → hôte que nous n'avons pas |

Un fichier de la forme `sous-réseau ; VLAN ; libellé` couvrirait donc tout le
parc sans saisie par hôte. À demander sous cette forme.

Rien n'est encore développé : il n'existe aucun import dans le produit (seul
l'**export** CSV existe) et aucune notion de sous-réseau. À arbitrer avant de
le bâtir.

### Point 6 — livré le 1er septembre 2026

Trouvé **déjà construit** côté plateforme, et vérifié plutôt que réécrit.
`monitoring_plan.py` couvre les quatre demandes du point 6, et son propre
en-tête raconte ce qu'il a remplacé : des écrans de paramétrage qui
affichaient « mise à jour réussie » sans rien écrire, pendant que le moteur
d'alerte comparait à une liste vide codée en dur.

| Demande | État |
|---|---|
| CPU et RAM par défaut | seuils sur `Agent`, vide = suit la politique globale |
| disque + choix des partitions et de leurs seuils | `disk_mount_rules` |
| liste de services (peut être vide) | `MonitoredService` + état attendu *running* ou *stopped* |
| fichier dont l'existence — ou l'absence — alerte | `FileCondition.MUST_EXIST` / `MUST_NOT_EXIST` |

Le second sens compte dans les deux cas : alerter quand un service critique
s'arrête, mais aussi quand un service qui devait rester à l'arrêt se remet à
tourner ; alerter sur un journal manquant, mais aussi sur un fichier
sentinelle qui apparaît.

**Ce qui manquait était côté agent.** Le plan descend dans la réponse au
battement — seul canal vers un hôte derrière NAT — et l'agent reconstruit le
laissait passer. Ajout de `plan.py` : il range le plan sur l'hôte, puis
l'acquitte.

L'ordre est imposé et tenu par un test : **écrire d'abord, acquitter
ensuite**. Acquitter une version non rangée la ferait disparaître — la
plateforme cesserait de la pousser alors que l'hôte ne l'a jamais reçue, et
l'écart ne se découvrirait qu'au prochain incident. À l'inverse, un accusé
perdu n'interrompt pas le battement : la plateforme repoussera, alors que
priver l'hôte de sa présence serait bien plus lourd.

La version annoncée dans chaque battement est celle **appliquée**, relue du
disque, jamais celle qui vient d'arriver.

17 tests unitaires, plus deux de bout en bout : un plan posé sur la
plateforme descend, se range et s'acquitte, après quoi la plateforme cesse de
le republier — et, sans accusé, il revient à chaque battement, ce qui est
précisément la raison pour laquelle l'acquittement n'est pas facultatif.

**Hors périmètre :** mesurer d'après ce plan. C'est le point 7.

### Relance des alertes ouvertes — livré le 2 septembre 2026

Demande ajoutée en cours de route : *« mail reminder at 3hrs defaults, mais
configurable même par alerte »*. Porté à 12 h le 3 septembre : trois heures
faisait sonner l'alarme au milieu d'une même prise de poste ; douze heures
croise le relais du matin et celui du soir sans devenir du bruit de fond.

Une alerte notifiée une fois puis oubliée ne vaut guère mieux qu'une alerte
jamais émise. Un rappel périodique part donc tant qu'elle reste ouverte.

| Réglage | Où | Valeur |
|---|---|---|
| Parc entier | Paramètres → Seuils globaux | 12 h par défaut, `0` coupe tout |
| Une alerte | Tiroir d'alerte → Relance par courriel | 30 min à 1 jour, ou plus du tout |

Trois décisions valent d'être notées, parce qu'elles auraient pu être prises
autrement :

- **Le décompte repart du dernier message**, pas de l'ouverture. Sans cela, un
  délai raccourci de douze heures à une demi-heure déclencherait aussitôt un
  rappel pour un incident vieux de deux jours.
- **La prise en charge n'interrompt pas la relance.** L'alerte attribuée puis
  oubliée est exactement le cas que ce rappel existe pour rattraper ; l'arrêter
  à l'acquittement le rendrait sans effet, puisqu'on acquitte immédiatement.
  Seule la résolution y met fin.
- **Le réglage vit sur l'alerte, pas sur la vérification.** C'est en traitant
  un incident qu'on sait s'il mérite un rappel rapproché ou aucun, et ce
  jugement ne vaut pas pour toutes les alertes du même type.

Le courriel porte un préfixe `[RELANCE n]` et un bandeau : sans marque, une
relance se lit comme un second incident et fait rouvrir une investigation déjà
en cours. Le gabarit par vérification reste celui de l'exploitant — on le
préfixe plutôt que de le remplacer, faute de quoi il faudrait maintenir deux
mises en forme par vérification, qui divergeraient.

Une fenêtre de maintenance suspend la relance sans la perdre. Un plancher d'un
quart d'heure empêche que le rappel devienne du harcèlement : passé un certain
rythme, l'opérateur apprend à filtrer les messages de la plateforme, et c'est
la notification initiale qui se perd avec eux.

23 tests (`server/tests/test_alert_reminders.py`).

### Prise en charge — correction du 2 septembre 2026

Signalé à l'usage : *« Attribuer à, n'attribue pas réellement »*. Le geste
aboutissait pourtant côté serveur. Deux causes indépendantes se cumulaient :

1. `refreshData()` ne rechargeait rien. Il parcourait les hôtes en mémoire pour
   leur réécrire un horodatage, puis affichait « Données actualisées ». Le nom
   et le message affirmaient tous deux le contraire de ce que la fonction
   faisait.
2. Le tiroir conservait l'alerte telle qu'elle était à son ouverture. Même un
   rechargement réel n'aurait rien changé à l'écran.

Le vrai `refreshFleet` est exposé, et le tiroir lit l'alerte vivante dans la
liste plutôt qu'un instantané.

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

### Refonte visuelle — livrée le 3 septembre 2026

Demande : « build the UI using this as model », une maquette complète
fournie (palette bleue, typographie Geist, barre latérale + en-tête +
palette de commandes, thème clair/sombre).

L'accent retenu est l'or CBC (#A68523), pas le bleu de la maquette : c'est
la couleur de marque déjà en usage dans tout le produit, et les gravités
d'alerte (rose/ambre/orange/bleu) n'ont pas été rouvertes.

Fondations en jetons CSS réels (`src/index.css`, `@theme` Tailwind v4),
redéfinis sous `:root[data-theme="dark"]` : c'est ce qui permet à un thème
sombre de s'appliquer d'un coup plutôt que de reprendre chaque `bg-white`
un par un. Bascule explicite (pas de suivi des préférences système),
mémorisée, exposée dans `AppContext`. Barre latérale rendue sensible au
thème (panneau clair ou sombre) au lieu d'un navy fixe — le changement le
plus visible du modèle repris.

Passe mécanique sur 32 fichiers : les classes Tailwind de gris neutre
(`bg-slate-50`, `text-slate-900`…) remplacées par leurs équivalents en
valeur arbitraire pointant sur les jetons, ce qui propage le thème sombre à
toute l'application sans réécrire chaque écran.

**Restructurés au modèle** : coquille (barre latérale, en-tête, palette de
commandes, toasts), tableau de bord (indicateurs en cartes distinctes avec
ligne d'explication réelle). **Suivent seulement les jetons neutres**, sans
restructuration écran par écran : Paramètres, Utilisateurs, Audit,
Intégrations. La page de connexion garde son fond sombre fixe — un choix,
pas un oubli.

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

### Installateur Windows — livré le 3 septembre 2026

Demande : « créons un installateur Windows... avec la possibilité de changer
l'adresse IP de l'agent au niveau du serveur pour si on met en production.
Aussi les plugins pour les mises à jour ou désinstallation. »

`agent/packaging/build_windows.ps1` fabrique un paquet autonome (13 Mo,
aucune dépendance Python) : `cbc-agent.exe`, `Install-CbcAgent.ps1`,
`LISEZ-MOI.txt`. `Install-CbcAgent.ps1` porte les cinq gestes de la vie de
l'agent sur une machine :

| Action | Ce qu'elle fait |
|---|---|
| `Install` | dépose le binaire, écrit la configuration, enrôle, enregistre le service, démarre |
| `Update` | remplace le binaire — identité, jetons et historique conservés, aucun jeton consommé ; revient à la version précédente si le nouveau binaire ne démarre pas |
| `Configure` | change l'adresse de la plateforme **sans réenrôler** — le geste demandé pour la bascule laboratoire → production |
| `Uninstall` | signale le désenrôlement **avant** tout effacement local |
| `Status` | identifiant, plateforme jointe, liaison, état du service |

`Configure` existe aussi côté agent : `cbc-agent configure --server-url
<adresse>`. Réinstaller un parc de deux cents postes pour un simple
changement d'adresse ferait perdre à chacun son identité et son historique,
et consommerait un jeton par poste — pour ce volume, une journée de travail
en pure perte. L'écriture est atomique et ne touche que la section
`server:` : le reste du réglage (type de machine, délai) survit. Un
avertissement explicite prévient si la bascule vers HTTPS conserverait la
tolérance au certificat non vérifié héritée du laboratoire — une régression
de sécurité que rien d'autre n'aurait signalée.

Le désenrôlement précède toujours l'effacement : sans cet ordre, un hôte
retiré resterait affiché « hors ligne » dans le parc et alerterait pour une
absence décidée, indistincte d'une vraie panne. Le service redémarre
automatiquement après un échec, à intervalles croissants.

Le paquet a été construit et éprouvé sur ce poste : les six commandes
répondent depuis le binaire gelé, `configure` réécrit correctement une
configuration réelle. 25 tests.

`agent.spec` était périmé depuis la refonte de l'agent — il déclarait une
dizaine de modules retirés (`durable_buffer`, `action_plugins`,
`windows_service`...) et ne construisait plus rien. Réécrit.

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

### 1. La suite de tests serveur se figeait — résolu le 1er septembre

`pytest server/tests` s'arrêtait invariablement après **33 tests** et n'avançait
plus. Cause : `server/tests/load_test.py` correspondait au motif de collecte par
défaut `*_test.py`. Le collecter importait Locust, qui applique le
*monkey-patching* gevent sur `ssl`, `socket` et `threading` — **après** que la
suite ait importé ces modules. Le portail bloquant d'anyio, sur lequel repose
`TestClient`, attendait alors indéfiniment.

Corrigé en deux gestes : le fichier est parti sous
`tools/load_test/locustfile.py` (ce n'est pas un test, il ne doit pas être
collecté), et `pyproject.toml` fixe `python_files = ["test_*.py"]` pour que le
motif `*_test.py` ne rattrape plus rien d'autre par accident.

> Piège de diagnostic : la sortie de pytest est bufferisée par bloc. Sans
> `python -u`, une suite en bonne santé ressemble à un blocage.

### 2. Workflow CI invalide — corrigé

`.github/workflows/ci.yml` ne se lisait pas : ligne 26,
`DATABASE_URL: sqlite:///:memory:` — un scalaire non quoté terminé par un
deux-points, que YAML refuse. Le fichier était donc **invalide depuis son
ajout et n'a jamais pu s'exécuter**, malgré son envoi sur le dépôt. Corrigé
par mise entre guillemets ; le document se lit désormais et expose trois
tâches : `linux-tests`, `lint`, `dashboard`. Les trois passent.

### 3. Dette pré-existante — résorbée

`ruff` signalait 3 clés de dictionnaire dupliquées dans `server/src/main.py`
(`ram_total_gb` ligne 1798, `disk_total_gb` et `ram_total_gb` ligne 2304).
Python conserve la dernière liaison : la fiche d'hôte réécrivait la valeur
d'inventaire avec celle du dernier battement, si bien qu'un hôte fraîchement
enrôlé — qui n'a pas encore battu — affichait `None` là où l'inventaire avait
la donnée. Corrigé par repli sur la valeur d'inventaire. `ruff` est propre.

### 4. Relais SMTP — résolu le 3 septembre 2026

Premier envoi réussi, par le chemin du produit. Il aura fallu défaire trois
obstacles empilés, dont deux ne se voyaient pas.

**a. Le conteneur ne parlait pas au bon serveur.** `smtp.gie.local` se résout
en `10.11.20.171` depuis le conteneur et en `10.12.20.172` depuis le poste. Les
deux acceptent une connexion sur le port 25, ce qui rendait le défaut
invisible : la conversation SMTP restait simplement en attente, sans erreur
exploitable. `extra_hosts` fixe l'adresse dans `docker-compose.yml`, réglable
par `SMTP_RELAY_IP` sans reconstruire l'image.

**b. Le certificat est auto-signé.** STARTTLS est obligatoire — le port 25 en
clair n'annonce que `AUTH NTLM`, que `smtplib` ne sait pas parler — mais la
vérification échouait. L'option `smtp_verify_cert` permet de l'accepter, comme
un choix posé et non un contournement muet.

**c. Le relais n'accepte pas l'authentification de base**, bien qu'il annonce
`LOGIN` après STARTTLS. Trois formes d'identifiant ont été essayées —
`cbcautoma`, `cbcautoma@groupecommercialbank.com`, `GIE\cbcautoma` — toutes
refusées en `535 5.7.3`. Le mot de passe stocké est pourtant intact (14
caractères, sans mutilation ni caractère perdu). Les essais ont été arrêtés là :
au-delà, le compte de service risquait le verrouillage.

Le relais accepte en revanche la **remise anonyme**, y compris chiffrée — la
configuration habituelle d'un connecteur applicatif, restreint par adresse IP.
C'est ce qui est retenu :

| Réglage | Valeur |
|---|---|
| Serveur | `smtp.gie.local` → `10.12.20.172` |
| Port | 25 |
| Authentification | **désactivée** |
| Chiffrement | STARTTLS |
| Vérification du certificat | désactivée (auto-signé) |
| Expéditeur | `sentinel@groupecommercialbank.com` |

Le mot de passe reste stocké : il redeviendra utile si l'authentification est
ouverte plus tard sur ce connecteur.

**À faire côté infrastructure**, dans l'ordre d'importance décroissante :
faire signer le certificat du relais par l'autorité interne puis remettre la
vérification ; corriger la résolution de `smtp.gie.local` du côté Docker pour
retirer `extra_hosts` ; ouvrir l'authentification si la remise anonyme par IP
n'est pas jugée suffisante.

Défaut trouvé au passage : la copie était versée dans `To`. L'en-tête `Cc`
n'existait pas, si bien qu'un lecteur en copie se lisait comme destinataire
direct — et sur une alerte, cela change qui se croit chargé de la traiter.

### 5. Destinataires d'alerte — résolu le 2 septembre 2026

`recipients` était vide et bloquait tout envoi, quel que soit le canal. Mais
cette liste globale n'aurait de toute façon pas dû être le mécanisme principal :
tenue à la main, elle diverge le jour où quelqu'un change de poste, et les
alertes continuent de partir vers une personne qui n'a plus la machine en
charge, sans que rien ne le signale.

Le destinataire est désormais **le responsable de l'hôte** et les membres de
l'**équipe responsable**, dont l'adresse vient de l'annuaire. Les copies se
saisissent hôte par hôte, dans l'onglet Configuration de sa fiche.

Au passage, un défaut qui ne s'était jamais vu : l'équipe responsable était
purement et simplement ignorée. Un hôte confié à une équipe plutôt qu'à une
personne n'alertait personne, alors que l'attribution s'affichait comme faite.

Vérifié sur la plateforme en service :

| Hôte | Responsable | Équipe | Destinataires |
|---|---|---|---|
| `B20E58` | jkoum (annuaire) | Équipe Monétique | jkoum@groupecommercialbank.com, operator@cbcam.cm |
| `587A2B` | aucun | Équipe Monétique | operator@cbcam.cm |

La liste globale ne sert plus que de filet, pour un hôte sans responsable ni
équipe.

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

---

## Voir le produit tourner sur un poste

```powershell
.\scripts\run-test-agent.ps1 -Token demo-token-123
```

Enrôle ce poste auprès d'une plateforme de test et fait battre l'agent
jusqu'à Ctrl+C. Trois précautions, parce que le script tourne sur un poste de
travail et non sur un serveur :

- l'état vit sous `%LOCALAPPDATA%\CBC Agent Demo`, **jamais** dans
  ProgramData : le poste n'est pas « installé », et tout s'efface en
  supprimant un dossier ;
- le mode est déclaré `console`, pour que la fiche d'hôte dise la vérité — un
  agent lancé à la main s'arrête avec la session, et cela doit se voir plutôt
  que de ressembler à une panne ;
- le jeton n'est jamais écrit dans un fichier du dépôt.

Options : `-ServerUrl`, `-Interval`, `-Reset`. Pour retirer proprement l'hôte
du parc à la fin, le script affiche la commande `uninstall`.
