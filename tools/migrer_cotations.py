"""Migre cotations.db vers le schema qui porte la convention de cotation.

reference.db se reconstruit et ignore la question des migrations. cotations.db
s'accumule -- c'est sa raison d'etre -- et ne peut donc pas etre refaite : il
faut deplacer les lignes existantes.

La migration ajoute `base` a la cle primaire. Les valeurs deja en place sont
toutes brutes, sans ambiguite : le collecteur lit `indicators.quote[0].close`
et n'a jamais lu `adjclose`. C'est un UPDATE, pas une heuristique.

Sans effet si la base est deja au nouveau schema.

    python tools/migrer_cotations.py
"""
import datetime
import os
import shutil
import sqlite3
import sys

RACINE = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
COTATIONS = os.path.join(RACINE, "data/cotations.db")
SCHEMA = os.path.join(RACINE, "db/schema_cotations.sql")


def colonnes(cx, table):
    return [ligne[1] for ligne in cx.execute(f"PRAGMA table_info({table})")]


def main():
    if not os.path.exists(COTATIONS):
        print("Aucune base de cotations : rien a migrer, le schema sera cree au chargement.")
        return 0
    cx = sqlite3.connect(COTATIONS)
    if "base" in colonnes(cx, "valeur_liquidative"):
        print("Base deja au nouveau schema : rien a faire.")
        cx.close()
        return 0

    avant = cx.execute("SELECT COUNT(*) FROM valeur_liquidative").fetchone()[0]
    supports = cx.execute("SELECT COUNT(DISTINCT isin) FROM valeur_liquidative").fetchone()[0]
    cx.close()

    # Une copie horodatee avant de toucher a des donnees qui ne se regenerent pas.
    sauvegarde = f"{COTATIONS}.avant-migration-{datetime.date.today().isoformat()}"
    shutil.copy2(COTATIONS, sauvegarde)
    print(f"Sauvegarde : {os.path.relpath(sauvegarde, RACINE)}")

    cx = sqlite3.connect(COTATIONS)
    cx.execute("ALTER TABLE valeur_liquidative RENAME TO valeur_liquidative_ancienne")
    cx.executescript(open(SCHEMA, encoding="utf-8").read())

    lot = cx.execute(
        "INSERT INTO import_cotation (fichier, empreinte, extrait_le, importe_le,"
        " lignes_lues, retenues, rejetees) VALUES (?,?,?,?,?,?,?)",
        ("(collectes anterieures a la migration)", "—", None,
         datetime.datetime.now().isoformat(timespec="seconds"), avant, avant, 0)).lastrowid

    cx.execute(
        "INSERT INTO valeur_liquidative (isin, date, base, valeur, devise, moment, source,"
        " import_id) SELECT isin, date, 'brute', valeur, devise, 'cloture', source, ?"
        " FROM valeur_liquidative_ancienne", (lot,))
    apres = cx.execute("SELECT COUNT(*) FROM valeur_liquidative").fetchone()[0]
    if apres != avant:
        cx.rollback()
        cx.close()
        print(f"ECHEC : {avant} lignes avant, {apres} apres. Rien n'a ete ecrit, "
              f"la base d'origine est intacte.", file=sys.stderr)
        return 1
    cx.execute("DROP TABLE valeur_liquidative_ancienne")
    cx.commit()
    cx.execute("VACUUM")
    print(f"{apres} valeurs sur {supports} supports migrees, toutes marquees « brute ».")
    cx.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
