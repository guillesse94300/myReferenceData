"""Le lecteur de series est verifie contre les reponses reellement capturees."""
import glob
import json
import os
import sys

RACINE = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(RACINE, "tools"))
from collecte import yahoo

HISTORIQUES = os.path.join(RACINE, "data/raw/captures/historiques")


def charges():
    return {os.path.basename(c).split("__")[0]: open(c, encoding="utf-8").read()
            for c in sorted(glob.glob(os.path.join(HISTORIQUES, "*__yahoo_chart.json")))}


def test_les_series_couvrent_cinq_ans():
    """Douze des quatorze supports livrent cinq ans de séances, deux aucune.

    Le nombre de séances varie d'un fonds à l'autre : 978 pour un fonds
    luxembourgeois dont la valeur n'est pas publiée tous les jours ouvrés,
    1 280 pour un tracker coté. L'étendue varie aussi : neuf séries remontent à
    septembre 2021, trois fonds luxembourgeois s'arrêtent à mars 2022. Le seuil
    retient donc le moins-disant, quatre ans et demi.
    """
    fournies = {i: yahoo.serie(c) for i, c in charges().items()}
    assert fournies, "aucune capture d'historique"
    exploitables = {i: v for i, v in fournies.items() if len(v) > 900}
    assert len(exploitables) == 12, f"{len(exploitables)} séries exploitables au lieu de 12"
    for isin, valeurs in exploitables.items():
        etendue = (max(valeurs) - min(valeurs)).days
        assert etendue > 1600, f"{isin} ne couvre que {etendue} jours"


def test_les_deux_supports_sans_serie_sont_ceux_resolus_vers_une_place():
    """Fidelity China et Pictet : Yahoo n'a renvoyé qu'une cotation de place.

    Ces deux-là avaient été résolus vers FJRH.F et PBFW.MU, des cotations
    secondaires quasi sans échanges, au lieu d'un identifiant Morningstar.
    """
    vides = {i for i, c in charges().items() if len(yahoo.serie(c)) < 10}
    assert vides == {"LU0173614495", "LU0503631987"}


def test_les_trous_sont_ecartes_et_non_combles():
    for charge in charges().values():
        brut = json.loads(charge)["chart"]["result"][0]
        nuls = sum(1 for v in brut["indicators"]["quote"][0]["close"] or [] if v is None)
        assert len(yahoo.serie(charge)) == len(brut.get("timestamp") or []) - nuls


def test_un_fonds_est_identifie_comme_tel():
    meta = yahoo.metadonnees(charges()["FR0013332418"])
    assert meta["instrumentType"] == "MUTUALFUND"
    assert meta["currency"] == "EUR"


def test_la_performance_annuelle_se_calcule_sur_les_bornes_disponibles():
    valeurs = yahoo.serie(charges()["FR0013332418"])
    # Fonds obligataire peu volatil : la borne manquante du 31 décembre y coûte
    # moins d'un centième de point, la concordance doit donc être exacte.
    assert abs(yahoo.performance_annuelle(valeurs, 2024) - 8.80) < 0.05
    assert yahoo.performance_annuelle(valeurs, 2015) is None
