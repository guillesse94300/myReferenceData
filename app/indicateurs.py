"""Indicateurs calcules a partir d'une serie de valeurs liquidatives.

Tout est calcule dans la devise du support. Convertir melangerait la
performance du fonds et le mouvement de la devise, alors que ces indicateurs
servent precisement a juger le fonds seul.
"""
import math

SEANCES_PAR_AN = 252


def rendements(valeurs):
    """Rendements d'une seance a l'autre, en pourcentage."""
    dates = sorted(valeurs)
    return [(valeurs[dates[i]] / valeurs[dates[i - 1]] - 1) * 100
            for i in range(1, len(dates)) if valeurs[dates[i - 1]]]


def base_cent(valeurs):
    """Serie ramenee a 100 au premier point.

    Les valeurs liquidatives brutes vont de quelques euros a plusieurs
    centaines : leur niveau n'a aucun sens en soi, seule leur trajectoire en a.
    """
    dates = sorted(valeurs)
    if not dates:
        return {}
    depart = valeurs[dates[0]]
    return {d: valeurs[d] / depart * 100 for d in dates}


def volatilite_annualisee(valeurs):
    """Ecart-type des rendements quotidiens, ramene a l'annee."""
    quotidiens = rendements(valeurs)
    if len(quotidiens) < 30:
        return None
    moyenne = sum(quotidiens) / len(quotidiens)
    ecart = math.sqrt(sum((r - moyenne) ** 2 for r in quotidiens) / len(quotidiens))
    return ecart * math.sqrt(SEANCES_PAR_AN)


def courbe_de_perte(valeurs):
    """Ecart a chaque date par rapport au plus haut atteint jusque-la, en pourcentage.

    Toujours negatif ou nul : c'est la perte qu'aurait subie quelqu'un entre au
    plus mauvais moment precedent.
    """
    sommet, courbe = None, {}
    for date in sorted(valeurs):
        sommet = valeurs[date] if sommet is None else max(sommet, valeurs[date])
        courbe[date] = (valeurs[date] / sommet - 1) * 100
    return courbe


def perte_maximale(valeurs):
    """La plus forte baisse depuis un sommet, en pourcentage."""
    courbe = courbe_de_perte(valeurs)
    return min(courbe.values()) if courbe else None


def rendement_annualise(valeurs):
    """Rendement annualise sur toute la periode couverte, en pourcentage."""
    dates = sorted(valeurs)
    if len(dates) < 2:
        return None
    annees = (dates[-1] - dates[0]).days / 365.25
    if annees <= 0 or not valeurs[dates[0]]:
        return None
    return ((valeurs[dates[-1]] / valeurs[dates[0]]) ** (1 / annees) - 1) * 100
