"""Lecture et reecriture des fiches Markdown de l'univers BoursoVie.

Le gabarit est reproduit a l'identique de l'existant : la fidelite se verifie
en regenerant les fiches deja validees et en exigeant un diff vide.
"""
import re
import unicodedata

SOURCE = ("Bourso Vie (5101) — Annexe financière, liste des supports en gestion libre, "
          "Generali Vie / BoursoBank, 18 septembre 2026")
CONTRAT = "Bourso Vie (5101) — gestion libre"
ASSUREUR = "Generali Vie"
MILLESIME = "2026-09-18"

CHAMPS = ["isin", "nom", "societe", "nature", "sfdr", "avenant", "origine_classification",
          "perf_brute_a", "frais_actif_b", "perf_nette_c", "frais_contrat_d",
          "frais_totaux_e", "perf_finale", "retrocessions"]

AVERTISSEMENT = (
    "Frais de gestion du contrat : 0,75 %. Les frais totaux suivent la formule de l'assureur\n"
    "**E = B + (1 + C) × D**, qui fait croître les frais affichés avec la performance :\n"
    "elle n'est pas directement comparable à une somme de taux.\n"
    "La performance porte sur le dernier exercice clos.\n"
)


def slugifier(grande_classe, type_actif):
    """Les deux parties sont slugifiees separement puis jointes par un double tiret."""
    def part(texte):
        texte = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
        return re.sub(r"-+", "-", re.sub(r"[^a-zA-Z0-9]+", "-", texte)).strip("-").lower()
    return f"{part(grande_classe)}--{part(type_actif)}"


def nom_de_fichier(grande_classe, type_actif):
    """Reproduit la convention de nommage : accents retires, / et & remplaces."""
    base = unicodedata.normalize("NFKD", type_actif).encode("ascii", "ignore").decode()
    base = base.replace("/", "-").replace("&", "et")
    base = re.sub(r"\s+", " ", base).strip()
    classe = unicodedata.normalize("NFKD", grande_classe).encode("ascii", "ignore").decode()
    return f"{classe} - {base}.md"


def _fiche(s):
    # Le corps de la fiche affiche "n.c." la ou l'en-tete YAML conserve le "NC" du PDF.
    societe = "n.c." if s["societe"] == "NC" else s["societe"]
    entete = f"`{s['isin']}` · {societe} · {s['nature']} · SFDR {s['sfdr']}"
    if s["avenant"] == "oui":
        entete += " · avenant spécifique requis"
    return f"""## {s['nom']}

{entete}

### Identité

| | |
|---|---|
| Code ISIN | `{s['isin']}` |
| Société de gestion | {societe} |
| Nature juridique | {s['nature']} |
| Classification SFDR | {s['sfdr']} |
| Avenant spécifique | {s['avenant']} |
| Classification d'actif | {s['type_actif']} ({s['origine_classification']}) |

### Frais

| Poste | Taux |
|---|---|
| Frais de gestion de l'actif (B) | {s['frais_actif_b']} |
| Frais de gestion du contrat (D) | {s['frais_contrat_d']} |
| **Frais totaux (E = B + (1 + C) × D)** | **{s['frais_totaux_e']}** |
| Taux de rétrocession de commissionnement | {s['retrocessions']} |

### Performances du dernier exercice clos

| Niveau | Taux |
|---|---|
| Brute de l'actif (A) | {s['perf_brute_a']} |
| Nette de l'unité de compte (C = A − B) | {s['perf_nette_c']} |
| **Finale (A − E)** | **{s['perf_finale']}** |
"""


def rendre(grande_classe, type_actif, supports):
    """Genere le contenu complet d'une fiche de categorie."""
    supports = sorted(supports, key=lambda s: s["nom"])
    lignes = ["---",
              f'grande_classe: "{grande_classe}"',
              f'type_actif: "{type_actif}"',
              f"slug: {slugifier(grande_classe, type_actif)}",
              f'contrat: "{CONTRAT}"',
              f'assureur: "{ASSUREUR}"',
              f'millesime: "{MILLESIME}"',
              f"nombre_de_supports: {len(supports)}",
              f'source: "{SOURCE}"',
              "supports:"]
    for s in supports:
        for i, cle in enumerate(CHAMPS):
            tiret = "  - " if i == 0 else "    "
            lignes.append(f'{tiret}{cle}: "{s[cle]}"')
    lignes += ["---", "", f"# {grande_classe} — {type_actif}", "",
               f"{len(supports)} support(s) · {SOURCE}.", "", AVERTISSEMENT,
               "## Tableau de synthèse", "",
               "| ISIN | Support | Société | Frais totaux | Perf. finale | Rétrocessions | SFDR |",
               "|---|---|---|---|---|---|---|"]
    for s in supports:
        societe = "n.c." if s["societe"] == "NC" else s["societe"]
        lignes.append(f"| `{s['isin']}` | {s['nom']} | {societe} | {s['frais_totaux_e']} "
                      f"| {s['perf_finale']} | {s['retrocessions']} | {s['sfdr']} |")
    # Chaque fiche se termine par un saut de ligne : le trait de separation qui suit
    # n'a donc pas besoin d'etre precede d'une ligne vide, contrairement au premier,
    # qui vient juste apres la derniere ligne du tableau de synthese.
    for rang, s in enumerate(supports):
        lignes += ["", "---"] if rang == 0 else ["---", ""]
        lignes.append(_fiche(dict(s, type_actif=type_actif)))
    return "\n".join(lignes)
