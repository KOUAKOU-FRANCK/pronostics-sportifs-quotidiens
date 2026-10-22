"""Sélection des paris « value » : on parie seulement quand notre probabilité
est nettement supérieure à celle implicite dans la cote du marché."""

MIN_EDGE = 0.05      # avantage minimum de 5 %
MAX_EDGE = 0.25      # au-delà, c'est presque toujours une info manquante (blessure, rotation...)
MIN_PROB = 0.25      # on évite les gros outsiders (variance énorme)
MAX_ODDS = 5.0
KELLY_FRACTION = 0.25
MAX_STAKE = 0.03     # jamais plus de 3 % de la bankroll sur un pari

MARKETS = {
    "H": "Victoire domicile", "D": "Match nul", "A": "Victoire extérieur",
    "O25": "Plus de 2,5 buts", "U25": "Moins de 2,5 buts",
}


def market_probs(odds):
    """Probabilités implicites du marché, marge du bookmaker retirée."""
    out = {}
    for group in (("H", "D", "A"), ("O25", "U25")):
        if all(odds.get(k) for k in group):
            inv = {k: 1 / odds[k] for k in group}
            s = sum(inv.values())
            out.update({k: v / s for k, v in inv.items()})
    return out


def evaluate(pred, odds, blend=0.35):
    """Renvoie la liste des paris intéressants pour un match.

    On mélange notre modèle avec le marché (le marché est très bien informé :
    blessures, compositions...). blend = poids donné au marché."""
    mp = market_probs(odds)
    picks = []
    for k in MARKETS:
        o = odds.get(k)
        if not o or k not in mp:
            continue
        p = (1 - blend) * pred[k] + blend * mp[k]
        edge = p * o - 1
        if edge < MIN_EDGE or edge > MAX_EDGE or p < MIN_PROB or o > MAX_ODDS:
            continue
        kelly = edge / (o - 1)
        stake = min(KELLY_FRACTION * kelly, MAX_STAKE)
        picks.append({"market": k, "label": MARKETS[k], "odds": o, "prob": p,
                      "fair": 1 / p, "edge": edge, "stake": stake})
    return picks


def confidence(p):
    edge, prob = p["edge"], p["prob"]
    if edge >= 0.10 and prob >= 0.45:
        return "Élevée"
    if edge >= 0.07 or prob >= 0.5:
        return "Moyenne"
    return "Faible"
