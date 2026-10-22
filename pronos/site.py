"""Génération de la page HTML statique (docs/index.html)."""
import html
from datetime import date

from .data import LEAGUES
from .picks import MARKETS, confidence

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
        "septembre", "octobre", "novembre", "décembre"]


def fr_date(d: date):
    return f"{JOURS[d.weekday()]} {d.day} {MOIS[d.month - 1]} {d.year}"


def pct(x):
    return f"{x * 100:.0f} %"


def e(s):
    return html.escape(str(s))


def render(today, rows, bt, generated_at):
    picks = sorted([(r, p) for r in rows for p in r["picks"]],
                   key=lambda rp: -rp[1]["edge"])
    top = picks[:10]

    def pick_card(r, p):
        m = r["match"]
        return f"""
      <article class="pick">
        <div class="pick-top"><span class="league">{e(LEAGUES.get(m.div, m.div))}</span>
          <span class="when">{e(fr_date(m.day))} {e(m.time)}</span></div>
        <h3>{e(m.home)} <span class="vs">vs</span> {e(m.away)}</h3>
        <p class="bet">{e(p['label'])} <strong>@ {p['odds']:.2f}</strong></p>
        <dl>
          <div><dt>Notre proba</dt><dd>{pct(p['prob'])}</dd></div>
          <div><dt>Cote juste</dt><dd>{p['fair']:.2f}</dd></div>
          <div><dt>Avantage</dt><dd class="pos">+{p['edge'] * 100:.1f} %</dd></div>
          <div><dt>Mise conseillée</dt><dd>{p['stake'] * 100:.1f} % bankroll</dd></div>
        </dl>
        <span class="conf conf-{confidence(p).lower().replace('é', 'e')}">Confiance {confidence(p).lower()}</span>
      </article>"""

    cards = "".join(pick_card(r, p) for r, p in top) or \
        '<p class="empty">Aucun pari ne passe nos filtres aujourd\'hui. Ne pas parier est aussi une décision gagnante.</p>'

    trs = []
    for r in sorted(rows, key=lambda r: (r["match"].day, r["match"].time, r["match"].div)):
        m, pr = r["match"], r["pred"]
        o = m.odds
        def cell(k):
            odd = f'<small>{o[k]:.2f}</small>' if o.get(k) else ""
            hl = " hl" if any(p["market"] == k for p in r["picks"]) else ""
            return f'<td class="num{hl}">{pct(pr[k])}{odd}</td>'
        trs.append(f"""<tr><td>{e(m.day.strftime('%d/%m'))} {e(m.time)}</td><td>{e(m.div)}</td>
          <td class="teams">{e(m.home)} – {e(m.away)}</td>
          <td class="num">{pr['xg_home']:.1f} – {pr['xg_away']:.1f}</td><td class="num">{e(pr['score'])}</td>
          {cell('H')}{cell('D')}{cell('A')}{cell('O25')}<td class="num">{pct(pr['BTTS'])}</td></tr>""")
    table = "\n".join(trs)

    if bt.get("n"):
        mk = "".join(f"<li>{e(MARKETS[k])} : {v['n']} paris, ROI {v['roi'] * 100:+.1f} %</li>"
                     for k, v in sorted(bt["per_market"].items()))
        bt_html = f"""
      <div class="stats">
        <div><b>{bt['n']}</b><span>paris simulés (12 derniers mois)</span></div>
        <div><b>{pct(bt['hit_rate'])}</b><span>taux de réussite</span></div>
        <div><b>{bt['avg_odds']:.2f}</b><span>cote moyenne</span></div>
        <div><b class="{'pos' if bt['roi_flat'] >= 0 else 'neg'}">{bt['roi_flat'] * 100:+.1f} %</b><span>ROI mise fixe</span></div>
        <div><b class="{'pos' if bt['roi_kelly'] >= 0 else 'neg'}">{bt['roi_kelly'] * 100:+.1f} %</b><span>ROI mise conseillée</span></div>
      </div>
      <ul class="markets">{mk}</ul>"""
    else:
        bt_html = "<p>Backtest indisponible (pas assez de données).</p>"

    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pronos du jour</title>
<style>
:root {{ --bg:#f6f7f9; --card:#fff; --ink:#15181e; --mute:#5d6573; --line:#e3e6eb; --acc:#0b7a4b; --neg:#b42318; --hl:#e6f4ec; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#0f1115; --card:#181b21; --ink:#e8eaee; --mute:#9aa3b2; --line:#2a2f38; --acc:#3fcf8e; --neg:#ff6b5e; --hl:#163326; }} }}
* {{ box-sizing:border-box }}
body {{ margin:0; background:var(--bg); color:var(--ink); font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif }}
main {{ max-width:1100px; margin:0 auto; padding:24px 16px 64px }}
h1 {{ margin:0 0 4px; font-size:28px }} h2 {{ margin:40px 0 12px; font-size:20px }}
.sub {{ color:var(--mute); margin:0 }}
.warn {{ background:var(--card); border:1px solid var(--line); border-left:4px solid #d4a017; padding:12px 16px; border-radius:8px; margin:20px 0; color:var(--mute); font-size:14px }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); gap:14px }}
.pick {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:16px }}
.pick-top {{ display:flex; justify-content:space-between; gap:8px; font-size:12px; color:var(--mute) }}
.pick h3 {{ margin:8px 0 4px; font-size:17px }} .vs {{ color:var(--mute); font-weight:400; font-size:13px }}
.bet {{ margin:0 0 10px; font-size:16px }} .bet strong {{ color:var(--acc) }}
dl {{ display:grid; grid-template-columns:1fr 1fr; gap:6px 12px; margin:0 0 10px }}
dt {{ font-size:12px; color:var(--mute) }} dd {{ margin:0; font-weight:600 }}
.pos {{ color:var(--acc) }} .neg {{ color:var(--neg) }}
.conf {{ display:inline-block; font-size:12px; padding:2px 8px; border-radius:99px; border:1px solid var(--line) }}
.conf-elevee {{ background:var(--hl); color:var(--acc); border-color:transparent }}
.empty {{ color:var(--mute) }}
.stats {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:10px }}
.stats div {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:12px }}
.stats b {{ display:block; font-size:22px }} .stats span {{ font-size:12px; color:var(--mute) }}
.markets {{ color:var(--mute); font-size:14px }}
.tbl {{ overflow-x:auto; background:var(--card); border:1px solid var(--line); border-radius:12px }}
table {{ border-collapse:collapse; width:100%; font-size:13px; white-space:nowrap }}
th, td {{ padding:7px 10px; border-bottom:1px solid var(--line); text-align:left }}
th {{ font-size:12px; color:var(--mute); font-weight:600 }}
td.num {{ text-align:right; font-variant-numeric:tabular-nums }} td small {{ display:block; color:var(--mute); font-size:11px }}
td.hl {{ background:var(--hl); font-weight:600 }}
footer {{ margin-top:40px; color:var(--mute); font-size:13px }}
</style></head><body><main>
  <h1>Pronos du jour</h1>
  <p class="sub">{e(fr_date(today))} · {len(rows)} matchs analysés dans {len({r['match'].div for r in rows})} championnats</p>
  <div class="warn">Ces pronostics sont des estimations statistiques, pas des certitudes. Aucun modèle ne garantit des gains :
  même un bon modèle perd souvent sur de longues séries. Ne misez que de l'argent que vous pouvez perdre, fixez-vous une limite,
  et n'essayez jamais de « vous refaire ». Aide : joueurs-info-service.fr · 09 74 75 13 13.</div>

  <h2>Meilleurs paris value</h2>
  <div class="grid">{cards}</div>

  <h2>Comment la stratégie aurait performé</h2>
  {bt_html}

  <h2>Tous les matchs à venir</h2>
  <p class="sub">Probabilités du modèle, cote moyenne du marché en dessous. Case verte = pari recommandé.</p>
  <div class="tbl"><table>
    <thead><tr><th>Date</th><th>Ligue</th><th>Match</th><th>Buts attendus</th><th>Score probable</th>
    <th>1</th><th>N</th><th>2</th><th>+2,5</th><th>Les 2 marquent</th></tr></thead>
    <tbody>{table}</tbody></table></div>

  <footer>Méthode : modèle de Poisson (Dixon-Coles) sur 3 saisons de résultats pondérés dans le temps, mélangé à 35 % avec les
  probabilités du marché. Un pari est retenu si l'avantage estimé dépasse 5 %. Mise : quart de Kelly, plafonnée à 3 %.
  Données : football-data.co.uk. Généré le {e(generated_at)}.</footer>
</main></body></html>"""
