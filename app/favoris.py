"""Liste des supports suivis.

Les favoris sont une donnee de l'utilisateur, pas une donnee derivee : ils sont
donc conserves hors de la base, que construire.bat efface et reconstruit a
chaque execution. Le fichier est un CSV a deux colonnes, lisible et modifiable
dans un tableur, et suivi par Git pour servir de sauvegarde.
"""
import csv
import datetime
import os

FICHIER = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data", "favoris.csv"))
COLONNES = ["isin", "ajoute_le"]


def charger():
    """ISIN suivis, associes a leur date d'ajout."""
    if not os.path.exists(FICHIER):
        return {}
    with open(FICHIER, newline="", encoding="utf-8") as fichier:
        return {ligne["isin"]: ligne.get("ajoute_le", "") for ligne in csv.DictReader(fichier)
                if ligne.get("isin")}


def enregistrer(suivis):
    os.makedirs(os.path.dirname(FICHIER), exist_ok=True)
    with open(FICHIER, "w", newline="", encoding="utf-8") as fichier:
        redacteur = csv.DictWriter(fichier, fieldnames=COLONNES)
        redacteur.writeheader()
        for isin in sorted(suivis):
            redacteur.writerow({"isin": isin, "ajoute_le": suivis[isin]})


def basculer(isin, suivre):
    """Ajoute ou retire un support, et renvoie la liste mise a jour."""
    suivis = charger()
    if suivre:
        suivis.setdefault(isin, datetime.date.today().isoformat())
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
            suivis[isin] = aujourdhui
            modifie = True
        elif isin not in voulus and isin in suivis:
            del suivis[isin]
            modifie = True
    if modifie:
        enregistrer(suivis)
    return suivis, modifie
