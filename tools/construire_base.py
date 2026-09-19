"""Construit la base locale de l'univers d'investissement a partir des fiches.

Les fiches Markdown sont la source d'entree, les PDF la reference de controle :
le chargement echoue si l'effectif charge ne correspond pas a l'inventaire des
ISIN du document d'origine. La base est reconstruite entierement a chaque
execution, ce qui la rend reproductible et rend inutile toute migration.

Usage : python tools/construire_base.py [--base data/reference.db]
"""
import csv
import argparse
import collections
import datetime
import glob
import hashlib
import os
import re
import sqlite3
import sys
import unicodedata

import yaml

sys.path.insert(0, os.path.dirname(__file__))
from parse_boursorama_pdf import ISIN as RE_ISIN

RACINE = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
FICHES = os.path.join(RACINE, "data/raw/md")
DETENUS = os.path.join(RACINE, "data/raw/favorites.txt")
SCHEMA = os.path.join(RACINE, "db/schema.sql")

PDF = {
    "SwissLife": os.path.join(
        RACINE, "data/raw/Liste UC (Annexes IA IB IC) - Produits de Retraite et d'Epargne 06.2026 (1).pdf"),
    "BoursoVie": os.path.join(RACINE, "data/raw/annexe-financiere-libre.pdf"),
}
# Pages de chaque PDF portant les instruments du perimetre retenu (OPC et ETF
# pour SwissLife, l'integralite du document pour BoursoVie).
PAGES_PERIMETRE = {"SwissLife": [(0, 47), (84, 89)], "BoursoVie": [(0, 25)]}
EFFECTIF_ATTENDU = {"SwissLife": 902, "BoursoVie": 631}

CONTRAT = {"SwissLife": "Produits de retraite et d'épargne",
           "BoursoVie": "Bourso Vie (5101) — gestion libre"}

# Marqueurs d'absence de valeur rencontres dans les deux sources.
ABSENCE = re.compile(r"^(|ND%?|n\.c\.|NC|-|Création \d{4})$")

# Le decoupage en colonnes du PDF SwissLife brouille les formes juridiques
# ecrites sur plusieurs lignes ; le suffixe (2) est un appel de note.
FORME = {
    "d'investissement Compagnie de fonds ouverts": "Compagnie d'investissement de fonds ouverts",
    "d'investissement de fonds ouverts": "Compagnie d'investissement de fonds ouverts",
}


def nombre(valeur):
    """Convertit '2,89%' ou '1 681,06%' en reel ; None si la valeur est absente."""
    texte = str(valeur or "").strip().replace(" ", " ")
    if ABSENCE.match(texte):
        return None
    texte = texte.replace("%", "").replace(" ", "").replace(",", ".")
    try:
        return float(texte)
    except ValueError:
        return None


def forme_juridique(valeur):
    texte = FORME.get(valeur, valeur or "")
    return re.sub(r"\s*\(\d\)\s*$", "", texte).strip() or None


def lire_fiches(fournisseur, cle):
    """Enregistrements des fiches d'un fournisseur, enrichis de leur categorie."""
    dossier = "swisslife" if fournisseur == "SwissLife" else "boursorama"
    lignes = []
    for chemin in sorted(glob.glob(os.path.join(FICHES, dossier, "*.md"))):
        if os.path.basename(chemin).startswith("00 -"):
            continue
        entete = yaml.safe_load(
            re.match(r"^---\n(.*?)\n---", open(chemin, encoding="utf-8").read(), re.S).group(1))
        if cle not in entete:
            continue
        for enregistrement in entete[cle]:
            lignes.append(dict(enregistrement,
                               grande_classe=entete["grande_classe"],
                               type_actif=entete["type_actif"],
                               millesime=entete["millesime"]))
    return lignes


def isins_du_pdf(fournisseur):
    """Inventaire des ISIN du document source, sur le perimetre retenu."""
    import pymupdf
    doc = pymupdf.open(PDF[fournisseur])
    trouves = set()
    for debut, fin in PAGES_PERIMETRE[fournisseur]:
        for page in range(debut, min(fin, doc.page_count)):
            trouves |= {m for m in re.findall(r"\b[A-Z]{2}[A-Z0-9]{9}[0-9]\b", doc[page].get_text())}
    doc.close()
    return trouves


def empreinte(chemin):
    with open(chemin, "rb") as fichier:
        return hashlib.sha256(fichier.read()).hexdigest()


def supports_detenus():
    """Supports de la liste de detention qui ne sont offerts par aucun assureur.

    Un instrument n'a pas besoin d'etre offert pour exister : les fonds de PEE,
    l'ETF loge en PEA ou la part de SCPI sont detenus, donc suivis, sans etre
    achetables dans l'un des deux contrats. Ils entrent au referentiel sans
    offre rattachee.
    """
    if not os.path.exists(DETENUS):
        return []
    retenus, sans_isin = [], []
    with open(DETENUS, encoding="utf-8", newline="") as fichier:
        for ligne in csv.DictReader(fichier, delimiter="\t"):
            code = (ligne.get("ISIN") or "").strip()
            libelle = (ligne.get("Fonds") or "").strip()
            if not RE_ISIN.match(code):
                sans_isin.append(libelle)
            else:
                retenus.append({"isin": code, "nom": libelle,
                                "enveloppe": (ligne.get("Détenu dans") or "").strip()})
    return retenus, sans_isin


def type_instrument(fournisseur, ligne):
    if ligne["grande_classe"] == "Actions vives":
        return "action"
    if ligne["grande_classe"] == "ETF" or (fournisseur == "SwissLife" and ligne.get("annexe") == "IB"):
        return "etf"
    return "opc"


def construire(base):
    maintenant = datetime.datetime.now().isoformat(timespec="seconds")
    if os.path.exists(base):
        os.remove(base)
    os.makedirs(os.path.dirname(base), exist_ok=True)
    cx = sqlite3.connect(base)
    cx.executescript(open(SCHEMA, encoding="utf-8").read())

    # Referentiel des titres vifs SwissLife : sert a renseigner le pays et la
    # notation des actions en direct offertes par BoursoVie.
    titres = {t["isin"]: t for t in lire_fiches("SwissLife", "titres")}

    instruments, offres, performances, anomalies = {}, [], [], []
    for fournisseur, cle in (("SwissLife", "fonds"), ("BoursoVie", "supports")):
        lignes = lire_fiches(fournisseur, cle)
        import_id = cx.execute(
            "INSERT INTO import (fournisseur, document, empreinte, millesime, importe_le, lignes)"
            " VALUES (?,?,?,?,?,?)",
            (fournisseur, os.path.basename(PDF[fournisseur]), empreinte(PDF[fournisseur]),
             lignes[0]["millesime"], maintenant, len(lignes))).lastrowid

        for ligne in lignes:
            isin, nature = ligne["isin"], type_instrument(fournisseur, ligne)
            reference = titres.get(isin, {})
            candidat = {
                "nom": ligne["nom"],
                "societe_gestion": None if str(ligne.get("societe", "")).strip() in ("", "NC") else ligne["societe"],
                "type_instrument": nature,
                "forme_juridique": forme_juridique(ligne.get("forme") or ligne.get("nature")),
                "devise": ligne.get("devise") or reference.get("devise"),
                "pays": reference.get("pays"),
                "notation": reference.get("notation") or None,
            }
            if isin in instruments:
                # SwissLife est charge en premier : son referentiel fait foi, mais
                # une divergence de societe de gestion est signalee.
                connu = instruments[isin]
                if _societes_distinctes(connu["societe_gestion"], candidat["societe_gestion"]):
                    anomalies.append(("identité divergente entre fournisseurs", "avertissement", isin,
                                      f"société de gestion : SwissLife {connu['societe_gestion']!r} "
                                      f"contre BoursoVie {candidat['societe_gestion']!r}"))
                for champ in ("devise", "pays", "notation", "societe_gestion"):
                    connu[champ] = connu[champ] or candidat[champ]
            else:
                instruments[isin] = candidat

            frais_fonds = nombre(ligne.get("frais_uc_b") or ligne.get("frais_actif_b"))
            frais_contrat = nombre(ligne.get("frais_contrat_c") or ligne.get("frais_contrat_d"))
            comparables = None if frais_fonds is None or frais_contrat is None else round(frais_fonds + frais_contrat, 4)
            offres.append(
                (import_id, isin, fournisseur, CONTRAT[fournisseur], ligne["grande_classe"],
                 ligne["type_actif"], ligne.get("origine_classification") or "taxonomie SwissLife",
                 ligne["sfdr"], int(ligne["sri"]) if str(ligne.get("sri", "")).isdigit() else None,
                 ligne.get("label") or None, ligne.get("statut"), 1 if ligne.get("avenant") == "oui" else 0,
                 frais_fonds, frais_contrat,
                 nombre(ligne.get("frais_totaux") or ligne.get("frais_totaux_e")), comparables,
                 nombre(ligne.get("retrocessions")),
                 nombre(ligne.get("perf_brute_2025") or ligne.get("perf_brute_a")),
                 nombre(ligne.get("perf_nette_2025") or ligne.get("perf_nette_c")),
                 nombre(ligne.get("perf_finale_2025") or ligne.get("perf_finale")),
                 nombre(ligne.get("perf_finale_5a"))))

            for annee in range(2021, 2026):
                valeur = nombre(ligne.get(f"p{annee}"))
                if valeur is not None:
                    performances.append((isin, fournisseur, annee, valeur))

    # Supports detenus hors des deux contrats : ils rejoignent le referentiel
    # sans offre, pour que la liste de suivi soit complete.
    detenus, sans_isin = supports_detenus()
    hors_contrats = 0
    for support in detenus:
        if support["isin"] in instruments:
            continue
        instruments[support["isin"]] = {
            "nom": support["nom"],
            "societe_gestion": None,
            "type_instrument": "etf" if "ETF" in support["nom"].upper() else "opc",
            "forme_juridique": None, "devise": None, "pays": None, "notation": None}
        hors_contrats += 1
    for libelle in sans_isin:
        anomalies.append(("support détenu sans ISIN", "avertissement", None,
                          f"{libelle} — non rattachable au référentiel, l'ISIN manque"))

    # Les instruments sont inseres avant les offres, qui les referencent.
    cx.executemany("INSERT INTO instrument (isin, nom, societe_gestion, type_instrument, forme_juridique,"
                   " devise, pays, notation) VALUES (?,?,?,?,?,?,?,?)",
                   [(isin, v["nom"], v["societe_gestion"], v["type_instrument"], v["forme_juridique"],
                     v["devise"], v["pays"], v["notation"]) for isin, v in instruments.items()])
    cx.executemany(
        "INSERT INTO offre (import_id, isin, fournisseur, contrat, grande_classe, type_actif,"
        " origine_classification, sfdr, sri, label, statut, avenant, frais_fonds, frais_contrat,"
        " frais_totaux_publies, frais_totaux_comparables, retrocessions, perf_brute_n1,"
        " perf_nette_n1, perf_finale_n1, perf_finale_5a)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", offres)
    cx.executemany("INSERT INTO performance_annuelle (isin, fournisseur, annee, perf_nette)"
                   " VALUES (?,?,?,?)", performances)
    cx.commit()
    return cx, anomalies


def _plie(texte):
    sans = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", sans.lower())


# Mentions de forme sociale et d'activite, sans valeur distinctive.
BRUIT_SOCIETE = re.compile(
    r"\b(am|asset|management|mngt|gestion|investment|investments|investissement|investissements|"
    r"fund|funds|sa|sas|sca|plc|ltd|gmbh|nv|bv|spa|llc|inc|group|groupe|europe|european|"
    r"france|lux|luxembourg|ireland|deutschland|international|uk|us|co)\b")


def _marque(raison_sociale):
    """Partie distinctive d'une raison sociale, formes juridiques et activite retirees."""
    sans_accent = unicodedata.normalize("NFKD", raison_sociale).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", BRUIT_SOCIETE.sub(" ", re.sub(r"[^a-z0-9]+", " ", sans_accent)))


def _societes_distinctes(gauche, droite):
    """Vrai si deux raisons sociales designent vraisemblablement des maisons differentes.

    Le controle vise un ISIN mal apparie, pas une difference de style : SwissLife
    abrege ("Sycomore AM") la ou BoursoVie donne la raison sociale complete
    ("SYCOMORE ASSET MANAGEMENT"). La comparaison porte donc sur la seule partie
    distinctive, et une marque contenue dans l'autre ne compte pas comme un ecart.
    """
    if not gauche or not droite:
        return False
    a, b = _marque(gauche), _marque(droite)
    if not a or not b:
        return False
    return a not in b and b not in a


def controler(cx, anomalies):
    """Confronte la base a ses sources et a sa propre coherence interne."""
    ajouter = lambda *a: anomalies.append(a)

    for fournisseur, attendu in EFFECTIF_ATTENDU.items():
        charges = cx.execute("SELECT COUNT(*) FROM offre WHERE fournisseur = ?", (fournisseur,)).fetchone()[0]
        if charges != attendu:
            ajouter("effectif", "bloquant", None, f"{fournisseur} : {charges} offres chargées, {attendu} attendues")
        source = isins_du_pdf(fournisseur)
        base = {r[0] for r in cx.execute("SELECT isin FROM offre WHERE fournisseur = ?", (fournisseur,))}
        for isin in sorted(source - base):
            ajouter("réconciliation PDF", "bloquant", isin, f"{fournisseur} : présent dans le PDF, absent de la base")
        for isin in sorted(base - source):
            ajouter("réconciliation PDF", "bloquant", isin, f"{fournisseur} : présent dans la base, absent du PDF")

    # Les frais publies doivent se deduire des composantes, selon la formule
    # propre a chaque assureur.
    for isin, f, b, c, publies in cx.execute(
            "SELECT isin, fournisseur, frais_fonds, frais_contrat, frais_totaux_publies FROM offre"
            " WHERE frais_fonds IS NOT NULL AND frais_contrat IS NOT NULL AND frais_totaux_publies IS NOT NULL"):
        perf = cx.execute("SELECT perf_nette_n1 FROM offre WHERE isin = ? AND fournisseur = ?", (isin, f)).fetchone()[0]
        if f == "SwissLife":
            recalcule = b + c
        elif perf is None:
            continue
        else:
            recalcule = b + (1 + perf / 100) * c
        if abs(recalcule - publies) > 0.02:
            ajouter("cohérence des frais", "avertissement", isin,
                    f"{f} : frais publiés {publies:.2f} %, recalculés {recalcule:.2f} %")

    for isin, f, brute, nette, frais in cx.execute(
            "SELECT isin, fournisseur, perf_brute_n1, perf_nette_n1, frais_fonds FROM offre"
            " WHERE perf_brute_n1 IS NOT NULL AND perf_nette_n1 IS NOT NULL AND frais_fonds IS NOT NULL"):
        if abs((brute - frais) - nette) > 0.02:
            ajouter("cohérence des performances", "avertissement", isin,
                    f"{f} : brute {brute:.2f} % − frais {frais:.2f} % ≠ nette {nette:.2f} %")

    # Les frais du fonds lui-meme devraient etre identiques chez les deux
    # assureurs : ils sont une propriete du fonds, pas du contrat.
    for isin, sl, bo in cx.execute(
            "SELECT sl.isin, sl.frais_fonds, bo.frais_fonds FROM offre sl"
            " JOIN offre bo ON bo.isin = sl.isin AND bo.fournisseur = 'BoursoVie'"
            " WHERE sl.fournisseur = 'SwissLife'"
            " AND sl.frais_fonds IS NOT NULL AND bo.frais_fonds IS NOT NULL"
            " AND ABS(bo.frais_fonds - sl.frais_fonds) > 0.05"):
        ajouter("frais du fonds divergents entre assureurs", "avertissement", isin,
                f"SwissLife {sl:.2f} %, BoursoVie {bo:.2f} %, écart {bo - sl:+.2f} pt")

    # Un frais de gestion nul sur un fonds gere activement traduit presque
    # toujours une donnee non communiquee, publiee comme un zero.
    for isin, f in cx.execute(
            "SELECT o.isin, o.fournisseur FROM offre o JOIN instrument i ON i.isin = o.isin"
            " WHERE o.frais_fonds = 0 AND i.type_instrument <> 'etf'"):
        ajouter("frais de gestion nuls", "avertissement", isin,
                f"{f} : frais du fonds à 0 %, valeur vraisemblablement non communiquée")

    orphelines = cx.execute("SELECT COUNT(*) FROM offre o"
                            " LEFT JOIN instrument i ON i.isin = o.isin WHERE i.isin IS NULL").fetchone()[0]
    if orphelines:
        ajouter("intégrité", "bloquant", None, f"{orphelines} offres sans instrument")

    cx.executemany("INSERT INTO anomalie (controle, gravite, isin, detail) VALUES (?,?,?,?)", anomalies)
    cx.commit()
    return anomalies


def rapport(cx, anomalies, base):
    ligne = lambda r: cx.execute(r).fetchone()[0]
    print(f"\nBase : {base}  ({os.path.getsize(base) / 1024:.0f} Ko)")
    print(f"  instruments            {ligne('SELECT COUNT(*) FROM instrument'):5d}")
    hors = ligne("SELECT COUNT(*) FROM instrument i LEFT JOIN offre o ON o.isin = i.isin"
                 " WHERE o.isin IS NULL")
    if hors:
        print(f"     dont hors contrats-----{hors:5d}  (détenus, non offerts par les assureurs)")
    for nature, n in cx.execute("SELECT type_instrument, COUNT(*) FROM instrument"
                                " GROUP BY 1 ORDER BY 2 DESC"):
        print(f"     dont {nature:-<18s} {n:5d}")
    print(f"  offres                 {ligne('SELECT COUNT(*) FROM offre'):5d}")
    for f, n in cx.execute("SELECT fournisseur, COUNT(*) FROM offre GROUP BY 1"):
        print(f"     dont {f:-<18s} {n:5d}")
    print(f"  performances annuelles {ligne('SELECT COUNT(*) FROM performance_annuelle'):5d}")
    communs = ligne("SELECT COUNT(*) FROM v_univers WHERE disponibilite = 'les deux'")
    print(f"  disponibles chez les deux {communs:5d}"
          f"  dont {ligne('SELECT COUNT(*) FROM v_arbitrage')} comparables sur les frais")

    print("\nContrôles")
    if not anomalies:
        print("  aucun écart")
    for controle, gravite in sorted({(a[0], a[1]) for a in anomalies}):
        n = sum(1 for a in anomalies if a[0] == controle and a[1] == gravite)
        print(f"  {gravite:14s} {controle:32s} {n:4d}")
    bloquants = sum(1 for a in anomalies if a[1] == "bloquant")

    print("\nÉcart de frais sur les fonds communs")
    for fiabilite, n in cx.execute("SELECT fiabilite, COUNT(*) FROM v_arbitrage GROUP BY 1 ORDER BY 2 DESC"):
        print(f"  {n:4d}  {fiabilite}")
    fiables = list(cx.execute("SELECT isin, nom, frais_swisslife, frais_boursorama, ecart"
                              " FROM v_arbitrage WHERE fiabilite = 'comparable' ORDER BY ecart LIMIT 5"))
    print("  sur les lignes comparables :")
    for isin, nom, sl, bo, ecart in fiables:
        print(f"    {isin}  {nom[:30]:30s} SwissLife {sl:5.2f} %  BoursoVie {bo:5.2f} %  {ecart:+6.2f} pt")
    gagnant = collections.Counter(r[0] for r in cx.execute(
        "SELECT moins_cher FROM v_arbitrage WHERE fiabilite = 'comparable'"))
    print(f"    moins cher : BoursoVie {gagnant['BoursoVie']} fois, SwissLife {gagnant['SwissLife']} fois")
    return bloquants


if __name__ == "__main__":
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--base", default=os.path.join(RACINE, "data/reference.db"))
    options = analyseur.parse_args()
    connexion, ecarts = construire(options.base)
    ecarts = controler(connexion, ecarts)
    sys.exit(1 if rapport(connexion, ecarts, options.base) else 0)
