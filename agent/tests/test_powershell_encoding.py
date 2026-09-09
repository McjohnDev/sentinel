"""Les scripts PowerShell doivent porter un BOM UTF-8.

Ce test existe a cause d'une panne reelle, le 9 septembre 2026 : l'installateur
depose sur la machine Laragon refusait de s'analyser, avec douze erreurs de
syntaxe portant sur des lignes qui n'etaient pas du code.

La cause tient en une phrase. Sans BOM, Windows PowerShell 5.1 lit un .ps1 en
CP1252. Le tiret cadratin « - » (U+2014), soit E2 80 94 en UTF-8, s'y relit en
trois caracteres dont le dernier est U+201D — un guillemet **valide** pour
PowerShell. Chaque tiret cadratin injecte donc un delimiteur de chaine
parasite ; passe un certain nombre, l'analyseur se desynchronise et le contenu
des chaines multilignes finit interprete comme du code.

Pourquoi personne ne le voyait : PowerShell 7 lit l'UTF-8 par defaut, et c'est
lui qu'on a sous la main en developpement. Le defaut n'apparait que sur la
machine cible, souvent en production, et son message d'erreur ne nomme jamais
l'encodage.

Les fins de ligne, elles, ne jouent aucun role : verifie par bissection sur le
fichier fautif (BOM absent -> 12 erreurs en LF comme en CRLF ; BOM present ->
analyse propre dans les deux cas).
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

BOM = b"\xef\xbb\xbf"
RACINE = Path(__file__).resolve().parents[2]

#: Caracteres dont la relecture en CP1252 produit un delimiteur de chaine.
#: Ce sont eux qui cassent l'analyse ; les accents simples, eux, ne font que
#: s'afficher de travers.
DELIMITEURS = set('"“”„' + "'‘’‚")


def _scripts() -> list[Path]:
    return sorted(
        p
        for p in RACINE.rglob("*.ps1")
        if "node_modules" not in p.parts
        and ".venv" not in p.parts
        and "dist" not in p.parts
    )


def test_des_scripts_existent():
    """Un test qui ne verifie rien passerait silencieusement."""
    assert _scripts(), "aucun script PowerShell trouve — le motif de recherche est-il juste ?"


@pytest.mark.parametrize("script", _scripts(), ids=lambda p: p.name)
def test_un_script_non_ascii_porte_un_bom(script: Path):
    brut = script.read_bytes()
    corps = brut[len(BOM):] if brut.startswith(BOM) else brut

    try:
        texte = corps.decode("utf-8")
    except UnicodeDecodeError:
        pytest.fail("%s n'est pas de l'UTF-8." % script.name)

    if all(ord(c) < 128 for c in texte):
        return  # Purement ASCII : aucun risque, quel que soit l'encodage.

    assert brut.startswith(BOM), (
        "%s contient des caracteres non-ASCII sans BOM UTF-8.\n"
        "Windows PowerShell 5.1 le lira en CP1252 : les accents s'afficheront "
        "de travers, et un tiret cadratin suffit a casser l'analyse du script."
        % script.name
    )


@pytest.mark.parametrize("script", _scripts(), ids=lambda p: p.name)
def test_aucun_delimiteur_parasite_en_cp1252(script: Path):
    """La verification qui compte vraiment : le nombre de guillemets change-t-il ?

    Le BOM suffit en pratique, mais ce test dit *pourquoi* il suffit, et
    attraperait un fichier qui perdrait son BOM en chemin — par un outil
    d'edition, un copier-coller, ou un commit depuis un autre systeme.
    """
    brut = script.read_bytes()
    corps = brut[len(BOM):] if brut.startswith(BOM) else brut
    if brut.startswith(BOM):
        return  # Lu correctement : la question ne se pose pas.

    texte = corps.decode("utf-8")
    relu = corps.decode("cp1252", errors="replace")

    avant = sum(1 for c in texte if c in DELIMITEURS)
    apres = sum(1 for c in relu if c in DELIMITEURS)

    assert avant == apres, (
        "%s : relu en CP1252, le fichier gagne %d delimiteur(s) de chaine. "
        "L'analyseur de PowerShell 5.1 s'y desynchronisera."
        % (script.name, apres - avant)
    )


def test_le_piege_est_bien_celui_decrit():
    """Fige la mecanique, pour que le commentaire ci-dessus reste verifiable.

    Si un jour ce test echoue, c'est que la table CP1252 ou l'encodage UTF-8
    ont change — auquel cas toute l'explication est a revoir.
    """
    tiret_cadratin = "—"
    relu = tiret_cadratin.encode("utf-8").decode("cp1252")

    assert relu[-1] in DELIMITEURS, (
        "le tiret cadratin ne produit plus de guillemet en CP1252 ; "
        "l'explication de ce module est a reprendre."
    )


def test_le_repertoire_de_travail_ne_change_rien(tmp_path):
    """Le test doit porter sur le depot, pas sur le dossier courant."""
    fichier = tmp_path / "ailleurs.ps1"
    with io.open(fichier, "w", encoding="utf-8") as f:
        f.write("Write-Host 'sans accent'\n")

    assert fichier not in _scripts()
