"""Classement Elo des clubs, calculé à partir des résultats (même méthode que clubelo.com :
bonus selon l'écart de buts, avantage du terrain). Une équipe nouvelle dans un championnat
démarre un peu sous la moyenne de ce championnat."""
from collections import defaultdict

HOME_ADV = 70  # points Elo d'avantage du terrain
K = 20.0


def expected(r_home, r_away):
    return 1 / (1 + 10 ** (-(r_home - r_away + HOME_ADV) / 400))


def compute(history):
    """Renvoie (notes actuelles {ligue: {équipe: elo}}, notes avant chaque match {id(match): (dom, ext)})."""
    ratings = defaultdict(dict)
    pre = {}
    for m in sorted(history, key=lambda m: m.day):
        r = ratings[m.div]
        base = (sum(r.values()) / len(r) - 50) if r else 1500.0
        rh, ra = r.get(m.home, base), r.get(m.away, base)
        pre[id(m)] = (rh, ra)
        res = 1.0 if m.hg > m.ag else 0.5 if m.hg == m.ag else 0.0
        gd = abs(m.hg - m.ag)
        mult = 1 if gd <= 1 else 1.5 if gd == 2 else (11 + gd) / 8
        delta = K * mult * (res - expected(rh, ra))
        r[m.home], r[m.away] = rh + delta, ra - delta
    return ratings, pre


def probs_1x2(r_home, r_away, p_draw):
    """Probabilités 1N2 : nul pris au consensus du marché, le reste partagé selon l'Elo."""
    e = expected(r_home, r_away)
    return {"H": (1 - p_draw) * e, "D": p_draw, "A": (1 - p_draw) * (1 - e)}
