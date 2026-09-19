"""Confronte les series de valeurs liquidatives aux performances publiees.

Une valeur liquidative est nette des frais du fonds, comme la performance
annuelle que publie l'assureur : les deux doivent concorder. C'est le controle
qui permet d'accepter une source sans avoir a lui faire confiance.

La concordance ne peut toutefois pas etre exacte. L'assureur arrete au
31 decembre, date souvent absente des series, si bien que le calcul porte sur
la derniere seance disponible de chaque annee. L'ecart qui en resulte vaut un a
deux mouvements quotidiens du fonds : nul sur un fonds obligataire, sensible
sur un fonds aurifere. Le critere tient donc compte de la volatilite du support
plutot que d'exiger un seuil unique.

    python tools/valider_series.py
"""
import glob
import os
import sqlite3
import statistics
import sys

RACINE = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(RACINE, "tools"))
from collecte import yahoo

HISTORIQUES = os.path.join(RACINE, "data/raw/captures/historiques")
BASE = os.path.join(RACINE, "data/reference.db")

# Un decalage d'une a deux seances aux bornes de l'annee : l'ecart admis est
# donc proportionnel au mouvement quotidien du fonds, avec une marge.
TOLERANCE_EN_JOURNEES = 2.5
PLANCHER = 0.10          # en deca, la precision d'arrondi des sources domine


def publiees():
    cx = sqlite3.connect(BASE)
    perfs = {(r[0], r[1]): r[2] for r in cx.execute(
        "SELECT isin, annee, perf_nette FROM performance_annuelle")}
    noms = {r[0]: r[1] for r in cx.execute("SELECT isin, nom FROM instrument")}
    cx.close()
    return perfs, noms


def meilleures_series():
    """La serie la plus fournie par support, toutes sondes confondues.

    Un meme support peut avoir ete interroge par plusieurs sondes -- la
    recherche directe et la sonde croisee passant par l'identifiant Boursorama.
    C'est la plus longue qui est retenue.
    """
    retenues = {}
    for chemin in sorted(glob.glob(os.path.join(HISTORIQUES, "*__yahoo*.json"))):
        isin = os.path.basename(chemin).split("__")[0]
        valeurs = yahoo.serie(open(chemin, encoding="utf-8").read())
        if len(valeurs) > len(retenues.get(isin, {})):
            retenues[isin] = valeurs
    return retenues


def main():
    perfs, noms = publiees()
    lignes, refuses = [], []
    for isin, valeurs in meilleures_series().items():
        if len(valeurs) < 100:
            refuses.append((isin, len(valeurs)))
            continue
        volatilite = yahoo.volatilite_quotidienne(valeurs)
        tolerance = max(PLANCHER, TOLERANCE_EN_JOURNEES * volatilite)
        for annee in range(2021, 2026):
            publiee = perfs.get((isin, annee))
            calculee = yahoo.performance_annuelle(valeurs, annee)
            if publiee is None or calculee is None:
                continue
            lignes.append({"isin": isin, "nom": noms.get(isin, "?"), "annee": annee,
                           "publiee": publiee, "calculee": calculee,
                           "ecart": calculee - publiee, "volatilite": volatilite,
                           "tolerance": tolerance,
                           "conforme": abs(calculee - publiee) <= tolerance})

    print(f"{'ISIN':14s}{'année':>6s}{'publiée':>10s}{'calculée':>10s}{'écart':>8s}"
          f"{'toléré':>8s}   support")
    for l in lignes:
        print(f"{l['isin']:14s}{l['annee']:>6d}{l['publiee']:>9.2f}%{l['calculee']:>9.2f}%"
              f"{l['ecart']:>+8.2f}{l['tolerance']:>8.2f}"
              f"{'' if l['conforme'] else '  ÉCART'}   {l['nom'][:24]}")

    if not lignes:
        print("\nAucun couple à comparer.")
        return 1
    ecarts = [abs(l["ecart"]) for l in lignes]
    hors = [l for l in lignes if not l["conforme"]]
    print(f"\n{len(lignes)} couples comparés sur "
          f"{len({l['isin'] for l in lignes})} supports")
    print(f"  écart médian        {statistics.median(ecarts):.2f} pt")
    print(f"  hors tolérance      {len(hors)} ({100 * len(hors) / len(lignes):.0f} %)")
    for l in hors:
        print(f"      {l['isin']} {l['annee']} : {l['ecart']:+.2f} pt pour "
              f"{l['tolerance']:.2f} toléré")
    if refuses:
        print(f"  séries inexploitables : {len(refuses)}")
        for isin, n in refuses:
            print(f"      {isin} — {n} point(s), symbole résolu vers une cotation de place")
    verdict = not hors
    print(f"\n{'ACCEPTÉ' if verdict else 'REFUSÉ'} — critère : écart annuel inférieur à "
          f"{TOLERANCE_EN_JOURNEES} mouvements quotidiens du fonds")
    return 0 if verdict else 1


if __name__ == "__main__":
    sys.exit(main())
