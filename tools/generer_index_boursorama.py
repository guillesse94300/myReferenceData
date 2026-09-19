"""Regenere l'index et la comparaison SwissLife de l'univers BoursoVie.

Les deux fichiers sont derives des fiches de categorie : ils doivent etre
reconstruits des que l'univers change, sous peine d'annoncer des comptages faux.
"""
import collections
import glob
import os
import re

import yaml

RACINE = os.path.join(os.path.dirname(__file__), "..")
FICHES = os.path.join(RACINE, "data/raw/md/boursorama")
SOURCE = ("Bourso Vie (5101) — Annexe financière, liste des supports en gestion libre, "
          "Generali Vie / BoursoBank, 18 septembre 2026")
ORDRE = ["Monetaire", "Obligataire", "Mixte", "Actions", "Immobilier",
         "Alternatif", "Autres", "ETF", "Actions vives"]


def charger(repertoire, cle):
    """Fiches du repertoire portant la cle demandee.

    Le repertoire SwissLife melange deux natures de fiches : les unites de
    compte (cle "fonds") et les titres vifs de l'annexe IB (cle "titres").
    """
    fiches = []
    for chemin in sorted(glob.glob(os.path.join(repertoire, "*.md"))):
        if os.path.basename(chemin).startswith("00 -"):
            continue
        entete = yaml.safe_load(re.match(r"^---\n(.*?)\n---", open(chemin, encoding="utf-8").read(), re.S).group(1))
        if cle in entete:
            fiches.append((entete, os.path.basename(chemin)))
    return fiches


def taux(valeur):
    """Convertit '2,75%' en 2.75 ; renvoie None si la valeur n'est pas chiffree."""
    brut = str(valeur).strip().replace("%", "").replace(",", ".").replace(" ", "").replace(" ", "")
    try:
        return float(brut)
    except ValueError:
        return None


def ecrire_index(fiches):
    supports = [s for e, _ in fiches for s in e["supports"]]
    origines = collections.Counter(s["origine_classification"] for s in supports)
    avenants = sum(1 for s in supports if s["avenant"] == "oui")
    par_classe = collections.Counter(e["grande_classe"] for e, _ in fiches for _ in e["supports"])
    etf = par_classe["ETF"]
    vives = par_classe["Actions vives"]

    lignes = [
        "# Index — Univers BoursoVie (gestion libre)",
        "",
        f"Source : {SOURCE} (25 pages).",
        "",
        f"- **{len(supports)} supports** répartis en {len(fiches)} types d'actifs",
        f"- {len(supports) - etf - vives - avenants} OPC actifs, {etf} ETF, {vives} actions en direct, "
        f"{avenants} supports sous avenant spécifique",
        "",
        "**Le document source ne comporte aucune classification par type d'actif.**",
        "Celle-ci a donc été reconstituée de deux façons, tracées support par support",
        "dans le champ `origine_classification` :",
        "",
    ]
    for libelle in ["déduite du libellé", "annexe IA SwissLife (par ISIN)",
                    "annexe IB SwissLife (par ISIN)", "non déterminé"]:
        lignes.append(f"- {libelle} : {origines[libelle]} supports")
    lignes += [
        "",
        "La déduction par libellé a été calibrée puis mesurée sur les 134 fonds communs",
        "du périmètre initial : **88 % d'exactitude** au niveau de la grande classe.",
        "Elle n'a donc pas la fiabilité de la taxonomie SwissLife.",
        "",
        "Voir aussi [00 - COMPARAISON SwissLife.md](<00 - COMPARAISON SwissLife.md>).",
        "",
        "| Grande classe | Type d'actif | Supports | Origine dominante | Fichier |",
        "|---|---|---|---|---|",
    ]
    for entete, fichier in sorted(fiches, key=lambda f: (ORDRE.index(f[0]["grande_classe"]), f[0]["type_actif"])):
        dominante = collections.Counter(s["origine_classification"] for s in entete["supports"]).most_common(1)[0][0]
        lignes.append(f"| {entete['grande_classe']} | {entete['type_actif']} | {len(entete['supports'])} "
                      f"| {dominante} | [{fichier}](<{fichier}>) |")
    open(os.path.join(FICHES, "00 - INDEX.md"), "w", encoding="utf-8").write("\n".join(lignes) + "\n")
    return len(supports)


def ecrire_comparaison(fiches):
    bourso = {s["isin"]: s for e, _ in fiches for s in e["supports"]}
    swisslife = {f["isin"]: f for e, _ in charger(os.path.join(RACINE, "data/raw/md/swisslife"), "fonds")
                 for f in e["fonds"]}
    communs = sorted(set(bourso) & set(swisslife))
    comparables = []
    for isin in communs:
        a, b = taux(bourso[isin]["frais_totaux_e"]), taux(swisslife[isin]["frais_totaux"])
        if a is not None and b is not None:
            comparables.append((a - b, isin, a, b))
    comparables.sort()

    lignes = [
        "# Le même fonds chez les deux assureurs",
        "",
        f"{len(communs)} unités de compte sont référencées à la fois chez BoursoVie (Generali, septembre 2026) "
        f"et chez SwissLife (juin 2026).",
        f"{len(comparables)} d'entre elles affichent des frais totaux chiffrés des deux côtés et figurent ci-dessous.",
        "",
        "Attention : les deux assureurs ne calculent pas les frais totaux de la même façon.",
        "SwissLife additionne les taux (B + C). Generali applique **B + (1 + perf nette) × D**,",
        "ce qui gonfle mécaniquement le chiffre quand le fonds performe. L'écart ci-dessous",
        "mélange donc un vrai écart tarifaire (contrat à 0,75 % contre 0,96 %) et un effet de formule.",
        "",
        "| ISIN | Fonds (libellé BoursoVie) | Frais BoursoVie | Frais SwissLife | Écart |",
        "|---|---|---|---|---|",
    ]
    fr = lambda x: f"{x:.2f}".replace(".", ",")
    for ecart, isin, a, b in comparables:
        lignes.append(f"| `{isin}` | {bourso[isin]['nom']} | {fr(a)} % | {fr(b)} % "
                      f"| {'+' if ecart >= 0 else '-'}{fr(abs(ecart))} pt |")
    open(os.path.join(FICHES, "00 - COMPARAISON SwissLife.md"), "w", encoding="utf-8").write("\n".join(lignes) + "\n")
    return len(communs), len(comparables)


if __name__ == "__main__":
    fiches = charger(FICHES, "supports")
    total = ecrire_index(fiches)
    communs, comparables = ecrire_comparaison(fiches)
    print(f"index : {total} supports, {len(fiches)} catégories")
    print(f"comparaison : {communs} fonds communs, {comparables} comparables")
