"""Interroge les sources candidates de valeur liquidative et enregistre leurs reponses.

Ce script ne comprend rien a ce qu'il recoit : il sonde, mesure et archive. Les
reponses brutes servent ensuite a ecrire les parseurs et a les tester hors
ligne, sans dependre du reseau ni du format du jour.

A lancer depuis un poste ayant acces a internet :

    .venv\\Scripts\\python tools\\capturer_sources.py

Les reponses vont dans data/raw/captures/, accompagnees d'un journal JSON.
Relire le tableau affiche en fin d'execution : il dit quelle source a repondu
pour quel support, et c'est cela qui decidera de l'ordre de la cascade.
"""
import argparse
import csv
import datetime
import hashlib
import json
import os
import re
import sqlite3
import time
import urllib.error
import urllib.request

RACINE = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(RACINE, "data/reference.db")
FAVORIS = os.path.join(RACINE, "data/favoris.csv")
CAPTURES = os.path.join(RACINE, "data/raw/captures")

# Un navigateur courant : plusieurs sites refusent une requete sans en-tete.
ENTETES = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}
DELAI = 2.0          # secondes entre deux requetes, par politesse et pour ne pas se faire bloquer
DELAI_EXPIRATION = 25

# Sondes a tenter pour chaque support. L'URL exacte de chaque source est une
# hypothese : c'est precisement ce que la capture doit confirmer ou infirmer.
SONDES = [
    ("yahoo_recherche", "https://query1.finance.yahoo.com/v1/finance/search?q={isin}&quotesCount=5", "json"),
    ("boursorama_recherche", "https://www.boursorama.com/recherche/?query={isin}", "html"),
    ("quantalys_recherche", "https://www.quantalys.com/Recherche/Rechercher?txtRecherche={isin}", "html"),
    ("amf_geco", "https://geco.amf-france.org/Bio/rech_opcvm.aspx?varvalidform=on&CodeISIN={isin}", "html"),
]


def supports(limite):
    """Les supports suivis, enrichis de leur nom et de leur nature."""
    suivis = [ligne["isin"] for ligne in csv.DictReader(open(FAVORIS, encoding="utf-8"))
              if ligne.get("isin")]
    if not suivis:
        raise SystemExit("Aucun favori dans data/favoris.csv : rien à capturer.")
    cx = sqlite3.connect(BASE)
    marques = ",".join("?" * len(suivis))
    lignes = cx.execute(f"SELECT isin, nom, type_instrument FROM instrument WHERE isin IN ({marques})",
                        suivis).fetchall()
    cx.close()
    return lignes[:limite] if limite else lignes


def interroger(url):
    """Renvoie (statut, type de contenu, corps) sans jamais lever d'exception."""
    debut = time.time()
    requete = urllib.request.Request(url, headers=ENTETES)
    try:
        with urllib.request.urlopen(requete, timeout=DELAI_EXPIRATION) as reponse:
            return reponse.status, reponse.headers.get("Content-Type", ""), reponse.read(), time.time() - debut
    except urllib.error.HTTPError as erreur:
        return erreur.code, erreur.headers.get("Content-Type", "") if erreur.headers else "", \
               erreur.read()[:20000], time.time() - debut
    except Exception as erreur:                        # réseau, DNS, TLS, expiration
        return 0, type(erreur).__name__, str(erreur).encode(), time.time() - debut


def verdict(statut, corps):
    """Lecture rapide : la réponse contient-elle vraisemblablement quelque chose ?"""
    if statut == 0:
        return "injoignable"
    if statut >= 400:
        return f"refus {statut}"
    if len(corps) < 500:
        return "réponse vide"
    return "à examiner"


def main():
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--limite", type=int, default=0, help="ne sonder que les N premiers supports")
    analyseur.add_argument("--source", help="ne tenter qu'une source, par son nom")
    options = analyseur.parse_args()

    os.makedirs(CAPTURES, exist_ok=True)
    sondes = [s for s in SONDES if not options.source or s[0] == options.source]
    liste = supports(options.limite)
    print(f"{len(liste)} support(s) × {len(sondes)} source(s) = "
          f"{len(liste) * len(sondes)} requêtes, environ "
          f"{len(liste) * len(sondes) * DELAI / 60:.0f} min\n")

    journal = []
    for isin, nom, nature in liste:
        print(f"{isin}  {nom[:38]:38s} [{nature}]")
        for source, gabarit, extension in sondes:
            url = gabarit.format(isin=isin)
            statut, type_contenu, corps, duree = interroger(url)
            fichier = f"{isin}__{source}.{extension}"
            if statut and statut < 400 and corps:
                with open(os.path.join(CAPTURES, fichier), "wb") as sortie:
                    sortie.write(corps)
            journal.append({
                "isin": isin, "nom": nom, "nature": nature, "source": source, "url": url,
                "statut": statut, "type_contenu": type_contenu, "octets": len(corps),
                "secondes": round(duree, 2), "verdict": verdict(statut, corps),
                "empreinte": hashlib.sha256(corps).hexdigest()[:16],
                "fichier": fichier if statut and statut < 400 and corps else None,
            })
            print(f"    {source:22s} {journal[-1]['verdict']:14s} {len(corps):>8d} o  {duree:4.1f}s")
            time.sleep(DELAI)

    chemin = os.path.join(CAPTURES, "journal.json")
    with open(chemin, "w", encoding="utf-8") as sortie:
        json.dump({"capture_le": datetime.datetime.now().isoformat(timespec="seconds"),
                   "requetes": journal}, sortie, ensure_ascii=False, indent=2)

    print("\n" + "=" * 62)
    print(f"{'source':24s} {'répondu':>8s} {'refusé':>8s} {'injoignable':>12s}")
    for source, _, _ in sondes:
        lignes = [l for l in journal if l["source"] == source]
        print(f"{source:24s} {sum(1 for l in lignes if l['verdict'] == 'à examiner'):>8d}"
              f" {sum(1 for l in lignes if l['verdict'].startswith('refus')):>8d}"
              f" {sum(1 for l in lignes if l['verdict'] == 'injoignable'):>12d}")
    print(f"\nCaptures dans {os.path.relpath(CAPTURES, RACINE)}, journal dans journal.json.")
    print("Committez ce dossier : les parseurs seront écrits et testés contre lui.")


if __name__ == "__main__":
    main()
