"""Public track record: log every published pick, then mark them to market.

Logging every pick (not just winners) is the credibility moat and also protects you from
cherry-picking claims. Marks use the current mid; expired picks settle at intrinsic value
using the last close. Dividends and commissions are ignored in marks.
"""
from __future__ import annotations

import csv
import json
import pandas as pd
from dataclasses import asdict
from datetime import date
from pathlib import Path

from .structures import Pick

FIELDS = ["id", "asof", "ticker", "structure", "expiry", "spot", "legs", "metrics"]


def pick_rows(picks: list[Pick], asof: date) -> list[dict]:
    return [{"id": p.id, "asof": asof.isoformat(), "ticker": p.ticker, "structure": p.structure,
             "expiry": p.expiry.isoformat(), "spot": p.spot,
             "legs": json.dumps([asdict(l) for l in p.legs]), "metrics": json.dumps(p.metrics)} for p in picks]


def append_rows(path: Path, rows: list[dict]) -> int:
    """Append rows whose id is not already logged. Called only after an issue was actually sent."""
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = set()
    if path.exists():
        with path.open() as f:
            existing = {r["id"] for r in csv.DictReader(f)}
    new = [r for r in rows if r["id"] not in existing]
    write_header = not path.exists()
    with path.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if write_header:
            w.writeheader()
        w.writerows(new)
    return len(new)


def log_picks(path: Path, picks: list[Pick], asof: date) -> int:
    return append_rows(path, pick_rows(picks, asof))


def _leg_value(leg: dict, provider, ticker: str, expiry: date, spot_now: float, chain):
    if leg["kind"] == "stock":
        return spot_now
    if provider.asof >= expiry:  # settle at intrinsic
        k = leg["strike"]
        return max(spot_now - k, 0.0) if leg["kind"] == "call" else max(k - spot_now, 0.0)
    row = chain[(chain.type == leg["kind"]) & ((chain.strike - leg["strike"]).abs() < 1e-6)]
    if row.empty:
        return None
    r = row.iloc[0]
    return (float(r.bid) + float(r.ask)) / 2.0


def mark_log(path: Path, provider) -> dict:
    """Return a summary of open and closed picks with per-pick return on capital at risk."""
    if not path.exists():
        return {"n": 0, "open": [], "closed": [], "unmarked": [], "hit_rate": None}
    with path.open() as f:
        rows = list(csv.DictReader(f))
    open_, closed, unmarked = [], [], []
    for r in rows:
        legs = json.loads(r["legs"])
        expiry = date.fromisoformat(r["expiry"])
        try:
            if provider.asof >= expiry:
                # settle on the close of expiry day, not on today's price
                hist = provider.history(r["ticker"], 252)
                hist = hist[hist.index <= pd.Timestamp(expiry)]
                if hist.empty:
                    raise ValueError("no close on or before expiry")
                spot_now, chain = float(hist.iloc[-1]), None
            else:
                spot_now, chain = provider.spot(r["ticker"]), provider.chain(r["ticker"], expiry)
        except Exception:
            unmarked.append(r["id"])
            continue
        pnl, ok = 0.0, True
        for leg in legs:
            v = _leg_value(leg, provider, r["ticker"], expiry, spot_now, chain)
            if v is None:
                ok = False
                break
            pnl += leg["side"] * (v - leg["px"])
        if not ok:
            unmarked.append(r["id"])  # never drop an idea silently: the page says how many could not be marked
            continue
        m = json.loads(r["metrics"])
        risk = m.get("max_loss") or float(r["spot"])  # spreads: debit; collars: capital in the stock
        item = {"id": r["id"], "asof": r["asof"], "ticker": r["ticker"], "structure": r["structure"],
                "expiry": r["expiry"], "pnl_per_share": round(pnl, 3), "return_pct": round(100 * pnl / risk, 1)}
        (closed if provider.asof >= expiry else open_).append(item)
    wins = [c for c in closed if c["pnl_per_share"] > 0]
    return {"n": len(rows), "open": open_, "closed": closed, "unmarked": unmarked,
            "hit_rate": round(100 * len(wins) / len(closed), 1) if closed else None}


def summarize(scorecard: dict) -> dict:
    """Plain numbers for the track-record page. Returns on the most you could lose, after mid-price marks."""
    import statistics

    closed = scorecard.get("closed", [])
    rets = [c["return_pct"] for c in closed]
    out = {"n": scorecard.get("n", 0), "open": len(scorecard.get("open", [])), "settled": len(closed),
           "median": None, "best": None, "worst": None, "positive_pct": None}
    if rets:
        out.update(median=round(statistics.median(rets), 1), best=max(rets), worst=min(rets),
                   positive_pct=round(100 * sum(1 for r in rets if r > 0) / len(rets)))
    by = {}
    for c in closed + scorecard.get("open", []):
        by[c["structure"]] = by.get(c["structure"], 0) + 1
    out["unmarked"] = len(scorecard.get("unmarked", []))
    out["by_structure"] = by
    return out


def _stats(items: list[dict]) -> dict:
    import statistics

    rets = [i["return_pct"] for i in items]
    if not rets:
        return {"n": 0, "settled": 0, "avg": None, "median": None, "worst": None, "positive_pct": None}
    return {"n": len(rets), "settled": sum(1 for i in items if i.get("settled")),
            "avg": round(statistics.mean(rets), 1), "median": round(statistics.median(rets), 1),
            "worst": min(rets), "positive_pct": round(100 * sum(1 for r in rets if r > 0) / len(rets))}


def period_returns(scorecard: dict, asof: date) -> dict:
    """Group every logged idea by the date it was published: last 7 days, last 30 days, year to date,
    plus one row per week (Monday start) and per month. Open ideas count at their current mid-price mark.
    These are averages of per-idea results, not the return of a portfolio you could have held."""
    from datetime import timedelta

    items = ([dict(c, settled=True) for c in scorecard.get("closed", [])]
             + [dict(o, settled=False) for o in scorecard.get("open", [])])
    for i in items:
        i["_d"] = date.fromisoformat(i["asof"])

    def within(start):
        return [i for i in items if start <= i["_d"] <= asof]

    windows = {"Last 7 days": _stats(within(asof - timedelta(days=6))),
               "Last 30 days": _stats(within(asof - timedelta(days=29))),
               f"{asof.year} to date": _stats(within(date(asof.year, 1, 1)))}
    weeks, months = {}, {}
    for i in items:
        weeks.setdefault(i["_d"] - timedelta(days=i["_d"].weekday()), []).append(i)
        months.setdefault(i["_d"].replace(day=1), []).append(i)
    return {"windows": windows,
            "weeks": [(k, _stats(v)) for k, v in sorted(weeks.items(), reverse=True)],
            "months": [(k, _stats(v)) for k, v in sorted(months.items(), reverse=True)]}


def render_track_record(scorecard: dict, cfg: dict, asof: date, path: Path) -> Path:
    """Write a public, self-contained track-record page from the marked pick log."""
    import html

    b = cfg["brand"]
    sm = summarize(scorecard)
    pr = period_returns(scorecard, asof)
    e = html.escape

    def pct(x):
        return "n/a" if x is None else f"{x:+.1f}%"

    def rows(items):
        return "".join(
            f"<tr><td>{e(i['asof'])}</td><td>{e(i['ticker'])}</td><td>{e(i['structure'])}</td><td>{e(i['expiry'])}</td>"
            f"<td style='text-align:right'>{i['return_pct']:+.1f}%</td></tr>" for i in sorted(items, key=lambda x: x["asof"], reverse=True))

    def period_table(label_head, rows_):
        head = (f"<tr><td><b>{label_head}</b></td><td style='text-align:right'><b>Ideas</b></td>"
                "<td style='text-align:right'><b>Average</b></td><td style='text-align:right'><b>Worst</b></td>"
                "<td style='text-align:right'><b>Finished positive</b></td></tr>")
        body_ = "".join(
            f"<tr><td>{e(lbl)}</td><td style='text-align:right'>{s['n']} ({s['settled']} settled)</td>"
            f"<td style='text-align:right'>{pct(s['avg'])}</td><td style='text-align:right'>{pct(s['worst'])}</td>"
            f"<td style='text-align:right'>{'n/a' if s['positive_pct'] is None else str(s['positive_pct']) + '%'}</td></tr>"
            for lbl, s in rows_ if s["n"])
        return f"<table>{head}{body_}</table>"

    note = b.get("track_record_note", "")
    note_html = f"<p class='fine'><b>Note on earlier entries.</b> {e(note)}</p>" if note else ""
    returns_html = (
        "<h2>Results by period</h2>"
        "<p class='fine'>Each row averages the results of the ideas we published in that period, so the first row is the ideas "
        "from the last 7 days. This is not the return of a portfolio you could have held: ideas overlap, sizes differ, and open ideas "
        "are counted at today's mid-price mark and can still change.</p>"
        + period_table("Period", list(pr["windows"].items()))
        + "<h3>By week published</h3>"
        + period_table("Week of", [(f"{k:%b %d, %Y}", s) for k, s in pr["weeks"]])
        + "<h3>By month published</h3>"
        + period_table("Month", [(f"{k:%B %Y}", s) for k, s in pr["months"]]))

    if sm["n"] == 0:
        body = "<p>No ideas have been published yet, so there is no history to show. This page fills in automatically with the first issue.</p>"
    else:
        body = (
            f"<p>{sm['n']} ideas logged, {sm['settled']} settled and {sm['open']} still open.</p>"
            + (f"<p class='fine'>{sm['unmarked']} logged idea(s) could not be priced today (no usable quote) and are not in the results below. "
               "We count them here instead of leaving them out silently.</p>" if sm["unmarked"] else "")
            + (f"<p>Among the settled ideas: typical result {pct(sm['median'])}, best {pct(sm['best'])}, worst {pct(sm['worst'])}. "
               f"{sm['positive_pct']}% finished positive.</p>" if sm["settled"] else "<p>Nothing has settled yet.</p>")
            + "<p><b>How to read this.</b> Income ideas (Rent Check, Entry Optimizer) can finish positive most of the time and still lose a lot "
              "in the few cases that go wrong, so the worst result matters as much as the share that finished positive. "
              "Results are the return on the most you could lose. Marks use mid prices and ignore dividends, commissions and taxes. "
              "Small numbers prove very little: statistics describe odds, not results.</p>"
            + note_html
            + returns_html
            + f"<h2>Settled</h2><table>{rows(scorecard.get('closed', [])) or '<tr><td>None yet</td></tr>'}</table>"
            + f"<h2>Open</h2><table>{rows(scorecard.get('open', [])) or '<tr><td>None</td></tr>'}</table>")
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(b['short'])} track record</title>
<style>body{{font-family:system-ui,sans-serif;max-width:720px;margin:0 auto;padding:16px;line-height:1.55;color:#1c2330}}
table{{width:100%;border-collapse:collapse;font-size:14px}}td{{border-top:1px solid #e1e4ea;padding:6px 4px}}.fine{{font-size:12px;color:#5b6577}}</style></head>
<body><h1>{e(b['short'])} track record</h1><p class="fine">Updated {asof:%B %d, %Y}. Every idea we publish is logged here, winners and losers.</p>{body}
<p class="fine">{e(b['transparency_short'])} Educational only, not personalized investment advice. Options involve risk. Past results do not guarantee future results.</p></body></html>"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page)
    return path
