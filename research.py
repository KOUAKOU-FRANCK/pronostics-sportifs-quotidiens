"""Réglage des paramètres : python research.py (affiche les résultats dans le terminal).
On règle sur l'avant-dernière année et on vérifie sur la dernière, pour ne pas se tromper soi-même."""
import os
from datetime import date, timedelta

from pronos import backtest, data

ROOT = os.path.dirname(os.path.abspath(__file__))
cache = os.path.join(ROOT, ".cache")
today = date.today()

fx_path = os.path.join(cache, "fixtures.csv")
data.load_fixtures(cache)
if os.path.exists(fx_path):
    raw = open(fx_path, encoding="utf-8-sig", errors="replace").read()
    print("fixtures.csv :", len(raw), "octets")
    print(raw[:700])
    fx = data.parse_csv(raw)
    print("lignes lues :", len(fx), "| ligues :", sorted({m.div for m in fx}),
          "| dates :", sorted({m.day.isoformat() for m in fx})[:10])

history = data.load_history(today, cache, seasons=4)
print(len(history), "matchs historiques")
# blend=1.0 : on ignore le modèle et on cherche seulement les bookmakers en retard sur le consensus
grid = [{"blend": b, "min_edge": e, "use_max": True}
        for b in (0.35, 0.9, 1.0) for e in (0.02, 0.03, 0.04, 0.06, 0.08)]
for label, end in (("RÉGLAGE (il y a 2 ans -> 1 an)", today - timedelta(days=365)),
                   ("VALIDATION (12 derniers mois)", today)):
    print("\n==", label)
    for g, r in zip(grid, backtest.run(history, end, grid=grid)):
        if r["n"]:
            print(f"max={g['use_max']!s:5} blend={g['blend']:.2f} edge>={g['min_edge']:.2f}  "
                  f"n={r['n']:5}  réussite={r['hit_rate']:.3f}  cote={r['avg_odds']:.2f}  "
                  f"ROI={r['roi_flat'] * 100:+.1f}%  ROI kelly={r['roi_kelly'] * 100:+.1f}%")
