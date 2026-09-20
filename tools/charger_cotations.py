"""Charge les series capturees dans la base des cotations, dans les deux conventions.

Cette base s'accumule : contrairement a reference.db, elle n'est pas effacee a
chaque execution. Le chargement est donc idempotent -- une valeur deja presente
pour un couple (support, date, convention) est remplacee, jamais dupliquee.

Les deux conventions sont chargees cote a cote plutot qu'arbitrees ici :
`serie` donne la cloture brute, qui est le prix du jour, et `serie_ajustee` la
cloture ajustee des dividendes, qui est la base d'une performance dividendes
reinvestis. C'est la vue v_serie qui tranche a la lecture, pas le chargeur.

La source est pour l'instant le dossier de captures. Le collecteur, plus tard,
alimentera la meme base par le meme chemin.

    python tools/charger_cotations.py
"""
import datetime
import glob
import hashlib
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from collecte import yahoo

RACINE = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
HISTORIQUES = os.path.join(RACINE, "data/raw/captures/historiques")
COTATIONS = os.path.join(RACINE, "data/cotations.db")
SCHEMA = os.path.join(RACINE, "db/schema_cotations.sql")


def meilleures_series():
    """La capture la plus fournie par support, ses deux conventions et sa devise."""
    retenues = {}
    for chemin in sorted(glob.glob(os.path.join(HISTORIQUES, "*__yahoo*.json"))):
        fichier = os.path.basename(chemin)
        isin, sonde = fichier.split("__")[0], fichier.split("__")[1].removesuffix(".json")
        charge = open(chemin, encoding="utf-8").read()
        brute = yahoo.serie(charge)
        if len(brute) > len(retenues.get(isin, {}).get("brute", {})):
            retenues[isin] = {"brute": brute, "ajustee": yahoo.serie_ajustee(charge),
                              "sonde": sonde,
                              "devise": yahoo.metadonnees(charge).get("currency")}
    return retenues


def empreinte_du_dossier():
    """SHA-256 des captures retenues : deux chargements identiques se reconnaissent."""
    condense = hashlib.sha256()
    for chemin in sorted(glob.glob(os.path.join(HISTORIQUES, "*__yahoo*.json"))):
        condense.update(os.path.basename(chemin).encode())
        condense.update(open(chemin, "rb").read())
    return condense.hexdigest()


def main():
    os.makedirs(os.path.dirname(COTATIONS), exist_ok=True)
    cx = sqlite3.connect(COTATIONS)
    cx.executescript(open(SCHEMA, encoding="utf-8").read())
    maintenant = datetime.datetime.now().isoformat(timespec="seconds")
    series = meilleures_series()
    lues = sum(len(s["brute"]) + len(s["ajustee"]) for s in series.values())

    lot = cx.execute(
        "INSERT INTO import_cotation (fichier, empreinte, extrait_le, importe_le,"
        " lignes_lues, retenues, rejetees) VALUES (?,?,?,?,?,?,?)",
        (os.path.relpath(HISTORIQUES, RACINE), empreinte_du_dossier(), None,
         maintenant, lues, 0, 0)).lastrowid

    ecrites = 0
    print(f"{'ISIN':14s}{'brute':>7s}{'ajustée':>9s}{'écart max':>11s}{'devise':>8s}  période")
    for isin, lu in sorted(series.items()):
        dates = sorted(lu["brute"])
        for base in ("brute", "ajustee"):
            valeurs = lu[base]
            if not valeurs:
                continue
            cx.executemany(
                "INSERT INTO valeur_liquidative (isin, date, base, valeur, devise, moment,"
                " source, import_id) VALUES (?,?,?,?,?,'cloture',?,?)"
                " ON CONFLICT (isin, date, base) DO UPDATE SET valeur = excluded.valeur,"
                " devise = excluded.devise, source = excluded.source,"
                " import_id = excluded.import_id",
                [(isin, d.isoformat(), base, valeurs[d], lu["devise"], lu["sonde"], lot)
                 for d in sorted(valeurs)])
            ecrites += len(valeurs)
        # L'ecart entre conventions vaut d'etre vu : nul sur un capitalisant, il
        # dit sur un distribuant ce que la serie brute passe sous silence.
        communes = [(lu["ajustee"][d], lu["brute"][d]) for d in lu["brute"]
                    if d in lu["ajustee"] and lu["brute"][d]]
        ecart = max((abs(a / b - 1) * 100 for a, b in communes), default=0.0)
        statut = "obtenu" if len(lu["brute"]) >= 100 else ("vide" if not lu["brute"] else "insuffisant")
        cx.execute("INSERT INTO collecte (isin, source, symbole, tente_le, statut, points,"
                   " debut, fin, devise, detail) VALUES (?,?,?,?,?,?,?,?,?,?)",
                   (isin, lu["sonde"], None, maintenant, statut, len(lu["brute"]),
                    dates[0].isoformat() if dates else None,
                    dates[-1].isoformat() if dates else None, lu["devise"],
                    f"chargé depuis les captures, écart ajusté/brut {ecart:.2f} %"))
        print(f"{isin:14s}{len(lu['brute']):>7d}{len(lu['ajustee']):>9d}{ecart:>10.2f} %"
              f"{str(lu['devise']):>8s}  {dates[0] if dates else '—'} → {dates[-1] if dates else '—'}")

    cx.execute("UPDATE import_cotation SET retenues = ? WHERE id = ?", (ecrites, lot))
    cx.commit()
    supports = cx.execute("SELECT COUNT(DISTINCT isin) FROM valeur_liquidative").fetchone()[0]
    lignes = cx.execute("SELECT COUNT(*) FROM valeur_liquidative").fetchone()[0]
    retenue = dict(cx.execute("SELECT base, COUNT(DISTINCT isin) FROM v_serie GROUP BY 1"))
    print(f"\nBase : {os.path.relpath(COTATIONS, RACINE)} "
          f"({os.path.getsize(COTATIONS) / 1024:.0f} Ko)")
    print(f"  {lignes} valeurs sur {supports} supports  (+{ecrites} écrites ce tour)")
    print(f"  série retenue par v_serie : " +
          ", ".join(f"{n} en {b}" for b, n in sorted(retenue.items())))
    cx.close()


if __name__ == "__main__":
    main()
