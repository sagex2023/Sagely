"""Candidate generation and scoring for defined-risk, positive-skew structures.

Three prongs of the Sagely method plus one optional extra:
  * Entry Optimizer (enter) : cash-secured put. Paid to wait; worst case is owning the stock at the breakeven.
  * Rent Check  (hold)   : covered call. Paid to hold; upside is capped, protection is only the premium.
  * Risk Limiter   (protect): collar = long 100 shares + long put + short call. Worst case is the "floor".
  * Call spread (optional, off by default): worst case is the debit paid.

Every number is per share and uses conservative fills (see fill_price). Rankings are
heuristics for surfacing ideas, not forecasts or expected returns.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd

from .pricing import prob_finish_above, prob_finish_below


@dataclass
class Leg:
    kind: str  # "stock" | "call" | "put"
    side: int  # +1 long, -1 short
    strike: float | None
    px: float  # entry fill price per share


@dataclass
class Pick:
    id: str
    ticker: str
    structure: str
    expiry: date
    dte: int
    spot: float
    legs: list[Leg]
    metrics: dict = field(default_factory=dict)
    score: float = 0.0
    tier: str = ""
    notes: list[str] = field(default_factory=list)
    prong: str = ""  # "enter" | "hold" | "protect" | "" (extras)


def fill_price(row: pd.Series, side: int, slip: float) -> float | None:
    """Conservative fill: move `slip` of the way from mid to the adverse side of the market.

    side=+1 (buying) pays more than mid, side=-1 (selling) receives less. Returns None if a
    sell would have no bid.
    """
    bid, ask = float(row["bid"]), float(row["ask"])
    if ask <= 0 or ask < bid:
        return None
    if side < 0 and bid <= 0:
        return None
    mid = (bid + ask) / 2.0
    half = (ask - bid) / 2.0
    return round(mid + side * slip * half, 4)


def _liquid(row: pd.Series, cfg: dict) -> bool:
    bid, ask = float(row["bid"]), float(row["ask"])
    if ask <= 0:
        return False
    mid = (bid + ask) / 2.0
    spread_pct = (ask - bid) / mid if mid > 0 else 1.0
    return (row["openInterest"] >= cfg["min_open_interest"] and spread_pct <= cfg["max_spread_pct"]
            and mid >= cfg.get("min_mid_price", 0.0))


def realized_vol(closes: pd.Series, window: int = 60) -> float:
    r = np.log(closes).diff().dropna().tail(window)
    return float(r.std() * math.sqrt(252)) if len(r) > 5 else float("nan")


def _pick_id(ticker: str, structure: str, expiry: date, strikes: list[float], asof: date) -> str:
    raw = f"{asof}|{ticker}|{structure}|{expiry}|{'/'.join(f'{k:g}' for k in strikes)}"
    return hashlib.sha1(raw.encode()).hexdigest()[:10]


def find_collars(ticker, spot, chain_by_exp, asof, rf, q, cfg) -> list[Pick]:
    c = cfg["collar"]
    out: list[Pick] = []
    rf_at = rf if callable(rf) else (lambda d, _r=rf: _r)  # matched-maturity bill yield, or a flat rate
    for expiry, ch in chain_by_exp.items():
        dte = (expiry - asof).days
        if not (c["min_dte"] <= dte <= c["max_dte"]):
            continue
        T = dte / 365.0
        puts = ch[(ch.type == "put") & (ch.strike >= spot * c["put_moneyness"][0]) & (ch.strike <= spot * c["put_moneyness"][1])]
        calls = ch[(ch.type == "call") & (ch.strike >= spot * c["call_moneyness"][0]) & (ch.strike <= spot * c["call_moneyness"][1])]
        puts = puts[puts.apply(lambda r: _liquid(r, cfg), axis=1)] if len(puts) else puts
        calls = calls[calls.apply(lambda r: _liquid(r, cfg), axis=1)] if len(calls) else calls
        div = spot * q * T
        bill = rf_at(dte)
        carry = spot * bill * T  # what the same capital earns in a bill of the same maturity, locked today
        for _, p in puts.iterrows():
            p_px = fill_price(p, +1, cfg["fill_slippage"])
            if p_px is None:
                continue
            for _, k in calls.iterrows():
                k_px = fill_price(k, -1, cfg["fill_slippage"])
                if k_px is None:
                    continue
                net_debit = p_px - k_px
                floor_pnl = (p.strike - spot) - net_debit + div
                cap_pnl = (k.strike - spot) - net_debit + div
                floor_ret = floor_pnl / spot
                cap_ret = cap_pnl / spot
                if floor_ret < c["min_floor_return"] or cap_ret <= 0:
                    continue
                excess_floor = (floor_pnl - carry) / spot
                excess_cap = (cap_pnl - carry) / spot
                floor_ex_div_ret = (floor_pnl - div) / spot
                # Dividends are modelled from yield x time, are not guaranteed, and can be cut, so the
                # strongest label requires the floor to clear zero WITHOUT them.
                if floor_ex_div_ret >= 0:
                    tier = "Capital-protected (floor >= 0 after costs, ignoring dividends)"
                elif floor_ret >= 0:
                    tier = "Protected only if modelled dividends are paid"
                else:
                    tier = "Near-protected (small worst-case loss)"
                score = cap_ret * 365.0 / dte + 3.0 * floor_ret * 365.0 / dte  # annualised, floor weighted
                out.append(Pick(
                    id=_pick_id(ticker, "collar", expiry, [p.strike, k.strike], asof),
                    ticker=ticker, structure="Collar", expiry=expiry, dte=dte, spot=spot,
                    legs=[Leg("stock", +1, None, round(spot, 4)),
                          Leg("put", +1, float(p.strike), p_px),
                          Leg("call", -1, float(k.strike), k_px)],
                    metrics={
                        "net_option_debit": round(net_debit, 3),
                        "floor_pnl": round(floor_pnl, 3),
                        "floor_return_pct": round(100 * floor_ret, 2),
                        "floor_ex_div_return_pct": round(100 * floor_ex_div_ret, 2),
                        "cap_pnl": round(cap_pnl, 3),
                        "cap_return_pct": round(100 * cap_ret, 2),
                        "floor_vs_tbill_pct": round(100 * excess_floor, 2),
                        "cap_vs_tbill_pct": round(100 * excess_cap, 2),
                        "expected_dividends": round(div, 3),
                        "bill_yield_pct": round(100 * bill, 2),
                        "net_option_cost_pct": round(100 * net_debit / spot, 2),
                        "capital": round(spot * 100, 2),
                    },
                    score=score, tier=tier, prong="protect",
                    notes=["Short call is American-style: watch ex-dividend dates for early assignment.",
                           "Floor assumes you hold the shares to expiry and exclude commissions and taxes."],
                ))
    return out


def find_call_spreads(ticker, spot, chain_by_exp, asof, rf, q, rv, cfg) -> list[Pick]:
    c = cfg["call_spread"]
    out: list[Pick] = []
    for expiry, ch in chain_by_exp.items():
        dte = (expiry - asof).days
        if not (c["min_dte"] <= dte <= c["max_dte"]):
            continue
        T = dte / 365.0
        calls = ch[(ch.type == "call") & (ch.strike >= spot * c["long_moneyness"][0]) & (ch.strike <= spot * c["short_moneyness"][1])]
        calls = calls[calls.apply(lambda r: _liquid(r, cfg), axis=1)] if len(calls) else calls
        longs = calls[(calls.strike >= spot * c["long_moneyness"][0]) & (calls.strike <= spot * c["long_moneyness"][1])]
        shorts = calls[(calls.strike >= spot * c["short_moneyness"][0]) & (calls.strike <= spot * c["short_moneyness"][1])]
        for _, lo in longs.iterrows():
            lo_px = fill_price(lo, +1, cfg["fill_slippage"])
            if lo_px is None:
                continue
            for _, sh in shorts.iterrows():
                if sh.strike <= lo.strike:
                    continue
                sh_px = fill_price(sh, -1, cfg["fill_slippage"])
                if sh_px is None:
                    continue
                debit = lo_px - sh_px
                width = sh.strike - lo.strike
                if debit <= 0 or debit >= width:
                    continue
                max_gain = width - debit
                rr = max_gain / debit
                if rr < c["min_reward_risk"] or debit / spot > c["max_debit_pct"]:
                    continue
                breakeven = lo.strike + debit
                be_move = breakeven / spot - 1.0
                if be_move > c["max_breakeven_move"]:
                    continue
                iv = float(lo.iv) if lo.iv and lo.iv > 0 else float("nan")
                pop = prob_finish_above(spot, breakeven, T, rf, q, iv) if iv == iv else float("nan")
                vol_ratio = (rv / iv) if (iv == iv and rv == rv and iv > 0) else 1.0
                score = rr * (pop if pop == pop else 0.3) * min(1.3, max(0.7, vol_ratio))
                notes = ["Defined risk: the most you can lose is the debit paid.",
                         "Probability is risk-neutral and model-based, not a forecast."]
                if vol_ratio < 0.85:
                    notes.append("Implied vol is well above recent realized vol: you are paying up for the long call.")
                out.append(Pick(
                    id=_pick_id(ticker, "call_spread", expiry, [lo.strike, sh.strike], asof),
                    ticker=ticker, structure="Call debit spread", expiry=expiry, dte=dte, spot=spot,
                    legs=[Leg("call", +1, float(lo.strike), lo_px), Leg("call", -1, float(sh.strike), sh_px)],
                    metrics={
                        "debit": round(debit, 3),
                        "max_loss": round(debit, 3),
                        "max_gain": round(max_gain, 3),
                        "reward_risk": round(rr, 2),
                        "breakeven": round(breakeven, 2),
                        "breakeven_move_pct": round(100 * be_move, 2),
                        "risk_neutral_prob_profit_pct": round(100 * pop, 1) if pop == pop else None,
                        "iv_long_leg_pct": round(100 * iv, 1) if iv == iv else None,
                        "realized_vol_60d_pct": round(100 * rv, 1) if rv == rv else None,
                    },
                    score=score, tier="Defined risk, positive skew", notes=notes, prong="",
                ))
    return out


def _atm_iv(ch: pd.DataFrame, spot: float) -> float:
    ok = ch[(ch.iv > 0)]
    if ok.empty:
        return float("nan")
    near = ok.iloc[(ok.strike - spot).abs().argsort()[:2]]
    return float(near.iv.mean())


def find_cash_secured_puts(ticker, spot, chain_by_exp, asof, rf, q, rv, cfg) -> list[Pick]:
    """Entry Optimizer: sell a put you are happy to be assigned on, fully backed by cash."""
    c = cfg["cash_secured_put"]
    rf_at = rf if callable(rf) else (lambda d, _r=rf: _r)
    out: list[Pick] = []
    for expiry, ch in chain_by_exp.items():
        dte = (expiry - asof).days
        if not (c["min_dte"] <= dte <= c["max_dte"]):
            continue
        T = dte / 365.0
        bill = rf_at(dte)
        puts = ch[(ch.type == "put") & (ch.strike >= spot * c["moneyness"][0]) & (ch.strike <= spot * c["moneyness"][1])]
        puts = puts[puts.apply(lambda r: _liquid(r, cfg), axis=1)] if len(puts) else puts
        for _, p in puts.iterrows():
            prem = fill_price(p, -1, cfg["fill_slippage"])
            if prem is None or prem <= 0:
                continue
            breakeven = float(p.strike) - prem
            discount = 1.0 - breakeven / spot
            yield_on_cash = prem / float(p.strike)
            if discount < c["min_discount_pct"] / 100.0 or yield_on_cash <= 0:
                continue
            ann = yield_on_cash * 365.0 / dte
            iv = float(p.iv) if p.iv and p.iv > 0 else float("nan")
            p_assign = prob_finish_below(spot, float(p.strike), T, bill, q, iv) if iv == iv else float("nan")
            vol_ratio = (iv / rv) if (iv == iv and rv == rv and rv > 0) else 1.0
            if p_assign == p_assign and p_assign > c["max_assignment_prob"]:
                continue
            score = ann * min(1.3, max(0.7, vol_ratio))  # selling rich vol is better than selling cheap vol
            out.append(Pick(
                id=_pick_id(ticker, "csp", expiry, [p.strike], asof),
                ticker=ticker, structure="Cash-secured put", expiry=expiry, dte=dte, spot=spot,
                legs=[Leg("put", -1, float(p.strike), prem)],
                metrics={
                    "premium": round(prem, 3),
                    "strike": float(p.strike),
                    "breakeven": round(breakeven, 2),
                    "discount_to_spot_pct": round(100 * discount, 2),
                    "yield_on_cash_pct": round(100 * yield_on_cash, 2),
                    "annualized_yield_pct": round(100 * ann, 2),
                    "bill_yield_pct": round(100 * bill, 2),
                    "yield_vs_bill_pct": round(100 * (yield_on_cash - bill * T), 2),
                    "assignment_prob_pct": round(100 * p_assign, 1) if p_assign == p_assign else None,
                    "max_loss": round(breakeven, 3),  # per share: stock to zero, premium kept
                    "capital": round(float(p.strike) * 100, 2),
                    "iv_pct": round(100 * iv, 1) if iv == iv else None,
                    "realized_vol_60d_pct": round(100 * rv, 1) if rv == rv else None,
                },
                score=score, tier="Paid to wait (cash-secured, NOT capital-protected)", prong="enter",
                notes=["Worst case: the stock falls to zero and you own it at the strike, less the premium kept. "
                       "This is stock-like risk, not a floor.",
                       "Assignment can happen before expiry. Keep the full cash to buy 100 shares at the strike.",
                       "You miss a rally if the stock rises: the premium is the most you earn."],
            ))
    return out


def find_covered_calls(ticker, spot, chain_by_exp, asof, rf, q, rv, cfg) -> list[Pick]:
    """Rent Check: sell a call against 100 shares you already own."""
    c = cfg["covered_call"]
    rf_at = rf if callable(rf) else (lambda d, _r=rf: _r)
    out: list[Pick] = []
    for expiry, ch in chain_by_exp.items():
        dte = (expiry - asof).days
        if not (c["min_dte"] <= dte <= c["max_dte"]):
            continue
        T = dte / 365.0
        bill = rf_at(dte)
        div = spot * q * T
        calls = ch[(ch.type == "call") & (ch.strike >= spot * c["moneyness"][0]) & (ch.strike <= spot * c["moneyness"][1])]
        calls = calls[calls.apply(lambda r: _liquid(r, cfg), axis=1)] if len(calls) else calls
        for _, k in calls.iterrows():
            prem = fill_price(k, -1, cfg["fill_slippage"])
            if prem is None or prem <= 0:
                continue
            income = prem / spot
            called_pnl = (float(k.strike) - spot) + prem + div
            called_ret = called_pnl / spot
            if called_ret < c["min_called_away_return_pct"] / 100.0:
                continue
            ann = income * 365.0 / dte
            iv = float(k.iv) if k.iv and k.iv > 0 else float("nan")
            p_called = prob_finish_above(spot, float(k.strike), T, bill, q, iv) if iv == iv else float("nan")
            if p_called == p_called and p_called > c["max_called_prob"]:
                continue
            vol_ratio = (iv / rv) if (iv == iv and rv == rv and rv > 0) else 1.0
            score = (ann + 0.5 * called_ret * 365.0 / dte) * min(1.3, max(0.7, vol_ratio))
            out.append(Pick(
                id=_pick_id(ticker, "covered_call", expiry, [k.strike], asof),
                ticker=ticker, structure="Covered call", expiry=expiry, dte=dte, spot=spot,
                legs=[Leg("stock", +1, None, round(spot, 4)), Leg("call", -1, float(k.strike), prem)],
                metrics={
                    "premium": round(prem, 3),
                    "strike": float(k.strike),
                    "income_pct": round(100 * income, 2),
                    "annualized_income_pct": round(100 * ann, 2),
                    "cushion_breakeven": round(spot - prem, 2),
                    "cushion_pct": round(100 * income, 2),
                    "called_away_pnl": round(called_pnl, 3),
                    "called_away_return_pct": round(100 * called_ret, 2),
                    "called_away_ex_div_return_pct": round(100 * (called_pnl - div) / spot, 2),
                    "called_prob_pct": round(100 * p_called, 1) if p_called == p_called else None,
                    "bill_yield_pct": round(100 * bill, 2),
                    "income_vs_bill_pct": round(100 * (income - bill * T), 2),
                    "capital": round(spot * 100, 2),
                    "iv_pct": round(100 * iv, 1) if iv == iv else None,
                    "realized_vol_60d_pct": round(100 * rv, 1) if rv == rv else None,
                    "expected_dividends": round(div, 3),
                },
                score=score, tier="Income on shares you own (cushion = premium only, NOT a floor)", prong="hold",
                notes=["The premium cushions a small drop; it does not protect against a large one. "
                       "Only a collar sets a floor.",
                       "Gains stop at the strike. If the stock rallies past it, shares are called away.",
                       "Short call is American-style: watch ex-dividend dates for early assignment."],
            ))
    return out


def forecast(spot: float, closes: pd.Series, atm_iv: float, rv: float, risk_profile: str, cfg: dict) -> dict:
    """Rules-based mode switch: which prong suits this stock today?

    Descriptive, not a recommendation to any individual. The reader's own risk profile and holdings
    are unknown; the rules use the stock's own behaviour plus the publication's stated risk setting.
    """
    f = cfg["forecast"]
    sma = float(closes.tail(f["trend_window"]).mean())
    trend = spot / sma - 1.0
    ret_3m = spot / float(closes.iloc[-min(63, len(closes))]) - 1.0
    vol_ratio = (atm_iv / rv) if (atm_iv == atm_iv and rv == rv and rv > 0) else 1.0
    rich = atm_iv == atm_iv and atm_iv >= f["min_iv_for_income"] and vol_ratio >= f["min_vol_ratio"]
    wild = (rv == rv and rv >= f["high_vol"]) or ret_3m >= f["run_up_3m"]
    if risk_profile == "cautious" or wild:
        mode, why = "protect", ("Big recent run-up" if ret_3m >= f["run_up_3m"] else
                                "Volatile stock" if (rv == rv and rv >= f["high_vol"]) else "Cautious setting")
    elif trend <= -f["pullback"]:
        mode, why = "enter", "Trading below its recent average: a lower entry price is on the table"
    elif rich:
        mode, why = "hold", "Option premiums look rich relative to recent movement"
    else:
        mode, why = "sit_out", "Premiums look thin and nothing stands out"
    return {"mode": mode, "why": why, "trend_pct": round(100 * trend, 1), "ret_3m_pct": round(100 * ret_3m, 1),
            "vol_ratio": round(vol_ratio, 2), "atm_iv_pct": round(100 * atm_iv, 1) if atm_iv == atm_iv else None}


def top_per_ticker(picks: list[Pick]) -> list[Pick]:
    best: dict[tuple[str, str], Pick] = {}
    for p in picks:
        key = (p.ticker, p.structure)
        if key not in best or p.score > best[key].score:
            best[key] = p
    return sorted(best.values(), key=lambda p: p.score, reverse=True)
