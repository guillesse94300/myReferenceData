"""Indicateurs calcules a partir d'une serie de valeurs liquidatives.

Tout est calcule dans la devise du support. Convertir melangerait la
performance du fonds et le mouvement de la devise, alors que ces indicateurs
servent precisement a juger le fonds seul.
"""
import datetime
import math

SEANCES_PAR_AN = 252

# Periodes glissantes affichees, en mois.
GLISSANTES = (3, 6, 12, 24)


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


def valeur_au(valeurs, cible):
    """Derniere valeur connue a la date visee, ou avant.

    Une valeur liquidative n'est pas publiee tous les jours : viser une date
    exacte echouerait un jour sur trois. On prend donc la derniere connue.
    """
    anterieures = [d for d in valeurs if d <= cible]
    return valeurs[max(anterieures)] if anterieures else None


def performance_entre(valeurs, debut, fin):
    """Performance cumulee entre deux dates, en pourcentage."""
    depart, arrivee = valeur_au(valeurs, debut), valeur_au(valeurs, fin)
    if not depart or arrivee is None:
        return None
    return (arrivee / depart - 1) * 100


def _recule_de_mois(date, mois):
    """Meme quantieme, `mois` mois plus tot, ramene au dernier jour du mois si besoin."""
    annee, rang = divmod(date.month - 1 - mois, 12)
    jour = min(date.day, [31, 29 if (date.year + annee) % 4 == 0 else 28, 31, 30, 31, 30,
                          31, 31, 30, 31, 30, 31][rang])
    return datetime.date(date.year + annee, rang + 1, jour)


def performances_usuelles(valeurs):
    """Performances de reference d'un support, toutes cumulees et non annualisees.

    Le dernier exercice civil complet, le depuis-le-1er-janvier, puis les
    periodes glissantes. Une periode que l'historique ne couvre pas rend None
    plutot qu'un chiffre calcule sur une fenetre tronquee, qui serait faux.
    """
    if not valeurs:
        return {}
    dernier = max(valeurs)
    debut_serie = min(valeurs)
    exercice = dernier.year - 1

    mesures = {}
    fin_precedente = datetime.date(exercice - 1, 12, 31)
    if debut_serie <= fin_precedente:
        mesures[str(exercice)] = performance_entre(
            valeurs, fin_precedente, datetime.date(exercice, 12, 31))
    else:
        mesures[str(exercice)] = None

    debut_annee = datetime.date(dernier.year - 1, 12, 31)
    mesures["depuis le 1er janvier"] = (performance_entre(valeurs, debut_annee, dernier)
                                        if debut_serie <= debut_annee else None)

    for mois in GLISSANTES:
        depart = _recule_de_mois(dernier, mois)
        mesures[f"{mois} mois"] = (performance_entre(valeurs, depart, dernier)
                                   if debut_serie <= depart else None)
    return mesures
