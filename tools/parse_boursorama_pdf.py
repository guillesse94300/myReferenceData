"""Extraction des supports de l'annexe financiere Bourso Vie (gestion libre).

Chaque support occupe deux lignes visuelles dans le PDF :
  1. la ligne de titre  : NOM ... ISIN - Societe de gestion : SG
  2. la ligne de donnees: nature juridique puis huit colonnes chiffrees.

Les colonnes chiffrees sont CENTREES, pas alignees a gauche : une valeur a
trois chiffres deborde donc vers la colonne precedente. L'affectation se fait
en consequence sur le centre de chaque mot, ce qui rattache aussi au bon
champ le "1" d'un millier separe par une espace ("1 681,06%").
"""
import re
import sys

import pymupdf

ISIN = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")

# Centre d'abscisse de chaque colonne de la ligne de donnees, releve sur le PDF.
CENTRES = [
    ("nature", 70),
    ("perf_brute_a", 142),
    ("frais_actif_b", 198),
    ("perf_nette_c", 255),
    ("frais_contrat_d", 309),
    ("frais_totaux_e", 363),
    ("perf_finale", 419),
    ("retrocessions", 476),
    ("sfdr", 535),
]
# Frontieres a mi-chemin entre deux centres consecutifs.
FRONTIERES = [(CENTRES[i][1] + CENTRES[i + 1][1]) / 2 for i in range(len(CENTRES) - 1)]


def lignes_visuelles(page, tolerance=2.5):
    """Regroupe les mots de la page en lignes, chacune triee de gauche a droite.

    Le tri interne se fait sur l'abscisse seule : deux spans d'une meme ligne
    peuvent differer de quelques millisimes en ordonnee, ce qui suffirait a
    desordonner les mots si l'ordonnee entrait dans la cle de tri.
    """
    mots = sorted(page.get_text("words"), key=lambda w: (w[1], w[0]))
    lignes, courante, y = [], [], None
    for mot in mots:
        if y is not None and abs(mot[1] - y) >= tolerance:
            lignes.append(sorted(courante, key=lambda w: w[0]))
            courante = []
        courante.append(mot)
        y = mot[1]
    if courante:
        lignes.append(sorted(courante, key=lambda w: w[0]))
    return lignes


def ligne_de_titre(ligne):
    """Renvoie (isin, nom, societe) si la ligne introduit un support."""
    positions = [i for i, m in enumerate(ligne) if ISIN.match(m[4])]
    if not positions:
        return None
    texte = " ".join(m[4] for m in ligne)
    if "Société de gestion" not in texte:
        return None
    pos = positions[0]
    nom = " ".join(m[4] for m in ligne[:pos]).strip()
    societe = texte.split("Société de gestion :", 1)[1].strip()
    return ligne[pos][4], nom, societe


def valeurs(ligne):
    """Affecte chaque mot d'une ligne de donnees a la colonne dont il est le plus proche."""
    seaux = {nom: [] for nom, _ in CENTRES}
    for mot in ligne:
        centre = (mot[0] + mot[2]) / 2
        index = sum(1 for f in FRONTIERES if centre >= f)
        seaux[CENTRES[index][0]].append(mot[4])
    return {cle: " ".join(v).strip() for cle, v in seaux.items()}


def extraire(chemin):
    doc = pymupdf.open(chemin)
    supports, attente = [], None
    for page in doc:
        for ligne in lignes_visuelles(page):
            titre = ligne_de_titre(ligne)
            if titre:
                attente = titre
                continue
            if attente is None:
                continue
            champs = valeurs(ligne)
            # Une ligne de donnees porte toujours une nature juridique en tete.
            if not champs["nature"]:
                continue
            isin, nom, societe = attente
            supports.append({"isin": isin, "nom": nom, "societe": societe, **champs})
            attente = None
    doc.close()
    return supports


if __name__ == "__main__":
    for s in extraire(sys.argv[1]):
        print(s)
