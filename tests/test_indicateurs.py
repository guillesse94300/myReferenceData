"""Les indicateurs sont verifies sur des series construites, puis sur les vraies."""
import datetime
import os
import sqlite3
import sys

RACINE = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(RACINE, "app"))
import indicateurs

COTATIONS = os.path.join(RACINE, "data/cotations.db")


def serie_construite(niveaux):
    depart = datetime.date(2024, 1, 1)
    return {depart + datetime.timedelta(days=i): v for i, v in enumerate(niveaux)}


def test_la_base_cent_conserve_la_trajectoire():
    ramenee = list(indicateurs.base_cent(serie_construite([50, 55, 45])).values())
    # Comparaison approchée : une division puis une multiplication laissent
    # 110,00000000000001 là où l'on attend 110.
    assert all(abs(obtenu - attendu) < 1e-9
               for obtenu, attendu in zip(ramenee, [100, 110, 90]))


def test_une_serie_qui_ne_baisse_jamais_n_a_pas_de_perte():
    assert indicateurs.perte_maximale(serie_construite([100, 110, 120])) == 0


def test_la_perte_se_mesure_depuis_le_sommet_et_non_depuis_le_depart():
    """Partie de 100, montée à 200, redescendue à 150 : la perte est de 25 %."""
    assert abs(indicateurs.perte_maximale(serie_construite([100, 200, 150])) + 25) < 1e-9


def test_le_rendement_annualise_tient_compte_de_la_duree():
    deux_ans = {datetime.date(2024, 1, 1): 100, datetime.date(2026, 1, 1): 121}
    assert abs(indicateurs.rendement_annualise(deux_ans) - 10) < 0.1


def test_une_serie_trop_courte_ne_donne_pas_de_volatilite():
    assert indicateurs.volatilite_annualisee(serie_construite([100, 101, 102])) is None


def test_les_indicateurs_sont_plausibles_sur_les_series_reelles():
    if not os.path.exists(COTATIONS):
        return
    cx = sqlite3.connect(COTATIONS)
    for (isin,) in cx.execute("SELECT DISTINCT isin FROM valeur_liquidative"):
        valeurs = {datetime.date.fromisoformat(d): v for d, v in cx.execute(
            "SELECT date, valeur FROM valeur_liquidative WHERE isin = ?", (isin,))}
        volatilite = indicateurs.volatilite_annualisee(valeurs)
        perte = indicateurs.perte_maximale(valeurs)
        assert 0 < volatilite < 100, f"{isin} : volatilité de {volatilite:.1f} %"
        assert -100 < perte <= 0, f"{isin} : perte maximale de {perte:.1f} %"
    cx.close()
