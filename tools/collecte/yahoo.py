"""Lecture d'une serie de valeurs liquidatives servie par Yahoo Finance.

La reponse porte une suite d'horodatages et les cloture correspondantes, avec
des trous : jours feries de la place, et surtout absence frequente du
31 decembre. Les valeurs nulles sont ecartees plutot que comblees -- inventer
une valeur fausserait la volatilite.
"""
import datetime
import json


def _resultat(charge):
    """Premier resultat de la reponse, ou None si elle n'en est pas une.

    Le dossier de captures contient aussi les reponses d'autres sondes, qui ne
    suivent pas cette forme : mieux vaut les ignorer que lever une exception.
    """
    try:
        charge_lue = json.loads(charge)
    except (TypeError, ValueError):
        return None
    if not isinstance(charge_lue, dict):
        return None
    resultats = (charge_lue.get("chart") or {}).get("result") or []
    return resultats[0] if resultats else None


def metadonnees(charge):
    resultat = _resultat(charge)
    return resultat.get("meta", {}) if resultat else {}


def serie(charge):
    """{date: valeur}, dans la devise de cotation, trous exclus."""
    resultat = _resultat(charge)
    if not resultat:
        return {}
    horodatages = resultat.get("timestamp") or []
    clotures = (resultat.get("indicators", {}).get("quote") or [{}])[0].get("close") or []
    return {datetime.date.fromtimestamp(h): v
            for h, v in zip(horodatages, clotures) if v is not None}


def performance_annuelle(valeurs, annee):
    """Performance civile, de la derniere seance de N-1 a la derniere de N.

    Elle ne coincide pas exactement avec celle que publie l'assureur : celui-ci
    arrete au 31 decembre, date souvent absente de la serie. L'ecart qui en
    resulte vaut un a deux mouvements quotidiens du fonds -- negligeable sur un
    fonds obligataire, sensible sur un fonds aurifere.
    """
    debut = [d for d in valeurs if d.year == annee - 1]
    fin = [d for d in valeurs if d.year == annee]
    if not debut or not fin:
        return None
    return (valeurs[max(fin)] / valeurs[max(debut)] - 1) * 100


def volatilite_quotidienne(valeurs):
    """Ecart-type des rendements journaliers, en pourcentage."""
    dates = sorted(valeurs)
    if len(dates) < 30:
        return None
    rendements = [(valeurs[dates[i]] / valeurs[dates[i - 1]] - 1) * 100
                  for i in range(1, len(dates))]
    moyenne = sum(rendements) / len(rendements)
    return (sum((r - moyenne) ** 2 for r in rendements) / len(rendements)) ** 0.5
