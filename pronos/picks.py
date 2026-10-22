"""Sélection des paris « value ».

Le backtest sur 2 saisons (voir research.py) a montré que notre modèle de Poisson seul
ne bat PAS le marché. Ce qui a été positif : prendre la probabilité « juste » du consensus
des bookmakers (cote moyenne, marge retirée) et parier quand UN bookmaker propose une cote
nettement au-dessus (il est en retard sur le marché). Le modèle sert d'analyse, pas de signal."""

MIN_EDGE = 0.04      # avantage minimum de 4 %
MAX_EDGE = 0.25      # au-delà, c'est presque toujours une info manquante (blessure, rotation...)
MIN_PROB = 0.25      # on évite les gros outsiders (variance énorme)
MAX_ODDS = 5.0
KELLY_FRACTION = 0.25
MAX_STAKE = 0.03     # jamais plus de 3 % de la bankroll sur un pari
BLEND = 1.0          # poids du consensus du marché dans la probabilité (1.0 = modèle ignoré)
PRICE = "best"       # cote jouée : "avg" moyenne, "max" max du marché, "best" meilleur bookmaker nommé

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


def evaluate(pred, odds, blend=BLEND, min_edge=MIN_EDGE, price=PRICE):
    """Renvoie la liste des paris intéressants pour un match.

    On mélange notre modèle avec le marché (le marché est très bien informé :
    blessures, compositions...). blend = poids donné au marché."""
    mp = market_probs(odds)
    picks = []
    for k in MARKETS:
        o = odds.get(k) if price == "avg" else odds.get(f"{k}_{price}")
        if not o or k not in mp:
            continue
        p = (1 - blend) * pred[k] + blend * mp[k]
        edge = p * o - 1
        if edge < min_edge or edge > MAX_EDGE or p < MIN_PROB or o > MAX_ODDS:
            continue
        kelly = edge / (o - 1)
        stake = min(KELLY_FRACTION * kelly, MAX_STAKE)
        picks.append({"market": k, "label": MARKETS[k], "odds": o, "prob": p,
                      "fair": 1 / p, "edge": edge, "stake": stake,
                      "book": odds.get(k + "_book") if price == "best" else None,
                      "model_prob": pred[k], "avg_odds": odds.get(k)})
    return picks


def confidence(p):
    """Plus d'avantage, et le modèle d'accord avec le pari = plus de confiance."""
    agrees = p["model_prob"] >= p["prob"]
    if p["edge"] >= 0.06 and agrees:
        return "Élevée"
    if p["edge"] >= 0.06 or agrees:
        return "Moyenne"
    return "Faible"
