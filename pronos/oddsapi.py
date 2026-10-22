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
# groupes suivis ; le football inclut tous les championnats que l'API propose
GROUPS = ["Soccer", "Basketball", "Ice Hockey", "American Football", "Tennis", "Baseball",
          "Mixed Martial Arts", "Rugby Union", "Rugby League", "Handball", "Aussie Rules", "Cricket"]
# championnats déjà couverts gratuitement par football-data : inutile d'y dépenser le quota
COVERED = {"soccer_epl", "soccer_efl_champ", "soccer_england_league1", "soccer_england_league2",
           "soccer_germany_bundesliga", "soccer_germany_bundesliga2", "soccer_italy_serie_a",
           "soccer_italy_serie_b", "soccer_spain_la_liga", "soccer_spain_segunda_division",
           "soccer_france_ligue_one", "soccer_france_ligue_two", "soccer_netherlands_eredivisie",
           "soccer_belgium_first_div", "soccer_portugal_primeira_liga", "soccer_turkey_super_league",
           "soccer_greece_super_league", "soccer_spl"}
# priorité 0 : ce qui est le plus joué sur Bet360 ; 1 : grandes ligues des autres sports
TOP_CUPS = ("uefa_champs_league", "uefa_europa_league", "uefa_europa_conference_league",
            "africa_cup", "fifa_world_cup", "copa_libertadores", "copa_sudamericana")
TOP_OTHERS = ("basketball_nba", "basketball_euroleague", "icehockey_nhl", "americanfootball_nfl",
              "baseball_mlb", "tennis_atp", "tennis_wta")
MIN_BOOKS = 5         # consensus fiable seulement avec assez de bookmakers
MIN_REMAINING = 15    # on s'arrête avant d'épuiser le quota mensuel
SCORES_RESERVE = 8    # requêtes gardées chaque jour pour régler les paris (scores)
HORIZON_HOURS = 48
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


def priority(sport):
    key = sport["key"]
    if any(c in key for c in TOP_CUPS):
        return 0
    if any(key.startswith(t) for t in TOP_OTHERS):
        return 1
    return 2 if sport["group"] == "Soccer" else 3


def daily_budget(remaining, today=None):
    """Requêtes de cotes à dépenser aujourd'hui pour tenir jusqu'à la fin du mois."""
    if remaining is None:
        return 8
    today = today or datetime.now(timezone.utc).date()
    nxt = (today.replace(day=28) + timedelta(days=4)).replace(day=1)
    days_left = (nxt - today).days
    return max(0, min(40, (remaining - MIN_REMAINING) // days_left - SCORES_RESERVE))


def pick_sports(client, sports):
    """Compétitions actives qui ont des matchs dans les 48 h, par priorité, dans le budget du jour.
    La liste des matchs (/events) ne coûte rien ; seules les cotes consomment le quota."""
    active = [s for s in sports or [] if s.get("active") and not s.get("has_outrights")
              and s.get("group") in GROUPS and s["key"] not in COVERED]
    now = datetime.now(timezone.utc)
    limit = now + timedelta(hours=HORIZON_HOURS)
    with_games = []
    start_quota = client.remaining
    for s in active:
        if start_quota is not None and client.remaining is not None and start_quota - client.remaining > 3:
            print("[oddsapi] ATTENTION : /events consomme du quota, arrêt du balayage")
            break
        events = client.get(f"/sports/{s['key']}/events", dateFormat="iso") or []
        n = sum(1 for ev in events
                if now < datetime.fromisoformat(ev["commence_time"].replace("Z", "+00:00")) < limit)
        if n:
            with_games.append((priority(s), -n, s))
    with_games.sort(key=lambda t: (t[0], t[1]))
    budget = daily_budget(client.remaining)
    chosen = [s for _, _, s in with_games[:budget]]
    print(f"[oddsapi] {len(with_games)} compétitions jouent dans les {HORIZON_HOURS} h, budget {budget}, "
          f"quota restant {client.remaining}")
    print("[oddsapi] retenues :", ", ".join(s["title"] for s in chosen))
    skipped = [s["title"] for _, _, s in with_games[budget:]]
    if skipped:
        print("[oddsapi] hors budget :", ", ".join(skipped))
    return chosen


def evaluate_event(ev, horizon_hours=HORIZON_HOURS, fairs=None):
    """Paris value d'un match ; si `fairs` est une liste, on y ajoute aussi ses cotes justes."""
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
    if fairs is not None:
        fairs.append({"sport": ev["sport_title"], "start": ev["commence_time"],
                      "home": ev["home_team"], "away": ev["away_team"],
                      "fair": {n: 1 / q for n, q in fair.items()}})
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


def fetch_picks(client, fairs=None):
    sports = pick_sports(client, client.get("/sports"))  # /sports et /events ne comptent pas dans le quota
    picks = []
    for s in sports:
        events = client.get(f"/sports/{s['key']}/odds", regions="eu", markets="h2h",
                            oddsFormat="decimal", dateFormat="iso")
        for ev in events or []:
            picks += evaluate_event(ev, fairs=fairs)
    print(f"[oddsapi] {len(sports)} sports, {len(picks)} paris, quota restant {client.remaining}")
    return picks


def fetch_scores(client, sport_key):
    """Scores des 3 derniers jours (coûte 2 requêtes)."""
    return client.get(f"/sports/{sport_key}/scores", daysFrom=3, dateFormat="iso") or []
