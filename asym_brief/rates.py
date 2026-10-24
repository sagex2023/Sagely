"""Matched-maturity T-bill benchmark.

The honest comparison for any position is what cash would have earned over the SAME horizon,
locked in today. A 90-day collar is compared with the 90-day bill yield, not a long-bond ETF
(TLT has a duration of roughly 16 years and is not a bill proxy) and not a stale average.

`BillCurve` interpolates a short-end curve given as {days_to_maturity: annual_yield}. Build it
from a static override in config.json, from the Treasury par yield curve (`fetch_treasury_curve`,
written to the published CSV format but UNTESTED from the build sandbox), or fall back to a flat rate.
"""
from __future__ import annotations

import csv
import io
import logging
from bisect import bisect_left
from datetime import date

log = logging.getLogger("asym_brief")

# Column name in Treasury's daily par yield curve CSV -> approximate days
TENORS = {"1 Mo": 30, "2 Mo": 60, "3 Mo": 91, "4 Mo": 121, "6 Mo": 182, "1 Yr": 365}


class BillCurve:
    def __init__(self, points: dict[int, float], source: str = "flat"):
        if not points:
            raise ValueError("empty curve")
        self.points = sorted((int(d), float(y)) for d, y in points.items())
        self.source = source

    def at(self, dte: int) -> float:
        """Linear interpolation; flat extrapolation outside the quoted tenors."""
        days = [d for d, _ in self.points]
        if dte <= days[0]:
            return self.points[0][1]
        if dte >= days[-1]:
            return self.points[-1][1]
        i = bisect_left(days, dte)
        (d0, y0), (d1, y1) = self.points[i - 1], self.points[i]
        return y0 + (y1 - y0) * (dte - d0) / (d1 - d0)

    def __call__(self, dte: int) -> float:
        return self.at(dte)


def flat_curve(rate: float) -> BillCurve:
    return BillCurve({30: rate, 365: rate}, source="flat default")


def parse_treasury_csv(text: str) -> dict[int, float]:
    """Parse the most recent row of Treasury's daily par yield curve CSV (yields in percent)."""
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        raise ValueError("no rows")
    latest = rows[0]  # Treasury lists the newest date first
    pts = {}
    for col, days in TENORS.items():
        v = (latest.get(col) or "").strip()
        if v:
            pts[days] = float(v) / 100.0
    if not pts:
        raise ValueError("no recognised tenor columns")
    return pts


def fetch_treasury_curve(year: int | None = None, timeout: int = 15) -> BillCurve:
    import requests

    year = year or date.today().year
    url = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
           f"daily-treasury-rates.csv/{year}/all?type=daily_treasury_yield_curve"
           f"&field_tdr_date_value={year}&page&_format=csv")
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return BillCurve(parse_treasury_csv(r.text), source="US Treasury par yield curve")


def load_curve(cfg: dict, live: bool = False) -> BillCurve:
    """Static override in config wins; then live Treasury (if asked and reachable); then flat default."""
    static = cfg.get("bill_curve")
    if static:
        return BillCurve({int(k): float(v) for k, v in static.items()}, source="config override")
    if live:
        try:
            return fetch_treasury_curve()
        except Exception as exc:
            log.warning("Treasury curve unavailable (%s); using flat default", exc)
    return flat_curve(cfg["risk_free_default"])
