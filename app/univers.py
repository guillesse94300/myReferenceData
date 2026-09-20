"""Interface locale de consultation de l'univers d'investissement.

Lecture seule : l'application n'ecrit jamais dans la base, qui se reconstruit
par construire.bat. Elle affiche les reserves de lecture la ou elles portent,
plutot que de presenter des chiffres incertains comme s'ils ne l'etaient pas.
"""
import datetime
import os
import sqlite3
import sys

import altair as alt
import pandas as pd
import streamlit as st

import favoris as suivi
import indicateurs
from version import DATE, VERSION

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

RACINE = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(RACINE, "data/reference.db")
COTATIONS = os.path.join(RACINE, "data/cotations.db")

# Palette de reference, declinaison claire, validee contre la surface #fcfcfb.
ENCRE, ENCRE_DOUCE, GRILLE = "#0b0b0b", "#52514e", "#e6e5e1"
BLEU, ROUGE, GRIS = "#2a78d6", "#e34948", "#c9c8c3"
# Rampe ordinale : plus le risque est eleve, plus la teinte est soutenue. Le pas
# le plus clair reste au-dessus du plancher de contraste de 2:1 sur fond clair.
RAMPE_RISQUE = ["#86b6ef", "#6da7ec", "#5598e7", "#3987e5", "#2a78d6", "#1c5cab", "#104281"]

MENUS = ["LISTE", "PERF", "COMPARE"]
ANNEXES = ["Frais", "Qualité des données"]
# Axe « vehicule » : ce que le support est, non ce dans quoi il investit. Livret
# n'a encore aucun membre -- il figure quand meme, parce qu'une case absente se
# lit comme une categorie qui n'existe pas, et celle-ci existe.
ORDRE_VEHICULES = ["Fond UC", "ETF", "Actions", "FCPE", "SCPI", "Livret"]
# Palette categorielle, huit teintes dans un ordre fixe, jamais cyclees. Validee
# contre la surface #fcfcfb : bande de clarte, plancher de chroma, separation
# daltonienne et vision normale sur les paires adjacentes. Trois teintes passent
# sous 3:1 de contraste, ce qui impose un releve -- legende, etiquettes de fin de
# courbe et tableau des valeurs, tous presents sur COMPARE.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
          "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
MAX_COMPARE = len(SERIES)

st.set_page_config(page_title="Univers d'investissement", page_icon="◈", layout="wide")

FORMATS = {
    "Perf. annualisée": "{:+.2f} %", "Perf. N-1": "{:+.2f} %",
    "Depuis 1er janv.": "{:+.2f} %", "12 mois": "{:+.2f} %",
    "Frais totaux": "{:.2f} %", "Frais SwissLife": "{:.2f} %", "Frais BoursoVie": "{:.2f} %",
    "Frais du fonds": "{:.2f} %", "Frais de contrat": "{:.2f} %",
    "Frais totaux publiés": "{:.2f} %", "Frais totaux homogènes": "{:.2f} %",
    "Rétrocessions": "{:.2f} %", "Perf. brute": "{:+.2f} %", "Perf. nette": "{:+.2f} %",
    "Écart (pt)": "{:+.2f}", "Écart frais du fonds (pt)": "{:+.2f}",
    "SRI": "{:.0f}", "Années": "{:.0f}",
}


def tableau(cadre, **options):
    """Tableau aux taux formates, le tri restant numerique.

    Les cellules vides s'affichent "None" : c'est le rendu des valeurs absentes
    propre au composant. Les convertir en texte donnerait un tri alphabetique,
    ce qui coute plus cher ici que la mention elle-meme.
    """
    formats = {c: f for c, f in FORMATS.items() if c in cadre.columns}
    st.dataframe(cadre.style.format(formats), width="stretch", hide_index=True, **options)


def annualiser(rendements):
    """Rendement annualise a partir de performances annuelles, en pourcentage.

    La moyenne arithmetique surestime le rendement reellement obtenu -- jusqu'a
    huit points sur les fonds les plus volatils de cet univers. C'est donc la
    moyenne geometrique qui est retenue.
    """
    cumul = 1.0
    for taux in rendements:
        cumul *= 1 + taux / 100
    return (cumul ** (1 / len(rendements)) - 1) * 100


@st.cache_data
def charger_cotations():
    """Valeurs liquidatives, si la base des cotations existe.

    Elle est facultative : l'application reste utilisable sans elle, les
    sections qui en dependent disparaissant simplement.
    """
    if not os.path.exists(COTATIONS):
        return pd.DataFrame(columns=["isin", "date", "valeur", "devise"])
    cx = sqlite3.connect(COTATIONS)
    series = pd.read_sql("SELECT isin, date, valeur, devise FROM valeur_liquidative", cx,
                         parse_dates=["date"])
    cx.close()
    return series


@st.cache_data
def charger():
    if not os.path.exists(BASE):
        return None
    cx = sqlite3.connect(BASE)
    univers = pd.read_sql("SELECT * FROM v_univers", cx)
    performances = pd.read_sql("SELECT * FROM performance_annuelle", cx)
    arbitrage = pd.read_sql("SELECT * FROM v_arbitrage", cx)
    offres = pd.read_sql("SELECT * FROM offre", cx)
    anomalies = pd.read_sql("SELECT * FROM anomalie", cx)
    imports = pd.read_sql("SELECT * FROM import", cx)
    cx.close()

    for colonne in ("frais_swisslife", "frais_boursorama", "frais_fonds_swisslife",
                    "frais_fonds_boursorama", "sri"):
        univers[colonne] = pd.to_numeric(univers[colonne], errors="coerce")
    for colonne in ("frais_fonds", "frais_contrat", "frais_totaux_publies", "frais_totaux_comparables",
                    "retrocessions", "perf_brute_n1", "perf_nette_n1", "perf_finale_n1", "perf_finale_5a"):
        offres[colonne] = pd.to_numeric(offres[colonne], errors="coerce")

    univers["frais"] = univers[["frais_swisslife", "frais_boursorama"]].min(axis=1)
    série = performances.sort_values("annee").groupby("isin")["perf_nette"].agg(list)
    annualisées = pd.DataFrame({
        "isin": série.index,
        "perf_annualisee": [annualiser(v) for v in série],
        "annees": [len(v) for v in série],
    })
    # Le dernier exercice clos couvre bien plus d'instruments que l'historique
    # complet : il sert de repli quand l'annualise n'est pas calculable.
    dernier = (offres.dropna(subset=["perf_nette_n1"]).groupby("isin")["perf_nette_n1"]
               .max().rename("perf_n1").reset_index())
    univers = univers.merge(annualisées, on="isin", how="left").merge(dernier, on="isin", how="left")
    return univers, performances, arbitrage, offres, anomalies, imports


suivis = suivi.charger()
cotations = charger_cotations()
donnees = charger()
if donnees is None:
    st.error(f"Base introuvable : {BASE}\n\nLancez `construire.bat` pour la créer.")
    st.stop()
univers, performances, arbitrage, offres, anomalies, imports = donnees
avec_vl = set(cotations["isin"].unique())
usuelles_par_isin = {
    isin: indicateurs.performances_usuelles(
        {ligne.date.date(): ligne.valeur for ligne in groupe.itertuples()})
    for isin, groupe in cotations.groupby("isin")} if len(cotations) else {}
univers = univers.assign(cotee=univers["isin"].isin(avec_vl),
                         favori=univers["isin"].isin(suivis),
                         note=univers["isin"].map(lambda i: suivis.get(i, {}).get("note", "")))

# Le dernier exercice clos porte un millesime qui avance : il est lu dans les
# series plutot qu'ecrit en dur, faute de quoi la grille se figerait sur 2025.
ANNEE = max(cotations["date"]).year if len(cotations) else None
EXERCICE = str(ANNEE - 1) if ANNEE else "exercice clos"
# Les six horizons, dans l'ordre du croquis : 1 an, 2 ans, exercice clos, puis
# l'annee en cours, 3 mois et 6 mois.
HORIZONS = [("12 mois", "1 an"), ("24 mois", "2 ans"), (EXERCICE, EXERCICE),
            ("depuis le 1er janvier", f"{ANNEE} à ce jour" if ANNEE else "Depuis le 1er janvier"),
            ("3 mois", "3 mois"), ("6 mois", "6 mois")]
for cle, _ in HORIZONS:
    univers[cle] = univers["isin"].map(lambda i, c=cle: usuelles_par_isin.get(i, {}).get(c))


MOIS = ["janvier", "février", "mars", "avril", "mai", "juin",
        "juillet", "août", "septembre", "octobre", "novembre", "décembre"]


def en_toutes_lettres(date_iso):
    """'2026-09-19' donne '19 septembre 2026', le premier du mois prenant 'er'."""
    annee, mois, jour = date_iso.split("-")
    quantieme = "1er" if int(jour) == 1 else str(int(jour))
    return f"{quantieme} {MOIS[int(mois) - 1]} {annee}"


def en_tete(titre, sous_titre=None):
    """Titre de page. La version et le millesime vivent en barre laterale."""
    st.title(titre)
    if sous_titre:
        st.caption(sous_titre)


# ----------------------------------------------------------------- graphiques

def classement(cadre, cle, plafond=12):
    """Supports ordonnes sur un horizon, du meilleur au pire.

    Paire divergente bleu/rouge : la polarite est le signe de la performance,
    pas son rang. Chaque barre porte sa valeur -- douze au plus, l'etiquetage
    reste lisible et dispense d'aller lire un axe.
    """
    donnees = (cadre.dropna(subset=[cle])[["nom", cle]]
               .sort_values(cle, ascending=False).head(plafond)
               .rename(columns={cle: "taux"}))
    if donnees.empty:
        return None
    bornes = marge(donnees["taux"])
    # L'ordre est fixe ici plutot que delegue a « -x » : la couche du zero ne
    # porte pas le champ de tri, et Vega abandonne le rendu de tout le graphique.
    base = alt.Chart(donnees).encode(
        alt.Y("nom:N", sort=list(donnees["nom"]), title=None,
              axis=alt.Axis(labelColor=ENCRE, labelLimit=150, domainColor=GRILLE,
                            ticks=False, labelPadding=6, labelFontSize=11)),
        alt.X("taux:Q", title=None, axis=None, scale=alt.Scale(domain=bornes)))
    barres = base.mark_bar(cornerRadius=4, height=13).encode(
        color=alt.condition(alt.datum.taux >= 0, alt.value(BLEU), alt.value(ROUGE)),
        tooltip=[alt.Tooltip("nom:N", title="Support"),
                 alt.Tooltip("taux:Q", title="Performance", format="+.2f")])
    # L'etiquette bascule du cote ou la barre s'etend, sans quoi elle la recouvre.
    valeurs = base.mark_text(
        align=alt.expr(alt.expr.if_(alt.datum.taux >= 0, "left", "right")),
        dx=alt.expr(alt.expr.if_(alt.datum.taux >= 0, 5, -5)),
        color=ENCRE_DOUCE, fontSize=10).encode(text=alt.Text("taux:Q", format="+.1f"))
    # La regle du zero porte explicitement la meme echelle que les barres. Sans
    # elle, Vega ne resout pas l'echelle de bande partagee et abandonne le rendu
    # du graphique entier -- silencieusement, la page restant simplement vide.
    zero = (alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(color=GRILLE, strokeWidth=1)
            .encode(alt.X("x:Q", axis=None, scale=alt.Scale(domain=bornes))))
    return ((zero + barres + valeurs).properties(height=max(90, 22 * len(donnees)))
            .configure_view(strokeWidth=0))


def marge(taux):
    """Domaine elargi de 18 %, pour que les etiquettes de valeur tiennent."""
    bas, haut = min(taux.min(), 0), max(taux.max(), 0)
    jeu = max((haut - bas) * 0.18, 0.5)
    return [bas - jeu, haut + jeu]


def superposition(series, noms):
    """Trajectoires de plusieurs supports ramenees a 100 a leur depart commun.

    Base 100 parce que les valeurs liquidatives brutes, de quelques euros a
    plusieurs centaines, ne se superposent pas : seule l'evolution se compare.
    Le depart est la premiere date ou tous les supports cotent, sans quoi une
    serie plus courte partirait avec un avantage qu'elle n'a pas.
    """
    debut = max(min(v) for v in series.values())
    lignes = []
    for rang, (isin, valeurs) in enumerate(series.items()):
        retenues = {d: v for d, v in valeurs.items() if d >= debut}
        for date, indice in indicateurs.base_cent(retenues).items():
            lignes.append({"date": date, "base": indice, "support": noms[isin], "rang": rang})
    trace = pd.DataFrame(lignes)
    ordre = [noms[i] for i in series]
    echelle = alt.Scale(domain=ordre, range=SERIES[:len(ordre)])

    courbes = alt.Chart(trace).mark_line(strokeWidth=2).encode(
        alt.X("date:T", title=None,
              axis=alt.Axis(gridColor=GRILLE, labelColor=ENCRE, format="%b %Y", tickCount=6)),
        alt.Y("base:Q", title="Base 100 au départ commun", scale=alt.Scale(zero=False),
              axis=alt.Axis(gridColor=GRILLE, labelColor=ENCRE, titleColor=ENCRE_DOUCE)),
        alt.Color("support:N", scale=echelle,
                  legend=alt.Legend(title=None, labelColor=ENCRE, orient="bottom", columns=2)),
        tooltip=[alt.Tooltip("support:N", title="Support"),
                 alt.Tooltip("date:T", title="Date", format="%d/%m/%Y"),
                 alt.Tooltip("base:Q", title="Base 100", format=".1f")])
    # Etiquette de fin de courbe : trois teintes de la palette passent sous 3:1
    # de contraste, l'identite ne peut donc pas reposer sur la couleur seule.
    fins = trace.sort_values("date").groupby("support", as_index=False).last()
    bouts = alt.Chart(fins).mark_text(align="left", dx=6, fontSize=11, color=ENCRE).encode(
        alt.X("date:T"), alt.Y("base:Q"), text="support:N")
    return ((courbes + bouts).properties(height=380,
            padding={"left": 16, "top": 5, "right": 90, "bottom": 5})
            .configure_view(strokeWidth=0))


# --------------------------------------------------------------------- filtres

def parcours_et_pertes(serie):
    """Trajectoire du support ramenee a 100, et perte depuis le plus haut.

    Deux graphiques empiles partageant l'axe des dates : le premier dit ce que
    serait devenu un placement, le second ce qu'il aurait fallu supporter en
    chemin. La valeur liquidative brute n'est pas tracee telle quelle -- son
    niveau, de quelques euros a plusieurs centaines, n'a aucun sens en soi.
    """
    valeurs = {ligne.date.date(): ligne.valeur for ligne in serie.itertuples()}
    trajectoire = pd.DataFrame(
        [{"date": d, "base": v, "perte": p} for (d, v), p
         in zip(sorted(indicateurs.base_cent(valeurs).items()),
                [indicateurs.courbe_de_perte(valeurs)[d] for d in sorted(valeurs)])])

    survol = alt.selection_point(nearest=True, on="pointerover", fields=["date"], empty=False)
    axe_dates = alt.Axis(gridColor=GRILLE, labelColor=ENCRE, format="%b %Y", tickCount=6)

    # Les deux graphiques partagent la même échelle de temps : seul celui du bas
    # en porte les libellés, pour ne pas les afficher deux fois.
    base = alt.Chart(trajectoire).encode(
        alt.X("date:T", title=None, axis=alt.Axis(gridColor=GRILLE, labels=False,
                                                  tickCount=6, domainColor=GRILLE)))
    ligne = base.mark_line(color=BLEU, strokeWidth=2).encode(
        alt.Y("base:Q", title="Base 100", scale=alt.Scale(zero=False),
              axis=alt.Axis(gridColor=GRILLE, labelColor=ENCRE, titleColor=ENCRE_DOUCE)))
    reperes = base.mark_point(size=60, opacity=0).encode(
        tooltip=[alt.Tooltip("date:T", title="Date", format="%d/%m/%Y"),
                 alt.Tooltip("base:Q", title="Base 100", format=".1f"),
                 alt.Tooltip("perte:Q", title="Perte depuis le plus haut", format="+.1f")]
    ).add_params(survol)
    trait = base.mark_rule(color=ENCRE_DOUCE, strokeWidth=1).encode(
        opacity=alt.condition(survol, alt.value(0.4), alt.value(0)))

    perte = alt.Chart(trajectoire).mark_area(
        color=ROUGE, opacity=0.18, line={"color": ROUGE, "strokeWidth": 1.5}).encode(
        alt.X("date:T", title=None, axis=axe_dates),
        alt.Y("perte:Q", title="Perte (%)",
              axis=alt.Axis(gridColor=GRILLE, labelColor=ENCRE, titleColor=ENCRE_DOUCE)))

    # La marge se pose sur l'empilement, Altair la refusant sur ses éléments.
    return alt.vconcat(
        (ligne + trait + reperes).properties(height=240),
        perte.properties(height=110),
        spacing=8).properties(padding={"left": 16, "top": 5, "right": 5, "bottom": 5}) \
        .configure_view(strokeWidth=0)


def quitter_les_annexes():
    """Le choix d'un menu referme la fiche et les annexes qui le recouvraient."""
    st.session_state["annexe"] = None
    st.session_state["fiche"] = None


def ouvrir(annexe):
    st.session_state["annexe"] = annexe
    st.session_state["fiche"] = None


def barre_laterale():
    """Date, version, les trois menus, les filtres, et les annexes en pied.

    Les filtres s'appliquent aux trois menus. Les annexes -- frais et qualite
    des donnees -- ont leurs propres selecteurs et ignorent la selection.
    """
    barre = st.sidebar
    aujourdhui = datetime.date.today().isoformat()
    barre.markdown(f"**{en_toutes_lettres(aujourdhui)}**")
    millesimes = " · ".join(f"{ligne.fournisseur} {en_toutes_lettres(ligne.millesime)}"
                            for ligne in imports.itertuples())
    barre.caption(f"Version {VERSION} du {en_toutes_lettres(DATE)}\n\nDonnées {millesimes}")

    barre.divider()
    barre.radio("Menu", MENUS, key="menu", horizontal=True, label_visibility="collapsed",
                on_change=quitter_les_annexes)

    barre.divider()
    vue = univers.copy()

    recherche = barre.text_input("Nom ou ISIN")
    if recherche:
        vue = vue[vue["nom"].str.contains(recherche, case=False, na=False)
                  | vue["isin"].str.contains(recherche.upper(), na=False)]

    # Un support detenu mais depourvu d'ISIN ne peut etre rattache a rien : le
    # dire ici evite que la liste paraisse silencieusement incomplete.
    manquants = int((anomalies["controle"] == "support détenu sans ISIN").sum())
    aide = f"{len(suivis)} supports suivis"
    if manquants:
        aide += (f" — {manquants} autre{'s' if manquants > 1 else ''} de votre liste "
                 f"{'sont' if manquants > 1 else 'est'} sans ISIN exploitable, donc "
                 f"{'non rattachables' if manquants > 1 else 'non rattachable'}. "
                 "Voir Qualité des données.")
    favori = barre.radio("Favoris", ["Tous", "Oui", "Non"], horizontal=True, help=aide)
    if favori == "Oui":
        vue = vue[vue["favori"]]
        if manquants:
            accord = "reste" if manquants == 1 else "restent"
            pluriel = "" if manquants == 1 else "s"
            barre.caption(f"⚠ {manquants} support{pluriel} de votre liste {accord} hors "
                          "d'atteinte, faute d'ISIN.")
    elif favori == "Non":
        vue = vue[~vue["favori"]]

    barre.markdown("**Classe d'actif**")
    effectifs = univers["vehicule"].value_counts()
    coches = [v for v in ORDRE_VEHICULES
              if barre.checkbox(f"{v} ({int(effectifs.get(v, 0))})", key=f"veh_{v}")]
    if coches:
        vue = vue[vue["vehicule"].isin(coches)]

    # Les filtres du croquis tiennent en deux blocs ; les autres restent
    # disponibles, replies, plutot que d'etre supprimes ou d'encombrer.
    with barre.expander("Autres filtres"):
        sri = st.slider("Indicateur de risque (SRI)", 1, 7, (1, 7))
        if sri != (1, 7):
            vue = vue[vue["sri"].between(*sri)]
        plafond = st.slider("Frais totaux maximum (%)", 0.0, 6.0, 6.0, 0.25)
        if plafond < 6.0:
            vue = vue[vue["frais"] <= plafond]
        sfdr = st.multiselect("Classification SFDR", sorted(univers["sfdr"].dropna().unique()))
        if sfdr:
            vue = vue[vue["sfdr"].isin(sfdr)]
        if st.checkbox("Avec historique de valeurs liquidatives",
                       help="Les performances glissantes et les trajectoires ne peuvent être "
                            "calculées que pour ces supports."):
            vue = vue[vue["cotee"]]

    barre.caption(f"**{len(vue)}** instruments sur {len(univers)}")
    barre.divider()
    for annexe in ANNEXES:
        barre.button(annexe, width="stretch", on_click=ouvrir, args=(annexe,))
    return vue


# ----------------------------------------------------------------------- pages

def page_liste(vue):
    en_tete("LISTE", f"{len(vue)} instruments — sélectionnez une ligne pour agir dessus")
    if vue.empty:
        st.info("Aucun instrument ne correspond aux filtres.")
        return

    colonnes = {"favori": "Suivi", "isin": "ISIN", "nom": "Support", "vehicule": "Classe",
                "type_actif": "Type d'actif", "sri": "SRI", "frais": "Frais"}
    # Pour un support detenu, savoir dans quelle enveloppe prime sur savoir chez
    # quel assureur il s'achete : la colonne prend la place de l'autre. Il faut
    # que tous les supports affiches soient detenus, sinon la colonne serait vide
    # sur l'essentiel des lignes et chasserait une information qui, elle, y est.
    tous_detenus = vue["note"].astype(bool).all()
    colonnes["note" if tous_detenus else "disponibilite"] = (
        "Détenu dans" if tous_detenus else "Disponible")
    # Les valeurs liquidatives remplacent les mesures tirees des exercices publies
    # plutot que de s'y ajouter : plus fines, plus recentes, et le tableau garde
    # un nombre de colonnes lisible.
    if vue["12 mois"].notna().any():
        colonnes["depuis le 1er janvier"] = f"{ANNEE} à ce jour"
        colonnes["12 mois"] = "1 an"
        tri = "1 an"
    else:
        colonnes["perf_annualisee"] = "Perf. ann."
        tri = "Perf. ann."

    affiche = (vue[list(colonnes)].rename(columns=colonnes)
               .sort_values(tri, ascending=False).reset_index(drop=True))
    # Largeurs contraintes : laissees libres, le libelle et le type d'actif
    # s'etalent et rejettent les dernieres colonnes hors du cadre.
    rendement = lambda libelle, largeur: st.column_config.NumberColumn(
        libelle, format="%+.2f %%", width=largeur)
    choix = st.dataframe(
        affiche, width="stretch", hide_index=True, height=440, key="liste",
        on_select="rerun", selection_mode="single-row",
        column_config={
            "Suivi": st.column_config.CheckboxColumn("Suivi", width=60),
            "ISIN": st.column_config.TextColumn("ISIN", width=100),
            "Support": st.column_config.TextColumn("Support", width=175),
            "Classe": st.column_config.TextColumn("Classe", width=80),
            "Type d'actif": st.column_config.TextColumn("Type d'actif", width=150),
            "Détenu dans": st.column_config.TextColumn("Détenu dans", width=130),
            "Disponible": st.column_config.TextColumn("Disponible", width=85),
            "SRI": st.column_config.NumberColumn("SRI", format="%d", width=50),
            "Frais": st.column_config.NumberColumn("Frais", format="%.2f %%", width=65),
            f"{ANNEE} à ce jour": rendement(f"{ANNEE} à ce jour", 105),
            "1 an": rendement("1 an", 80), "Perf. ann.": rendement("Perf. ann.", 90)})

    lignes = choix["selection"]["rows"]
    if not lignes:
        st.caption("Aucune ligne sélectionnée.")
        return
    isin = affiche.loc[lignes[0], "ISIN"]
    ligne = univers[univers["isin"] == isin].iloc[0]
    st.divider()
    nom, bascule, fiche = st.columns([4, 1, 1])
    nom.markdown(f"**{ligne['nom']}** · `{isin}`")
    if bascule.toggle("Suivi", value=isin in suivis, key=f"suivi_{isin}") != (isin in suivis):
        suivi.basculer(isin, isin not in suivis)
        st.rerun()
    fiche.button("Ouvrir la fiche", width="stretch", on_click=voir_fiche, args=(isin,))


def page_perf(vue):
    """Les six horizons cote a cote, chacun classant les memes supports.

    La grille est batie sur les seules series de valeurs liquidatives. Les
    performances annuelles publiees par les assureurs couvriraient bien plus de
    supports sur la case de l'exercice clos, mais elles obeissent a une autre
    definition -- exercice civil, en euro, nette des frais du fonds. Les melanger
    rendrait cette case incomparable a ses cinq voisines, ce qui est precisement
    ce que la grille sert a faire.
    """
    cotes = vue[vue["cotee"]]
    en_tete("PERF", f"{len(cotes)} supports de la sélection ont un historique de valeurs "
                    f"liquidatives, sur {len(vue)}")
    if cotes.empty:
        st.info("Aucun support de la sélection n'a d'historique de valeurs liquidatives. "
                "Les six horizons se calculent sur ces séries, non sur les performances "
                "annuelles publiées.")
        return
    st.caption("Performances cumulées, non annualisées, dans la devise du fonds. Une période que "
               "l'historique ne couvre pas laisse le support hors du classement, plutôt que de "
               "le calculer sur une fenêtre tronquée.")

    for rangee in (HORIZONS[:3], HORIZONS[3:]):
        cases = st.columns(3)
        for case, (cle, libelle) in zip(cases, rangee):
            with case:
                st.markdown(f"**{libelle}**")
                graphique = classement(cotes, cle)
                if graphique is None:
                    st.caption("Aucun support ne couvre cet horizon.")
                    continue
                st.altair_chart(graphique, width="stretch")
                couverts = int(cotes[cle].notna().sum())
                if couverts > 12:
                    st.caption(f"Les 12 premiers sur {couverts}.")


def page_compare(vue):
    """Selection a gauche, trajectoires superposees a droite."""
    cotes = vue[vue["cotee"]]
    en_tete("COMPARE", "Superposition des trajectoires, ramenées à 100 à leur départ commun")
    if cotes.empty:
        st.info("Aucun support de la sélection n'a d'historique de valeurs liquidatives.")
        return

    gauche, droite = st.columns([1, 2])
    with gauche:
        st.markdown("**Supports**")
        etiquettes = {f"{l.nom}": l.isin for l in cotes.itertuples()}
        defaut = list(etiquettes)[:min(4, len(etiquettes))]
        retenus = st.multiselect("Supports", list(etiquettes), default=defaut,
                                 max_selections=MAX_COMPARE, label_visibility="collapsed")
        st.caption(f"{MAX_COMPARE} au maximum : au-delà, les courbes ne se distinguent plus.")

    isins = [etiquettes[e] for e in retenus]
    if not isins:
        droite.info("Choisissez au moins un support.")
        return
    series = {isin: {l.date.date(): l.valeur
                     for l in cotations[cotations["isin"] == isin].itertuples()}
              for isin in isins}
    noms = {l.isin: l.nom for l in cotes.itertuples()}
    with droite:
        st.altair_chart(superposition(series, noms), width="stretch")

    debut = max(min(v) for v in series.values())
    st.caption(f"Départ commun au {debut.strftime('%d/%m/%Y')}, première séance où tous les "
               "supports retenus cotent.")
    # La couleur seule ne porte pas l'identite : le meme contenu se relit ici en
    # clair, ce qu'exige le contraste de trois teintes de la palette.
    st.markdown("**Performances par horizon**")
    valeurs = cotes[cotes["isin"].isin(isins)]
    grille = (valeurs[["nom"] + [c for c, _ in HORIZONS]]
              .rename(columns={"nom": "Support", **{c: l for c, l in HORIZONS}}))
    st.dataframe(grille, width="stretch", hide_index=True,
                 column_config={l: st.column_config.NumberColumn(l, format="%+.2f %%")
                                for _, l in HORIZONS})


def voir_fiche(isin):
    st.session_state["fiche"] = isin


def page_fiche(isin):
    """Detail d'un support, ouvert depuis une ligne de LISTE."""
    st.button("← Retour à la liste", on_click=voir_fiche, args=(None,))
    ligne = univers[univers["isin"] == isin].iloc[0]

    titre, bascule = st.columns([5, 1])
    titre.subheader(ligne["nom"])
    if bascule.toggle("Favori", value=isin in suivis, key=f"fav_{isin}") != (isin in suivis):
        suivi.basculer(isin, isin not in suivis)
        st.rerun()
    st.caption(f"`{isin}` · {ligne['vehicule']} · "
               f"{ligne['societe_gestion'] or 'société non communiquée'} · {ligne['type_actif']} · "
               f"classe {ligne['grande_classe']} · SFDR {ligne['sfdr']} · "
               f"disponible chez {ligne['disponibilite']}")
    if ligne["note"]:
        st.info(f"Support suivi — détenu dans : {ligne['note']}")
    if ligne["origine_classification"] == "déduite du libellé":
        st.warning("Classe d'actif déduite du libellé du support, non confirmée par un référentiel.")

    colonnes = st.columns(3)
    colonnes[0].metric("Indicateur de risque",
                       "non renseigné" if pd.isna(ligne["sri"]) else f"{int(ligne['sri'])} / 7")
    colonnes[1].metric(
        "Rendement annualisé publié",
        "—" if pd.isna(ligne["perf_annualisee"]) else f"{ligne['perf_annualisee']:+.2f} %/an",
        help="Calculé sur les performances annuelles publiées par l'assureur, en euro"
             + ("" if pd.isna(ligne["annees"]) else f", sur {int(ligne['annees'])} exercice(s)."))
    colonnes[2].metric("Frais totaux",
                       "—" if pd.isna(ligne["frais"]) else f"{ligne['frais']:.2f} %")

    serie = cotations[cotations["isin"] == isin].sort_values("date")
    if len(serie) > 100:
        valeurs = {ligne.date.date(): ligne.valeur for ligne in serie.itertuples()}
        devise = serie["devise"].iloc[0]
        debut, fin = min(valeurs), max(valeurs)
        st.markdown("**Performances**")
        usuelles = indicateurs.performances_usuelles(valeurs)
        # Memes horizons, meme ordre et memes libelles que la grille PERF : un
        # chiffre doit porter ici le nom sous lequel il y a ete lu.
        cases = st.columns(len(HORIZONS))
        for case, (cle, libelle) in zip(cases, HORIZONS):
            taux = usuelles.get(cle)
            case.metric(libelle, "—" if taux is None else f"{taux:+.2f} %")
        st.caption(
            f"Cumulées et non annualisées, calculées sur la série de valeurs liquidatives, "
            f"en {devise}. Une période que l'historique ne couvre pas reste vide plutôt que "
            "d'être calculée sur une fenêtre tronquée."
            + ("" if devise == "EUR" else
               " Le support étant hors euro, ces chiffres diffèrent des performances annuelles "
               "publiées plus bas, que l'assureur donne en euro."))

        st.markdown("**Risque et parcours**")
        mesures = st.columns(3)
        mesures[0].metric("Rendement annualisé observé",
                          f"{indicateurs.rendement_annualise(valeurs):+.2f} %/an",
                          help="Calculé sur la série de valeurs liquidatives, dans la devise du "
                               "fonds et sur la période couverte — il diffère donc du rendement "
                               "publié, qui porte sur des exercices civils et en euro.")
        mesures[1].metric("Volatilité annualisée",
                          f"{indicateurs.volatilite_annualisee(valeurs):.1f} %")
        mesures[2].metric("Perte maximale", f"{indicateurs.perte_maximale(valeurs):.1f} %",
                          help="La plus forte baisse depuis un plus haut, sur la période couverte.")
        st.caption(f"{len(valeurs)} séances du {debut.strftime('%d/%m/%Y')} au "
                   f"{fin.strftime('%d/%m/%Y')}."
                   + ("" if devise == "EUR" else
                      " Support hors euro : ces mesures portent sur le fonds seul, "
                      "sans l'effet du change subi par un investisseur en euro."))
        st.altair_chart(parcours_et_pertes(serie), width="stretch")

    historique = performances[performances["isin"] == isin].sort_values("annee")
    if not historique.empty:
        st.markdown("**Performance nette annuelle**")
        base = alt.Chart(historique).encode(
            alt.X("annee:O", title=None,
                  axis=alt.Axis(labelColor=ENCRE, labelAngle=0, domainColor=GRILLE)),
            alt.Y("perf_nette:Q", title="Performance nette (%)",
                  axis=alt.Axis(gridColor=GRILLE, labelColor=ENCRE, titleColor=ENCRE_DOUCE)))
        barres = base.mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, cornerRadiusBottomLeft=4,
                               cornerRadiusBottomRight=4, size=38).encode(
            # Paire divergente bleu/rouge : le signe de la performance est la polarite.
            color=alt.condition(alt.datum.perf_nette >= 0, alt.value(BLEU), alt.value(ROUGE)),
            tooltip=[alt.Tooltip("annee:O", title="Année"),
                     alt.Tooltip("perf_nette:Q", title="Performance nette", format="+.2f")])
        # Cinq barres au plus : chacune porte sa valeur.
        etiquettes = base.mark_text(dy=alt.expr(alt.expr.if_(alt.datum.perf_nette >= 0, -8, 14)),
                                    color=ENCRE, fontSize=11).encode(
            text=alt.Text("perf_nette:Q", format="+.1f"))
        zero = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color=ENCRE, strokeWidth=1).encode(y="y:Q")
        st.altair_chart((barres + zero + etiquettes).properties(height=260)
                        .configure_view(strokeWidth=0), width="stretch")
    else:
        st.info("Aucun historique annuel pour ce support.")

    detail = offres[offres["isin"] == isin]
    st.markdown("**Conditions par assureur**")
    tableau(detail[["fournisseur", "contrat", "frais_fonds", "frais_contrat", "frais_totaux_publies",
                    "frais_totaux_comparables", "retrocessions", "perf_brute_n1", "perf_nette_n1"]]
            .rename(columns={"fournisseur": "Assureur", "contrat": "Contrat",
                             "frais_fonds": "Frais du fonds", "frais_contrat": "Frais de contrat",
                             "frais_totaux_publies": "Frais totaux publiés",
                             "frais_totaux_comparables": "Frais totaux homogènes",
                             "retrocessions": "Rétrocessions", "perf_brute_n1": "Perf. brute",
                             "perf_nette_n1": "Perf. nette"}))
    if len(detail) == 2 and detail["frais_fonds"].notna().all() \
            and abs(detail["frais_fonds"].iloc[0] - detail["frais_fonds"].iloc[1]) > 0.05:
        st.warning("Les deux assureurs annoncent des frais de fonds différents pour ce même "
                   "support : les frais totaux ne sont pas directement comparables.")


def page_frais(_):
    st.button("← Retour", on_click=quitter_les_annexes)
    en_tete("Frais — le même fonds chez les deux assureurs")
    st.info("Les deux assureurs ne publient pas la même grandeur pour les frais du fonds : "
            "SwissLife paraît donner les charges supportées sur le dernier exercice, BoursoVie les "
            "frais contractuels. Seules les lignes marquées **comparable** autorisent une conclusion "
            "tarifaire. Sur celles-ci, l'écart se réduit à la différence de frais de contrat, "
            "0,96 % contre 0,75 %.")
    fiable = arbitrage[arbitrage["fiabilite"] == "comparable"]
    colonnes = st.columns(3)
    colonnes[0].metric("Fonds communs", len(arbitrage))
    colonnes[1].metric("Dont réellement comparables", len(fiable))
    colonnes[2].metric("Écart médian sur ces lignes",
                       "—" if fiable.empty else f"{fiable['ecart'].median():+.2f} pt")
    retenues = st.multiselect("Fiabilité", sorted(arbitrage["fiabilite"].unique()),
                              default=["comparable"])
    vue = arbitrage[arbitrage["fiabilite"].isin(retenues)] if retenues else arbitrage
    tableau(vue.rename(columns={"isin": "ISIN", "nom": "Support", "type_actif": "Type d'actif",
                                "frais_swisslife": "Frais SwissLife",
                                "frais_boursorama": "Frais BoursoVie", "ecart": "Écart (pt)",
                                "ecart_frais_fonds": "Écart frais du fonds (pt)",
                                "moins_cher": "Moins cher", "fiabilite": "Fiabilité"})
            .drop(columns=["grande_classe"]), height=420)


def page_qualite(_):
    st.button("← Retour", on_click=quitter_les_annexes)
    en_tete("Qualité des données")
    st.markdown("### Provenance")
    tableau(imports.rename(columns={"fournisseur": "Assureur", "document": "Document",
                                    "empreinte": "Empreinte SHA-256", "millesime": "Millésime",
                                    "importe_le": "Importé le", "lignes": "Lignes"})
            .drop(columns=["id"]))
    st.markdown("### Couverture")
    colonnes = st.columns(3)
    colonnes[0].metric("Rendement annualisé connu", int(univers["perf_annualisee"].notna().sum()))
    colonnes[1].metric("Indicateur de risque connu", int(univers["sri"].notna().sum()))
    colonnes[2].metric("Classification déduite du libellé",
                       int((univers["origine_classification"] == "déduite du libellé").sum()))
    st.markdown("### Écarts relevés au chargement")
    if anomalies.empty:
        st.success("Aucun écart relevé.")
        return
    resume = (anomalies.groupby(["gravite", "controle"]).size().reset_index(name="Occurrences")
              .rename(columns={"gravite": "Gravité", "controle": "Contrôle"})
              .sort_values("Occurrences", ascending=False))
    tableau(resume)
    controle = st.selectbox("Détail d'un contrôle", sorted(anomalies["controle"].unique()))
    tableau(anomalies[anomalies["controle"] == controle][["isin", "detail"]]
            .rename(columns={"isin": "ISIN", "detail": "Détail"}), height=300)


st.session_state.setdefault("annexe", None)
st.session_state.setdefault("fiche", None)
selection = barre_laterale()
# La fiche et les annexes recouvrent le menu courant sans le changer : on y
# revient par un simple retour, la selection restant celle qu'on avait laissee.
if st.session_state["fiche"]:
    page_fiche(st.session_state["fiche"])
elif st.session_state["annexe"]:
    {"Frais": page_frais, "Qualité des données": page_qualite}[st.session_state["annexe"]](selection)
else:
    {"LISTE": page_liste, "PERF": page_perf,
     "COMPARE": page_compare}[st.session_state["menu"]](selection)
