"""Table sous-réseau → VLAN fournie par l'équipe réseau.

Pourquoi une table de **sous-réseaux** et non une liste d'hôtes : une machine
sur port d'accès ne peut pas connaître son VLAN, mais l'agent remonte son
adresse IP à chaque battement. Un VLAN correspondant presque toujours à un ou
plusieurs sous-réseaux, la table permet de déduire le VLAN de **tout** le parc
sans saisie par hôte — et la déduction suit d'elle-même quand une machine
change d'adresse ou de site.

Une liste `hôte → VLAN` serait juste le jour de son export et fausse dès la
première machine rebranchée.

Le fichier vient d'Excel : le séparateur est donc souvent le point-virgule
(convention française), le fichier peut porter une signature d'octets, et les
en-têtes sont en français. Tout cela est absorbé ici plutôt que d'être exigé
de l'équipe réseau.
"""

from __future__ import annotations

import csv
import io
import ipaddress
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

#: Bornes 802.1Q. 0 et 4095 sont réservés.
VLAN_MIN = 1
VLAN_MAX = 4094

#: En-têtes acceptés pour chaque colonne, en minuscules sans accent.
_SUBNET_HEADERS = {"sous-reseau", "sous reseau", "subnet", "reseau", "cidr", "network", "plage"}
_VLAN_HEADERS = {"vlan", "vlan id", "vlanid", "id vlan", "numero", "numero vlan", "tag"}
_LABEL_HEADERS = {"libelle", "label", "nom", "name", "description", "designation", "zone"}

_ACCENTS = str.maketrans("àâäéèêëîïôöùûüç", "aaaeeeeiioouuuc")


class VlanImportError(ValueError):
    """Fichier inexploitable — message destiné à l'exploitant."""


@dataclass(frozen=True)
class SubnetRow:
    cidr: str
    vlan: str
    label: Optional[str]

    @property
    def network(self) -> ipaddress.IPv4Network:
        return ipaddress.ip_network(self.cidr, strict=False)


@dataclass
class ImportReport:
    rows: List[SubnetRow]
    rejected: List[Dict[str, Any]]

    @property
    def accepted_count(self) -> int:
        return len(self.rows)


def _fold(value: Any) -> str:
    return str(value or "").strip().lower().translate(_ACCENTS)


def normalise_cidr(value: Any) -> Optional[str]:
    """Ramène une saisie réseau à une notation CIDR, ou None.

    Accepte `10.20.4.0/24`, une adresse seule (traitée comme /32) et la forme
    `10.20.4.0 255.255.255.0` que produisent certains exports.
    """
    raw = str(value or "").strip()
    if not raw:
        return None
    raw = raw.replace(" ", " ")  # espace insécable, fréquent depuis Excel

    # Forme « réseau masque »
    parts = raw.split()
    if len(parts) == 2:
        try:
            network = ipaddress.ip_network("%s/%s" % (parts[0], parts[1]), strict=False)
            return str(network)
        except ValueError:
            return None

    try:
        network = ipaddress.ip_network(raw, strict=False)
    except ValueError:
        return None
    return str(network)


def normalise_vlan(value: Any) -> Optional[str]:
    """Extrait un identifiant 802.1Q valide, ou None.

    Tolère « VLAN 20 » et « 20 (Monétique) » : l'équipe réseau écrit rarement
    un entier nu dans un tableur.
    """
    raw = str(value or "").strip()
    if not raw:
        return None
    match = re.search(r"\d+", raw)
    if not match:
        return None
    number = int(match.group())
    if not (VLAN_MIN <= number <= VLAN_MAX):
        return None
    return str(number)


def _read_csv(content: bytes) -> List[Sequence[Any]]:
    text = content.decode("utf-8-sig", errors="replace")
    if not text.strip():
        return []
    sample = text[:4096]
    try:
        # Excel francais ecrit des points-virgules ; l'anglais des virgules.
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ";" if sample.count(";") >= sample.count(",") else ","
    return [row for row in csv.reader(io.StringIO(text), delimiter=delimiter) if any(c.strip() for c in row)]


def _read_xlsx(content: bytes) -> List[Sequence[Any]]:
    try:
        from openpyxl import load_workbook
    except ImportError:  # pragma: no cover - dépendance déclarée
        raise VlanImportError(
            "Lecture .xlsx indisponible sur ce serveur. Réenregistrer le "
            "fichier au format CSV et le réimporter."
        )
    try:
        workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except Exception as exc:
        raise VlanImportError("Classeur illisible : %s" % exc)
    sheet = workbook.active
    rows = []
    for row in sheet.iter_rows(values_only=True):
        if row and any(str(c).strip() for c in row if c is not None):
            rows.append(list(row))
    workbook.close()
    return rows


def _column_positions(header: Sequence[Any]) -> Optional[Tuple[int, int, Optional[int]]]:
    """Repère les colonnes d'après leur intitulé, si la ligne en est un."""
    folded = [_fold(c) for c in header]
    subnet = vlan = label = None
    for index, name in enumerate(folded):
        if subnet is None and name in _SUBNET_HEADERS:
            subnet = index
        elif vlan is None and name in _VLAN_HEADERS:
            vlan = index
        elif label is None and name in _LABEL_HEADERS:
            label = index
    if subnet is None or vlan is None:
        return None
    return subnet, vlan, label


def parse(content: bytes, filename: str = "") -> ImportReport:
    """Lit le fichier de l'équipe réseau et rend les lignes exploitables.

    Une ligne fautive est **rejetée nommément**, jamais ignorée en silence :
    un import qui avale à moitié un fichier de segmentation laisserait des
    hôtes rattachés à un VLAN qui n'est pas le leur, sans que personne ne le
    sache.
    """
    if not content:
        raise VlanImportError("Fichier vide.")

    lowered = (filename or "").lower()
    if lowered.endswith((".xlsx", ".xlsm")):
        raw_rows = _read_xlsx(content)
    elif lowered.endswith(".xls"):
        raise VlanImportError(
            "Format .xls (Excel 97) non pris en charge. Réenregistrer en .xlsx "
            "ou en CSV."
        )
    else:
        raw_rows = _read_csv(content)

    if not raw_rows:
        raise VlanImportError("Aucune ligne exploitable dans le fichier.")

    positions = _column_positions(raw_rows[0])
    if positions is not None:
        subnet_at, vlan_at, label_at = positions
        body = raw_rows[1:]
    else:
        # Pas d'en-tête reconnu : on suppose l'ordre naturel du document
        # demandé — sous-réseau, VLAN, libellé.
        subnet_at, vlan_at, label_at = 0, 1, 2
        body = raw_rows

    accepted: List[SubnetRow] = []
    rejected: List[Dict[str, Any]] = []
    seen: Dict[str, int] = {}

    for offset, row in enumerate(body):
        line = offset + (2 if positions is not None else 1)

        def cell(index: Optional[int]) -> Any:
            if index is None or index >= len(row):
                return None
            return row[index]

        cidr = normalise_cidr(cell(subnet_at))
        vlan = normalise_vlan(cell(vlan_at))

        if cidr is None:
            rejected.append({"line": line, "reason": "sous-réseau illisible", "value": _cell_text(cell(subnet_at))})
            continue
        if vlan is None:
            rejected.append({"line": line, "reason": "VLAN absent ou hors 1-4094", "value": _cell_text(cell(vlan_at))})
            continue
        if cidr in seen:
            rejected.append({
                "line": line,
                "reason": "sous-réseau déjà défini ligne %d" % seen[cidr],
                "value": cidr,
            })
            continue

        seen[cidr] = line
        label = _cell_text(cell(label_at)) or None
        accepted.append(SubnetRow(cidr=cidr, vlan=vlan, label=label[:120] if label else None))

    if not accepted:
        raise VlanImportError(
            "Aucune ligne valide. Attendu : sous-réseau (10.20.4.0/24), "
            "VLAN (1-4094), libellé facultatif."
        )
    return ImportReport(rows=accepted, rejected=rejected)


def _cell_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def match_ip(ip_address: Optional[str], rows: Iterable[SubnetRow]) -> Optional[SubnetRow]:
    """Sous-réseau le plus spécifique contenant cette adresse.

    Le plus spécifique, et non le premier trouvé : les plans d'adressage
    déclarent couramment un /16 de site *et* les /24 qui le découpent. Rendre
    le /16 rattacherait tous les hôtes au mauvais VLAN.
    """
    if not ip_address:
        return None
    try:
        address = ipaddress.ip_address(str(ip_address).strip())
    except ValueError:
        return None

    best: Optional[SubnetRow] = None
    best_length = -1
    for row in rows:
        try:
            network = row.network
        except ValueError:
            continue
        if address.version != network.version:
            continue
        if address in network and network.prefixlen > best_length:
            best = row
            best_length = network.prefixlen
    return best
