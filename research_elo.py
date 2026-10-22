"""Test : la force Elo des clubs (clubelo.com) améliore-t-elle la stratégie ?

On compare, sur l'avant-dernière année (réglage) et les 12 derniers mois (validation) :
- la stratégie actuelle (consensus du marché vs meilleure cote) ;
- la même avec une part w de probabilité Elo mélangée au consensus ;
- la stratégie actuelle filtrée : seulement quand l'Elo est d'accord avec le pari.
Les notes Elo utilisées sont celles publiées AVANT chaque période de matchs."""
import csv
import difflib
import io
import os
import re
import time
import urllib.request
from collections import defaultdict
from datetime import date, timedelta

from pronos import data
from pronos.backtest import summarize, won
from pronos.picks import evaluate, market_probs

ROOT = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(ROOT, ".cache", "elo")
COUNTRY = {"E0": "ENG", "E1": "ENG", "E2": "ENG", "E3": "ENG", "EC": "ENG", "SC0": "SCO",
           "SC1": "SCO", "D1": "GER", "D2": "GER", "I1": "ITA", "I2": "ITA", "SP1": "ESP",
           "SP2": "ESP", "F1": "FRA", "F2": "FRA", "N1": "NED", "B1": "BEL", "P1": "POR",
           "T1": "TUR", "G1": "GRE"}
HOME_ADV = 70  # points Elo d'avantage du terrain
# noms football-data -> noms Club Elo quand la ressemblance ne suffit pas
ALIASES = {"Ath Madrid": "Atletico", "Ath Bilbao": "Bilbao", "Espanol": "Espanyol",
           "Sp Lisbon": "Sporting", "Sp Braga": "Braga", "Vallecano": "Rayo Vallecano",
           "Inter": "Inter", "Milan": "Milan", "Nott'm Forest": "Forest", "Bayern Munich": "Bayern",
           "M'gladbach": "Gladbach", "Ein Frankfurt": "Frankfurt", "FC Koln": "Koeln",
           "St Etienne": "Saint-Etienne", "Paris SG": "Paris SG", "Celta": "Celta",
           "La Coruna": "Depor", "Sociedad": "Sociedad"}


def snapshot(d):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, f"{d.isoformat()}.csv")
    if not os.path.exists(path):
        for attempt in range(3):
            try:
                with urllib.request.urlopen(f"http://api.clubelo.com/{d.isoformat()}", timeout=60) as r:
                    open(path, "wb").write(r.read())
                break
            except Exception as e:
                print(f"[elo] {d} essai {attempt + 1} : {e}")
                time.sleep(3)
        time.sleep(0.5)
    if not os.path.exists(path):
        return {}
    out = defaultdict(dict)
    for row in csv.DictReader(io.StringIO(open(path, encoding="utf-8", errors="replace").read())):
        try:
            out[row["Country"]][row["Club"]] = float(row["Elo"])
        except (KeyError, ValueError):
            pass
    return out


def norm(s):
    s = s.lower().replace("&", "and")
    s = re.sub(r"\b(fc|cf|ac|afc|sc|sv|vfb|vfl|fsv|tsg|rc|cd|ud|sd|ss|us|as|sk|fk|bk)\b", "", s)
    return re.sub(r"[^a-z0-9]", "", s)


class Matcher:
    def __init__(self):
        self.cache = {}
        self.missing = set()

    def find(self, team, clubs):
        key = (team, tuple(sorted(clubs))[:3])
        if key in self.cache:
            return self.cache[key]
        if ALIASES.get(team) in clubs:
            self.cache[key] = ALIASES[team]
            return ALIASES[team]
        n = norm(team)
        by_norm = {norm(c): c for c in clubs}
        hit = by_norm.get(n)
        if not hit:
            cand = difflib.get_close_matches(n, list(by_norm), n=1, cutoff=0.75)
            if not cand:  # préfixe : "Nott'm Forest" -> "Forest", "Man City" -> "ManCity"
                cand = [k for k in by_norm if k and (n.startswith(k) or k.startswith(n) or k in n)]
            hit = by_norm[cand[0]] if len(cand) == 1 else None  # ambigu -> on s'abstient
        if not hit and team not in self.missing:
            self.missing.add(team)
        self.cache[key] = hit
        return hit


def run(history, end, grid, days=365, step=7):
    start = end - timedelta(days=days)
    bets = {name: [] for name in grid}
    matcher, matched, total = Matcher(), 0, 0
    cursor = start
    while cursor < end:
        nxt = cursor + timedelta(days=step)
        window = [m for m in history if cursor <= m.day < nxt]
        elo = snapshot(cursor - timedelta(days=1)) if window else {}
        cursor = nxt
        for m in window:
            clubs = elo.get(COUNTRY.get(m.div, ""), {})
            mp = market_probs(m.odds)
            if "H" not in mp:
                continue
            total += 1
            h, a = matcher.find(m.home, clubs), matcher.find(m.away, clubs)
            if not (h and a):
                continue
            matched += 1
            e = 1 / (1 + 10 ** (-(clubs[h] - clubs[a] + HOME_ADV) / 400))
            elo_p = {"H": (1 - mp["D"]) * e, "D": mp["D"], "A": (1 - mp["D"]) * (1 - e),
                     "O25": mp.get("O25", 0), "U25": mp.get("U25", 0)}
            for name, (w, edge, filt) in grid.items():
                for p in evaluate(elo_p, m.odds, blend=1 - w, min_edge=edge):
                    if p["market"] not in ("H", "D", "A"):
                        continue
                    agree = elo_p[p["market"]] >= mp[p["market"]]
                    if filt == "accord" and not agree or filt == "désaccord" and agree:
                        continue
                    bets[name].append({"market": p["market"], "odds": p["odds"], "stake": p["stake"],
                                       "profit": (p["odds"] - 1) if won(p["market"], m) else -1.0})
    print(f"  équipes trouvées dans Club Elo : {matched}/{total} matchs ({matched / max(total, 1):.0%})")
    print("  non trouvées :", ", ".join(sorted(matcher.missing))[:1500])
    return {name: summarize(b) for name, b in bets.items()}


def main():
    today = date.today()
    history = data.load_history(today, os.path.join(ROOT, ".cache"), seasons=4)
    print(len(history), "matchs historiques")
    grid = {}
    for edge in (0.02, 0.04):
        grid[f"actuel        edge>={edge}"] = (0.0, edge, None)
        grid[f"actuel+accord edge>={edge}"] = (0.0, edge, "accord")
        grid[f"actuel-désacc edge>={edge}"] = (0.0, edge, "désaccord")
        for w in (0.2, 0.4, 0.6):
            grid[f"elo w={w}     edge>={edge}"] = (w, edge, None)
    for label, end in (("RÉGLAGE (il y a 2 ans -> 1 an)", today - timedelta(days=365)),
                       ("VALIDATION (12 derniers mois)", today)):
        print("\n==", label, "(1N2 uniquement)")
        for name, r in run(history, end, grid).items():
            if r["n"]:
                print(f"{name}  n={r['n']:4}  réussite={r['hit_rate']:.3f}  cote={r['avg_odds']:.2f}  "
                      f"ROI={r['roi_flat'] * 100:+.1f}%  ROI kelly={r['roi_kelly'] * 100:+.1f}%")
            else:
                print(f"{name}  aucun pari")


if __name__ == "__main__":
    main()
