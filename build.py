"""Point d'entrée : python build.py  ->  docs/index.html"""
import argparse
import json
import os
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from pronos import backtest, data, site
from pronos.model import PoissonModel
from pronos.picks import evaluate

ROOT = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=3, help="horizon des matchs à venir")
    ap.add_argument("--no-backtest", action="store_true")
    ap.add_argument("--cache", default=os.path.join(ROOT, ".cache"))
    args = ap.parse_args()

    today = date.today()
    history = data.load_history(today, args.cache)
    fixtures = [f for f in data.load_fixtures(args.cache)
                if today <= f.day <= today + timedelta(days=args.days)]
    print(f"{len(history)} matchs historiques, {len(fixtures)} matchs à venir")

    by_div = defaultdict(list)
    for m in history:
        by_div[m.div].append(m)
    models = {div: PoissonModel().fit(ms, today) for div, ms in by_div.items()}

    rows = []
    for f in fixtures:
        model = models.get(f.div)
        if not model:
            continue
        pred = model.predict(f.home, f.away)
        rows.append({"match": f, "pred": pred, "picks": evaluate(pred, f.odds)})

    bt = {"n": 0} if args.no_backtest else backtest.run(history, today)
    out_dir = os.path.join(ROOT, "docs")
    os.makedirs(out_dir, exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(site.render(today, rows, bt, now))
    with open(os.path.join(out_dir, "picks.json"), "w", encoding="utf-8") as fh:
        json.dump([{"date": r["match"].day.isoformat(), "league": r["match"].div,
                    "home": r["match"].home, "away": r["match"].away, **p}
                   for r in rows for p in r["picks"]], fh, ensure_ascii=False, indent=1)
    print(f"{sum(len(r['picks']) for r in rows)} paris retenus · backtest: {bt}")


if __name__ == "__main__":
    main()
