"""Génération de la page HTML statique (docs/index.html)."""
import html
from datetime import date, datetime
from zoneinfo import ZoneInfo

from .data import LEAGUES
from .journal import stats as journal_stats
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


PARIS = ZoneInfo("Europe/Paris")


def local_time(iso):
    try:
        d = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(PARIS)
        return f"{fr_date(d.date())} {d:%H:%M}"
    except ValueError:
        return iso


def other_card(p):
    return f"""
      <article class="pick">
        <div class="pick-top"><span class="league">{e(p['sport'])}</span>
          <span class="when">{e(local_time(p['start']))}</span></div>
        <h3>{e(p['home'])} <span class="vs">vs</span> {e(p['away'])}</h3>
        <p class="bet">{e(p['label'])} <strong>@ {p['odds']:.2f}</strong> <span class="book">chez {e(p['book'])}</span></p>
        <dl>
          <div><dt>Proba (consensus)</dt><dd>{pct(p['prob'])}</dd></div>
          <div><dt>Cote juste / moyenne</dt><dd>{p['fair']:.2f} / {p['avg_odds']:.2f}</dd></div>
          <div><dt>Avantage</dt><dd class="pos">+{p['edge'] * 100:.1f} %</dd></div>
          <div><dt>Mise conseillée</dt><dd>{p['stake'] * 100:.1f} % bankroll</dd></div>
        </dl>
        <span class="conf">{p['n_books']} bookmakers comparés</span>
      </article>"""


def journal_html(entries):
    def block(title, st):
        if not st["n"] and not st["pending"]:
            return f'<div><b>–</b><span>{e(title)} : aucun pari encore</span></div>'
        cls = "pos" if st["profit"] >= 0 else "neg"
        return (f'<div><b class="{cls}">{st["profit"]:+.2f} u</b><span>{e(title)} : {st["n"]} réglés, '
                f'{st["pending"]} en attente · réussite {pct(st["hit_rate"])} · ROI {st["roi"] * 100:+.1f} %</span></div>')
    total = journal_stats(entries)
    head = f"""<div class="stats">{block("Tous les paris", total)}{block("Football", journal_stats(entries, "Football"))}{block("Autres sports", journal_stats(entries, "autres"))}</div>
  <p class="sub">u = unité : gain ou perte si on avait misé 1 € sur chaque pari, à la cote affichée le jour où il a été proposé.</p>"""
    if not entries:
        return head + '<p class="empty">Le journal démarre aujourd\'hui : chaque pari proposé y sera enregistré puis réglé avec le vrai score.</p>'
    order = {"en attente": 0}
    recent = sorted(entries, key=lambda x: (order.get(x["status"], 1), x["start"]), reverse=False)
    pend = [x for x in recent if x["status"] == "en attente"]
    done = sorted([x for x in recent if x["status"] != "en attente"], key=lambda x: x["start"], reverse=True)
    trs = []
    for x in (pend + done)[:60]:
        st = x["status"]
        cls = {"gagné": "pos", "perdu": "neg"}.get(st, "")
        prof = f'{x["profit"]:+.2f}' if x["profit"] is not None else ""
        trs.append(f"""<tr><td>{e(local_time(x['start']) if 'T' in x['start'] and x['sport'] != 'Football' else x['start'][:10])}</td>
          <td>{e(x['sport'] if x['sport'] != 'Football' else LEAGUES.get(x['league'], x['league']))}</td>
          <td class="teams">{e(x['home'])} – {e(x['away'])}</td><td>{e(x['label'])}</td>
          <td class="num">{x['odds']:.2f}</td><td>{e(x.get('book') or '')}</td><td class="num">{e(x['result'] or '')}</td>
          <td class="{cls}">{e(st)}</td><td class="num {cls}">{prof}</td></tr>""")
    return head + f"""
  <div class="tbl"><table>
    <thead><tr><th>Date</th><th>Compétition</th><th>Match</th><th>Pari</th><th>Cote</th><th>Bookmaker</th><th>Score</th><th>Statut</th><th>Gain (u)</th></tr></thead>
    <tbody>{"".join(trs)}</tbody></table></div>"""


def render(today, rows, bt, generated_at, others=(), entries=(), odds_api=False):
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
        <p class="bet">{e(p['label'])} <strong>@ {p['odds']:.2f}</strong>{f' <span class="book">chez {e(p["book"])}</span>' if p.get('book') else ''}</p>
        <dl>
          <div><dt>Proba (consensus)</dt><dd>{pct(p['prob'])}</dd></div>
          <div><dt>Cote juste / moyenne</dt><dd>{p['fair']:.2f} / {p['avg_odds']:.2f}</dd></div>
          <div><dt>Notre modèle</dt><dd>{pct(p['model_prob'])}</dd></div>
          <div><dt>Avantage</dt><dd class="pos">+{p['edge'] * 100:.1f} %</dd></div>
          <div><dt>Mise conseillée</dt><dd>{p['stake'] * 100:.1f} % bankroll</dd></div>
        </dl>
        <span class="conf conf-{confidence(p).lower().replace('é', 'e')}">Confiance {confidence(p).lower()}</span>
      </article>"""

    cards = "".join(pick_card(r, p) for r, p in top) or \
        '<p class="empty">Aucun pari ne passe nos filtres aujourd\'hui. Ne pas parier est aussi une décision gagnante.</p>'

    others = sorted(others, key=lambda p: -p["edge"])[:12]
    if others:
        others_html = '<div class="grid">' + "".join(other_card(p) for p in others) + "</div>"
    elif odds_api:
        others_html = '<p class="empty">Aucun pari ne passe nos filtres dans les autres sports aujourd\'hui.</p>'
    else:
        others_html = '<p class="empty">Désactivé : ajoutez une clé The Odds API (voir le README).</p>'
    journal = journal_html(list(entries))

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
        <div><b>{bt['n']}</b><span>paris simulés sur les 12 derniers mois</span></div>
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
.bet {{ margin:0 0 10px; font-size:16px }} .bet strong {{ color:var(--acc) }} .book {{ font-size:13px; color:var(--mute) }}
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

  <h2>Autres sports</h2>
  {others_html}

  <h2>Journal des paris proposés</h2>
  {journal}

  <h2>Comment la stratégie aurait performé (football, simulation)</h2>
  {bt_html}

  <h2>Tous les matchs à venir</h2>
  <p class="sub">Probabilités du modèle, cote moyenne du marché en dessous. Case verte = pari recommandé.</p>
  <div class="tbl"><table>
    <thead><tr><th>Date</th><th>Ligue</th><th>Match</th><th>Buts attendus</th><th>Score probable</th>
    <th>1</th><th>N</th><th>2</th><th>+2,5</th><th>Les 2 marquent</th></tr></thead>
    <tbody>{table}</tbody></table></div>

  <footer><p><b>Méthode des paris.</b> On calcule la probabilité « juste » de chaque issue à partir de la cote moyenne de tous
  les bookmakers (marge retirée). Un pari est proposé quand un bookmaker offre une cote au moins 2 % au-dessus de cette valeur
  juste : il est en retard sur le marché. Testé sur 2 saisons, c'est la seule approche qui a été positive (environ +2 %
  par pari sur ~200 paris par an), alors que notre modèle seul perdait entre 5 et 13 %. Ce résultat reste fragile : sur si peu de
  paris, le hasard peut à lui seul expliquer un écart de plus ou moins 20 %. La cote peut bouger avant que vous pariiez : vérifiez-la, et ne pariez pas si elle a baissé sous la cote juste.
  Mise : quart de Kelly, plafonnée à 3 %.</p>
  <p><b>Analyse des matchs.</b> Modèle de Poisson (Dixon-Coles) sur 3 saisons, matchs récents pondérés plus fort : buts attendus,
  score probable, probabilités. La confiance est « élevée » quand le modèle va dans le même sens que le pari.</p>
  <p>Données : football-data.co.uk. Généré le {e(generated_at)}.</p></footer>
</main></body></html>"""
