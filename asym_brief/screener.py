"""Run the screen across the configured universe."""
from __future__ import annotations

import logging

from .rates import BillCurve, flat_curve
from .structures import (Pick, _atm_iv, find_call_spreads, find_cash_secured_puts, find_collars,
                         find_covered_calls, forecast, realized_vol, top_per_ticker)

log = logging.getLogger("asym_brief")

COLLAR_TIER_RANK = {"Capital-protected": 0, "Protected only if": 1, "Near-protected": 2}


def _tier_rank(p: Pick) -> int:
    for k, v in COLLAR_TIER_RANK.items():
        if p.tier.startswith(k):
            return v
    return 3


def pick_vignettes(collars: list[Pick], enter: list[Pick], hold: list[Pick]) -> dict:
    """One of each: the best-protected Risk Limiter and the best income pick (Entry Optimizer or Rent Check).

    Best-protected = strongest tier first (floor clears zero ignoring dividends), then highest floor, then score.
    Best income = highest annualized yield on the capital involved.
    """
    floor = None
    if collars:
        floor = sorted(collars, key=lambda p: (_tier_rank(p), -p.metrics["floor_return_pct"], -p.score))[0]
    income_pool = enter + hold
    income = None
    if income_pool:
        income = max(income_pool, key=lambda p: p.metrics.get("annualized_yield_pct", p.metrics.get("annualized_income_pct", 0)))
    return {"floor": floor, "income": income}


def run_screen(provider, cfg: dict, curve: BillCurve | None = None) -> dict:
    excluded = {t.upper() for t in cfg["universe"].get("exclude", [])}
    tickers = [t for t in cfg["universe"]["tickers"] if t.upper() not in excluded]
    rf = getattr(provider, "risk_free", cfg["risk_free_default"])
    curve = curve or flat_curve(rf)
    enabled_spreads = cfg.get("call_spread", {}).get("enabled", False)
    risk_profile = cfg.get("forecast", {}).get("risk_profile", "balanced")
    collars: list[Pick] = []
    puts: list[Pick] = []
    calls: list[Pick] = []
    spreads: list[Pick] = []
    forecasts: dict[str, dict] = {}
    skipped: list[str] = []
    dte_lo = min(cfg["collar"]["min_dte"], cfg["cash_secured_put"]["min_dte"], cfg["covered_call"]["min_dte"])
    dte_hi = max(cfg["collar"]["max_dte"], cfg["cash_secured_put"]["max_dte"], cfg["covered_call"]["max_dte"])
    for t in tickers:
        try:
            spot = provider.spot(t)
            q = provider.div_yield(t)
            closes = provider.history(t, 252)
            rv = realized_vol(closes, 60)
            chains = {e: provider.chain(t, e) for e in provider.expiries(t)
                      if dte_lo <= (e - provider.asof).days <= dte_hi}
            near = next(iter(sorted(chains.items(), key=lambda kv: abs((kv[0] - provider.asof).days - 45))), None)
            atm_iv = _atm_iv(near[1], spot) if near else float("nan")
            forecasts[t] = forecast(spot, closes, atm_iv, rv, risk_profile, cfg)
            new = (find_collars(t, spot, chains, provider.asof, curve, q, cfg),
                   find_cash_secured_puts(t, spot, chains, provider.asof, curve, q, rv, cfg),
                   find_covered_calls(t, spot, chains, provider.asof, curve, q, rv, cfg))
            collars += new[0]
            puts += new[1]
            calls += new[2]
            if enabled_spreads:
                spreads += find_call_spreads(t, spot, chains, provider.asof, rf, q, rv, cfg)
        except Exception as exc:  # one bad ticker must never kill the whole issue
            log.warning("skipping %s: %s", t, exc)
            skipped.append(f"{t} ({type(exc).__name__})")
    n = cfg["newsletter"]["top_n_per_structure"]
    top_collars = top_per_ticker(collars)[:n]
    top_puts = top_per_ticker(puts)[:n]
    top_calls = top_per_ticker(calls)[:n]
    return {
        "asof": provider.asof,
        "risk_free": rf,
        "curve_source": curve.source,
        "collars": top_collars,
        "puts": top_puts,
        "covered_calls": top_calls,
        "call_spreads": top_per_ticker(spreads)[:n],
        "vignettes": pick_vignettes(top_collars, top_puts, top_calls),
        "forecasts": forecasts,
        "n_candidates": len(collars) + len(puts) + len(calls) + len(spreads),
        "skipped": skipped,
        "tickers": tickers,
    }
