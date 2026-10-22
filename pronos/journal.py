"""Journal des paris réellement proposés par le site, réglés avec les vrais scores.

Stocké dans docs/journal.json (versionné dans le dépôt : l'historique ne se perd pas).
Chaque pari est enregistré à sa première apparition, avec la cote affichée ce jour-là."""
import json
import os
from datetime import datetime, timedelta, timezone

from .backtest import won


def load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def save(path, entries):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=1)


def _base(p):
    return {"odds": round(p["odds"], 3), "book": p.get("book"), "prob": round(p["prob"], 4),
            "edge": round(p["edge"], 4), "stake": round(p["stake"], 4),
            "added": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "status": "en attente", "result": None, "profit": None,
            "elo_agree": p.get("elo_agree")}


def add_football(entries, rows):
    known = {e["id"] for e in entries}
    for r in rows:
        m = r["match"]
        for p in r["picks"]:
            pid = f"foot|{m.day.isoformat()}|{m.div}|{m.home}|{m.away}|{p['market']}"
            if pid in known:
                continue
            known.add(pid)
            entries.append({"id": pid, "sport": "Football", "league": m.div,
                            "start": f"{m.day.isoformat()}T{m.time or '00:00'}",
                            "home": m.home, "away": m.away, "market": p["market"],
                            "label": p["label"], **_base(p)})


def add_other(entries, picks):
    known = {e["id"] for e in entries}
    for p in picks:
        if p["id"] in known:
            continue
        known.add(p["id"])
        entries.append({"id": p["id"], "sport": p["sport"], "sport_key": p["sport_key"],
                        "event_id": p["event_id"], "start": p["start"], "home": p["home"],
                        "away": p["away"], "outcome": p["outcome"], "label": p["label"],
                        **_base(p)})


def _settle(e, ok):
    e["status"] = "gagné" if ok else "perdu"
    e["profit"] = round(e["odds"] - 1, 3) if ok else -1.0


def settle_football(entries, history):
    results = {(m.div, m.day.isoformat(), m.home, m.away): m for m in history}
    for e in entries:
        if e["sport"] != "Football" or e["status"] != "en attente":
            continue
        m = results.get((e["league"], e["start"][:10], e["home"], e["away"]))
        if m:
            e["result"] = f"{m.hg}-{m.ag}"
            _settle(e, won(e["market"], m))
        elif e["start"][:10] < (datetime.now(timezone.utc) - timedelta(days=14)).date().isoformat():
            e["status"], e["profit"] = "annulé", 0.0  # match reporté ou introuvable


def pending_sports(entries):
    """Sports (hors foot) avec un pari en attente dont le match a commencé il y a plus de 3 h."""
    limit = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    return sorted({e["sport_key"] for e in entries
                   if e["sport"] != "Football" and e["status"] == "en attente" and e["start"] < limit})


def settle_other(entries, sport_key, scores):
    by_id = {s["id"]: s for s in scores}
    for e in entries:
        if e.get("sport_key") != sport_key or e["status"] != "en attente":
            continue
        s = by_id.get(e["event_id"])
        if s and s.get("completed") and s.get("scores"):
            pts = {x["name"]: float(x["score"]) for x in s["scores"]}
            if e["home"] in pts and e["away"] in pts:
                h, a = pts[e["home"]], pts[e["away"]]
                e["result"] = f"{h:g}-{a:g}"
                winner = "Draw" if h == a else (e["home"] if h > a else e["away"])
                _settle(e, winner == e["outcome"])
        elif e["start"] < (datetime.now(timezone.utc) - timedelta(days=3)).isoformat():
            # au-delà de 3 jours l'API ne renvoie plus le score
            e["status"], e["profit"] = "annulé", 0.0


def stats(entries, sport=None, elo_agree="tous"):
    sel = [e for e in entries if sport is None or (e["sport"] == "Football") == (sport == "Football")]
    if elo_agree != "tous":
        sel = [e for e in sel if e.get("elo_agree") is elo_agree]
    done = [e for e in sel if e["status"] in ("gagné", "perdu")]
    n = len(done)
    wins = sum(e["status"] == "gagné" for e in done)
    profit = sum(e["profit"] for e in done)
    staked = sum(e["stake"] for e in done)
    kelly = sum(e["stake"] * e["profit"] for e in done)
    return {"n": n, "pending": sum(e["status"] == "en attente" for e in sel),
            "hit_rate": wins / n if n else 0.0, "profit": profit,
            "roi": profit / n if n else 0.0, "roi_kelly": kelly / staked if staked else 0.0}
