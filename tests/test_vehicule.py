"""L'axe vehicule : ce que le support est, non ce dans quoi il investit.

La classification est verifiee sur la base reelle, parce que sa propriete
essentielle -- etre exhaustive et sans recouvrement -- ne se demontre pas sur
un echantillon construit : elle porte sur les 1 378 lignes ou nulle part.
"""
import os
import sqlite3

import pytest

RACINE = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(RACINE, "data/reference.db")
ORDRE = ["Fond UC", "ETF", "Actions", "FCPE", "SCPI", "Livret"]

pytestmark = pytest.mark.skipif(not os.path.exists(BASE),
                                reason="base absente : lancer construire.bat")


@pytest.fixture(scope="module")
def cx():
    connexion = sqlite3.connect(BASE)
    connexion.row_factory = sqlite3.Row
    yield connexion
    connexion.close()


def test_chaque_instrument_a_un_vehicule(cx):
    orphelins = cx.execute("SELECT COUNT(*) FROM v_univers WHERE vehicule IS NULL").fetchone()[0]
    assert orphelins == 0


def test_les_vehicules_somment_a_l_univers(cx):
    total = cx.execute("SELECT COUNT(*) FROM instrument").fetchone()[0]
    par_vehicule = dict(cx.execute("SELECT vehicule, COUNT(*) FROM v_univers GROUP BY 1"))
    assert sum(par_vehicule.values()) == total


def test_aucun_vehicule_hors_de_la_liste(cx):
    connus = {l["vehicule"] for l in cx.execute("SELECT DISTINCT vehicule FROM v_univers")}
    assert connus <= set(ORDRE), f"véhicule imprévu : {connus - set(ORDRE)}"


def test_un_etf_reste_un_etf_meme_hors_contrat(cx):
    """L'ETF loge en PEA n'est offert par aucun assureur, il reste un ETF."""
    ligne = cx.execute("SELECT vehicule, disponibilite FROM v_univers "
                       "WHERE isin = 'FR001400U5Q4'").fetchone()
    assert ligne["disponibilite"] == "hors contrats"
    assert ligne["vehicule"] == "ETF"


def test_un_fonds_de_pee_est_un_fcpe(cx):
    ligne = cx.execute("SELECT vehicule FROM v_univers WHERE isin = 'FR001400R849'").fetchone()
    assert ligne["vehicule"] == "FCPE"


def test_un_support_hors_contrat_sans_pee_tombe_en_scpi(cx):
    ligne = cx.execute("SELECT vehicule FROM v_univers WHERE isin = 'FR00140001C5'").fetchone()
    assert ligne["vehicule"] == "SCPI"


def test_les_actions_en_direct_ne_sont_pas_des_fonds(cx):
    melange = cx.execute("SELECT COUNT(*) FROM v_univers "
                         "WHERE type_instrument = 'action' AND vehicule <> 'Actions'").fetchone()[0]
    assert melange == 0


def test_un_fond_uc_est_toujours_offert_par_un_assureur(cx):
    """« Fond UC » dit que le support s'achete dans l'un des contrats."""
    fantomes = cx.execute("SELECT COUNT(*) FROM v_univers "
                          "WHERE vehicule = 'Fond UC' AND disponibilite = 'hors contrats'"
                          ).fetchone()[0]
    assert fantomes == 0
