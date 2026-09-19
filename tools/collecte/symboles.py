"""Extraction du symbole d'un support, a partir des reponses des sources.

Un ISIN ne suffit pas a interroger un historique : chaque source a son propre
identifiant. Ce module le retrouve dans les reponses deja capturees, ce qui le
rend testable hors ligne.

La nature du symbole compte autant que sa valeur : pour un fonds non cote, un
cours de bourse n'est pas une valeur liquidative. Un identifiant Morningstar
(prefixe 0P) donne la VL ; un code de place donne un cours, qui peut s'en
ecarter. La cascade doit donc preferer le premier.
"""
import json
import re

# Prefixes rencontres dans les symboles Boursorama, par ordre de preference.
NATURE_BOURSORAMA = [
    ("0P", "vl", "identifiant de fonds Morningstar, valeur liquidative"),
    ("MP-", "vl", "code de fonds Boursorama, valeur liquidative"),
    ("1rT", "cours", "tracker coté sur Euronext"),
    ("1rP", "cours", "action cotée sur Euronext"),
]


def nature(symbole):
    """Le symbole designe-t-il une valeur liquidative ou un cours de bourse ?"""
    for prefixe, genre, libelle in NATURE_BOURSORAMA:
        if symbole.startswith(prefixe):
            return genre, libelle
    return "cours", "place non identifiée"


def depuis_boursorama(html):
    """Symbole Boursorama lu sur la fiche d'un support.

    La recherche par ISIN redirige vers la fiche ; le symbole y figure dans la
    charge utile JSON de la page. Renvoie None si la page n'est pas une fiche.
    """
    trouve = re.search(r'"symbol"\s*:\s*"([^"]+)"', html)
    if not trouve:
        return None
    symbole = trouve.group(1)
    genre, libelle = nature(symbole)
    return {"symbole": symbole, "genre": genre, "precision": libelle}


def depuis_yahoo(charge):
    """Symbole Yahoo, choisi parmi les resultats de recherche.

    Un identifiant Morningstar est prefere a une cotation de place : il porte la
    valeur liquidative, la seconde un prix de marche qui peut s'en ecarter.
    """
    resultats = json.loads(charge).get("quotes") or []
    if not resultats:
        return None
    morningstar = [r for r in resultats if str(r.get("symbol", "")).startswith("0P")]
    retenu = (morningstar or resultats)[0]
    symbole = retenu.get("symbol")
    return {"symbole": symbole,
            "genre": "vl" if symbole.startswith("0P") else "cours",
            "precision": f"{retenu.get('exchange', '?')} — {retenu.get('quoteType', '?')}"}
