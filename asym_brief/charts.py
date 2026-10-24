"""Plain-dollar payoff numbers and charts for newsletter vignettes.

All payoffs are per 100 shares at expiry, in dollars, ignoring dividends, commissions and taxes
(the chart footnote says so). One payoff function drives the scenario table, the SVG and the PNG,
so the three can never disagree.

Email clients such as Gmail strip inline SVG and data URIs, so emails use the PNG via a hosted URL
(`chart_base_url` in config.json). The SVG is used for the web archive and local previews.
"""
from __future__ import annotations

import io
from pathlib import Path

import numpy as np

MOVES = (-20, 0, 10, 20)  # stock move scenarios, percent
LO, HI = 0.70, 1.30      # chart x-range as a fraction of spot

STRAT = "#2a78d6"   # the strategy line (the one accent)
OWN = "#7d7c77"     # just owning 100 shares (neutral gray)
GRID = "#e3e2de"
AXIS = "#9a9992"
TEXT = "#44433f"
BG = "#ffffff"


def payoff(pick, S: float) -> float:
    """Profit or loss in dollars on one 100-share-sized position at expiry, stock price S."""
    total = 0.0
    for leg in pick.legs:
        if leg.kind == "stock":
            val = S
        elif leg.kind == "call":
            val = max(S - leg.strike, 0.0)
        else:
            val = max(leg.strike - S, 0.0)
        total += leg.side * (val - leg.px)
    return total * 100.0


def own(pick, S: float) -> float:
    return (S - pick.spot) * 100.0


def label_for(pick, cfg: dict) -> str:
    return {"protect": "Rain Gear", "hold": "Rent Check", "enter": "Waiting Room"}.get(pick.prong, pick.structure)


def money(x: float, plus: bool = False) -> str:
    x = round(x)
    sign = "-" if x < 0 else ("+" if plus and x > 0 else "")
    return f"{sign}${abs(x):,.0f}"


def scenarios(pick) -> list[dict]:
    out = []
    for m in MOVES:
        S = pick.spot * (1 + m / 100.0)
        out.append({"move": m, "price": round(S, 2), "own": own(pick, S), "strategy": payoff(pick, S)})
    return out


def key_numbers(pick) -> dict:
    """Worst case, best case and breakeven in dollars for the card."""
    grid = np.linspace(0.0, pick.spot * 3.0, 3001)
    vals = np.array([payoff(pick, float(s)) for s in grid])
    worst, best = float(vals.min()), float(vals.max())
    capped = best < payoff(pick, pick.spot * 3.0) - 1e-6 or abs(best - float(vals[-1])) < 1e-6
    # unbounded upside only if payoff still rising at 3x spot
    rising = payoff(pick, pick.spot * 3.0) > payoff(pick, pick.spot * 2.9) + 1e-6
    be = None
    sign = np.sign(vals)
    for i in range(1, len(vals)):
        if sign[i - 1] < 0 <= sign[i]:
            be = float(grid[i])
            break
    return {"worst": worst, "best": None if rising else best, "breakeven_price": be,
            "capital": pick.metrics.get("capital", pick.spot * 100.0)}


def risk_reward(pick) -> dict:
    """Max loss, max gain and reward/risk (best case divided by worst case; higher is better) in dollars per 100 shares.

    Max loss is the true worst case over any stock price from zero up (stock to zero for a covered call or
    cash-secured put). `loss_30` is the loss if the stock falls 30% instead, for context. Ratio is None when
    gains are uncapped or there is no loss at all.
    """
    grid = np.linspace(0.0, pick.spot * 3.0, 3001)
    vals = np.array([payoff(pick, float(s)) for s in grid])
    max_loss = float(-min(vals.min(), 0.0))
    uncapped = payoff(pick, pick.spot * 3.0) > payoff(pick, pick.spot * 2.9) + 1e-6
    max_gain = None if uncapped else float(vals.max())
    loss30 = float(max(-payoff(pick, pick.spot * 0.7), 0.0))
    ratio = (max_gain / max_loss) if (max_gain is not None and max_loss > 1e-9) else None
    ratio30 = (max_gain / loss30) if (max_gain is not None and loss30 > 1e-9) else None
    return {"max_loss": max_loss, "max_gain": max_gain, "ratio": ratio, "loss_30": loss30, "ratio_30": ratio30}


def pct_text(x) -> str:
    return "n/a" if x is None else f"{x * 100:,.0f}%"


def mult_text(x) -> str:
    """Reward/risk as a multiple: 1.4x, 12x, 0.10x. None (uncapped gain or no possible loss) -> n/a."""
    if x is None:
        return "n/a"
    if x >= 10:
        return f"{x:,.0f}x"
    if x >= 1:
        return f"{x:.1f}x"
    return f"{x:.2f}x"


def _nice_ticks(lo: float, hi: float, n: int = 5):
    span = hi - lo
    raw = span / n
    mag = 10 ** np.floor(np.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)
    start = np.ceil(lo / step) * step
    ticks = []
    t = start
    while t <= hi + 1e-9:
        ticks.append(float(t))
        t += step
    return ticks


def _series(pick, n=121):
    xs = np.linspace(LO, HI, n)
    return xs, [own(pick, pick.spot * x) for x in xs], [payoff(pick, pick.spot * x) for x in xs]


def _compact(v: float) -> str:
    a = abs(v)
    s = f"${a/1000:.1f}".rstrip("0").rstrip(".") + "K" if a >= 1000 else f"${a:.0f}"
    return ("-" if v < 0 else "") + s


def aria(pick, cfg) -> str:
    k = key_numbers(pick)
    best = f"best case {money(k['best'], True)}" if k["best"] is not None else "upside not capped"
    return (f"Payoff chart for {pick.ticker} {label_for(pick, cfg)} at expiry per 100 shares: "
            f"worst case {money(k['worst'])}, {best}. Compared with simply owning 100 shares.")


def payoff_svg(pick, cfg: dict, width: int = 640, height: int = 300) -> str:
    xs, own_y, st_y = _series(pick)
    ys = own_y + st_y
    lo, hi = min(ys), max(ys)
    pad = (hi - lo) * 0.08
    lo, hi = min(lo - pad, -pad), max(hi + pad, pad)
    ml, mr, mt, mb = 52, 96, 14, 44
    W, H = width, height
    pw, ph = W - ml - mr, H - mt - mb

    def X(v):
        return ml + (v - LO) / (HI - LO) * pw

    def Y(v):
        return mt + (hi - v) / (hi - lo) * ph

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="100%" role="img" '
             f'aria-label="{aria(pick, cfg)}" style="max-width:{W}px;display:block;background:{BG};font-family:Arial,Helvetica,sans-serif">']
    for t in _nice_ticks(lo, hi):
        parts.append(f'<line x1="{ml}" x2="{ml+pw}" y1="{Y(t):.1f}" y2="{Y(t):.1f}" stroke="{GRID}" stroke-width="1"/>')
        parts.append(f'<text x="{ml-6}" y="{Y(t)+4:.1f}" font-size="11" text-anchor="end" fill="{TEXT}">{_compact(t)}</text>')
    parts.append(f'<line x1="{ml}" x2="{ml+pw}" y1="{Y(0):.1f}" y2="{Y(0):.1f}" stroke="{AXIS}" stroke-width="1.5"/>')
    for m in (-30, -20, -10, 0, 10, 20, 30):
        x = X(1 + m / 100)
        parts.append(f'<text x="{x:.1f}" y="{H-mb+16}" font-size="11" text-anchor="middle" fill="{TEXT}">{m:+d}%</text>' if m else
                     f'<text x="{x:.1f}" y="{H-mb+16}" font-size="11" text-anchor="middle" fill="{TEXT}">0%</text>')
    parts.append(f'<text x="{ml+pw/2:.1f}" y="{H-5}" font-size="10" text-anchor="middle" fill="{AXIS}">Stock price change by expiry</text>')
    own_pts = " ".join(f"{X(x):.1f},{Y(v):.1f}" for x, v in zip(xs, own_y))
    st_pts = " ".join(f"{X(x):.1f},{Y(v):.1f}" for x, v in zip(xs, st_y))
    parts.append(f'<polyline fill="none" stroke="{OWN}" stroke-width="2" points="{own_pts}"/>')
    parts.append(f'<polyline fill="none" stroke="{STRAT}" stroke-width="2.5" points="{st_pts}"/>')
    parts.append(f'<text x="{ml+pw+6}" y="{Y(own_y[-1])+4:.1f}" font-size="12" fill="{TEXT}">Just own</text>')
    parts.append(f'<text x="{ml+pw+6}" y="{Y(st_y[-1])+4:.1f}" font-size="12" font-weight="700" fill="{TEXT}">{label_for(pick, cfg)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def payoff_png(pick, cfg: dict, path: Path) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    xs, own_y, st_y = _series(pick)
    fig, ax = plt.subplots(figsize=(6.4, 3.0), dpi=150)
    ax.plot([x * 100 - 100 for x in xs], own_y, color=OWN, lw=2, label="Just own 100 shares")
    ax.plot([x * 100 - 100 for x in xs], st_y, color=STRAT, lw=2.5, label=f"{label_for(pick, cfg)} ({pick.structure.lower()})")
    ax.axhline(0, color=AXIS, lw=1.2)
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(AXIS)
    ax.tick_params(colors=TEXT, labelsize=8, length=0)
    ax.set_xticks([-30, -20, -10, 0, 10, 20, 30])
    ax.set_xticklabels(["-30%", "-20%", "-10%", "0%", "+10%", "+20%", "+30%"])
    ax.yaxis.set_major_formatter(lambda v, _: _compact(v))
    ax.set_xlabel("Stock price change by expiry", color=AXIS, fontsize=8)
    ax.legend(frameon=False, fontsize=8, loc="upper left", labelcolor=TEXT)
    fig.patch.set_facecolor(BG)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor=BG)
    plt.close(fig)
    return path
