"""L'amorcage des favoris : le CSV est local, la semence est versionnee."""
import os
import sys

RACINE = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(RACINE, "app"))
import favoris


def isoler(tmp_path, monkeypatch, semence=None):
    """Detourne le module vers un dossier jetable, avec ou sans semence."""
    csv_local = tmp_path / "favoris.csv"
    fichier_semence = tmp_path / "favorites.txt"
    if semence is not None:
        fichier_semence.write_text(semence, encoding="utf-8")
    monkeypatch.setattr(favoris, "FICHIER", str(csv_local))
    monkeypatch.setattr(favoris, "SEMENCE", str(fichier_semence))
    return csv_local


SEMENCE = ("Fonds\tISIN\tDétenu dans\n"
           "Claresco USA P\tLU1379103812\tPER Gilles\n"
           "Amundi Label Monétaire ESR-F\t990000107137\tPEE\n")


def test_le_csv_absent_est_amorce_depuis_la_semence(tmp_path, monkeypatch):
    csv_local = isoler(tmp_path, monkeypatch, SEMENCE)
    suivis = favoris.charger()
    assert list(suivis) == ["LU1379103812"]
    assert suivis["LU1379103812"]["note"] == "PER Gilles"
    assert csv_local.exists(), "l'amorcage doit etre ecrit, pas recalcule a chaque appel"


def test_la_ligne_sans_isin_est_ignoree(tmp_path, monkeypatch):
    isoler(tmp_path, monkeypatch, SEMENCE)
    assert "990000107137" not in favoris.charger()


def test_une_liste_videe_a_la_main_n_est_pas_ressuscitee(tmp_path, monkeypatch):
    csv_local = isoler(tmp_path, monkeypatch, SEMENCE)
    csv_local.write_text("isin,ajoute_le,note\n", encoding="utf-8")
    assert favoris.charger() == {}


def test_le_csv_existant_prime_sur_la_semence(tmp_path, monkeypatch):
    csv_local = isoler(tmp_path, monkeypatch, SEMENCE)
    csv_local.write_text("isin,ajoute_le,note\nFR0000000000,2026-01-01,ajout local\n",
                         encoding="utf-8")
    assert list(favoris.charger()) == ["FR0000000000"]


def test_sans_semence_la_liste_part_vide(tmp_path, monkeypatch):
    csv_local = isoler(tmp_path, monkeypatch)
    assert favoris.charger() == {}
    assert not csv_local.exists(), "rien a amorcer ne doit pas creer de fichier"


def test_appliquer_ne_touche_pas_aux_supports_hors_ecran(tmp_path, monkeypatch):
    csv_local = isoler(tmp_path, monkeypatch)
    csv_local.write_text("isin,ajoute_le,note\n"
                         "FR0000000001,2026-01-01,garde\n"
                         "FR0000000002,2026-01-01,retire\n", encoding="utf-8")
    suivis, modifie = favoris.appliquer(["FR0000000002", "FR0000000003"], {"FR0000000003"})
    assert modifie
    assert set(suivis) == {"FR0000000001", "FR0000000003"}
