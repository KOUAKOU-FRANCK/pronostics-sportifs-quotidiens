"""Téléchargement et lecture des données football-data.co.uk (gratuit, sans clé).

- Résultats historiques + cotes : https://www.football-data.co.uk/mmz4281/<saison>/<ligue>.csv
- Matchs à venir + cotes       : https://www.football-data.co.uk/fixtures.csv
"""
import csv
import io
import os
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime

BASE = "https://www.football-data.co.uk"

LEAGUES = {
    "E0": "Angleterre - Premier League",
    "E1": "Angleterre - Championship",
    "E2": "Angleterre - League One",
    "E3": "Angleterre - League Two",
    "SC0": "Écosse - Premiership",
    "D1": "Allemagne - Bundesliga",
    "D2": "Allemagne - 2. Bundesliga",
    "I1": "Italie - Serie A",
    "I2": "Italie - Serie B",
    "SP1": "Espagne - La Liga",
    "SP2": "Espagne - Segunda",
    "F1": "France - Ligue 1",
    "F2": "France - Ligue 2",
    "N1": "Pays-Bas - Eredivisie",
    "B1": "Belgique - Pro League",
    "P1": "Portugal - Liga",
    "T1": "Turquie - Süper Lig",
    "G1": "Grèce - Super League",
}


@dataclass
class Match:
    div: str
    day: date
    time: str
    home: str
    away: str
    hg: int | None = None
    ag: int | None = None
    odds: dict = field(default_factory=dict)  # clés: H, D, A, O25, U25


def season_code(d: date) -> str:
    start = d.year if d.month >= 7 else d.year - 1
    return f"{start % 100:02d}{(start + 1) % 100:02d}"


def _fetch(url: str, cache_dir: str, name: str) -> str:
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, name)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "pronos-site/1.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
        with open(path, "wb") as f:
            f.write(raw)
    except Exception as e:  # on retombe sur le cache si le réseau échoue
        if not os.path.exists(path):
            print(f"[data] échec {url}: {e}")
            return ""
        print(f"[data] réseau KO pour {url}, utilisation du cache")
    with open(path, "rb") as f:
        return f.read().decode("utf-8-sig", errors="replace")


def _num(row, *keys):
    for k in keys:
        v = (row.get(k) or "").strip()
        if v:
            try:
                x = float(v)
                if x > 1.0:
                    return x
            except ValueError:
                pass
    return None


def _parse_date(s: str) -> date | None:
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    return None


def parse_csv(text: str, default_div: str | None = None) -> list[Match]:
    out = []
    for row in csv.DictReader(io.StringIO(text)):
        div = (row.get("Div") or default_div or "").strip()
        d = _parse_date(row.get("Date") or "")
        home, away = (row.get("HomeTeam") or "").strip(), (row.get("AwayTeam") or "").strip()
        if not (div and d and home and away):
            continue
        hg, ag = (row.get("FTHG") or "").strip(), (row.get("FTAG") or "").strip()
        odds = {
            # moyenne du marché d'abord, puis Pinnacle, puis Bet365
            "H": _num(row, "AvgH", "BbAvH", "PSH", "B365H"),
            "D": _num(row, "AvgD", "BbAvD", "PSD", "B365D"),
            "A": _num(row, "AvgA", "BbAvA", "PSA", "B365A"),
            "O25": _num(row, "Avg>2.5", "BbAv>2.5", "P>2.5", "B365>2.5"),
            "U25": _num(row, "Avg<2.5", "BbAv<2.5", "P<2.5", "B365<2.5"),
        }
        out.append(Match(div, d, (row.get("Time") or "").strip(), home, away,
                         int(hg) if hg.isdigit() else None,
                         int(ag) if ag.isdigit() else None,
                         {k: v for k, v in odds.items() if v}))
    return out


def load_history(today: date, cache_dir: str, seasons: int = 3) -> list[Match]:
    matches = []
    y = today
    codes = []
    for _ in range(seasons):
        codes.append(season_code(y))
        y = date(y.year - 1, y.month, 1)
    for code in codes:
        for div in LEAGUES:
            txt = _fetch(f"{BASE}/mmz4281/{code}/{div}.csv", cache_dir, f"{code}_{div}.csv")
            matches += [m for m in parse_csv(txt, div) if m.hg is not None]
    return matches


def load_fixtures(cache_dir: str) -> list[Match]:
    txt = _fetch(f"{BASE}/fixtures.csv", cache_dir, "fixtures.csv")
    return [m for m in parse_csv(txt) if m.div in LEAGUES]
