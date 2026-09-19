"""Interface locale de consultation de l'univers d'investissement.

Lecture seule : l'application n'ecrit jamais dans la base, qui se reconstruit
par construire.bat. Elle affiche les reserves de lecture la ou elles portent,
plutot que de presenter des chiffres incertains comme s'ils ne l'etaient pas.
"""
import os
import sqlite3
import sys

import altair as alt
import pandas as pd
import streamlit as st

from version import DATE, VERSION

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

RACINE = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(RACINE, "data/reference.db")

# Palette de reference, declinaison claire, validee contre la surface #fcfcfb.
ENCRE, ENCRE_DOUCE, GRILLE = "#0b0b0b", "#52514e", "#e6e5e1"
BLEU, ROUGE, GRIS = "#2a78d6", "#e34948", "#c9c8c3"
# Rampe ordinale : plus le risque est eleve, plus la teinte est soutenue. Le pas
# le plus clair reste au-dessus du plancher de contraste de 2:1 sur fond clair.
RAMPE_RISQUE = ["#86b6ef", "#6da7ec", "#5598e7", "#3987e5", "#2a78d6", "#1c5cab", "#104281"]

PAGES = ["Accueil", "Parcourir", "Fiche", "Frais", "Qualité des données"]
ORDRE_CLASSES = ["Monetaire", "Obligataire", "Mixte", "Actions", "ETF",
                 "Actions vives", "Immobilier", "Alternatif", "Autres"]
BANDES_PERF = [("15 % et plus", 15, 999), ("10 à 15 %", 10, 15), ("5 à 10 %", 5, 10),
               ("0 à 5 %", 0, 5), ("négative", -999, 0)]

st.set_page_config(page_title="Univers d'investissement", page_icon="◈", layout="wide")

FORMATS = {
    "Perf. annualisée": "{:+.2f} %", "Perf. N-1": "{:+.2f} %",
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


donnees = charger()
if donnees is None:
    st.error(f"Base introuvable : {BASE}\n\nLancez `construire.bat` pour la créer.")
    st.stop()
univers, performances, arbitrage, offres, anomalies, imports = donnees


MOIS = ["janvier", "février", "mars", "avril", "mai", "juin",
        "juillet", "août", "septembre", "octobre", "novembre", "décembre"]


def en_toutes_lettres(date_iso):
    """'2026-09-19' donne '19 septembre 2026', le premier du mois prenant 'er'."""
    annee, mois, jour = date_iso.split("-")
    quantieme = "1er" if int(jour) == 1 else str(int(jour))
    return f"{quantieme} {MOIS[int(mois) - 1]} {annee}"


def en_tete(titre):
    """Titre de page, suivi de la version et du millesime des documents sources."""
    st.title(titre)
    millesimes = " · ".join(f"{ligne.fournisseur} {en_toutes_lettres(ligne.millesime)}"
                            for ligne in imports.itertuples())
    st.caption(f"Version {VERSION} du {en_toutes_lettres(DATE)}  ·  données {millesimes}")


def aller_a(page, **etat):
    """Change de page depuis un bouton, en preparant l'etat de la page visee."""
    st.session_state["page"] = page
    st.session_state.update(etat)


def classes_ordonnees(cadre):
    presentes = [c for c in ORDRE_CLASSES if c in set(cadre["grande_classe"].dropna())]
    return presentes + sorted(set(cadre["grande_classe"].dropna()) - set(presentes))


# ----------------------------------------------------------------- graphiques

def barres_horizontales(cadre, champ, titre=None, ordre=None, mises_en_avant=None):
    """Effectifs par categorie. Une selection met en avant, le reste s'efface."""
    comptes = cadre[champ].value_counts().rename_axis(champ).reset_index(name="n")
    if ordre:
        comptes[champ] = pd.Categorical(comptes[champ], categories=ordre, ordered=True)
        comptes = comptes.sort_values(champ)
    couleur = (alt.condition(alt.FieldOneOfPredicate(champ, list(mises_en_avant)),
                             alt.value(BLEU), alt.value(GRIS))
               if mises_en_avant else alt.value(BLEU))
    base = alt.Chart(comptes).encode(
        alt.Y(f"{champ}:N", sort=ordre or "-x", title=None,
              axis=alt.Axis(labelColor=ENCRE, labelLimit=260, domainColor=GRILLE, ticks=False,
                            labelOverlap=False, labelPadding=6)),
        alt.X("n:Q", title=None, axis=None))
    barres = base.mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4, height=18).encode(
        color=couleur, tooltip=[alt.Tooltip(f"{champ}:N", title="Catégorie"),
                                alt.Tooltip("n:Q", title="Instruments")])
    valeurs = base.mark_text(align="left", dx=6, color=ENCRE_DOUCE, fontSize=11).encode(text="n:Q")
    hauteur = max(110, 32 * len(comptes))
    graphique = (barres + valeurs).properties(height=hauteur)
    # Altair rejette un titre nul : il n'est pose que s'il existe.
    return graphique.properties(title=titre) if titre else graphique


def barres_risque(cadre):
    """Repartition par indicateur de risque, du plus clair au plus soutenu."""
    comptes = (cadre.dropna(subset=["sri"]).astype({"sri": int})["sri"]
               .value_counts().rename_axis("sri").reset_index(name="n").sort_values("sri"))
    base = alt.Chart(comptes).encode(
        alt.X("sri:O", title="Indicateur de risque (SRI)",
              axis=alt.Axis(labelColor=ENCRE, titleColor=ENCRE_DOUCE, labelAngle=0, domainColor=GRILLE)),
        alt.Y("n:Q", title=None, axis=None))
    barres = base.mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, size=42).encode(
        alt.Color("sri:O", scale=alt.Scale(domain=list(range(1, 8)), range=RAMPE_RISQUE), legend=None),
        tooltip=[alt.Tooltip("sri:O", title="SRI"), alt.Tooltip("n:Q", title="Instruments")])
    valeurs = base.mark_text(dy=-8, color=ENCRE_DOUCE, fontSize=11).encode(text="n:Q")
    return (barres + valeurs).properties(height=210, title="Profil de risque")


def risque_rendement(cadre):
    """Dispersion du rendement annualise a chaque niveau de risque.

    Une boite par niveau plutot qu'un nuage : le SRI est discret, un nuage
    n'afficherait que sept colonnes de points superposes, et c'est la
    dispersion -- pas le detail des points -- qui dit si le risque est paye.
    """
    donnees = cadre.dropna(subset=["sri", "perf_annualisee"]).copy()
    donnees["sri"] = donnees["sri"].astype(int)
    return (alt.Chart(donnees).mark_boxplot(size=34, median={"color": ENCRE}, outliers={"size": 8})
            .encode(
                alt.X("sri:O", title="Indicateur de risque (SRI)",
                      axis=alt.Axis(labelColor=ENCRE, titleColor=ENCRE_DOUCE, labelAngle=0,
                                    domainColor=GRILLE)),
                alt.Y("perf_annualisee:Q", title="Rendement annualisé (%/an)",
                      axis=alt.Axis(gridColor=GRILLE, labelColor=ENCRE, titleColor=ENCRE_DOUCE)),
                alt.Color("sri:O", scale=alt.Scale(domain=list(range(1, 8)), range=RAMPE_RISQUE),
                          legend=None))
            # Marge a gauche : sans elle le titre de l'axe, ecrit a la verticale,
            # deborde du conteneur et se retrouve rogne.
            .properties(height=300, padding={"left": 16, "top": 5, "right": 5, "bottom": 5}))


# --------------------------------------------------------------------- filtres

def barre_laterale():
    barre = st.sidebar
    barre.radio("Navigation", PAGES, key="page", label_visibility="collapsed")
    # L'accueil presente l'univers entier et les deux dernieres pages ont leurs
    # propres selecteurs : les filtres ne s'affichent que la ou ils agissent.
    if st.session_state["page"] in ("Accueil", "Frais", "Qualité des données"):
        return univers
    barre.divider()
    barre.subheader("Filtres")
    vue = univers.copy()

    recherche = barre.text_input("Nom ou ISIN")
    if recherche:
        vue = vue[vue["nom"].str.contains(recherche, case=False, na=False)
                  | vue["isin"].str.contains(recherche.upper(), na=False)]

    natures = barre.multiselect("Nature", sorted(univers["type_instrument"].unique()),
                                default=["opc", "etf"])
    if natures:
        vue = vue[vue["type_instrument"].isin(natures)]

    classes = barre.multiselect("Grande classe", classes_ordonnees(univers), key="classes")
    if classes:
        vue = vue[vue["grande_classe"].isin(classes)]

    sri = barre.slider("Indicateur de risque (SRI)", 1, 7, (1, 7))
    if sri != (1, 7):
        vue = vue[vue["sri"].between(*sri)]

    plancher = barre.slider("Rendement annualisé minimum (%/an)", -20, 20, -20)
    if plancher > -20:
        vue = vue[vue["perf_annualisee"] >= plancher]

    sfdr = barre.multiselect("Classification SFDR", sorted(univers["sfdr"].dropna().unique()))
    if sfdr:
        vue = vue[vue["sfdr"].isin(sfdr)]

    with barre.expander("Frais et fiabilité"):
        plafond = st.slider("Frais totaux maximum (%)", 0.0, 6.0, 6.0, 0.25)
        if plafond < 6.0:
            vue = vue[vue["frais"] <= plafond]
        if st.checkbox("Classification fiable uniquement",
                       help="Écarte les supports dont la classe d'actif a été déduite du libellé, "
                            "dont 12 % environ sont mal classés."):
            vue = vue[vue["origine_classification"] != "déduite du libellé"]

    barre.caption(f"{len(vue)} instruments sur {len(univers)}")
    return vue


# ----------------------------------------------------------------------- pages

def page_accueil(vue):
    en_tete("Univers d'investissement")

    colonnes = st.columns(4)
    colonnes[0].metric("Instruments", f"{len(univers):,}".replace(",", " "))
    colonnes[1].metric("Types d'actif", univers["type_actif"].nunique())
    colonnes[2].metric("Chez les deux assureurs",
                       int((univers["disponibilite"] == "les deux").sum()))
    colonnes[3].metric("Avec 5 ans d'historique", int((univers["annees"] == 5).sum()))

    st.divider()
    gauche, droite = st.columns([3, 2])
    with gauche:
        st.altair_chart(
            barres_horizontales(univers, "grande_classe", "Composition de l'univers",
                                ordre=classes_ordonnees(univers))
            .configure_view(strokeWidth=0).configure_title(color=ENCRE, fontSize=15, anchor="start"),
            width="stretch")
        st.button("Parcourir par classe d'actif", width="stretch",
                  on_click=aller_a, args=("Parcourir",), kwargs={"axe": "Classe d'actif"})
    with droite:
        st.altair_chart(
            barres_risque(univers).configure_view(strokeWidth=0)
            .configure_title(color=ENCRE, fontSize=15, anchor="start"), width="stretch")
        manquants = int(univers["sri"].isna().sum())
        st.caption(f"{manquants} instruments sans SRI : l'indicateur vient des annexes SwissLife, "
                   "les supports présents uniquement chez BoursoVie n'en portent pas.")
        st.button("Parcourir par risque", width="stretch",
                  on_click=aller_a, args=("Parcourir",), kwargs={"axe": "Risque"})

    st.divider()
    st.subheader("Le risque est-il payé ?")
    st.caption("Rendement annualisé sur l'historique disponible, net des frais du fonds, "
               f"pour les {int(univers['perf_annualisee'].notna().sum())} instruments dont la "
               "performance est connue. Chaque boîte couvre la moitié centrale des fonds du niveau, "
               "le trait noir est la médiane.")
    st.altair_chart(risque_rendement(univers).configure_view(strokeWidth=0), width="stretch")
    st.button("Parcourir par performance", on_click=aller_a, args=("Parcourir",),
              kwargs={"axe": "Performance"})


def page_parcourir(vue):
    en_tete("Parcourir l'univers")
    axe = st.segmented_control("Explorer par", ["Classe d'actif", "Risque", "Performance"],
                               key="axe", default="Classe d'actif")
    axe = axe or "Classe d'actif"

    if axe == "Classe d'actif":
        vue = vue.assign(segment=vue["grande_classe"])
        ordre = classes_ordonnees(vue)
        intitule = "Grande classe"
    elif axe == "Risque":
        vue = vue.assign(segment=vue["sri"].map(
            lambda s: f"SRI {int(s)}" if pd.notna(s) else "non renseigné"))
        ordre = [f"SRI {n}" for n in range(1, 8)] + ["non renseigné"]
        intitule = "Niveau de risque"
    else:
        def bande(ligne):
            taux = ligne["perf_annualisee"]
            if pd.isna(taux):
                return "performance inconnue"
            return next(nom for nom, bas, haut in BANDES_PERF if bas <= taux < haut)
        vue = vue.assign(segment=vue.apply(bande, axis=1))
        ordre = [nom for nom, _, _ in BANDES_PERF] + ["performance inconnue"]
        intitule = "Rendement annualisé"

    ordre = [s for s in ordre if s in set(vue["segment"])]
    if not ordre:
        st.info("Aucun instrument dans la sélection.")
        return

    choisis = st.pills(intitule, ordre, selection_mode="multi", key=f"seg_{axe}")
    st.altair_chart(
        barres_horizontales(vue, "segment", ordre=ordre, mises_en_avant=choisis or None)
        .configure_view(strokeWidth=0), width="stretch")

    detail = vue[vue["segment"].isin(choisis)] if choisis else vue
    if axe == "Classe d'actif" and choisis:
        types = st.pills("Type d'actif", sorted(detail["type_actif"].dropna().unique()),
                         selection_mode="multi", key="types")
        if types:
            detail = detail[detail["type_actif"].isin(types)]

    st.caption(f"{len(detail)} instruments")
    # Neuf colonnes tiennent sans troncature ; la société de gestion et la
    # classification SFDR restent consultables sur la fiche du support.
    colonnes = {"isin": "ISIN", "nom": "Support", "type_actif": "Type d'actif", "sri": "SRI",
                "perf_annualisee": "Perf. annualisée", "annees": "Années",
                "perf_n1": "Perf. N-1", "frais": "Frais totaux", "disponibilite": "Disponible"}
    tableau(detail[list(colonnes)].rename(columns=colonnes)
            .sort_values("Perf. annualisée", ascending=False), height=460)


def page_fiche(vue):
    en_tete("Fiche support")
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

    colonnes = st.columns(3)
    colonnes[0].metric("Indicateur de risque",
                       "non renseigné" if pd.isna(ligne["sri"]) else f"{int(ligne['sri'])} / 7")
    colonnes[1].metric(
        "Rendement annualisé",
        "—" if pd.isna(ligne["perf_annualisee"]) else f"{ligne['perf_annualisee']:+.2f} %/an",
        help=None if pd.isna(ligne["annees"]) else f"sur {int(ligne['annees'])} exercice(s)")
    colonnes[2].metric("Frais totaux",
                       "—" if pd.isna(ligne["frais"]) else f"{ligne['frais']:.2f} %")

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


st.session_state.setdefault("page", "Accueil")
selection = barre_laterale()
{"Accueil": page_accueil, "Parcourir": page_parcourir, "Fiche": page_fiche,
 "Frais": page_frais, "Qualité des données": page_qualite}[st.session_state["page"]](selection)
