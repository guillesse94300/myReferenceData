"""Sonde les points d'acces d'historique, avec les symboles deja resolus.

Deuxieme tour de capture. Le premier a montre que Boursorama et Yahoo
identifient chacun les 14 supports ; reste a savoir lequel accepte de livrer
une serie de valeurs, sur quelle profondeur et sous quelle forme.

Les symboles sont relus des captures du premier tour : aucune requete de
resolution n'est refaite. Les reponses attendues sont du JSON, donc legeres.

    .venv\\Scripts\\python tools\\capturer_historiques.py
"""
import argparse
import datetime
import glob
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

RACINE = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(RACINE, "tools"))
from collecte import symboles

CAPTURES = os.path.join(RACINE, "data/raw/captures")
HISTORIQUES = os.path.join(CAPTURES, "historiques")

ENTETES = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Referer": "https://www.boursorama.com/",
}
DELAI = 2.0
DELAI_EXPIRATION = 30
JOURS = 1825            # cinq ans

# Plusieurs formes sont tentees par source : laquelle repond est justement
# l'inconnue que cette capture doit lever.
SONDES = {
    "boursorama": [
        ("bourso_eod", "https://www.boursorama.com/bourse/action/graph/ws/GetTicksEOD"
                       "?symbol={symbole}&length={jours}&period=0&guid="),
        ("bourso_charts", "https://www.boursorama.com/bourse/action/graph/ws/UpdateCharts"
                          "?symbol={symbole}&period=-1"),
    ],
    "yahoo": [
        ("yahoo_chart", "https://query1.finance.yahoo.com/v8/finance/chart/{symbole}"
                        "?range=5y&interval=1d"),
    ],
}

# Sonde croisee : le point d'acces de Yahoo accepte les identifiants Morningstar,
# suffixes de la place de Francfort. Lorsque la recherche Yahoo a renvoye une
# cotation de place la ou Boursorama donnait un identifiant de fonds, c'est
# celui-ci qu'il faut essayer -- il porte la valeur liquidative.
SONDE_CROISEE = ("yahoo_via_boursorama",
                 "https://query1.finance.yahoo.com/v8/finance/chart/{symbole}.F"
                 "?range=5y&interval=1d")

# Dernier recours : chercher par le nom du fonds plutot que par son ISIN.
# Certains supports ne sont resolus par aucune source vers un identifiant de
# valeur liquidative, alors que la recherche par libelle en trouve un.
SONDE_PAR_NOM = ("yahoo_recherche_nom",
                 "https://query1.finance.yahoo.com/v1/finance/search"
                 "?q={nom}&quotesCount=10")


def libelles():
    """Nom de chaque support, pour la recherche de dernier recours."""
    import sqlite3
    cx = sqlite3.connect(os.path.join(RACINE, "data/reference.db"))
    noms = {r[0]: r[1] for r in cx.execute("SELECT isin, nom FROM instrument")}
    cx.close()
    return noms


def resoudre():
    """Symboles des deux sources, relus des captures du premier tour."""
    table = {}
    for chemin in sorted(glob.glob(os.path.join(CAPTURES, "*__boursorama_recherche.html"))):
        isin = os.path.basename(chemin).split("__")[0]
        lu = symboles.depuis_boursorama(open(chemin, encoding="utf-8", errors="replace").read())
        if lu:
            table.setdefault(isin, {})["boursorama"] = lu
    for chemin in sorted(glob.glob(os.path.join(CAPTURES, "*__yahoo_recherche.json"))):
        isin = os.path.basename(chemin).split("__")[0]
        lu = symboles.depuis_yahoo(open(chemin, encoding="utf-8", errors="replace").read())
        if lu:
            table.setdefault(isin, {})["yahoo"] = lu
    return table


def interroger(url):
    debut = time.time()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=ENTETES),
                                    timeout=DELAI_EXPIRATION) as reponse:
            return reponse.status, reponse.read(), time.time() - debut
    except urllib.error.HTTPError as erreur:
        return erreur.code, erreur.read()[:4000], time.time() - debut
    except Exception as erreur:
        return 0, f"{type(erreur).__name__}: {erreur}".encode(), time.time() - debut


def compter_points(corps):
    """Nombre de valeurs dans la reponse, sans en connaitre le format exact."""
    try:
        charge = json.loads(corps)
    except Exception:
        return None
    compte = 0

    def parcourir(noeud):
        nonlocal compte
        if isinstance(noeud, list):
            if noeud and all(isinstance(x, (int, float)) for x in noeud):
                compte = max(compte, len(noeud))
            for x in noeud:
                parcourir(x)
        elif isinstance(noeud, dict):
            for x in noeud.values():
                parcourir(x)

    parcourir(charge)
    return compte


def main():
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--limite", type=int, default=0)
    options = analyseur.parse_args()
    os.makedirs(HISTORIQUES, exist_ok=True)

    table, noms = resoudre(), libelles()
    if not table:
        raise SystemExit("Aucun symbole : lancez d'abord tools/capturer_sources.py.")
    supports = list(table.items())[:options.limite] if options.limite else list(table.items())
    total = sum(len(SONDES[s]) for _, sources in supports for s in sources if s in SONDES)
    print(f"{len(supports)} support(s), {total} requêtes, environ {total * DELAI / 60:.0f} min\n")

    journal = []
    for isin, sources in supports:
        genres = " ".join(f"{s}:{v['symbole']}({v['genre']})" for s, v in sources.items())
        print(f"{isin}  {genres}")
        tentatives = [(source, resolu, nom, gabarit)
                      for source, resolu in sources.items()
                      for nom, gabarit in SONDES.get(source, [])]
        bourso, yh = sources.get("boursorama"), sources.get("yahoo")
        if bourso and yh and bourso["symbole"].startswith("0P") and yh["genre"] != "vl":
            tentatives.append(("boursorama", bourso, *SONDE_CROISEE))
        # Un fonds non coté dont aucune source ne donne d'identifiant Morningstar :
        # la recherche par libellé est le dernier recours. Les trackers en sont
        # exclus, un cours de bourse y étant la donnée pertinente.
        elif (bourso and bourso["genre"] == "vl" and not bourso["symbole"].startswith("0P")
              and yh and yh["genre"] != "vl"):
            nom = urllib.parse.quote(noms.get(isin, ""))
            if nom:
                tentatives.append(("yahoo", {"symbole": nom, "genre": "recherche"},
                                   *SONDE_PAR_NOM))
        for source, resolu, nom, gabarit in tentatives:
                url = gabarit.format(symbole=resolu["symbole"], jours=JOURS,
                                     nom=resolu["symbole"])
                statut, corps, duree = interroger(url)
                points = compter_points(corps)
                if statut and statut < 400 and corps:
                    with open(os.path.join(HISTORIQUES, f"{isin}__{nom}.json"), "wb") as sortie:
                        sortie.write(corps)
                journal.append({"isin": isin, "source": source, "sonde": nom,
                                "symbole": resolu["symbole"], "genre": resolu["genre"],
                                "url": url, "statut": statut, "octets": len(corps),
                                "points_estimes": points, "secondes": round(duree, 2)})
                etat = (f"{points} valeurs" if points else
                        (f"refus {statut}" if statut >= 400 else
                         ("injoignable" if statut == 0 else "réponse non exploitable")))
                print(f"    {nom:16s} {etat:22s} {len(corps):>8d} o  {duree:4.1f}s")
                time.sleep(DELAI)

    with open(os.path.join(HISTORIQUES, "journal.json"), "w", encoding="utf-8") as sortie:
        json.dump({"capture_le": datetime.datetime.now().isoformat(timespec="seconds"),
                   "requetes": journal}, sortie, ensure_ascii=False, indent=2)

    print("\n" + "=" * 66)
    print(f"{'sonde':18s} {'répond':>8s} {'points médians':>16s}")
    for source, sondes in SONDES.items():
        for nom, _ in sondes:
            lignes = [l for l in journal if l["sonde"] == nom]
            utiles = sorted(l["points_estimes"] for l in lignes if l["points_estimes"])
            mediane = utiles[len(utiles) // 2] if utiles else 0
            print(f"{nom:18s} {len(utiles):>4d}/{len(lignes):<3d} {mediane:>16d}")
    print(f"\nRéponses dans {os.path.relpath(HISTORIQUES, RACINE)}. Committez ce dossier.")


if __name__ == "__main__":
    main()
