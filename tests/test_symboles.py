"""Le parseur de symboles est verifie contre les reponses reellement capturees.

Ces captures restent utiles apres la mise au point : si une source change de
format, le test echoue au lieu de laisser passer des donnees fausses.
"""
import glob
import os
import sys

RACINE = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(RACINE, "tools"))
from collecte import symboles

CAPTURES = os.path.join(RACINE, "data/raw/captures")


def captures(motif):
    return {os.path.basename(c).split("__")[0]: open(c, encoding="utf-8", errors="replace").read()
            for c in sorted(glob.glob(os.path.join(CAPTURES, motif)))}


def test_boursorama_resout_chaque_support():
    lus = {isin: symboles.depuis_boursorama(h)
           for isin, h in captures("*__boursorama_recherche.html").items()}
    assert lus, "aucune capture Boursorama"
    manquants = [i for i, v in lus.items() if not v]
    assert not manquants, f"symbole introuvable pour {manquants}"


def test_yahoo_resout_chaque_support():
    lus = {isin: symboles.depuis_yahoo(c)
           for isin, c in captures("*__yahoo_recherche.json").items()}
    assert lus, "aucune capture Yahoo"
    manquants = [i for i, v in lus.items() if not v]
    assert not manquants, f"symbole introuvable pour {manquants}"


def test_boursorama_donne_la_vl_sur_les_fonds_non_cotes():
    """Sur un fonds non cote, la source doit livrer une VL et non un cours."""
    attendus = {"FR0010011171", "LU0503631987", "LU0524465977",
                "LU1250158166", "LU1379103812", "LU0173614495"}
    lus = captures("*__boursorama_recherche.html")
    for isin in attendus & set(lus):
        resolu = symboles.depuis_boursorama(lus[isin])
        assert resolu["genre"] == "vl", f"{isin} : {resolu}"


def test_morningstar_prefere_a_une_cotation_de_place():
    charge = ('{"quotes":[{"symbol":"PBFW.MU","exchange":"MUN"},'
              '{"symbol":"0P0000PTZT.F","exchange":"FRA"}]}')
    assert symboles.depuis_yahoo(charge)["symbole"] == "0P0000PTZT.F"


def test_la_recherche_par_nom_livre_un_identifiant_de_fonds():
    """Fidelity China n'est résolu par aucune source : son nom, lui, l'est."""
    chemin = os.path.join(CAPTURES, "historiques", "LU0173614495__yahoo_recherche_nom.json")
    assert symboles.morningstar_dans_recherche(open(chemin, encoding="utf-8").read()) == "0P00000TDB"


def test_une_recherche_sans_fonds_ne_livre_rien():
    assert symboles.morningstar_dans_recherche('{"quotes":[{"symbol":"AAPL"}]}') is None
    assert symboles.morningstar_dans_recherche("pas du json") is None
