"""Backtest honnête : on rejoue la stratégie sur les matchs passés,
en n'utilisant que les données disponibles AVANT chaque match."""
from collections import defaultdict
from datetime import timedelta

from .model import PoissonModel
from .picks import evaluate


def won(market, m):
    t = m.hg + m.ag
    return {"H": m.hg > m.ag, "D": m.hg == m.ag, "A": m.hg < m.ag,
            "O25": t > 2, "U25": t <= 2}[market]


def run(history, today, days=365, refit_every=14):
    by_div = defaultdict(list)
    for m in history:
        by_div[m.div].append(m)
    start = today - timedelta(days=days)
    bets = []
    for div, ms in by_div.items():
        ms.sort(key=lambda m: m.day)
        cursor = start
        while cursor < today:
            nxt = cursor + timedelta(days=refit_every)
            window = [m for m in ms if cursor <= m.day < nxt]
            past = [m for m in ms if m.day < cursor]
            cursor = nxt
            if not window or len(past) < 150:
                continue
            model = PoissonModel().fit(past, window[0].day, iters=25)
            for m in window:
                for p in evaluate(model.predict(m.home, m.away), m.odds):
                    profit = (p["odds"] - 1) if won(p["market"], m) else -1.0
                    bets.append({"div": div, "market": p["market"], "odds": p["odds"],
                                 "stake": p["stake"], "profit": profit})
    return summarize(bets)


def summarize(bets):
    n = len(bets)
    if not n:
        return {"n": 0}
    wins = sum(b["profit"] > 0 for b in bets)
    flat = sum(b["profit"] for b in bets)
    staked = sum(b["stake"] for b in bets)
    kelly = sum(b["stake"] * b["profit"] for b in bets)
    per_market = defaultdict(lambda: [0, 0.0])
    for b in bets:
        per_market[b["market"]][0] += 1
        per_market[b["market"]][1] += b["profit"]
    return {
        "n": n,
        "hit_rate": wins / n,
        "avg_odds": sum(b["odds"] for b in bets) / n,
        "roi_flat": flat / n,
        "roi_kelly": kelly / staked if staked else 0.0,
        "per_market": {k: {"n": v[0], "roi": v[1] / v[0]} for k, v in per_market.items()},
    }
