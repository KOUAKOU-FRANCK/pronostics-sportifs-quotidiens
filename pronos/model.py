"""Modèle de Poisson (type Dixon-Coles) : force d'attaque / de défense par équipe,
avantage du terrain, pondération temporelle (les matchs récents comptent plus)."""
import math
from collections import defaultdict
from datetime import date

MAX_GOALS = 10
RHO = -0.06          # correction Dixon-Coles des petits scores (0-0, 1-0, 0-1, 1-1)
HALF_LIFE_DAYS = 150  # un match d'il y a 150 jours pèse moitié moins
PRIOR_GAMES = 4.0     # matchs fictifs « moyens » pour stabiliser les équipes peu connues


class PoissonModel:
    def __init__(self):
        self.att, self.dfn = {}, {}
        self.home_adv, self.base = 1.25, 1.2
        self.n_games = defaultdict(float)

    def fit(self, matches, as_of: date, iters: int = 40):
        xi = math.log(2) / HALF_LIFE_DAYS
        games = []
        for m in matches:
            age = (as_of - m.day).days
            if age < 0 or age > 3 * 365:
                continue
            games.append((m.home, m.away, m.hg, m.ag, math.exp(-xi * age)))
        if not games:
            return self
        teams = {g[0] for g in games} | {g[1] for g in games}
        att = {t: 1.0 for t in teams}
        dfn = {t: 1.0 for t in teams}  # >1 = encaisse beaucoup
        sw = sum(g[4] for g in games)
        base = sum(g[3] * g[4] for g in games) / sw  # buts à l'extérieur moyens
        home = max(sum(g[2] * g[4] for g in games) / sw / base, 1.0)
        for t in teams:
            self.n_games[t] = 0.0
        for h, a, _, _, w in games:
            self.n_games[h] += w
            self.n_games[a] += w

        for _ in range(iters):
            num_a = defaultdict(float); den_a = defaultdict(float)
            num_d = defaultdict(float); den_d = defaultdict(float)
            for h, a, hg, ag, w in games:
                num_a[h] += w * hg; den_a[h] += w * dfn[a] * home * base
                num_a[a] += w * ag; den_a[a] += w * dfn[h] * base
                num_d[a] += w * hg; den_d[a] += w * att[h] * home * base
                num_d[h] += w * ag; den_d[h] += w * att[a] * base
            k = PRIOR_GAMES
            att = {t: (num_a[t] + k * base * 1.1) / (den_a[t] + k * base * 1.1) for t in teams}
            dfn = {t: (num_d[t] + k * base * 1.1) / (den_d[t] + k * base * 1.1) for t in teams}
            ma = sum(att.values()) / len(att)
            md = sum(dfn.values()) / len(dfn)
            att = {t: v / ma for t, v in att.items()}
            dfn = {t: v / md for t, v in dfn.items()}
            hn = sum(w * hg for _, _, hg, _, w in games)
            hd = sum(w * att[h] * dfn[a] * base for h, a, _, _, w in games)
            home = hn / hd
            an = sum(w * ag for _, _, _, ag, w in games)
            ad = sum(w * att[a] * dfn[h] for h, a, _, _, w in games)
            base = an / ad
        self.att, self.dfn, self.home_adv, self.base = att, dfn, home, base
        return self

    def knows(self, team):
        return team in self.att

    def rates(self, home, away):
        # équipe inconnue (promue, etc.) : un peu plus faible que la moyenne
        ah, dh = self.att.get(home, 0.85), self.dfn.get(home, 1.15)
        aa, da = self.att.get(away, 0.85), self.dfn.get(away, 1.15)
        return ah * da * self.home_adv * self.base, aa * dh * self.base

    def predict(self, home, away):
        lh, la = self.rates(home, away)
        ph = [math.exp(-lh) * lh ** i / math.factorial(i) for i in range(MAX_GOALS + 1)]
        pa = [math.exp(-la) * la ** j / math.factorial(j) for j in range(MAX_GOALS + 1)]
        grid = [[ph[i] * pa[j] for j in range(MAX_GOALS + 1)] for i in range(MAX_GOALS + 1)]
        grid[0][0] *= 1 - lh * la * RHO
        grid[0][1] *= 1 + lh * RHO
        grid[1][0] *= 1 + la * RHO
        grid[1][1] *= 1 - RHO
        tot = sum(map(sum, grid))
        r = {"H": 0.0, "D": 0.0, "A": 0.0, "O25": 0.0, "BTTS": 0.0}
        best, best_p = (0, 0), 0.0
        for i in range(MAX_GOALS + 1):
            for j in range(MAX_GOALS + 1):
                p = grid[i][j] / tot
                r["H" if i > j else "D" if i == j else "A"] += p
                if i + j > 2:
                    r["O25"] += p
                if i and j:
                    r["BTTS"] += p
                if p > best_p:
                    best, best_p = (i, j), p
        r["U25"] = 1 - r["O25"]
        r["xg_home"], r["xg_away"] = lh, la
        r["score"] = f"{best[0]}-{best[1]}"
        return r
