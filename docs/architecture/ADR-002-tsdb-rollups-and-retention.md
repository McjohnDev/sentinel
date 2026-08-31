# ADR-002 — Agrégats et rétention de la base de séries temporelles

- **Statut :** accepté
- **Date :** 18 août 2026
- **Concerne :** FS2-04, STO-001, STO-002
- **Complète :** ADR-001 (choix de VictoriaMetrics)

---

## Contexte

La story FS2-04 énonce deux critères d'acceptation :

1. des agrégats **1m → 1h → 1d** ;
2. une rétention configurable **30 jours de données brutes / 13 mois d'agrégats**.

Aucun des deux n'était tenu. Le paramètre `--retentionPeriod=13` est codé en
dur dans le fichier Compose, la table `retention_config` n'était lue par aucun
traitement, et le paramètre `step` d'une requête — qui ne fait que choisir la
résolution d'affichage — était présenté comme un agrégat.

## Contrainte déterminante

**VictoriaMetrics en édition open source ne sait pas sous-échantillonner.** Le
sous-échantillonnage (`-downsampling.period`) est une fonction de l'édition
entreprise. La rétention par série (`-retentionFilter`) l'est également.

Deux conséquences, à énoncer clairement car elles engagent le périmètre :

- les agrégats doivent être **calculés hors de la base** si on veut les avoir ;
- une **rétention à deux niveaux dans une seule instance est impossible** : la
  rétention y est globale.

## Ce que coûte réellement le stockage

Le critère suppose implicitement que les agrégats servent à contenir le volume.
À l'échelle du parc CBC, ce n'est pas le facteur déterminant.

| Paramètre | Valeur |
|---|---|
| Agents (cible PLT-003) | 500 |
| Séries par agent (estimation) | ~50 |
| Séries actives | ~25 000 |
| Période d'échantillonnage | 30 s |
| Échantillons par jour | ~72 millions |
| Taille après compression (0,4–1 o/échantillon) | **~30 à 70 Mo/jour** |
| **13 mois de données brutes** | **~11 à 26 Go** |

Onze à vingt-six gigaoctets pour treize mois est un volume modeste pour une
infrastructure bancaire. **L'argument de volume ne justifie pas à lui seul les
agrégats.**

L'argument qui tient est la **latence de requête** : un graphique sur treize
mois lit aujourd'hui plusieurs dizaines de milliers de points bruts par série.
Sur la série agrégée journalière, il en lit environ quatre cents.

## Décision

**1. Les agrégats sont calculés par la plateforme et réécrits en séries
distinctes.**

L'ordonnanceur porte un job `tsdb_rollup` (toutes les 30 minutes) qui délègue
le calcul à VictoriaMetrics via `avg_over_time`, `min_over_time` et
`max_over_time`, puis réécrit le résultat sous :

| Série | Origine | Étiquettes ajoutées |
|---|---|---|
| `cbc_metric_1h` | `cbc_metric` | `rollup="1h"`, `agg="avg\|min\|max"` |
| `cbc_metric_1d` | `cbc_metric_1h` | `rollup="1d"`, `agg="avg\|min\|max"` |

Trois propriétés sont tenues par construction :

- **L'intervalle en cours n'est jamais agrégé.** L'agréger produirait une
  valeur partielle qui ne serait jamais corrigée.
- **Le traitement est idempotent.** La dernière borne traitée est mémorisée
  (`tsdb_rollup_state`) ; un redémarrage ne réécrit pas, une exécution manquée
  est rattrapée.
- **Les bornes sont alignées** sur l'heure et sur le jour, quel que soit
  l'instant d'exécution.

Le rattrapage est borné à 48 intervalles par passage : un arrêt prolongé ne
doit pas déclencher une reconstruction de plusieurs mois au redémarrage.

**2. Le niveau `1m` du critère n'est pas produit.**

La période d'échantillonnage est de 30 s. Un agrégat à la minute diviserait le
volume par deux pour un coût de calcul permanent — sans bénéfice de requête,
puisque les fenêtres courtes se lisent très bien en brut. C'est un écart
assumé au critère, pas un oubli.

**3. La rétention à deux niveaux n'est pas mise en œuvre.**

Elle est techniquement impossible dans une instance VictoriaMetrics OSS unique.
La rétention appliquée est **globale et unique**, désormais paramétrable par
variable d'environnement au lieu d'être figée dans le fichier Compose.

La rétention des données **relationnelles** (heartbeats, alertes résolues) est
en revanche réellement appliquée, par le job `apply_retention`, en lisant la
table `retention_config` que personne ne lisait.

## Options écartées

**vmalert avec des règles d'enregistrement.** C'est la voie usuelle de
l'écosystème Prometheus, et elle est valable. Écartée parce qu'elle ajoute un
conteneur, un fichier de règles et un mode de panne supplémentaires, pour une
fonction que l'ordonnanceur déjà en place — testé, supervisé, avec reprise —
assure sans nouvelle brique.

**Deux instances VictoriaMetrics** (brut 30 j / agrégé 13 mois). C'est la seule
manière d'obtenir une vraie rétention à deux niveaux en OSS. Écartée pour le
Lot 1 : elle double la surface d'exploitation pour économiser une dizaine de
gigaoctets. À reconsidérer si le parc dépasse nettement 500 agents.

**VictoriaMetrics entreprise.** Résout les deux points nativement. Hors
périmètre : décision commerciale qui appartient à CBC.

## Conséquences

Positives :

- les requêtes longue portée deviennent exploitables ;
- l'avancement des agrégats est observable (`tsdb_rollup_state`) ;
- la rétention relationnelle est enfin appliquée, avec deux protections : une
  alerte encore ouverte n'est jamais supprimée, et la piste d'audit n'est
  jamais purgée par ce réglage.

Négatives, à assumer devant CBC :

- **FS2-04 reste partielle.** Deux points du critère ne sont pas tenus : le
  niveau `1m` et la rétention à deux niveaux. Le second est une limite du
  composant retenu en ADR-001, pas un reste à faire.
- Les séries agrégées **s'ajoutent** au volume brut au lieu de le remplacer,
  puisque le brut n'est pas purgé séparément. Le surcoût est faible (les
  agrégats sont deux à trois ordres de grandeur plus petits).

## À décider par CBC

1. **Vraie rétention à deux niveaux ?** Si oui : seconde instance
   VictoriaMetrics (Lot 2) ou édition entreprise.
2. **Durée de rétention.** Treize mois est repris du critère ; à confirmer au
   regard des obligations de conservation COBAC, qui peuvent être plus longues.

## Vérification

```bash
pytest server/tests/test_tsdb_rollup.py -q
```

En exploitation, après une heure de fonctionnement :

```
GET /api/v1/query?query=cbc_metric_1h
```

doit renvoyer des séries portant `rollup="1h"` et les trois valeurs de `agg`.
