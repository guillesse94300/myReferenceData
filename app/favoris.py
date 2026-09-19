"""Liste des supports suivis.

Les favoris sont une donnee de l'utilisateur, pas une donnee derivee : ils sont
donc conserves hors de la base, que construire.bat efface et reconstruit a
chaque execution. Le fichier est un CSV lisible et modifiable dans un tableur,
et suivi par Git pour servir de sauvegarde.

La colonne `note` est libre : elle sert aujourd'hui a porter l'enveloppe dans
laquelle le support est detenu.
"""
import csv
import datetime
import os

FICHIER = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data", "favoris.csv"))
COLONNES = ["isin", "ajoute_le", "note"]


def charger():
    """Supports suivis : {isin: {"ajoute_le": ..., "note": ...}}."""
    if not os.path.exists(FICHIER):
        return {}
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
