"""Génération de la page HTML statique (docs/index.html)."""
import html
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from .data import LEAGUES
from .journal import stats as journal_stats
from .picks import MARKETS, MIN_EDGE, MY_BOOK_NAME, market_probs

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
        "septembre", "octobre", "novembre", "décembre"]


def fr_date(d: date):
    return f"{JOURS[d.weekday()]} {d.day} {MOIS[d.month - 1]} {d.year}"


def pct(x):
    return f"{x * 100:.0f} %"


def e(s):
    return html.escape(str(s))


LOCAL = ZoneInfo("Africa/Abidjan")   # heure affichée (GMT, Côte d'Ivoire)
LONDON = ZoneInfo("Europe/London")   # football-data donne les heures de Londres


def to_local(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(LOCAL)


def local_time(iso):
    try:
        d = to_local(iso)
        return f"{fr_date(d.date())} {d:%H:%M}"
    except ValueError:
        return iso


def foot_kickoff(m):
    """Coup d'envoi d'un match football-data en heure locale."""
    try:
        hh, mm = (int(x) for x in (m.time or "00:00").split(":"))
    except ValueError:
        hh, mm = 0, 0
    return datetime(m.day.year, m.day.month, m.day.day, hh, mm, tzinfo=LONDON).astimezone(LOCAL)


def day_label(d, today):
    delta = (d.date() - today).days
    return {0: "Aujourd'hui", 1: "Demain"}.get(delta, fr_date(d.date()).capitalize())


def min_odds(fair):
    """Cote minimum à trouver chez son bookmaker pour avoir l'avantage requis."""
    return fair * (1 + MIN_EDGE)


def mine_line(p):
    return (f'<p class="mine">Sur {e(MY_BOOK_NAME)} : à jouer seulement si la cote est '
            f'<b>≥ {min_odds(p["fair"]):.2f}</b></p>')


def min_odds_html(rows, other_fairs):
    out = []
    trs = []
    for r in sorted(rows, key=lambda r: (r["match"].day, r["match"].time)):
        m = r["match"]
        mp = market_probs(m.odds)
        if "H" not in mp:
            continue
        cells = "".join(f'<td class="num">{min_odds(1 / mp[k]):.2f}</td>' if k in mp else "<td></td>"
                        for k in ("H", "D", "A", "O25", "U25"))
        trs.append(f"<tr><td>{e(m.day.strftime('%d/%m'))} {e(m.time)}</td><td>{e(m.div)}</td>"
                   f'<td class="teams">{e(m.home)} – {e(m.away)}</td>{cells}</tr>')
    if trs:
        out.append(f"""<div class="tbl"><table>
    <thead><tr><th>Date</th><th>Ligue</th><th>Match</th><th>1</th><th>N</th><th>2</th><th>+2,5</th><th>-2,5</th></tr></thead>
    <tbody>{"".join(trs)}</tbody></table></div>""")
    trs = []
    for f in sorted(other_fairs, key=lambda f: f["start"]):
        cells = " · ".join(f"{e('Nul' if n == 'Draw' else n)} <b>{min_odds(v):.2f}</b>"
                           for n, v in sorted(f["fair"].items(),  # ordre domicile, nul, extérieur
                                              key=lambda kv: (kv[0] != f["home"], kv[0] != "Draw")))
        trs.append(f'<tr><td>{e(local_time(f["start"]))}</td><td>{e(f["sport"])}</td>'
                   f'<td class="teams">{e(f["home"])} – {e(f["away"])}</td><td>{cells}</td></tr>')
    if trs:
        out.append(f"""<div class="tbl" style="margin-top:14px"><table>
    <thead><tr><th>Date</th><th>Sport</th><th>Match</th><th>Cote minimum par issue</th></tr></thead>
    <tbody>{"".join(trs)}</tbody></table></div>""")
    return "".join(out) or '<p class="empty">Pas encore de matchs avec des cotes disponibles.</p>'


def elo_badge(p):
    if p.get("elo_agree") is None:
        return ""
    if p["elo_agree"]:
        return f'<span class="conf">Elo d\'accord ({pct(p["elo_prob"])})</span>'
    return f'<span class="conf conf-elevee" title="Sur 2 saisons, ces paris ont mieux marché (petit échantillon)">Elo en désaccord ({pct(p["elo_prob"])})</span>'


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
        {mine_line(p)}
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
  <p class="sub">u = unité : gain ou perte si on avait misé 1 € sur chaque pari, à la cote affichée le jour où il a été proposé.</p>
  <div class="stats">{block("Foot, Elo en désaccord", journal_stats(entries, "Football", False))}{block("Foot, Elo d'accord", journal_stats(entries, "Football", True))}</div>"""
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


def chances_label(p):
    if p >= 0.65:
        return '<span class="tag tag-hi">forte</span>'
    if p >= 0.5:
        return '<span class="tag tag-mid">moyenne</span>'
    return '<span class="tag tag-lo">faible</span>'


def build_items(rows, other_fairs, picks_by_key):
    """Une ligne de pronostic par match, quelle que soit la source."""
    items = []
    for r in rows:
        m, pr = r["match"], r["pred"]
        mp = market_probs(m.odds)
        src = mp if "H" in mp else pr  # consensus des bookmakers d'abord, sinon notre modèle
        probs = {"H": src["H"], "D": src["D"], "A": src["A"]}
        goals = None
        if "O25" in src:
            goals = ("Plus de 2,5 buts", src["O25"]) if src["O25"] >= 0.5 else ("Moins de 2,5 buts", 1 - src["O25"])
        items.append({"comp": LEAGUES.get(m.div, m.div), "when": foot_kickoff(m), "home": m.home,
                      "away": m.away, "probs": probs, "goals": goals, "score": pr.get("score"),
                      "value": [p for p in r["picks"]]})
    for f in other_fairs:
        fair = f["fair"]
        names = list(fair)
        probs = {"H": 1 / fair.get(f["home"], 1e9), "A": 1 / fair.get(f["away"], 1e9)}
        if "Draw" in fair:
            probs["D"] = 1 / fair["Draw"]
        if not (f["home"] in names and f["away"] in names):
            continue
        items.append({"comp": f["sport"], "when": to_local(f["start"]), "home": f["home"], "away": f["away"],
                      "probs": probs, "goals": None, "score": None,
                      "value": picks_by_key.get((f["home"], f["away"], f["start"]), [])})
    return items


def pronostic(it):
    probs, home, away = it["probs"], it["home"], it["away"]
    names = {"H": f"Victoire {home}", "D": "Match nul", "A": f"Victoire {away}"}
    k = max(probs, key=probs.get)
    main = (names[k], probs[k])
    safe = None
    if "D" in probs and probs[k] < 0.55:  # option prudente : double chance
        one_x, x_two = probs["H"] + probs["D"], probs["A"] + probs["D"]
        safe = (f"{home} ou nul", one_x) if one_x >= x_two else (f"{away} ou nul", x_two)
    return main, safe


def value_card(v, it):
    when = it["when"]
    return f"""
      <article class="pick">
        <div class="pick-top"><span>{e(it['comp'])}</span><span>{e(fr_date(when.date()))} · {when:%H:%M}</span></div>
        <h3>{e(it['home'])} <span class="vs">contre</span> {e(it['away'])}</h3>
        <p class="bet">⭐ {e(v['label_full'])}</p>
        <p class="line">Chances estimées : <b>{pct(v['prob'])}</b></p>
        <p class="mine">Sur {e(MY_BOOK_NAME)} : jouer seulement si la cote est <b>≥ {min_odds(v['fair']):.2f}</b></p>
        <p class="line small">Mise conseillée : {v['stake'] * 100:.1f} % de ton budget paris · déjà vu à {v['odds']:.2f} chez {e(v.get('book') or '?')}</p>
      </article>"""


def render(today, rows, bt, generated_at, others=(), entries=(), odds_api=False, other_fairs=()):
    picks_by_key = {}
    for p in others:
        picks_by_key.setdefault((p["home"], p["away"], p["start"]), []).append(p)
    items = build_items(rows, other_fairs, picks_by_key)
    now = datetime.now(LOCAL)
    items = [it for it in items if it["when"] > now - timedelta(hours=2)]
    items.sort(key=lambda it: it["when"])

    # paris conseillés (value), toutes sources confondues
    values = []
    for it in items:
        for v in it["value"]:
            if "market" in v:  # football-data
                lab = {"H": f"Victoire {it['home']}", "D": "Match nul", "A": f"Victoire {it['away']}"}.get(v["market"], v["label"])
            else:
                lab = "Match nul" if v["outcome"] == "Draw" else f"Victoire {v['outcome']}"
            values.append(({**v, "label_full": lab}, it))
    values.sort(key=lambda t: -t[0]["edge"])
    cards = "".join(value_card(v, it) for v, it in values[:8]) or \
        '<p class="empty">Aucun pari conseillé pour l\'instant. Ne pas parier est aussi une bonne décision.</p>'

    # tous les pronostics, regroupés par jour puis par compétition
    blocks, current_day = [], None
    by_day = {}
    for it in items:
        by_day.setdefault(it["when"].date(), {}).setdefault(it["comp"], []).append(it)
    for d in sorted(by_day):
        comps = by_day[d]
        blocks.append(f'<h3 class="day">{e(day_label(datetime(d.year, d.month, d.day), today))}</h3>')
        for comp in sorted(comps, key=lambda c: comps[c][0]["when"]):
            trs = []
            for it in comps[comp]:
                (lab, p), safe = pronostic(it)
                star = ' <span class="star" title="Pari conseillé">⭐</span>' if it["value"] else ""
                safe_html = (f'<div class="small">Option prudente : {e(safe[0])} · chances {pct(safe[1])} · '
                             f'cote mini {min_odds(1 / safe[1]):.2f}</div>') if safe else ""
                goals = (f'Buts : {e(it["goals"][0])} · {pct(it["goals"][1])} · cote mini {min_odds(1 / it["goals"][1]):.2f}'
                         if it["goals"] else "")
                score = f'Score probable : {e(it["score"])}' if it["score"] else ""
                extra = "".join(f'<div class="small">{x}</div>' for x in (goals, score) if x)
                trs.append(f"""<div class="row" data-q="{e((it['home'] + ' ' + it['away'] + ' ' + comp).lower())}">
              <div class="t">{it['when']:%H:%M}</div>
              <div class="m"><div class="teams">{e(it['home'])} – {e(it['away'])}</div>
                <div class="pr"><b>{e(lab)}</b>{star} <span class="small">· chances {pct(p)}</span> {chances_label(p)}</div>
                {safe_html}{extra}</div>
              <div class="mini"><span>cote mini</span><b>{min_odds(1 / p):.2f}</b></div></div>""")
            blocks.append(f"""<div class="comp" data-comp><h4>{e(comp)}</h4><div class="list">{"".join(trs)}</div></div>""")
    all_html = "".join(blocks) or '<p class="empty">Pas encore de matchs avec des cotes disponibles.</p>'
    n_comps = len({it["comp"] for it in items})

    journal = journal_html(list(entries))
    trs = []
    for r in sorted(rows, key=lambda r: (r["match"].day, r["match"].time, r["match"].div)):
        m, pr = r["match"], r["pred"]
        o = m.odds
        def cell(k):
            odd = f'<small>{o[k]:.2f}</small>' if o.get(k) else ""
            return f'<td class="num">{pct(pr[k])}{odd}</td>'
        trs.append(f"""<tr><td>{e(m.day.strftime('%d/%m'))}</td><td>{e(m.div)}</td>
          <td class="teams">{e(m.home)} – {e(m.away)}</td>
          <td class="num">{pr['xg_home']:.1f} – {pr['xg_away']:.1f}</td><td class="num">{e(pr['score'])}</td>
          {cell('H')}{cell('D')}{cell('A')}{cell('O25')}<td class="num">{pct(pr['BTTS'])}</td></tr>""")
    model_table = "\n".join(trs)

    if bt.get("n"):
        bt_html = f"""
      <div class="stats">
        <div><b>{bt['n']}</b><span>paris simulés sur les 12 derniers mois (foot européen)</span></div>
        <div><b>{pct(bt['hit_rate'])}</b><span>de paris gagnés</span></div>
        <div><b>{bt['avg_odds']:.2f}</b><span>cote moyenne</span></div>
        <div><b class="{'pos' if bt['roi_flat'] >= 0 else 'neg'}">{bt['roi_flat'] * 100:+.1f} %</b><span>gain moyen par pari</span></div>
      </div>"""
    else:
        bt_html = "<p>Bilan indisponible aujourd'hui.</p>"

    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pronostics du jour</title>
<style>
:root {{ --bg:#f6f7f9; --card:#fff; --ink:#15181e; --mute:#5d6573; --line:#e3e6eb; --acc:#0b7a4b; --neg:#b42318; --hl:#e6f4ec; --warn:#fff6e0; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#0f1115; --card:#181b21; --ink:#e8eaee; --mute:#9aa3b2; --line:#2a2f38; --acc:#3fcf8e; --neg:#ff6b5e; --hl:#163326; --warn:#2a2416; }} }}
* {{ box-sizing:border-box }}
body {{ margin:0; background:var(--bg); color:var(--ink); font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif }}
main {{ max-width:1000px; margin:0 auto; padding:24px 16px 64px }}
h1 {{ margin:0 0 4px; font-size:28px }} h2 {{ margin:36px 0 12px; font-size:21px }}
h3.day {{ margin:28px 0 8px; font-size:18px }} h4 {{ margin:16px 0 6px; font-size:14px; color:var(--mute); text-transform:uppercase; letter-spacing:.03em }}
.sub {{ color:var(--mute); margin:0 }}
.how {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:14px 18px; margin:18px 0 }}
.how ol {{ margin:6px 0 0; padding-left:20px }} .how li {{ margin:4px 0 }}
.warn {{ background:var(--warn); border-radius:8px; padding:10px 14px; margin:12px 0; color:var(--mute); font-size:13px }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:12px }}
.pick {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:14px 16px }}
.pick-top {{ display:flex; justify-content:space-between; gap:8px; font-size:12px; color:var(--mute) }}
.pick h3 {{ margin:6px 0 6px; font-size:17px }} .vs {{ color:var(--mute); font-weight:400; font-size:13px }}
.bet {{ margin:0 0 6px; font-size:17px; font-weight:700; color:var(--acc) }}
.line {{ margin:0 0 6px }} .small {{ font-size:12px; color:var(--mute) }}
.mine {{ margin:0 0 8px; font-size:14px; padding:8px 10px; border-radius:8px; background:var(--hl) }}
.tag {{ font-size:11px; padding:1px 7px; border-radius:99px; border:1px solid var(--line) }}
.tag-hi {{ background:var(--hl); color:var(--acc); border-color:transparent }}
.empty {{ color:var(--mute) }}
.search {{ width:100%; padding:10px 12px; border-radius:10px; border:1px solid var(--line); background:var(--card); color:var(--ink); font-size:15px; margin:4px 0 4px }}
.list {{ background:var(--card); border:1px solid var(--line); border-radius:12px }}
.row {{ display:grid; grid-template-columns:48px 1fr auto; gap:10px; padding:10px 12px; border-bottom:1px solid var(--line); align-items:start }}
.row:last-child {{ border-bottom:0 }}
.row .t {{ font-variant-numeric:tabular-nums; color:var(--mute); padding-top:1px }}
.row .teams {{ font-size:13px; color:var(--mute) }} .row .pr {{ margin:2px 0 }}
.mini {{ text-align:right; min-width:64px }} .mini span {{ display:block; font-size:11px; color:var(--mute) }}
.mini b {{ font-size:19px; font-variant-numeric:tabular-nums }}
.tbl {{ overflow-x:auto; background:var(--card); border:1px solid var(--line); border-radius:12px }}
table {{ border-collapse:collapse; width:100%; font-size:14px }}
th, td {{ padding:8px 10px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top }}
th {{ font-size:12px; color:var(--mute); font-weight:600; white-space:nowrap }}
td.num {{ text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap }} td.big {{ font-size:17px; font-weight:700 }}
td.teams {{ min-width:140px }} td small {{ display:block; color:var(--mute); font-size:11px }}
.stats {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:10px; margin:8px 0 }}
.stats div {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:12px }}
.stats b {{ display:block; font-size:22px }} .stats span {{ font-size:12px; color:var(--mute) }}
.pos {{ color:var(--acc) }} .neg {{ color:var(--neg) }}
details {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:12px 16px; margin:10px 0 }}
summary {{ cursor:pointer; font-weight:600 }}
details[open] summary {{ margin-bottom:10px }}
.conf {{ display:inline-block; font-size:12px; padding:2px 8px; border-radius:99px; border:1px solid var(--line) }}
footer {{ margin-top:30px; color:var(--mute); font-size:12px }}
</style></head><body><main>
  <h1>Pronostics du jour</h1>
  <p class="sub">{e(fr_date(today))} · {len(items)} matchs dans {n_comps} compétitions · heures de Côte d'Ivoire (GMT)</p>

  <div class="how"><b>Comment s'en servir</b>
    <ol>
      <li>Lis le <b>pronostic</b> du match et ses <b>chances</b> (probabilité que ça arrive).</li>
      <li>Sur {e(MY_BOOK_NAME)}, regarde la cote de ce pronostic.</li>
      <li>Si la cote {e(MY_BOOK_NAME)} est <b>égale ou plus haute</b> que la « cote mini » du site, le pari est intéressant. Sinon, passe : la cote ne paie pas assez le risque.</li>
    </ol>
    <div class="warn">Un pronostic à 60 % de chances perd quand même 4 fois sur 10. Aucun site ne garantit de gagner : ne mise que ce que tu peux perdre.</div>
  </div>

  <h2>⭐ Paris conseillés</h2>
  <p class="sub">Les matchs où au moins un bookmaker paie plus que la valeur juste. C'est la seule méthode qui a gagné sur nos tests.</p>
  <div class="grid" style="margin-top:10px">{cards}</div>

  <h2>Tous les pronostics</h2>
  <input class="search" id="q" type="search" placeholder="Chercher une équipe ou une compétition…">
  {all_html}

  <h2>Pour aller plus loin</h2>
  <details><summary>Bilan réel des paris conseillés (journal)</summary>{journal}</details>
  <details><summary>Ce qu'aurait donné la méthode sur les 12 derniers mois</summary>{bt_html}
    <p class="small">Simulation sur le football européen. Résultat fragile : sur si peu de paris, le hasard peut expliquer l'écart.</p></details>
  <details><summary>Analyse détaillée des matchs européens (buts attendus, modèle)</summary>
    <div class="tbl"><table>
    <thead><tr><th>Date</th><th>Ligue</th><th>Match</th><th>Buts attendus</th><th>Score probable</th>
    <th>1</th><th>N</th><th>2</th><th>+2,5</th><th>Les 2 marquent</th></tr></thead>
    <tbody>{model_table}</tbody></table></div></details>
  <details><summary>D'où viennent les pronostics ?</summary>
    <p><b>Chances</b> : moyenne des probabilités de 20 à 40 bookmakers (leur marge retirée). Ces cotes intègrent toutes les statistiques
    publiques (forme, blessures, xG…) : c'est l'estimation la plus fiable disponible. Pour les championnats européens absents des
    bookmakers, on utilise notre modèle statistique (Poisson, 3 saisons de résultats).</p>
    <p><b>Cote mini</b> : la cote juste (100 ÷ chances) plus {MIN_EDGE * 100:.0f} %. En dessous, le bookmaker garde l'avantage.</p>
    <p><b>Option prudente</b> : quand le favori a moins de 55 % de chances, le site propose aussi la « double chance » (équipe ou nul).</p>
    <p><b>Paris conseillés</b> : un bookmaker offre une cote au-dessus de la valeur juste. Testé sur 2 saisons : environ +2 % par pari,
    alors que suivre notre propre modèle perdait de 5 à 13 %. Mise : quart de Kelly, plafonnée à 3 % du budget.</p>
    <p>Données : football-data.co.uk, The Odds API. Généré le {e(generated_at)}.</p></details>
  <footer>Si le jeu devient un problème, parles-en à un proche ou à un professionnel.</footer>
<script>
document.getElementById('q').addEventListener('input', function () {{
  var q = this.value.toLowerCase().trim();
  document.querySelectorAll('.row[data-q]').forEach(function (tr) {{
    tr.style.display = !q || tr.dataset.q.indexOf(q) >= 0 ? '' : 'none';
  }});
  document.querySelectorAll('[data-comp]').forEach(function (c) {{
    c.style.display = c.querySelector('.row[data-q]:not([style*="none"])') ? '' : 'none';
  }});
}});
</script>
</main></body></html>"""
