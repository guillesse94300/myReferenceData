"""Liste des supports suivis.

Les favoris sont une donnee de l'utilisateur, pas une donnee derivee : ils sont
donc conserves hors de la base, que construire.bat efface et reconstruit a
chaque execution. Le fichier est un CSV lisible et modifiable dans un tableur.

Il n'est **pas** suivi par Git : l'application l'ecrit a chaque coche, et un
fichier que le programme modifie entre en conflit a chaque `git pull`. La
semence versionnee est `data/raw/favorites.txt`, tenue a la main ; le CSV en
est amorce la premiere fois, puis vit sa vie en local.

La colonne `note` est libre : elle sert aujourd'hui a porter l'enveloppe dans
laquelle le support est detenu.
"""
import csv
import datetime
import os
import re

FICHIER = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data", "favoris.csv"))
SEMENCE = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data", "raw", "favorites.txt"))
COLONNES = ["isin", "ajoute_le", "note"]
RE_ISIN = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")


def amorcer():
    """Lit la semence versionnee : {isin: {"ajoute_le": ..., "note": ...}}.

    Les lignes sans ISIN exploitable sont ignorees ici -- elles sont signalees
    par ailleurs, dans les anomalies de la base.
    """
    if not os.path.exists(SEMENCE):
        return {}
    aujourdhui = datetime.date.today().isoformat()
    depart = {}
    with open(SEMENCE, newline="", encoding="utf-8") as fichier:
        for ligne in csv.DictReader(fichier, delimiter="\t"):
            code = (ligne.get("ISIN") or "").strip()
            if RE_ISIN.match(code):
                depart[code] = {"ajoute_le": aujourdhui,
                                "note": (ligne.get("Détenu dans") or "").strip()}
    return depart


def charger():
    """Supports suivis : {isin: {"ajoute_le": ..., "note": ...}}.

    A la premiere execution le CSV n'existe pas : il est amorce depuis la
    semence, puis ecrit, pour que l'utilisateur parte de sa liste plutot que
    d'une page blanche. Une liste videe a la main laisse un fichier a en-tete
    seul, qui existe : elle n'est donc pas ressuscitee.
    """
    if not os.path.exists(FICHIER):
        depart = amorcer()
        if depart:
            enregistrer(depart)
        return depart
    with open(FICHIER, newline="", encoding="utf-8") as fichier:
        return {ligne["isin"]: {"ajoute_le": ligne.get("ajoute_le", ""),
                                "note": ligne.get("note", "") or ""}
                for ligne in csv.DictReader(fichier) if ligne.get("isin")}


def enregistrer(suivis):
    os.makedirs(os.path.dirname(FICHIER), exist_ok=True)
    with open(FICHIER, "w", newline="", encoding="utf-8") as fichier:
        redacteur = csv.DictWriter(fichier, fieldnames=COLONNES)
        redacteur.writeheader()
        for isin in sorted(suivis):
            redacteur.writerow({"isin": isin, **suivis[isin]})


def basculer(isin, suivre):
    """Ajoute ou retire un support, et renvoie la liste mise a jour."""
    suivis = charger()
    if suivre:
        suivis.setdefault(isin, {"ajoute_le": datetime.date.today().isoformat(), "note": ""})
    else:
        suivis.pop(isin, None)
    enregistrer(suivis)
    return suivis


def appliquer(isins, voulus):
    """Aligne le suivi sur une selection : `voulus` est l'ensemble coche parmi `isins`.

    Seuls les supports presents dans `isins` sont touches, pour qu'une edition
    portant sur un ecran filtre ne supprime pas le reste de la liste.
    """
    suivis = charger()
    aujourdhui = datetime.date.today().isoformat()
    modifie = False
    for isin in isins:
        if isin in voulus and isin not in suivis:
            suivis[isin] = {"ajoute_le": aujourdhui, "note": ""}
            modifie = True
        elif isin not in voulus and isin in suivis:
            del suivis[isin]
            modifie = True
    if modifie:
        enregistrer(suivis)
    return suivis, modifie
