import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from asym_brief import cli
from asym_brief.pricing import bs_price
from asym_brief.providers import FixtureProvider, SnapshotProvider
from asym_brief.screener import run_screen
from asym_brief import charts
from asym_brief.rates import BillCurve, parse_treasury_csv
from asym_brief.structures import (fill_price, find_call_spreads, find_cash_secured_puts, find_collars,
                                   find_covered_calls, forecast)
from asym_brief.track import log_picks, mark_log

ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "config.json").read_text())
SNAP = ROOT / "tests" / "data" / "lmt_2027-01-15_snapshot.json"


def test_put_call_parity():
    S, K, T, r, q, v = 100.0, 105.0, 0.5, 0.04, 0.02, 0.3
    c, p = bs_price("call", S, K, T, r, q, v), bs_price("put", S, K, T, r, q, v)
    import math
    assert c - p == pytest.approx(S * math.exp(-q * T) - K * math.exp(-r * T), abs=1e-9)


def test_fill_is_adverse_to_the_trader():
    row = pd.Series({"bid": 9.0, "ask": 11.0})
    assert fill_price(row, +1, 0.5) == pytest.approx(10.5)  # buy above mid
    assert fill_price(row, -1, 0.5) == pytest.approx(9.5)   # sell below mid
    assert fill_price(pd.Series({"bid": 0.0, "ask": 1.0}), -1, 0.5) is None  # no bid, cannot sell


def test_collar_math_on_real_lmt_snapshot():
    p = SnapshotProvider(str(SNAP))
    exp = p.expiries("LMT")[0]
    picks = find_collars("LMT", p.spot("LMT"), {exp: p.chain("LMT", exp)}, p.asof, p.risk_free, p.div_yield("LMT"), CFG)
    assert picks, "expected at least one collar from the real chain"
    best = max(picks, key=lambda x: x.score)
    put = next(l for l in best.legs if l.kind == "put")
    call = next(l for l in best.legs if l.kind == "call")
    spot, T = p.spot("LMT"), (exp - p.asof).days / 365
    div = spot * p.div_yield("LMT") * T
    net = put.px - call.px
    # independent recomputation of the headline numbers
    assert best.metrics["floor_pnl"] == pytest.approx((put.strike - spot) - net + div, abs=1e-2)
    assert best.metrics["cap_pnl"] == pytest.approx((call.strike - spot) - net + div, abs=1e-2)
    # conservative fills must not beat the quoted market
    ch = p.chain("LMT", exp)
    prow = ch[(ch.type == "put") & (ch.strike == put.strike)].iloc[0]
    crow = ch[(ch.type == "call") & (ch.strike == call.strike)].iloc[0]
    assert put.px >= (prow.bid + prow.ask) / 2 and call.px <= (crow.bid + crow.ask) / 2
    # a floor that only clears zero thanks to dividends must not be labelled capital-protected
    if best.metrics["floor_ex_div_return_pct"] < 0 <= best.metrics["floor_return_pct"]:
        assert "only if" in best.tier


def _chain(rows):
    return pd.DataFrame(rows, columns=["type", "strike", "bid", "ask", "iv", "volume", "openInterest"])


def test_call_spread_hand_example():
    # spot 100, 60 DTE. Buy 100c @ ~3.0, sell 110c @ ~0.8 with tight markets
    ch = _chain([("call", 100.0, 2.9, 3.1, 0.25, 50, 500), ("call", 110.0, 0.75, 0.85, 0.25, 50, 500)])
    cfg = json.loads(json.dumps(CFG))
    cfg["call_spread"].update(min_dte=30, max_dte=200, long_moneyness=[0.95, 1.08], short_moneyness=[1.05, 1.3],
                              min_reward_risk=3.0, max_debit_pct=0.04, max_breakeven_move=0.08)
    asof = date(2026, 10, 9)
    exp = date(2026, 12, 8)
    picks = find_call_spreads("XYZ", 100.0, {exp: ch}, asof, 0.04, 0.0, 0.25, cfg)
    assert len(picks) == 1
    m = picks[0].metrics
    # buy 3.0 + 0.5*0.1 = 3.05 ; sell 0.8 - 0.5*0.05 = 0.775 ; debit 2.275 ; width 10 ; gain 7.725
    assert m["debit"] == pytest.approx(2.275, abs=1e-6)
    assert m["max_gain"] == pytest.approx(7.725, abs=1e-6)
    assert m["reward_risk"] == pytest.approx(7.725 / 2.275, abs=0.01)
    assert m["breakeven"] == pytest.approx(102.275, abs=0.01)


def test_illiquid_legs_are_rejected():
    ch = _chain([("call", 100.0, 2.9, 3.1, 0.25, 50, 5), ("call", 110.0, 0.7, 0.9, 0.25, 50, 500)])  # OI 5 < 100
    cfg = json.loads(json.dumps(CFG))
    picks = find_call_spreads("XYZ", 100.0, {date(2026, 12, 8): ch}, date(2026, 10, 9), 0.04, 0.0, 0.25, cfg)
    assert picks == []


def test_end_to_end_synthetic_is_flagged_and_never_logged(tmp_path):
    out, log = tmp_path / "out", tmp_path / "log.csv"
    rc = cli.main(["--provider", "fixture", "--config", str(ROOT / "config.json"), "--out", str(out), "--log", str(log)])
    assert rc == 0
    html = next(out.glob("issue-*.html")).read_text()
    assert "SYNTHETIC TEST DATA" in html
    assert not log.exists(), "synthetic picks must never enter the public track record"


def test_screen_survives_a_broken_ticker():
    class Boom(FixtureProvider):
        def chain(self, ticker, expiry):
            if ticker == "XOM":
                raise RuntimeError("feed down")
            return super().chain(ticker, expiry)

    res = run_screen(Boom(), CFG)
    assert any(s.startswith("XOM") for s in res["skipped"])
    assert res["tickers"]  # others still ran


def test_exclude_list_removes_tickers():
    cfg = json.loads(json.dumps(CFG))
    cfg["universe"]["exclude"] = ["XOM", "CVX"]
    res = run_screen(FixtureProvider(), cfg)
    assert "XOM" not in res["tickers"] and "CVX" not in res["tickers"] and res["tickers"]


def test_track_record_logs_once_and_marks(tmp_path):
    p = SnapshotProvider(str(SNAP))
    res = run_screen(p, {**CFG, "universe": {**CFG["universe"], "tickers": ["LMT"]}})
    log = tmp_path / "log.csv"
    picks = res["collars"] + res["puts"] + res["covered_calls"] + res["call_spreads"]
    assert log_picks(log, picks, p.asof) == len(picks)
    assert log_picks(log, picks, p.asof) == 0  # idempotent
    score = mark_log(log, p)
    assert score["n"] == len(picks) and len(score["open"]) == len(picks)
    # marked at the same snapshot the entry used mid vs adverse fill, so P/L must be slightly negative or ~0
    assert all(item["pnl_per_share"] < 1.0 for item in score["open"])


# ---- Sagely additions ------------------------------------------------------------------

def _cfg():
    return json.loads(json.dumps(CFG))


def test_cash_secured_put_hand_example():
    # spot 100, 45 DTE. Sell the 95 put quoted 1.90/2.10 -> fill 2.00 - 0.5*0.10 = 1.95
    ch = _chain([("put", 95.0, 1.90, 2.10, 0.28, 50, 500)])
    asof, exp = date(2026, 10, 9), date(2026, 11, 23)
    picks = find_cash_secured_puts("XYZ", 100.0, {exp: ch}, asof, 0.04, 0.0, 0.25, _cfg())
    assert len(picks) == 1
    m = picks[0].metrics
    assert m["premium"] == pytest.approx(1.95)
    assert m["breakeven"] == pytest.approx(93.05)             # strike minus premium
    assert m["discount_to_spot_pct"] == pytest.approx(6.95)   # 100 -> 93.05
    assert m["yield_on_cash_pct"] == pytest.approx(100 * 1.95 / 95, abs=0.01)
    assert m["capital"] == pytest.approx(9500.0)
    assert "NOT capital-protected" in picks[0].tier           # never sold as a floor
    # payoff: stock to zero loses breakeven*100; above the strike keeps only the premium
    assert charts.payoff(picks[0], 0.0) == pytest.approx(-9305.0)
    assert charts.payoff(picks[0], 120.0) == pytest.approx(195.0)


def test_covered_call_hand_example():
    # spot 100, 45 DTE. Sell the 105 call quoted 1.40/1.60 -> fill 1.50 - 0.5*0.10 = 1.45
    ch = _chain([("call", 105.0, 1.40, 1.60, 0.25, 50, 500)])
    asof, exp = date(2026, 10, 9), date(2026, 11, 23)
    picks = find_covered_calls("XYZ", 100.0, {exp: ch}, asof, 0.04, 0.0, 0.25, _cfg())
    assert len(picks) == 1
    p, m = picks[0], picks[0].metrics
    assert m["premium"] == pytest.approx(1.45)
    assert m["called_away_pnl"] == pytest.approx(6.45)         # 5 of stock gain + 1.45 rent
    assert m["cushion_breakeven"] == pytest.approx(98.55)
    assert "NOT a floor" in p.tier
    assert charts.payoff(p, 130.0) == pytest.approx(645.0)     # capped
    assert charts.payoff(p, 0.0) == pytest.approx(-9855.0)     # cushion is not protection


def test_collar_payoff_matches_screener_floor_and_cap():
    p = SnapshotProvider(str(SNAP))
    exp = p.expiries("LMT")[0]
    best = max(find_collars("LMT", p.spot("LMT"), {exp: p.chain("LMT", exp)}, p.asof, p.risk_free, 0.0, CFG),
               key=lambda x: x.score)
    k = charts.key_numbers(best)
    # chart numbers exclude dividends, so compare with the screener at zero dividend yield
    assert k["worst"] == pytest.approx(100 * best.metrics["floor_pnl"], abs=1.0)
    assert k["best"] == pytest.approx(100 * best.metrics["cap_pnl"], abs=1.0)


def test_covered_call_upside_is_capped_and_csp_upside_is_capped():
    ch = _chain([("put", 95.0, 1.90, 2.10, 0.28, 50, 500), ("call", 105.0, 1.40, 1.60, 0.25, 50, 500)])
    asof, exp = date(2026, 10, 9), date(2026, 11, 23)
    csp = find_cash_secured_puts("XYZ", 100.0, {exp: ch}, asof, 0.04, 0.0, 0.25, _cfg())[0]
    cc = find_covered_calls("XYZ", 100.0, {exp: ch}, asof, 0.04, 0.0, 0.25, _cfg())[0]
    assert charts.key_numbers(csp)["best"] == pytest.approx(195.0)
    assert charts.key_numbers(cc)["best"] == pytest.approx(645.0)


def test_bill_curve_interpolates_and_extrapolates_flat():
    c = BillCurve({30: 0.040, 90: 0.042, 180: 0.044})
    assert c.at(30) == pytest.approx(0.040)
    assert c.at(60) == pytest.approx(0.041)                    # halfway between 30 and 90
    assert c.at(10) == pytest.approx(0.040) and c.at(400) == pytest.approx(0.044)


def test_treasury_csv_parser_takes_latest_row():
    csv_text = "Date,1 Mo,2 Mo,3 Mo,4 Mo,6 Mo,1 Yr\n10/09/2026,4.10,4.12,4.15,4.14,4.10,3.98\n10/08/2026,4.20,4.2,4.2,4.2,4.2,4.0\n"
    pts = parse_treasury_csv(csv_text)
    assert pts[91] == pytest.approx(0.0415) and pts[365] == pytest.approx(0.0398)


def test_collar_uses_matched_maturity_bill_not_a_flat_rate():
    p = SnapshotProvider(str(SNAP))
    exp = p.expiries("LMT")[0]
    args = ("LMT", p.spot("LMT"), {exp: p.chain("LMT", exp)}, p.asof)
    lo = max(find_collars(*args, BillCurve({30: 0.02, 365: 0.02}), p.div_yield("LMT"), CFG), key=lambda x: x.score)
    hi = max(find_collars(*args, BillCurve({30: 0.06, 365: 0.06}), p.div_yield("LMT"), CFG), key=lambda x: x.score)
    assert lo.metrics["floor_vs_tbill_pct"] > hi.metrics["floor_vs_tbill_pct"]
    assert hi.metrics["bill_yield_pct"] == pytest.approx(6.0)


def _closes(vals):
    return pd.Series(vals, index=pd.bdate_range(end="2026-10-09", periods=len(vals)))


def test_forecast_mode_switch_rules():
    cfg = _cfg()
    flat = _closes([100.0] * 120)
    # rich premiums on a calm, flat stock -> Rent Check
    assert forecast(100.0, flat, 0.30, 0.20, "balanced", cfg)["mode"] == "hold"
    # thin premiums -> sit out
    assert forecast(100.0, flat, 0.12, 0.12, "balanced", cfg)["mode"] == "sit_out"
    # pulled back below its recent average -> Entry Optimizer
    dip = _closes([100.0] * 110 + [96.0] * 10)
    assert forecast(95.0, dip, 0.30, 0.20, "balanced", cfg)["mode"] == "enter"
    # big 3-month run-up -> Risk Limiter
    run = _closes(list(np.linspace(60, 100, 120)))
    assert forecast(100.0, run, 0.30, 0.20, "balanced", cfg)["mode"] == "protect"
    # cautious setting always protects
    assert forecast(100.0, flat, 0.30, 0.20, "cautious", cfg)["mode"] == "protect"


def test_issue_has_two_vignettes_charts_and_honest_wording(tmp_path):
    import json
    cfgd = json.load(open(ROOT / "config.json")); cfgd["chart_base_url"] = ""
    cfgp = tmp_path / "cfg.json"; cfgp.write_text(json.dumps(cfgd))
    out = tmp_path / "out"
    cli.main(["--provider", "fixture", "--config", str(cfgp), "--out", str(out), "--log", str(tmp_path / "l.csv")])
    html = next(out.glob("issue-*.html")).read_text()
    assert "Best protected" in html and "Best income" in html
    assert "<svg" in html                                     # inline chart when no hosted image base URL
    assert any((out / "charts").glob("*.png"))                # email-safe PNGs were written
    assert "NOT a floor" in html or "not a floor" in html
    lowered = html.lower()
    assert "risk-free" not in lowered and "guaranteed" not in lowered and "can't lose" not in lowered


def test_reward_risk_text():
    from asym_brief import charts
    assert charts.mult_text(None) == "n/a"
    assert charts.mult_text(1.4) == "1.4x"
    assert charts.mult_text(0.0654) == "0.07x"
    assert charts.mult_text(12.3) == "12x"


def test_issue_uses_reward_risk_and_brand(tmp_path):
    out = tmp_path / "o"
    cli.main(["--provider", "fixture", "--config", str(ROOT / "config.json"), "--out", str(out), "--log", str(tmp_path / "l.csv")])
    html = next(out.glob("issue-*.html")).read_text()
    txt = next(out.glob("issue-*.txt")).read_text()
    soc = next(out.glob("social-*.txt")).read_text()
    for body in (html, txt):
        assert "Reward/risk" in body and "Data Driven Investing" in body and "no hype" in body.lower()
        assert "Risk/reward" not in body
    assert "reward/risk" in soc and "risk/reward" not in soc


def test_track_record_page(tmp_path):
    from asym_brief.track import render_track_record, summarize
    cfg = json.loads((ROOT / "config.json").read_text())
    empty = render_track_record({"n": 0, "open": [], "closed": [], "hit_rate": None}, cfg, __import__("datetime").date(2026, 10, 18), tmp_path / "t.html")
    assert "no history to show" in empty.read_text()
    sc = {"n": 3, "open": [{"id": "c", "asof": "2026-10-01", "ticker": "XOM", "structure": "covered_call", "expiry": "2026-12-01", "pnl_per_share": 1, "return_pct": 1.0}],
          "closed": [{"id": "a", "asof": "2026-08-01", "ticker": "KO", "structure": "cash_secured_put", "expiry": "2026-09-01", "pnl_per_share": 1, "return_pct": 2.0},
                     {"id": "b", "asof": "2026-08-01", "ticker": "JNJ", "structure": "collar", "expiry": "2026-09-01", "pnl_per_share": -1, "return_pct": -5.0}], "hit_rate": 50.0}
    s = summarize(sc)
    assert s["settled"] == 2 and s["worst"] == -5.0 and s["best"] == 2.0 and s["positive_pct"] == 50
    page = render_track_record(sc, cfg, __import__("datetime").date(2026, 10, 18), tmp_path / "t2.html").read_text()
    assert "worst -5.0%" in page and "winners and losers" in page


def test_push_only_without_issue(tmp_path, capsys):
    rc = cli.main(["--push-only", "--config", str(ROOT / "config.json"), "--out", str(tmp_path / "empty")])
    assert rc == 1


def test_corrections_and_footer_in_issue(tmp_path):
    out = tmp_path / "o"
    cli.main(["--provider", "fixture", "--config", str(ROOT / "config.json"), "--out", str(out), "--log", str(tmp_path / "l.csv")])
    assert "quietly edit" in next(out.glob("issue-*.html")).read_text()
