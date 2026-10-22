"""Autres sports via The Odds API (https://the-odds-api.com, clé gratuite : 500 requêtes/mois).

Même stratégie que pour le football : probabilité « juste » = moyenne des probabilités de
tous les bookmakers (marge retirée), pari quand un bookmaker propose une cote au-dessus.
Pas de backtest possible ici (l'historique des cotes est payant) : c'est le journal qui jugera."""
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from .picks import KELLY_FRACTION, MAX_EDGE, MAX_ODDS, MAX_STAKE, MIN_EDGE, MIN_PROB

API = "https://api.the-odds-api.com/v4"
# groupes de sports suivis, par ordre de priorité ; le football est déjà couvert par football-data
GROUPS = ["Basketball", "Ice Hockey", "American Football", "Tennis", "Baseball",
          "Mixed Martial Arts", "Rugby Union", "Rugby League", "Handball", "Aussie Rules"]
MAX_SPORTS = 6        # 6 appels/jour pour les cotes ≈ 180/mois, le reste sert aux scores
MIN_BOOKS = 5         # consensus fiable seulement avec assez de bookmakers
MIN_REMAINING = 15    # on s'arrête avant d'épuiser le quota mensuel
EXCHANGES = {"betfair_ex_eu", "betfair_ex_uk", "matchbook", "smarkets"}
EXCHANGE_COMMISSION = 0.05


class Client:
    def __init__(self, key):
        self.key = key
        self.remaining = None

    def get(self, path, **params):
        if self.remaining is not None and self.remaining < MIN_REMAINING:
            print(f"[oddsapi] quota presque épuisé ({self.remaining}), appel {path} sauté")
            return None
        url = f"{API}{path}?{urllib.parse.urlencode({'apiKey': self.key, **params})}"
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                rem = r.headers.get("x-requests-remaining")
                if rem is not None:
                    self.remaining = int(float(rem))
                return json.loads(r.read().decode())
        except Exception as e:
            print(f"[oddsapi] échec {path}: {e}")
            return None


def pick_sports(sports):
    active = [s for s in sports or [] if s.get("active") and not s.get("has_outrights")
              and s.get("group") in GROUPS]
    active.sort(key=lambda s: GROUPS.index(s["group"]))
    chosen, per_group = [], {}
    for s in active:  # au plus 2 compétitions par sport pour varier
        if per_group.get(s["group"], 0) < 2:
            chosen.append(s)
            per_group[s["group"]] = per_group.get(s["group"], 0) + 1
    return chosen[:MAX_SPORTS]


def evaluate_event(ev, horizon_hours=72):
    start = datetime.fromisoformat(ev["commence_time"].replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    if not (now < start < now + timedelta(hours=horizon_hours)):
        return []
    books = []
    for b in ev.get("bookmakers", []):
        m = next((m for m in b.get("markets", []) if m["key"] == "h2h"), None)
        if not m or len(m["outcomes"]) < 2:
            continue
        prices = {o["name"]: o["price"] for o in m["outcomes"] if o.get("price", 0) > 1}
        if b["key"] in EXCHANGES:
            prices = {k: 1 + (v - 1) * (1 - EXCHANGE_COMMISSION) for k, v in prices.items()}
        books.append((b["title"], prices))
    if len(books) < MIN_BOOKS:
        return []
    names = set.intersection(*(set(p) for _, p in books))
    books = [(t, p) for t, p in books if set(p) == names] if names else []
    if len(books) < MIN_BOOKS:
        return []
    fair = {n: 0.0 for n in names}
    for _, p in books:
        s = sum(1 / v for v in p.values())
        for n in names:
            fair[n] += (1 / p[n]) / s / len(books)
    picks = []
    for n in names:
        o, book = max((p[n], t) for t, p in books)
        prob, edge = fair[n], fair[n] * o - 1
        if edge < MIN_EDGE or edge > MAX_EDGE or prob < MIN_PROB or o > MAX_ODDS:
            continue
        stake = min(KELLY_FRACTION * edge / (o - 1), MAX_STAKE)
        avg = sum(p[n] for _, p in books) / len(books)
        picks.append({
            "id": f"{ev['sport_key']}|{ev['id']}|{n}",
            "sport": ev["sport_title"], "sport_key": ev["sport_key"], "event_id": ev["id"],
            "start": ev["commence_time"], "home": ev["home_team"], "away": ev["away_team"],
            "outcome": n, "label": "Match nul" if n == "Draw" else f"Victoire {n}",
            "odds": round(o, 3), "book": book, "prob": prob, "fair": 1 / prob,
            "avg_odds": avg, "edge": edge, "stake": stake, "n_books": len(books),
        })
    return sorted(picks, key=lambda p: -p["edge"])[:1]  # un seul côté par match


def fetch_picks(client):
    sports = pick_sports(client.get("/sports"))  # cet appel ne compte pas dans le quota
    picks = []
    for s in sports:
        events = client.get(f"/sports/{s['key']}/odds", regions="eu", markets="h2h",
                            oddsFormat="decimal", dateFormat="iso")
        for ev in events or []:
            picks += evaluate_event(ev)
    print(f"[oddsapi] {len(sports)} sports, {len(picks)} paris, quota restant {client.remaining}")
    return picks


def fetch_scores(client, sport_key):
    """Scores des 3 derniers jours (coûte 2 requêtes)."""
    return client.get(f"/sports/{sport_key}/scores", daysFrom=3, dateFormat="iso") or []
