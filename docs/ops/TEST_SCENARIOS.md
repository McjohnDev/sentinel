# Scénarios de test — Agents & Plateforme centrale

**Public :** exploitants CBC, testeurs, recette Lot 1
**Portée :** vérification pas à pas de l'agent et de l'application centrale
**Version :** 1.0 — 18 août 2026

Ce document est un plan de test **exécutable**. Chaque scénario indique la
préparation, les étapes, le résultat attendu et la manière de *prouver* le
résultat (log, appel API, écran). Un scénario dont le résultat ne peut pas être
prouvé est considéré comme non passé.

> **Convention.** ✅ = attendu · ❌ = échec à consigner · 🔍 = preuve à joindre
> à la fiche de recette.

---

## 0. Préparation de l'environnement

### 0.1 Démarrage de la plateforme

```powershell
docker compose -f docker/docker-compose.yml up -d --build
```

Attendre que tous les services soient sains :

```powershell
docker compose -f docker/docker-compose.yml ps
```

✅ `postgres`, `redis`, `victoria-metrics`, `loki`, `server`, `dashboard` en
`healthy` ou `running`.

🔍 Joindre la sortie de `docker compose ps`.

### 0.2 Vérifier que l'ordonnanceur tourne

```powershell
curl http://localhost:8443/health
```

✅ La réponse contient `"scheduler_running": true` et un `"timestamp"` récent.

> **Pourquoi c'est le premier test.** L'ordonnanceur porte la détection hors
> ligne, l'escalade et la purge. S'il est arrêté, l'API répond mais la
> plateforme est aveugle : aucune alerte de parc ne sera levée.

❌ Si `scheduler_running` vaut `false`, vérifier `SCHEDULER_ENABLED` dans
l'environnement du conteneur `server` et consulter ses logs.

### 0.3 Comptes de démonstration

| Rôle | Identifiant | Mot de passe |
|---|---|---|
| Administrateur | `admin@cbc.cm` | `Admin123!` |
| Opérateur | `operator@cbcam.cm` | `Operator123!` |
| Lecture seule | `readonly@cbcam.cm` | `Readonly123!` |

Le rôle **Sécurité** n'a pas de compte de démonstration : le créer au
scénario 3.4.

---

## 1. Enrôlement et cycle de vie de l'agent

### T1.1 — Un jeton inconnu est refusé

**Étapes**
1. Depuis Swagger (`http://localhost:8443/docs`), appeler
   `POST /api/agents/enroll` avec `token: "jeton-bidon"`.

✅ Réponse **401** `Token d'enrôlement invalide`.
✅ Aucun agent n'apparaît dans **Agents**.

🔍 Code de réponse + copie du corps.

### T1.2 — Un jeton d'administrateur permet l'enrôlement

> Régression couverte : les jetons émis par l'API n'étaient jamais consultés
> par l'endpoint d'enrôlement ; ils ne pouvaient donc enrôler aucun agent.

**Étapes**
1. Se connecter en **Administrateur**.
2. **Paramètres → Agents → Générer un jeton**. Noter la valeur `CBC-ENROLL-…`.
3. Vérifier que le jeton existe côté serveur :
   `GET /api/settings/tokens` (JWT admin).
4. Enrôler un agent avec ce jeton.

✅ Le jeton retourné par l'interface est **présent** dans la réponse de l'API
(il n'est plus fabriqué dans le navigateur).
✅ L'enrôlement réussit et l'agent apparaît dans **Agents**.

### T1.3 — Un jeton ne sert qu'une fois

**Étapes**
1. Réutiliser le jeton du test T1.2 pour enrôler une seconde machine
   (`machine_id` différent).

✅ Réponse **400** `Token déjà utilisé`.

**Variante — machine déjà connue :**
2. Réutiliser le même jeton avec le `machine_id` **déjà enrôlé**.

✅ Réponse **400** également. La consommation s'applique aussi au
ré-enrôlement d'un hôte connu.

### T1.4 — Un jeton expiré est refusé

**Étapes**
1. En base, avancer `expires_at` d'un jeton actif dans le passé :
   ```sql
   UPDATE enrollment_tokens SET expires_at = NOW() - INTERVAL '1 hour'
   WHERE token = '<jeton>';
   ```
2. Tenter l'enrôlement.

✅ Réponse **401** `Token d'enrôlement expiré`.
✅ Le statut du jeton passe à `expired` en base.

### T1.5 — Le binaire distribué vérifie TLS

**Étapes**
1. Ouvrir `agent/config.yaml` (le fichier embarqué dans le binaire).

✅ `tls_verify: true`.
✅ `enrollment_token: ""` — aucun jeton codé en dur n'est diffusé avec
l'installation.

2. Pointer un agent `tls_verify: true` vers une URL **http://**.

✅ L'agent échoue avec une erreur TLS explicite, il ne se rabat pas
silencieusement en clair.

### T1.6 — Instance unique

**Étapes**
1. Lancer un second agent avec le même verrou.

✅ Le second processus s'arrête avec un message clair et un code de sortie
non nul.

---

## 2. Collecte, métriques et empreinte

### T2.1 — Le parc remonte des métriques réelles

**Étapes**
1. Laisser l'agent tourner 2 minutes.
2. Ouvrir **Tableau de bord** puis **Agents**.

✅ CPU / RAM / disque non nuls et **cohérents avec le gestionnaire de tâches
de l'hôte**.

> **Contrôle anti-régression.** Le tableau de bord fabriquait auparavant la
> télémétrie avec `Math.random()` toutes les 10 secondes. Pour le prouver :
> **arrêter l'agent** et observer le tableau de bord pendant 60 s.
> ✅ Les valeurs doivent **cesser de bouger** (elles ne sont plus inventées).
> ❌ Si les courbes continuent d'osciller sans agent actif, la régression est
> revenue.

### T2.2 — Empreinte de l'agent (AGT-007)

> Régression couverte : la mesure CPU bloquait l'unique thread de l'agent, si
> bien qu'elle mesurait l'agent *pendant son sommeil*. Une charge réelle se
> lisait 0,0 % et un agent au repos produisait de faux pics à ~30 %.

**Étapes**
1. **Paramètres → Plateforme** ou `GET /api/agents/{id}` : relever
   `agent_cpu_percent` et `agent_ram_mb`.
2. Laisser tourner 5 minutes au repos.

✅ `agent_cpu_percent` reste bas et **stable** ; aucun pic isolé à 20–30 %.
✅ `agent_ram_mb` cohérent avec la RSS du processus (`Get-Process`).

3. Abaisser temporairement le budget pour déclencher l'alerte :
   ```sql
   UPDATE global_settings SET agent_cpu_max_percent = 0.01 WHERE id = 'default';
   ```
4. Attendre deux heartbeats.

✅ Une alerte **Mineure** de type `agent_footprint` apparaît.
5. Restaurer `agent_cpu_max_percent = 2`.
✅ L'alerte se **résout automatiquement**.

---

## 3. Utilisateurs, rôles et permissions

### T3.1 — Les quatre rôles existent et sont cohérents

**Étapes**
1. Se connecter en Administrateur.
2. `GET /api/auth/roles`.

✅ Quatre rôles : `admin`, `operator`, `security`, `read_only`.
✅ `admin` détient **toutes** les permissions listées.

### T3.2 — Les permissions du compte connecté sont exposées

**Étapes**
1. `GET /api/auth/permissions` avec le JWT de chaque rôle.

✅ Opérateur : contient `alert:ack`, `alert:resolve`, `agent:edit` ;
**ne contient pas** `user:manage`, `settings:edit`, `audit:view`.
✅ Lecture seule : uniquement des permissions `*:view`.
✅ Sécurité : contient `audit:view`, `audit:export`, `action:approve` ;
**ne contient pas** `agent:edit` ni `settings:edit`.

### T3.3 — La création d'utilisateur atteint réellement le serveur

> Régression couverte : le formulaire validait le mot de passe puis ne
> l'envoyait pas, et le compte n'était créé que dans l'état local du
> navigateur — il disparaissait au rechargement et la personne ne pouvait pas
> se connecter.

**Étapes**
1. **Utilisateurs → Ajouter**, créer `test.operateur` avec le rôle Opérateur.
2. **Recharger la page (Ctrl+F5).**

✅ Le compte est **toujours présent** après rechargement.
3. Se déconnecter et se connecter avec ce compte.
✅ La connexion réussit.

### T3.4 — Création et vérification du rôle Sécurité

**Étapes**
1. Créer `audit.cbc` avec le rôle **Sécurité**.
2. Se connecter avec ce compte.

✅ Les écrans de consultation sont accessibles.
✅ Toute tentative de modification (seuils, agents, paramètres) est refusée
côté **serveur** en **403** — pas seulement masquée dans l'interface.

🔍 Joindre la réponse 403 d'un `PUT /api/agents/{id}/thresholds`.

### T3.5 — La modification d'utilisateur est persistée

**Étapes**
1. Modifier le rôle de `test.operateur` en **Lecture seule**.
2. Recharger la page.

✅ Le rôle affiché est bien **Lecture seule**.
✅ Le compte perd immédiatement le droit d'acquitter une alerte.

### T3.6 — Garde-fous d'administration

**Étapes**
1. Connecté en Administrateur, tenter de **retirer son propre rôle
   administrateur**.

✅ Refus **400** `Impossible de retirer son propre rôle administrateur`.

2. Tenter de **désactiver son propre compte**.
✅ Refus **400**.

3. S'il ne reste qu'un seul administrateur actif, tenter de le rétrograder
   depuis un autre compte administrateur préalablement créé puis supprimé.
✅ Refus **400** `Dernier administrateur actif : opération refusée`.

> Ces garde-fous évitent de se verrouiller hors de la plateforme.

### T3.7 — Un compte désactivé perd l'accès immédiatement

**Étapes**
1. Se connecter avec `test.operateur` dans un second navigateur ; garder la
   session ouverte.
2. Depuis l'administrateur, **désactiver** ce compte.
3. Dans le second navigateur, effectuer une action quelconque.

✅ **403** `Compte désactivé` — sans attendre l'expiration du jeton.

### T3.8 — Révocation d'un agent (chemin critique)

> Régression couverte : la révocation ne changeait que l'état local. Un hôte
> compromis restait pleinement actif derrière un message de succès.

**Étapes**
1. **Agents → sélectionner l'agent → Révoquer**.
2. Recharger la page.

✅ L'agent reste **révoqué** après rechargement.
3. Observer les logs de l'agent.
✅ L'agent reçoit **401** à son prochain heartbeat et cesse d'être accepté.

🔍 Joindre l'extrait de log de l'agent montrant le 401.

---

## 4. Authentification annuaire (LDAP / Active Directory)

> À exécuter uniquement si CBC fournit un annuaire de test.

### T4.1 — Désactivé par défaut

**Étapes**
1. `GET /api/settings/ldap` en Administrateur.

✅ `enabled: false`, `operational: false`.
✅ Aucun mot de passe de compte de service n'est renvoyé —
seul `bind_dn_configured` (booléen) apparaît.

### T4.2 — Test de connexion

**Préparation** — renseigner dans l'environnement du serveur :

```
LDAP_ENABLED=true
LDAP_SERVER_URI=ldaps://dc01.cbcam.cm:636
LDAP_BIND_DN=CN=svc-sentinel,OU=Services,DC=cbc,DC=cm
LDAP_BIND_PASSWORD=<secret>
LDAP_USER_SEARCH_BASE=OU=Utilisateurs,DC=cbc,DC=cm
LDAP_USER_FILTER=(&(objectClass=user)(sAMAccountName={username}))
LDAP_ATTR_USERNAME=sAMAccountName
LDAP_ROLE_MAPPING={"CN=SOC,OU=Groupes,DC=cbc,DC=cm":"operator"}
```

**Étapes**
1. `POST /api/settings/ldap/test`.

✅ `ok: true`, `stage: "bind"`.
❌ Si `stage: "library"`, installer `ldap3` (`pip install ldap3`).

### T4.3 — Résolution d'un compte et du rôle

**Étapes**
1. `POST /api/settings/ldap/probe-user` avec un identifiant réel.

✅ `found: true`, le DN, les groupes et `resolved_role` sont retournés.
✅ `resolved_role` correspond à la table de correspondance des groupes.

> Ce test valide le filtre **avant** d'ouvrir l'authentification aux
> utilisateurs. Aucun mot de passe n'est demandé.

### T4.4 — Première connexion : provisionnement

**Étapes**
1. Se connecter avec un compte de l'annuaire.

✅ La connexion réussit.
✅ Le compte apparaît dans **Utilisateurs** avec l'origine `ldap`.
✅ Son rôle correspond à son groupe.

### T4.5 — Le rôle suit l'annuaire

**Étapes**
1. Retirer l'utilisateur du groupe correspondant côté annuaire.
2. Le faire se reconnecter.

✅ Son rôle est **réaligné** (retombe au rôle par défaut).
✅ Aucun doublon de compte n'est créé.

### T4.6 — Un compte d'annuaire ne s'authentifie pas localement

**Étapes**
1. Tenter de se connecter avec le compte LDAP et un mot de passe local
   quelconque, annuaire **coupé**.

✅ Refus. Le compte miroir ne porte pas de mot de passe exploitable.

### T4.7 — Repli local pendant une panne d'annuaire

**Étapes**
1. Rendre l'annuaire injoignable (couper le réseau ou pointer un port fermé).
2. Se connecter avec le compte **administrateur local**.

✅ La connexion locale fonctionne toujours (`LDAP_ALLOW_LOCAL_FALLBACK=true`).

> Sans ce repli, une panne d'annuaire ferme l'accès à la plateforme, y compris
> à l'administrateur.

### T4.8 — Filtre robuste à l'injection

**Étapes**
1. Tenter de se connecter avec l'identifiant `*`.

✅ Refus. Le caractère joker est échappé (RFC 4515) et ne fait pas remonter
le premier compte de l'annuaire.

---

## 5. Alertes — cycle de vie complet

### T5.1 — Les quatre gravités sont filtrables

> Régression couverte : le filtre proposait `Warning`, une valeur que le
> serveur ne renvoie jamais, et **omettait `Mineure`**.

**Étapes**
1. Ouvrir **Alertes**.

✅ Les chips de gravité sont exactement : **Critique · Majeure · Mineure ·
Info**.
✅ Aucun chip « Warning ».
2. Cliquer sur **Mineure** en présence d'une alerte d'empreinte (T2.2).
✅ L'alerte reste visible.

### T5.2 — Un pic bref ne déclenche pas d'alerte

**Étapes**
1. **Paramètres → Seuils** : `durationSeconds` = 300.
2. Charger le CPU 10 secondes.

✅ Aucune alerte CPU.
3. Maintenir la charge **> 5 minutes**.
✅ Alerte **Majeure** CPU.

### T5.3 — Acquittement, résolution et chronologie réelle

> Régressions couvertes : aucun bouton **Résoudre** n'existait dans
> l'interface, et la chronologie affichée était fabriquée côté client (avec
> « Webhook n8n OK » en dur).

**Étapes**
1. Ouvrir une alerte ouverte.
2. **Acquitter**.
3. **Résoudre** — le bouton doit exister.
4. Observer la chronologie.

✅ Les évènements affichés proviennent de `GET /api/alerts/{id}/timeline`
(vérifiable dans l'onglet réseau du navigateur).
✅ Aucun évènement « Mail CBC » ou « Webhook n8n » n'apparaît en succès s'il
n'a pas réellement eu lieu.

### T5.4 — L'état de livraison est honnête

**Étapes**
1. Configurer une URL d'API Mail **invalide**.
2. Déclencher une alerte majeure.

✅ L'indicateur de livraison affiche **Échec** (rouge), pas un état vert.

> Le serveur écrit `sent | failed | skipped | pending` ; l'interface testait
> auparavant la valeur `error`, qui n'est jamais écrite — un envoi en échec
> s'affichait donc en vert.

### T5.5 — Détection hors ligne pendant une panne de parc (test clé)

> Régression couverte : la détection tournait dans le handler de heartbeat.
> Lors d'une panne générale, plus aucun agent n'émettait, donc plus aucune
> évaluation ne tournait et **aucune alerte n'était levée** — précisément le
> scénario que le produit doit détecter.

**Étapes**
1. Noter l'heure.
2. **Arrêter tous les agents** :
   ```powershell
   docker stop sentinel-agent
   ```
   et arrêter l'agent Windows s'il tourne.
3. **N'effectuer aucune action dans l'interface** (pour ne générer aucune
   requête entrante). Attendre 3 minutes.

✅ Une alerte **Agent hors ligne** est levée pour chaque agent, **sans
qu'aucune requête n'ait été émise**.

🔍 Joindre la capture de l'écran Alertes avec l'horodatage.

4. Redémarrer les agents.
✅ Les agents repassent en ligne et les alertes se résolvent.

### T5.6 — Escalade

**Étapes**
1. Laisser une alerte majeure non acquittée.
2. Attendre `escalateAfterMinutes` (15 par défaut).

✅ La gravité passe à **Critique** et une nouvelle notification est tentée.
✅ L'escalade se produit **sans** qu'aucun heartbeat ne soit reçu.

---

## 6. Journal d'audit et conformité

### T6.1 — Les actions d'administration sont journalisées

> Régression couverte : `audit_logger.log_action()` n'existait pas alors que
> 16 endpoints l'appelaient **après** leur `db.commit()`. La donnée était
> écrite, le client recevait une **500**, et aucune trace d'audit n'était
> produite.

**Étapes**
1. **Paramètres → Groupes & config → Créer un groupe**.

✅ Réponse **200** (et non 500).
✅ Le groupe apparaît dans la liste.
2. Répéter avec : publication de configuration, création de fenêtre de
   maintenance, génération de jeton, modification d'utilisateur.
✅ Aucune de ces actions ne retourne 500.

3. Consulter les logs du serveur :
   ```powershell
   docker logs sentinel-server | Select-String "CREATE_GROUP"
   ```
✅ Une entrée d'audit correspond à chaque action.

🔍 Joindre les entrées d'audit correspondantes.

---

## 6bis. Piste d'audit persistée, rétention, réseau et journaux

### T6.2 — La piste d'audit est réelle et exportée par le serveur

> Régression couverte : l'écran Audit reconstituait ses lignes dans le
> navigateur à partir des alertes et des utilisateurs, avec l'adresse IP
> `10.1.1.40` codée en dur sur chaque ligne et une entrée d'exemple injectée,
> puis proposait ce résultat à l'export « pour COBAC ». Le journal réel du
> serveur n'était jamais consulté.

**Étapes**
1. Se connecter en **Administrateur**, effectuer trois actions traçables
   (créer un groupe, modifier un utilisateur, générer un jeton).
2. Ouvrir **Audit**.

✅ Les trois actions apparaissent, avec l'acteur réel et un horodatage serveur.
✅ Aucune ligne ne porte l'adresse `10.1.1.40`.
✅ Aucune entrée `groupe SWIFT v13` n'est présente.
3. Ouvrir l'onglet réseau du navigateur et actualiser.
✅ L'écran appelle `GET /api/audit` (il ne calcule plus ses lignes).

4. Cliquer **Exporter pour COBAC**.
✅ Le fichier est servi par `GET /api/audit/export` (réponse `text/csv`).
✅ Son contenu correspond aux lignes affichées.
5. Consulter de nouveau **Audit**.
✅ L'export lui-même est journalisé (`EXPORT_AUDIT`).

### T6.3 — L'accès à l'audit est restreint

**Étapes**
1. Se connecter en **Opérateur**, appeler `GET /api/audit`.

✅ **403**. L'audit est réservé aux rôles Administrateur et Sécurité.
2. Se connecter en **Sécurité**.
✅ **200**, et l'export fonctionne.

### T6.4 — Rétention des données (STO-002)

> Régression couverte : la table `retention_config` était administrable mais
> aucun traitement ne la lisait — heartbeats et alertes s'accumulaient sans
> limite.

**Étapes**
1. **Paramètres → Rétention** : régler heartbeats à **1 jour**.
2. Insérer un heartbeat daté de plus d'un jour (ou attendre).
3. Attendre le passage horaire du job, ou redémarrer le serveur.

✅ Les heartbeats au-delà de la fenêtre sont supprimés.
✅ Une alerte encore **ouverte ou acquittée** n'est **jamais** supprimée, quel
que soit son âge.
✅ La piste d'audit n'est **jamais** purgée par ce réglage (obligation
réglementaire).

4. Régler la rétention à **0**.
✅ Plus rien n'est supprimé — 0 signifie « conserver sans limite ».

### T6.5 — Sonde SNMP (AGT-029)

> Régression couverte : la sonde renvoyait la première chaîne imprimable de la
> réponse — c'est-à-dire la **communauté** réémise par l'équipement — en guise
> de description système. Tout équipement interrogé remontait donc « public ».

**Étapes**
1. **Réseau** → ajouter un équipement SNMP joignable, communauté `public`.
2. Lancer une sonde.

✅ La description retournée est celle de l'équipement (ex. « Cisco IOS
Software… »).
❌ Si la valeur affichée est exactement le nom de la communauté, la régression
est revenue.

### T6.6 — Rotation des journaux sans perte (FS3-01)

> Régressions couvertes : la position de lecture était mémorisée sous la seule
> clé du chemin, si bien qu'une rotation par renommage faisait sauter le début
> du nouveau fichier ; et le collecteur journald réécrivait un instantané
> périmé de l'état partagé, faisant reculer les positions et réexpédiant des
> lignes après un redémarrage.

**Étapes**
1. Activer la collecte de fichiers sur un journal de test.
2. Écrire 40 lignes, laisser l'agent les expédier.
3. Effectuer une rotation **par renommage** :
   ```powershell
   Move-Item app.log app.log.1
   ```
   puis écrire **60 nouvelles lignes** dans un nouveau `app.log`.
4. Laisser l'agent collecter.

✅ Les **60** lignes sont expédiées.
✅ La première ligne reçue est complète — pas un fragment de ligne.
✅ Aucune ligne de l'ancien fichier n'est réexpédiée.

5. Redémarrer l'agent sans nouvelle écriture.
✅ **Aucune** ligne n'est réexpédiée.

---

## 7. Résilience

### T7.1 — Panne de la plateforme, tampon durable

**Étapes**
1. `docker stop sentinel-server`.
2. Laisser l'agent tourner 3 à 5 minutes.
3. `docker start sentinel-server`.

✅ L'agent ne s'arrête pas et ne boucle pas en erreur.
✅ Les métriques accumulées sont rattrapées après le redémarrage.

### T7.2 — Redémarrage de la plateforme

**Étapes**
1. `docker restart sentinel-server`, attendre l'état sain.
2. `curl http://localhost:8443/health`.

✅ `scheduler_running: true` — l'ordonnanceur redémarre avec l'application.

---

## 8. Déploiement en production

### T8.1 — Les services d'infrastructure ne sont pas exposés

> Régression couverte : `ports: []` dans la surcharge de production ne
> supprimait rien (Compose **concatène** les listes `ports`). Postgres, Redis,
> VictoriaMetrics et Loki restaient publiés sur `0.0.0.0` avec un mot de passe
> publié dans ce dépôt.

**Étapes**
1. Rendre la configuration fusionnée :
   ```powershell
   docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml config
   ```

✅ Seuls **deux** ports sont publiés : `3000` (dashboard) et `8443` (API).
✅ Aucune section `ports` sur `postgres`, `redis`, `victoria-metrics`, `loki`.
✅ Aucune occurrence de `cbc_password`.
✅ `BOOTSTRAP_ENROLLMENT_TOKEN` est vide et `BOOTSTRAP_TOKEN_REUSABLE` vaut
`"false"`.

🔍 Joindre la sortie filtrée de cette commande — c'est la preuve d'acceptation
du scénario.

### T8.2 — Les secrets obligatoires sont exigés

**Étapes**
1. Lancer la production **sans** `SECRET_KEY` ni `POSTGRES_PASSWORD`.

✅ Compose **refuse de démarrer** avec un message explicite.

### T8.3 — Les dépendances déclarées suffisent

**Étapes**
1. Dans un environnement vierge :
   ```bash
   pip install -r server/requirements.txt
   python -c "import sys; sys.path.insert(0,'server'); import src.main"
   ```

✅ L'import réussit — `requirements.txt` est autoritatif.

---

## 9. Qualité du code (à faire tourner en intégration continue)

### T9.1 — Tests

```bash
pytest server/tests agent/tests shared/tests -q
```

✅ Suite verte.
> ⚠️ Exécuter `server/tests/test_integration.py` **séparément** : un blocage
> connu (portail anyio de TestClient sous Windows) se produit lorsqu'il suit
> les autres modules dans le même processus.

### T9.2 — Lint Python

```bash
python -m ruff check server/src agent/src shared
```

✅ `All checks passed!`

### T9.3 — Vérification de types et build du tableau de bord

```bash
npx tsc --noEmit
npm run build
```

✅ **0 erreur** de typage.
✅ Build réussi.

---

## Fiche de synthèse de recette

| # | Scénario | Résultat | Preuve | Testeur | Date |
|---|---|---|---|---|---|
| T1.1 | Jeton inconnu refusé | | | | |
| T1.2 | Jeton administrateur fonctionnel | | | | |
| T1.3 | Jeton à usage unique | | | | |
| T1.4 | Jeton expiré refusé | | | | |
| T1.5 | TLS vérifié dans le binaire | | | | |
| T1.6 | Instance unique | | | | |
| T2.1 | Métriques réelles | | | | |
| T2.2 | Empreinte agent | | | | |
| T3.1 | Quatre rôles | | | | |
| T3.2 | Permissions exposées | | | | |
| T3.3 | Création utilisateur persistée | | | | |
| T3.4 | Rôle Sécurité | | | | |
| T3.5 | Modification persistée | | | | |
| T3.6 | Garde-fous administrateur | | | | |
| T3.7 | Désactivation immédiate | | | | |
| T3.8 | Révocation d'agent effective | | | | |
| T4.1–T4.8 | Annuaire LDAP | | | | |
| T5.1 | Quatre gravités | | | | |
| T5.2 | Seuil de durée | | | | |
| T5.3 | Acquitter / résoudre / chronologie | | | | |
| T5.4 | État de livraison honnête | | | | |
| T5.5 | **Hors ligne pendant panne de parc** | | | | |
| T5.6 | Escalade | | | | |
| T6.1 | Journal d'audit | | | | |
| T6.2 | Audit persisté + export serveur | | | | |
| T6.3 | Accès audit restreint | | | | |
| T6.4 | Rétention appliquée | | | | |
| T6.5 | Sonde SNMP | | | | |
| T6.6 | Rotation des journaux sans perte | | | | |
| T7.1 | Tampon durable | | | | |
| T7.2 | Redémarrage plateforme | | | | |
| T8.1 | **Ports non exposés en production** | | | | |
| T8.2 | Secrets exigés | | | | |
| T8.3 | Dépendances suffisantes | | | | |
| T9.1–T9.3 | Tests, lint, types | | | | |

**Scénarios bloquants pour la mise en pilote :** T1.3, T1.5, T3.8, T5.5, T8.1,
T8.2.
