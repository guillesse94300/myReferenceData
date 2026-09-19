"""Interface locale de consultation de l'univers d'investissement.

Lecture seule : l'application n'ecrit jamais dans la base, qui se reconstruit
par construire.bat. Elle affiche les reserves de lecture la ou elles portent,
plutot que de presenter des chiffres incomparables comme s'ils l'etaient.
"""
import os
import sqlite3

import altair as alt
import pandas as pd
import streamlit as st

RACINE = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(RACINE, "data/reference.db")

# Couleurs de la palette de reference, declinaison claire. La paire divergente
# bleu/rouge a ete validee contre la surface #fcfcfb.
BLEU, ROUGE, ENCRE, GRILLE = "#2a78d6", "#e34948", "#0b0b0b", "#e6e5e1"

st.set_page_config(page_title="Univers d'investissement", page_icon="◈", layout="wide")

# Formats d'affichage par colonne. Le rendu passe par un Styler plutot que par
# column_config : il accepte un marqueur d'absence, la ou Streamlit afficherait
# "None", tout en conservant le type numerique et donc le tri.
FORMATS = {
    "Frais totaux": "{:.2f} %", "Frais SwissLife": "{:.2f} %", "Frais BoursoVie": "{:.2f} %",
    "Perf. moy. (%/an)": "{:+.2f}",
    "Frais du fonds": "{:.2f} %", "Frais de contrat": "{:.2f} %", "Frais totaux publiés": "{:.2f} %",
    "Frais totaux homogènes": "{:.2f} %", "Rétrocessions": "{:.2f} %",
    "Perf. brute": "{:+.2f} %", "Perf. nette": "{:+.2f} %",
    "Écart (pt)": "{:+.2f}", "Écart frais du fonds (pt)": "{:+.2f}",
    "SRI": "{:.0f}", "Années": "{:.0f}",
}


def tableau(cadre, **options):
    """Affiche un tableau dont les taux sont formates, en conservant le tri numerique.

    Les cellules vides s'affichent "None" : c'est le rendu des valeurs absentes
    propre au composant, que le na_rep du Styler ne remplace pas. Les formater
    en chaines donnerait un tri alphabetique, ce qui coute plus cher ici.
    """
    formats = {c: f for c, f in FORMATS.items() if c in cadre.columns}
    st.dataframe(cadre.style.format(formats), width="stretch", hide_index=True, **options)


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

    # Les colonnes chiffrees arrivent en objet des que la source contient des
    # valeurs manquantes ; sans conversion, l'interface afficherait "None".
    for colonne in ("frais_swisslife", "frais_boursorama", "frais_fonds_swisslife",
                    "frais_fonds_boursorama", "sri"):
        univers[colonne] = pd.to_numeric(univers[colonne], errors="coerce")
    for colonne in ("frais_fonds", "frais_contrat", "frais_totaux_publies", "frais_totaux_comparables",
                    "retrocessions", "perf_brute_n1", "perf_nette_n1", "perf_finale_n1", "perf_finale_5a"):
        offres[colonne] = pd.to_numeric(offres[colonne], errors="coerce")

    # Frais retenus pour le filtrage : les moins chers des deux assureurs.
    univers["frais"] = univers[["frais_swisslife", "frais_boursorama"]].min(axis=1)
    resume = (performances.groupby("isin")["perf_nette"]
              .agg(perf_moyenne="mean", annees="count").round(2).reset_index())
    univers = univers.merge(resume, on="isin", how="left")
    return univers, performances, arbitrage, offres, anomalies, imports


donnees = charger()
if donnees is None:
    st.error(f"Base introuvable : {BASE}\n\nLancez `construire.bat` pour la créer.")
    st.stop()
univers, performances, arbitrage, offres, anomalies, imports = donnees


def filtrer():
    """Filtres de l'univers, dans la barre laterale."""
    barre = st.sidebar
    barre.header("Filtres")
    vue = univers.copy()

    recherche = barre.text_input("Nom ou ISIN")
    if recherche:
        masque = (vue["nom"].str.contains(recherche, case=False, na=False)
                  | vue["isin"].str.contains(recherche.upper(), na=False))
        vue = vue[masque]

    disponibilite = barre.multiselect("Disponibilité", sorted(univers["disponibilite"].unique()))
    if disponibilite:
        vue = vue[vue["disponibilite"].isin(disponibilite)]

    natures = barre.multiselect("Nature", sorted(univers["type_instrument"].unique()), default=["opc", "etf"])
    if natures:
        vue = vue[vue["type_instrument"].isin(natures)]

    classes = barre.multiselect("Grande classe", sorted(univers["grande_classe"].dropna().unique()))
    if classes:
        vue = vue[vue["grande_classe"].isin(classes)]
        types = barre.multiselect("Type d'actif", sorted(vue["type_actif"].dropna().unique()))
        if types:
            vue = vue[vue["type_actif"].isin(types)]

    sfdr = barre.multiselect("Classification SFDR", sorted(univers["sfdr"].dropna().unique()))
    if sfdr:
        vue = vue[vue["sfdr"].isin(sfdr)]

    sri = barre.slider("Indicateur de risque (SRI)", 1, 7, (1, 7))
    vue = vue[vue["sri"].isna() | vue["sri"].between(*sri)]

    plafond = barre.slider("Frais totaux maximum (%)", 0.0, 6.0, 6.0, 0.25)
    if plafond < 6.0:
        vue = vue[vue["frais"] <= plafond]

    if barre.checkbox("Classification fiable uniquement",
                      help="Écarte les supports dont la classe d'actif a été déduite du libellé, "
                           "dont 12 % environ sont mal classés."):
        vue = vue[vue["origine_classification"] != "déduite du libellé"]

    barre.divider()
    barre.caption(f"{len(vue)} instruments sur {len(univers)}")
    return vue


def onglet_univers(vue):
    gauche, milieu, droite = st.columns(3)
    gauche.metric("Instruments", len(vue))
    milieu.metric("Frais totaux médians",
                  "—" if vue["frais"].isna().all() else f"{vue['frais'].median():.2f} %")
    droite.metric("Performance annuelle moyenne, 5 ans",
                  "—" if vue["perf_moyenne"].isna().all() else f"{vue['perf_moyenne'].mean():+.2f} %")

    chiffres = vue.dropna(subset=["frais"])
    if len(chiffres) > 1:
        st.altair_chart(
            alt.Chart(chiffres).mark_bar(color=BLEU, cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
            .encode(
                alt.X("frais:Q", bin=alt.Bin(maxbins=30), title="Frais totaux (%)",
                      axis=alt.Axis(gridColor=GRILLE, labelColor=ENCRE, titleColor=ENCRE,
                                    tickCount=8, format=".1f")),
                alt.Y("count():Q", title="Instruments",
                      axis=alt.Axis(gridColor=GRILLE, labelColor=ENCRE, titleColor=ENCRE)),
                tooltip=[alt.Tooltip("count():Q", title="Instruments"),
                         alt.Tooltip("frais:Q", bin=alt.Bin(maxbins=30), title="Frais totaux")])
            .properties(height=200, title="Répartition des frais dans la sélection")
            .configure_view(strokeWidth=0).configure_title(color=ENCRE, fontSize=14, anchor="start"),
            width="stretch")

    colonnes = {"isin": "ISIN", "nom": "Support", "societe_gestion": "Société de gestion",
                "type_actif": "Type d'actif", "sri": "SRI", "sfdr": "SFDR",
                "frais": "Frais totaux", "perf_moyenne": "Perf. moy. (%/an)", "annees": "Années",
                "disponibilite": "Disponible chez"}
    tableau(vue[list(colonnes)].rename(columns=colonnes), height=420)


def onglet_fiche(vue):
    if vue.empty:
        st.info("Aucun instrument dans la sélection.")
        return
    choix = st.selectbox("Support", vue["isin"] + " — " + vue["nom"], key="fiche")
    isin = choix.split(" — ")[0]
    ligne = univers[univers["isin"] == isin].iloc[0]

    st.subheader(ligne["nom"])
    st.caption(f"`{isin}` · {ligne['societe_gestion'] or 'société non communiquée'} · "
               f"{ligne['type_actif']} · SFDR {ligne['sfdr']} · disponible chez {ligne['disponibilite']}")
    if ligne["origine_classification"] == "déduite du libellé":
        st.warning("Classe d'actif déduite du libellé du support, non confirmée par un référentiel.")

    detail = offres[offres["isin"] == isin]
    st.markdown("**Conditions par assureur**")
    tableau(
        detail[["fournisseur", "contrat", "frais_fonds", "frais_contrat", "frais_totaux_publies",
                "frais_totaux_comparables", "retrocessions", "perf_brute_n1", "perf_nette_n1"]]
        .rename(columns={"fournisseur": "Assureur", "contrat": "Contrat", "frais_fonds": "Frais du fonds",
                         "frais_contrat": "Frais de contrat", "frais_totaux_publies": "Frais totaux publiés",
                         "frais_totaux_comparables": "Frais totaux homogènes",
                         "retrocessions": "Rétrocessions", "perf_brute_n1": "Perf. brute",
                         "perf_nette_n1": "Perf. nette"}))
    if len(detail) == 2 and detail["frais_fonds"].notna().all() \
            and abs(detail["frais_fonds"].iloc[0] - detail["frais_fonds"].iloc[1]) > 0.05:
        st.warning("Les deux assureurs annoncent des frais de fonds différents pour ce même support : "
                   "les frais totaux ne sont pas directement comparables.")

    historique = performances[performances["isin"] == isin].sort_values("annee")
    if historique.empty:
        st.info("Aucun historique de performance pour ce support.")
        return
    st.markdown("**Performance nette annuelle**")
    base = alt.Chart(historique).encode(
        alt.X("annee:O", title=None, axis=alt.Axis(labelColor=ENCRE, labelAngle=0, domainColor=GRILLE)),
        alt.Y("perf_nette:Q", title="Performance nette (%)",
              axis=alt.Axis(gridColor=GRILLE, labelColor=ENCRE, titleColor=ENCRE)))
    barres = base.mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4,
                           cornerRadiusBottomLeft=4, cornerRadiusBottomRight=4, size=38).encode(
        # Paire divergente bleu/rouge : le signe de la performance est la polarite.
        color=alt.condition(alt.datum.perf_nette >= 0, alt.value(BLEU), alt.value(ROUGE)),
        tooltip=[alt.Tooltip("annee:O", title="Année"),
                 alt.Tooltip("perf_nette:Q", title="Performance nette", format="+.2f")])
    # Chaque annee porte sa valeur : cinq barres, aucune raison de la faire chercher.
    etiquettes = base.mark_text(dy=alt.expr(alt.expr.if_(alt.datum.perf_nette >= 0, -8, 14)),
                                color=ENCRE, fontSize=11).encode(text=alt.Text("perf_nette:Q", format="+.1f"))
    ligne_zero = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color=ENCRE, strokeWidth=1).encode(y="y:Q")
    st.altair_chart((barres + ligne_zero + etiquettes).properties(height=260)
                    .configure_view(strokeWidth=0), width="stretch")


def onglet_arbitrage():
    st.markdown("### Le même fonds chez les deux assureurs")
    st.info("Les deux assureurs ne publient pas la même grandeur pour les frais du fonds : "
            "SwissLife paraît donner les charges supportées sur le dernier exercice, BoursoVie les frais "
            "contractuels. Seules les lignes marquées **comparable** autorisent une conclusion tarifaire. "
            "Sur celles-ci, l'écart se réduit à la différence de frais de contrat, 0,96 % contre 0,75 %.")

    fiable = arbitrage[arbitrage["fiabilite"] == "comparable"]
    gauche, milieu, droite = st.columns(3)
    gauche.metric("Fonds communs", len(arbitrage))
    milieu.metric("Dont réellement comparables", len(fiable))
    droite.metric("Écart médian sur ces lignes",
                  "—" if fiable.empty else f"{fiable['ecart'].median():+.2f} pt")

    retenues = st.multiselect("Fiabilité", sorted(arbitrage["fiabilite"].unique()), default=["comparable"])
    vue = arbitrage[arbitrage["fiabilite"].isin(retenues)] if retenues else arbitrage
    tableau(
        vue.rename(columns={"isin": "ISIN", "nom": "Support", "type_actif": "Type d'actif",
                            "frais_swisslife": "Frais SwissLife", "frais_boursorama": "Frais BoursoVie",
                            "ecart": "Écart (pt)", "ecart_frais_fonds": "Écart frais du fonds (pt)",
                            "moins_cher": "Moins cher", "fiabilite": "Fiabilité"})
        .drop(columns=["grande_classe"]), height=420)


def onglet_qualite():
    st.markdown("### Provenance")
    st.dataframe(imports.rename(columns={"fournisseur": "Assureur", "document": "Document",
                                         "empreinte": "Empreinte SHA-256", "millesime": "Millésime",
                                         "importe_le": "Importé le", "lignes": "Lignes"}).drop(columns=["id"]),
                 width="stretch", hide_index=True)

    st.markdown("### Écarts relevés au chargement")
    if anomalies.empty:
        st.success("Aucun écart relevé.")
        return
    resume = (anomalies.groupby(["gravite", "controle"]).size()
              .reset_index(name="Occurrences")
              .rename(columns={"gravite": "Gravité", "controle": "Contrôle"})
              .sort_values("Occurrences", ascending=False))
    st.dataframe(resume, width="stretch", hide_index=True)
    controle = st.selectbox("Détail d'un contrôle", sorted(anomalies["controle"].unique()))
    st.dataframe(anomalies[anomalies["controle"] == controle][["isin", "detail"]]
                 .rename(columns={"isin": "ISIN", "detail": "Détail"}),
                 width="stretch", hide_index=True, height=300)


st.title("Univers d'investissement")
st.caption("SwissLife · BoursoVie — base locale, lecture seule")
selection = filtrer()
univers_tab, fiche_tab, arbitrage_tab, qualite_tab = st.tabs(
    ["Univers", "Fiche", "Arbitrage", "Qualité des données"])
with univers_tab:
    onglet_univers(selection)
with fiche_tab:
    onglet_fiche(selection)
with arbitrage_tab:
    onglet_arbitrage()
with qualite_tab:
    onglet_qualite()
