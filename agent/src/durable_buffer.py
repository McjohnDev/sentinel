"""Tampon durable de type store-and-forward (AGT-005) : 24 h ou 500 Mo.

Garantie visée : **aucune perte** de mesure lorsque la plateforme est
injoignable, y compris si l'agent est tué pendant le rejeu.

L'implémentation précédente lisait la file puis supprimait le fichier *avant*
toute tentative d'envoi (`drain()`), et ne réécrivait que les enregistrements
en échec une fois la boucle terminée. Un arrêt brutal au milieu du rejeu —
coupure de courant, redémarrage du poste, arrêt de service — perdait donc tout
le lot déjà retiré du disque : exactement la perte que cette story existe pour
empêcher.

Le mécanisme retenu est le prélèvement en deux temps :

1. `checkout()` renomme atomiquement la file en fichier « en vol ». Les
   nouvelles écritures repartent sur une file vierge, sans se mélanger au lot
   en cours de traitement.
2. `commit(failed)` ne supprime le fichier en vol qu'après traitement, en
   réinjectant les échecs devant les enregistrements plus récents.
3. `recover()` — appelé à la construction — réintègre un fichier en vol laissé
   par un processus précédent.

Conséquence assumée : un enregistrement envoyé juste avant un arrêt brutal peut
être renvoyé au démarrage suivant. Pour de la métrologie, un doublon est
préférable à un trou.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DurableBuffer:
    """File JSONL sur disque. Survit au redémarrage. Rejeu ordonné."""

    def __init__(
        self,
        path: str | Path,
        max_bytes: int = 500 * 1024 * 1024,
        max_age_seconds: int = 24 * 3600,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        #: Lot prélevé mais pas encore acquitté. Le suffixe est stable : c'est
        #: ce qui permet de le retrouver après un arrêt brutal.
        self.inflight_path = self.path.with_suffix(self.path.suffix + ".inflight")
        self.max_bytes = max_bytes
        self.max_age_seconds = max_age_seconds
        self.recover()

    # ------------------------------------------------------------- écriture

    def enqueue(self, kind: str, payload: Any) -> None:
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "kind": kind,
            "payload": payload,
        }
        self._append([record])
        self.prune()

    def _append(self, records: List[Dict[str, Any]]) -> None:
        if not records:
            return
        with self.path.open("a", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec, default=str) + "\n")
            # Forcer l'écriture jusqu'au disque : sans cela, une coupure
            # d'alimentation perd un contenu que l'agent croyait persisté.
            f.flush()
            os.fsync(f.fileno())

    # -------------------------------------------------------------- lecture

    def __len__(self) -> int:
        return len(self.peek())

    def size_bytes(self) -> int:
        total = 0
        for p in (self.path, self.inflight_path):
            try:
                total += p.stat().st_size
            except OSError:
                pass
        return total

    def peek(self) -> List[Dict[str, Any]]:
        """Enregistrements en attente, en vol d'abord (ils sont plus anciens)."""
        return self._read(self.inflight_path) + self._read(self.path)

    @staticmethod
    def _read(path: Path) -> List[Dict[str, Any]]:
        if not path.exists():
            return []
        out: List[Dict[str, Any]] = []
        try:
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        out.append(json.loads(line))
                    except json.JSONDecodeError:
                        # Dernière ligne tronquée par un arrêt brutal : on
                        # ignore l'enregistrement partiel, pas le fichier.
                        logger.warning("Enregistrement illisible ignoré dans %s", path.name)
                        continue
        except OSError:
            logger.exception("Lecture impossible de %s", path)
        return out

    # ------------------------------------------------------- prélèvement

    def recover(self) -> int:
        """Réintègre un lot en vol laissé par un processus précédent.

        Les enregistrements en vol sont les plus anciens : ils doivent repasser
        devant ceux accumulés depuis, pour préserver l'ordre de rejeu.
        """
        if not self.inflight_path.exists():
            return 0
        stale = self._read(self.inflight_path)
        if not stale:
            self.inflight_path.unlink(missing_ok=True)
            return 0

        current = self._read(self.path)
        self._rewrite(self.path, stale + current)
        self.inflight_path.unlink(missing_ok=True)
        logger.warning(
            "%d enregistrement(s) récupéré(s) après un arrêt pendant le rejeu",
            len(stale),
        )
        return len(stale)

    def checkout(self) -> List[Dict[str, Any]]:
        """Prélève le lot à rejouer sans le détruire.

        Le renommage est atomique sur un même système de fichiers : soit la
        file devient le lot en vol, soit rien ne change. Aucun instant ne
        laisse les enregistrements nulle part.
        """
        # Un lot en vol déjà présent signifie que `commit` n'a pas été appelé :
        # le reprendre plutôt que de l'écraser.
        if self.inflight_path.exists():
            return self._read(self.inflight_path)
        if not self.path.exists():
            return []
        try:
            os.replace(self.path, self.inflight_path)
        except OSError:
            logger.exception("Prélèvement impossible ; le lot reste en file")
            return []
        return self._read(self.inflight_path)

    def commit(self, failed: Optional[List[Dict[str, Any]]] = None) -> None:
        """Clôt le prélèvement : réinjecte les échecs, supprime le lot en vol."""
        if failed:
            current = self._read(self.path)
            # Les échecs sont antérieurs : ils repassent devant.
            self._rewrite(self.path, list(failed) + current)
        self.inflight_path.unlink(missing_ok=True)

    def drain(self) -> List[Dict[str, Any]]:
        """Conservé pour compatibilité : équivaut à `checkout()`.

        Contrairement à la version précédente, le fichier n'est **pas** détruit
        ici. L'appelant doit clore par `commit()`.
        """
        return self.checkout()

    # ------------------------------------------------------------ entretien

    def replace(self, records: List[Dict[str, Any]]) -> None:
        """Réécrit la file (rejeu partiellement en échec)."""
        self._rewrite(self.path, records)
        self.inflight_path.unlink(missing_ok=True)

    @staticmethod
    def _rewrite(path: Path, records: List[Dict[str, Any]]) -> None:
        """Réécriture atomique : fichier temporaire puis renommage.

        Écrire en place laisserait un fichier tronqué si le processus s'arrête
        au milieu de l'opération.
        """
        if not records:
            path.unlink(missing_ok=True)
            return
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec, default=str) + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)

    def prune(self) -> None:
        """Applique les bornes d'âge et de taille (AGT-005)."""
        now = time.time()
        kept: List[Dict[str, Any]] = []
        for rec in self._read(self.path):
            ts_raw = rec.get("ts")
            try:
                ts = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
                age = now - ts.timestamp()
            except (TypeError, ValueError, OSError):
                age = 0
            if age <= self.max_age_seconds:
                kept.append(rec)

        dropped_age = len(self._read(self.path)) - len(kept)

        encoded = [json.dumps(r, default=str) for r in kept]
        total = sum(len(e.encode("utf-8")) + 1 for e in encoded)
        dropped_size = 0
        while kept and total > self.max_bytes:
            dropped = encoded.pop(0)
            kept.pop(0)
            total -= len(dropped.encode("utf-8")) + 1
            dropped_size += 1

        if dropped_age or dropped_size:
            # Une purge est une perte de données assumée : elle doit être
            # visible dans les journaux, pas silencieuse.
            logger.warning(
                "Purge du tampon : %d hors délai, %d par dépassement de taille",
                dropped_age,
                dropped_size,
            )
        self._rewrite(self.path, kept)
