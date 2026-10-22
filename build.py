"""Point d'entrée : python build.py  ->  docs/index.html"""
import argparse
import json
import os
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from pronos import backtest, data, elo, journal, oddsapi, site
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

    ratings, _ = elo.compute(history)
    rows = []
    for f in fixtures:
        model = models.get(f.div)
        if not model:
            continue
        pred = model.predict(f.home, f.away)
        picks = evaluate(pred, f.odds)
        r = ratings.get(f.div, {})
        if f.home in r and f.away in r:
            for p in picks:
                if p["market"] in ("H", "D", "A") and p.get("market_draw") is not None:
                    pe = elo.probs_1x2(r[f.home], r[f.away], p["market_draw"])[p["market"]]
                    p["elo_prob"] = pe
                    # test sur 2 saisons : les paris où l'Elo est en DÉSACCORD ont mieux marché
                    # (petit échantillon, à confirmer par le journal)
                    p["elo_agree"] = pe >= p["prob"]
        rows.append({"match": f, "pred": pred, "picks": picks})

    out_dir = os.path.join(ROOT, "docs")
    os.makedirs(out_dir, exist_ok=True)
    jpath = os.path.join(out_dir, "journal.json")
    entries = journal.load(jpath)
    journal.add_football(entries, rows)
    journal.settle_football(entries, history)

    # autres sports : seulement si la clé The Odds API est configurée (secret ODDS_API_KEY)
    others = []
    key = os.environ.get("ODDS_API_KEY", "").strip()
    if key:
        client = oddsapi.Client(key)
        for sport_key in journal.pending_sports(entries):
            journal.settle_other(entries, sport_key, oddsapi.fetch_scores(client, sport_key))
        others = oddsapi.fetch_picks(client)
        journal.add_other(entries, others)
    else:
        print("[oddsapi] pas de clé ODDS_API_KEY : autres sports désactivés")
    journal.save(jpath, entries)

    bt = {"n": 0} if args.no_backtest else backtest.run(history, today)
    now = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(site.render(today, rows, bt, now, others=others, entries=entries,
                             odds_api=bool(key)))
    with open(os.path.join(out_dir, "picks.json"), "w", encoding="utf-8") as fh:
        json.dump([{"date": r["match"].day.isoformat(), "league": r["match"].div,
                    "home": r["match"].home, "away": r["match"].away, **p}
                   for r in rows for p in r["picks"]], fh, ensure_ascii=False, indent=1)
    print(f"{sum(len(r['picks']) for r in rows)} paris retenus · backtest: {bt}")


if __name__ == "__main__":
    main()
