"""Render the issue (HTML + plain text) and auto-generated social snippets."""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from . import charts

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"

DISCLAIMER = (
    "For educational and informational purposes only. This is general, impersonal information sent to all "
    "subscribers; it is not personalized investment advice, a recommendation, or an offer to buy or sell any "
    "security, and the author is not your financial advisor. Options involve risk and are not suitable for "
    "every investor. Prices are delayed or modeled, fills are assumed conservatively and may not be "
    "achievable, and past results do not guarantee future results. Do your own research or consult a "
    "licensed professional."
)


def _legs_text(p) -> str:
    parts = []
    for l in p.legs:
        verb = "Buy" if l.side > 0 else "Sell"
        if l.kind == "stock":
            parts.append(f"{verb} 100 shares @ {l.px:.2f}")
        else:
            parts.append(f"{verb} {p.expiry:%b %d %Y} {l.strike:g} {l.kind} @ {l.px:.2f}")
    return "; ".join(parts)


APPROVAL_NOTE = ("Brokers set options approval levels differently: confirm yours allows this strategy before "
                 "placing anything. Cash-secured puts and covered calls are usually the most basic approvals; "
                 "collars often need a bit more.")


def card(pick, cfg: dict) -> dict:
    """Plain-dollar card for one pick: per 100 shares, worst case first."""
    k = charts.key_numbers(pick)
    m = pick.metrics
    name = cfg["brand"]["prongs"][pick.prong]["name"] if pick.prong in cfg["brand"].get("prongs", {}) else pick.structure
    date_s = f"{pick.expiry:%b %d, %Y}"
    t = pick.ticker
    bill_dollars = k["capital"] * m.get("bill_yield_pct", 0) / 100 * pick.dte / 365
    if pick.prong == "protect":
        put = next(l for l in pick.legs if l.kind == "put")
        call = next(l for l in pick.legs if l.kind == "call")
        headline = (f"Own 100 {t} shares until {date_s} and your worst case is {charts.money(k['worst'])}, "
                    f"while the most you can make is {charts.money(k['best'], True)}.")
        give_up = (f"Above {call.strike:g} you stop gaining, so a big rally leaves you behind simply owning the shares. "
                   f"The floor sits at {put.strike:g}.")
    elif pick.prong == "enter":
        headline = (f"Get paid {charts.money(m['premium']*100)} now for agreeing to buy 100 {t} shares at {m['strike']:g} "
                    f"by {date_s}. If it stays above {m['strike']:g} you keep the money and buy nothing; if it falls "
                    f"below, you own it at an effective {m['breakeven']:.2f}, {m['discount_to_spot_pct']}% under today's price.")
        rr0 = charts.risk_reward(pick)
        give_up = ("If the stock rallies, the premium is all you earn. "
                   f"If it falls below {m['strike']:g}, you buy 100 shares at {m['strike']:g} (effective {m['breakeven']:.2f}) and every $1 lower costs you another $100. "
                   f"At zero the mathematical worst case is {charts.money(rr0['max_loss'])}. "
                   "This is stock risk with a cushion, not a floor.")
    else:
        headline = (f"Collect {charts.money(m['premium']*100)} now for agreeing to sell 100 {t} shares you own at "
                    f"{m['strike']:g} by {date_s}. If it stays below {m['strike']:g} you keep the shares and the money.")
        give_up = (f"Gains stop at {m['strike']:g}. The {charts.money(m['premium']*100)} cushions a small drop "
                   f"(breakeven {m['cushion_breakeven']:.2f}); it is not a floor.")
    rr = charts.risk_reward(pick)

    return {
        "reward_risk": charts.mult_text(rr["ratio"]), "reward_risk_30": charts.mult_text(rr["ratio_30"]),
        "max_loss": charts.money(rr["max_loss"]), "max_gain": charts.money(rr["max_gain"], True) if rr["max_gain"] is not None else "No cap",
        "loss_30": charts.money(rr["loss_30"]), "is_collar": pick.prong == "protect",
        "name": name, "title": f"{t} {name}", "headline": headline, "give_up": give_up,
        "worst": charts.money(k["worst"]), "best": charts.money(k["best"], True) if k["best"] is not None else "No cap",
        "capital": charts.money(k["capital"]), "bill_dollars": charts.money(bill_dollars),
        "scenarios": [{"move": f"{x['move']:+d}%" if x['move'] else "Flat", "price": x["price"],
                       "own": charts.money(x["own"], True), "strategy": charts.money(x["strategy"], True)}
                      for x in charts.scenarios(pick)],
        "approval": APPROVAL_NOTE,
    }


def _build_vignettes(result: dict, cfg: dict, out_dir: Path) -> list[dict]:
    vig = []
    base = (cfg.get("chart_base_url") or "").rstrip("/")
    for slot, label in (("floor", "Best protected"), ("income", "Best income")):
        p = result["vignettes"].get(slot)
        if p is None:
            vig.append({"slot": slot, "label": label, "pick": None})
            continue
        c = card(p, cfg)
        fname = f"{p.id}.png"
        png_ok = False
        try:
            charts.payoff_png(p, cfg, out_dir / "charts" / fname)
            png_ok = True
        except Exception:  # matplotlib missing: fall back to inline SVG only
            pass
        c.update({"slot": slot, "label": label, "pick": p, "svg": Markup(charts.payoff_svg(p, cfg)),
                  "img_url": f"{base}/{fname}" if (base and png_ok) else "", "alt": charts.aria(p, cfg),
                  "forecast": result["forecasts"].get(p.ticker)})
        vig.append(c)
    return vig


def render_issue(result: dict, cfg: dict, provider, scorecard: dict | None, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html"]))
    env.filters["legs"] = _legs_text
    ctx = {"r": result, "cfg": cfg, "brand": cfg["brand"], "provider": provider, "scorecard": scorecard,
           "disclaimer": DISCLAIMER, "synthetic": provider.synthetic,
           "vignettes": _build_vignettes(result, cfg, out_dir), "prongs": cfg["brand"]["prongs"]}
    html = env.get_template("issue.html.j2").render(**ctx)
    txt = env.get_template("issue.txt.j2").render(**ctx)
    social = env.get_template("social.txt.j2").render(**ctx)
    stem = f"issue-{result['asof'].isoformat()}"
    paths = {}
    for name, body in (("html", html), ("txt", txt)):
        p = out_dir / f"{stem}.{name}"
        p.write_text(body)
        paths[name] = p
    p = out_dir / f"social-{result['asof'].isoformat()}.txt"
    p.write_text(social)
    paths["social"] = p
    return paths
