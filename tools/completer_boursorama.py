"""Ajoute aux fiches BoursoVie les 57 supports absents de l'extraction initiale.

Les supports sont relus du PDF par parse_boursorama_pdf (parseur valide champ a
champ contre les 574 fiches deja en place) puis classes selon les memes regles
que l'extraction d'origine :
  - actions en direct  -> secteur de l'annexe IB SwissLife, par ISIN ;
  - OPC et avenants    -> taxonomie de l'annexe IA SwissLife, par ISIN ;
  - a defaut, et systematiquement pour les ETF -> deduction depuis le libelle.
"""
import glob
import os
import re
import sys
import unicodedata

import pymupdf
import yaml

sys.path.insert(0, os.path.dirname(__file__))
from fiches_boursorama import nom_de_fichier, rendre
from parse_boursorama_pdf import ISIN as RE_ISIN
from parse_boursorama_pdf import extraire, lignes_visuelles

RACINE = os.path.join(os.path.dirname(__file__), "..")
PDF_BOURSO = os.path.join(RACINE, "data/raw/annexe-financiere-libre.pdf")
PDF_SWISSLIFE = os.path.join(
    RACINE, "data/raw/Liste UC (Annexes IA IB IC) - Produits de Retraite et d'Epargne 06.2026 (1).pdf")
FICHES = os.path.join(RACINE, "data/raw/md/boursorama")

# Le document est ordonne par sections, chacune triee alphabetiquement : les
# ruptures d'ordre en marquent les frontieres.
SECTIONS = [(0, 384, "OPC"), (385, 509, "ETF"), (510, 619, "Actions en direct"), (620, 630, "Avenant")]

# Deduction depuis le libelle, etablie support par support pour les 26 cas non
# couverts par une correspondance d'ISIN avec SwissLife.
PAR_LIBELLE = {
    "FR0007054358": ("ETF", "Actions Zone euro"),
    "LU1829219390": ("ETF", "Secteur Finance"),
    "LU1291098827": ("ETF", "Actions Zone euro"),
    "LU1291102447": ("ETF", "Actions Japon"),
    "IE00B3VWMM18": ("ETF", "Actions Zone euro"),
    "IE00B52VJ196": ("ETF", "Actions Europe"),
    "IE000UX5WPU4": ("ETF", "Obligations d'entreprise"),
    "LU0290356954": ("ETF", "Obligations souveraines"),
    "LU0839027447": ("ETF", "Actions Japon"),
    "IE00BJZ2DD79": ("ETF", "Actions États-Unis"),
    "FR001400CJ01": ("Obligataire", "Obligations à terme fixe"),
    "LU1894682704": ("Actions", "Actions États-Unis"),
    "LU1883861137": ("Obligataire", "Obligations haut rendement"),
    "LU0171289498": ("Actions", "Actions Amérique latine"),
    "LU1861216510": ("Actions", "Secteur Technologies"),
    "FR001400RWM2": ("Actions", "Secteur Écologie & climat"),
    "FR001400XBE1": ("Mixte", "Mixtes dynamiques"),
    "LU0284394664": ("Mixte", "Mixtes flexibles"),
    "LU0284396016": ("Actions", "Actions Europe"),
    "FR0010172767": ("Obligataire", "Obligations d'entreprise"),
    "LU2985305460": ("Actions", "Actions Zone euro"),
    "LU0088927925": ("Immobilier", "Immobilier coté"),
    "LU0190161025": ("Actions", "Secteur Santé"),
    "LU0302446645": ("Actions", "Secteur Écologie & climat"),
    "FR001400KQ02": ("Autres", "Capital investissement"),
    "FR001400HHQ5": ("Obligataire", "Obligations à terme fixe"),
}


def _pliage(texte):
    """Forme repliee d'un libelle : sans accent ni casse, pour reperer les doublons."""
    sans_accent = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sans_accent).strip().lower()


def sections_du_pdf(supports):
    appartenance = {}
    for debut, fin, nom in SECTIONS:
        for i in range(debut, fin + 1):
            appartenance[supports[i]["isin"]] = nom
    return appartenance


def taxonomie_swisslife():
    """Types d'actif SwissLife par ISIN : annexe IA depuis les fiches, IB depuis le PDF."""
    annexe_ia = {}
    for chemin in glob.glob(os.path.join(RACINE, "data/raw/md/swisslife/*.md")):
        if os.path.basename(chemin).startswith("00 -"):
            continue
        entete = yaml.safe_load(re.match(r"^---\n(.*?)\n---", open(chemin, encoding="utf-8").read(), re.S).group(1))
        for fonds in entete.get("fonds") or []:
            if fonds.get("annexe") == "IA":
                annexe_ia[fonds["isin"]] = (entete["grande_classe"], entete["type_actif"])

    secteurs = {}
    doc = pymupdf.open(PDF_SWISSLIFE)
    for page in range(89, 120):                      # annexe IB : titres vifs
        for ligne in lignes_visuelles(doc[page]):
            positions = [i for i, m in enumerate(ligne) if RE_ISIN.match(m[4])]
            if not positions:
                continue
            secteur = " ".join(m[4] for m in ligne if 340 <= m[0] < 560).strip()
            if secteur:
                secteurs[ligne[positions[0]][4]] = secteur
    doc.close()
    return annexe_ia, secteurs


def charger_fiches():
    fiches = {}
    for chemin in sorted(glob.glob(os.path.join(FICHES, "*.md"))):
        if os.path.basename(chemin).startswith("00 -"):
            continue
        entete = yaml.safe_load(re.match(r"^---\n(.*?)\n---", open(chemin, encoding="utf-8").read(), re.S).group(1))
        fiches[(entete["grande_classe"], entete["type_actif"])] = entete["supports"]
    return fiches


def normaliser(support, section, classe, origine):
    sfdr = {"8": "Article 8", "9": "Article 9"}.get(support["sfdr"], "non renseignée")
    valeur = lambda v: "n.c." if v.strip() in ("", "NC") else v.strip()
    return {
        "isin": support["isin"],
        "nom": support["nom"],
        "societe": support["societe"] or "NC",
        "nature": support["nature"],
        "sfdr": sfdr,
        "avenant": "oui" if section == "Avenant" else "non",
        "origine_classification": origine,
        "perf_brute_a": valeur(support["perf_brute_a"]),
        "frais_actif_b": valeur(support["frais_actif_b"]),
        "perf_nette_c": valeur(support["perf_nette_c"]),
        "frais_contrat_d": valeur(support["frais_contrat_d"]),
        "frais_totaux_e": valeur(support["frais_totaux_e"]),
        "perf_finale": valeur(support["perf_finale"]),
        "retrocessions": valeur(support["retrocessions"]),
    }, classe


def classer(support, section, annexe_ia, secteurs, existantes):
    isin = support["isin"]
    if section == "Actions en direct":
        if isin in secteurs:
            classe, origine = ("Actions vives", secteurs[isin]), "annexe IB SwissLife (par ISIN)"
        else:
            classe, origine = ("Actions vives", "Secteur non précisé"), "non déterminé"
    elif section != "ETF" and isin in annexe_ia:
        classe, origine = annexe_ia[isin], "annexe IA SwissLife (par ISIN)"
    else:
        classe, origine = PAR_LIBELLE[isin], "déduite du libellé"
    # Une categorie SwissLife qui ne differe d'une categorie existante que par la
    # casse ou les accents est rattachee a cette derniere, pour ne pas dedoubler.
    for grande, type_actif in existantes:
        if grande == classe[0] and _pliage(type_actif) == _pliage(classe[1]):
            classe = (grande, type_actif)
            break
    return normaliser(support, section, classe, origine)


def main():
    supports_pdf = extraire(PDF_BOURSO)
    section = sections_du_pdf(supports_pdf)
    fiches = charger_fiches()
    connus = {s["isin"] for liste in fiches.values() for s in liste}
    annexe_ia, secteurs = taxonomie_swisslife()

    ajouts = []
    for support in supports_pdf:
        if support["isin"] in connus:
            continue
        enregistrement, classe = classer(support, section[support["isin"]], annexe_ia, secteurs, fiches)
        fiches.setdefault(classe, []).append(enregistrement)
        ajouts.append((classe, enregistrement))

    for (grande, type_actif), liste in fiches.items():
        chemin = os.path.join(FICHES, nom_de_fichier(grande, type_actif))
        contenu = rendre(grande, type_actif, liste)
        if not os.path.exists(chemin) or open(chemin, encoding="utf-8").read() != contenu:
            open(chemin, "w", encoding="utf-8").write(contenu)

    for (grande, type_actif), e in sorted(ajouts, key=lambda a: (a[0], a[1]["nom"])):
        print(f"  {grande:14s} | {type_actif[:42]:42s} | {e['nom'][:32]:32s} | {e['origine_classification']}")
    print(f"\n{len(ajouts)} supports ajoutés, {len(fiches)} catégories")


if __name__ == "__main__":
    main()
