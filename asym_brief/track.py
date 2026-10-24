"""Public track record: log every published pick, then mark them to market.

Logging every pick (not just winners) is the credibility moat and also protects you from
cherry-picking claims. Marks use the current mid; expired picks settle at intrinsic value
using the last close. Dividends and commissions are ignored in marks.
"""
from __future__ import annotations

import csv
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

from .structures import Pick

FIELDS = ["id", "asof", "ticker", "structure", "expiry", "spot", "legs", "metrics"]


def log_picks(path: Path, picks: list[Pick], asof: date) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = set()
    if path.exists():
        with path.open() as f:
            existing = {r["id"] for r in csv.DictReader(f)}
    new = [p for p in picks if p.id not in existing]
    write_header = not path.exists()
    with path.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if write_header:
            w.writeheader()
        for p in new:
            w.writerow({"id": p.id, "asof": asof.isoformat(), "ticker": p.ticker, "structure": p.structure,
                        "expiry": p.expiry.isoformat(), "spot": p.spot,
                        "legs": json.dumps([asdict(l) for l in p.legs]), "metrics": json.dumps(p.metrics)})
    return len(new)


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
        return {"n": 0, "open": [], "closed": [], "hit_rate": None}
    with path.open() as f:
        rows = list(csv.DictReader(f))
    open_, closed = [], []
    for r in rows:
        legs = json.loads(r["legs"])
        expiry = date.fromisoformat(r["expiry"])
        try:
            spot_now = provider.spot(r["ticker"])
            chain = None if provider.asof >= expiry else provider.chain(r["ticker"], expiry)
        except Exception:
            continue
        pnl, ok = 0.0, True
        for leg in legs:
            v = _leg_value(leg, provider, r["ticker"], expiry, spot_now, chain)
            if v is None:
                ok = False
                break
            pnl += leg["side"] * (v - leg["px"])
        if not ok:
            continue
        m = json.loads(r["metrics"])
        risk = m.get("max_loss") or float(r["spot"])  # spreads: debit; collars: capital in the stock
        item = {"id": r["id"], "asof": r["asof"], "ticker": r["ticker"], "structure": r["structure"],
                "expiry": r["expiry"], "pnl_per_share": round(pnl, 3), "return_pct": round(100 * pnl / risk, 1)}
        (closed if provider.asof >= expiry else open_).append(item)
    wins = [c for c in closed if c["pnl_per_share"] > 0]
    return {"n": len(rows), "open": open_, "closed": closed,
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
    out["by_structure"] = by
    return out


def render_track_record(scorecard: dict, cfg: dict, asof: date, path: Path) -> Path:
    """Write a public, self-contained track-record page from the marked pick log."""
    import html

    b = cfg["brand"]
    sm = summarize(scorecard)
    e = html.escape

    def pct(x):
        return "n/a" if x is None else f"{x:+.1f}%"

    def rows(items):
        return "".join(
            f"<tr><td>{e(i['asof'])}</td><td>{e(i['ticker'])}</td><td>{e(i['structure'])}</td><td>{e(i['expiry'])}</td>"
            f"<td style='text-align:right'>{i['return_pct']:+.1f}%</td></tr>" for i in sorted(items, key=lambda x: x["asof"], reverse=True))

    if sm["n"] == 0:
        body = "<p>No ideas have been published yet, so there is no history to show. This page fills in automatically with the first issue.</p>"
    else:
        body = (
            f"<p>{sm['n']} ideas logged, {sm['settled']} settled and {sm['open']} still open.</p>"
            + (f"<p>Among the settled ideas: typical result {pct(sm['median'])}, best {pct(sm['best'])}, worst {pct(sm['worst'])}. "
               f"{sm['positive_pct']}% finished positive.</p>" if sm["settled"] else "<p>Nothing has settled yet.</p>")
            + "<p><b>How to read this.</b> Income ideas (Rent Check, Entry Optimizer) can finish positive most of the time and still lose a lot "
              "in the few cases that go wrong, so the worst result matters as much as the share that finished positive. "
              "Results are the return on the most you could lose. Marks use mid prices and ignore dividends, commissions and taxes. "
              "Small numbers prove very little: statistics describe odds, not results.</p>"
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
