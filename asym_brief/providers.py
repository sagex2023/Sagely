"""Market-data providers. Swap the provider without touching the screener.

FixtureProvider: deterministic synthetic data for tests, demos and CI. NEVER publish its output.
YahooProvider:   live data via yfinance (free, unofficial; fine for an MVP, replace before scaling).
"""
from __future__ import annotations

import zlib
from datetime import date, timedelta
from typing import Protocol

import numpy as np
import pandas as pd

from .pricing import bs_price

CHAIN_COLUMNS = ["type", "strike", "bid", "ask", "iv", "volume", "openInterest"]


class Provider(Protocol):
    name: str
    synthetic: bool
    asof: date
    risk_free: float

    def spot(self, ticker: str) -> float: ...
    def div_yield(self, ticker: str) -> float: ...
    def history(self, ticker: str, days: int = 252) -> pd.Series: ...
    def expiries(self, ticker: str) -> list[date]: ...
    def chain(self, ticker: str, expiry: date) -> pd.DataFrame: ...


class FixtureProvider:
    name = "SYNTHETIC FIXTURE - NOT REAL MARKET DATA"
    synthetic = True

    def __init__(self, asof: date | None = None, risk_free: float = 0.04):
        self.asof = asof or date(2026, 10, 9)
        self.risk_free = risk_free

    @staticmethod
    def _h(ticker: str) -> int:
        return zlib.crc32(ticker.encode())

    def spot(self, ticker: str) -> float:
        return float(40 + self._h(ticker) % 400)

    def div_yield(self, ticker: str) -> float:
        return 0.005 * (self._h(ticker) % 5)

    def _base_iv(self, ticker: str) -> float:
        return 0.18 + (self._h(ticker) % 25) / 100.0

    def history(self, ticker: str, days: int = 252) -> pd.Series:
        rng = np.random.default_rng(self._h(ticker))
        rv_factor = 0.8 + (self._h(ticker) % 41) / 100.0  # realized vs implied: 0.8x - 1.2x
        sigma = self._base_iv(ticker) * rv_factor
        rets = rng.normal(0.0003, sigma / np.sqrt(252), days)
        path = np.exp(np.cumsum(rets))
        path = path / path[-1] * self.spot(ticker)  # last close equals current spot
        idx = pd.bdate_range(end=pd.Timestamp(self.asof), periods=days)
        return pd.Series(path, index=idx)

    def expiries(self, ticker: str) -> list[date]:
        return [self.asof + timedelta(days=d) for d in (14, 28, 45, 60, 90, 120, 180)]

    def chain(self, ticker: str, expiry: date) -> pd.DataFrame:
        S = self.spot(ticker)
        q = self.div_yield(ticker)
        T = max((expiry - self.asof).days, 1) / 365.0
        base = self._base_iv(ticker)
        step = 0.5 if S < 100 else (1.0 if S < 250 else 5.0)
        rng = np.random.default_rng(self._h(ticker) + (expiry - self.asof).days)
        rows = []
        for K in np.arange(round(S * 0.7 / step) * step, S * 1.35, step):
            iv = max(0.08, base * (1.0 + 0.25 * (1.0 - K / S)))  # put skew
            for kind in ("call", "put"):
                px = bs_price(kind, S, float(K), T, self.risk_free, q, iv)
                half = max(0.01, px * (0.015 + 0.03 * rng.random()))
                bid = max(0.0, round(px - half, 2))
                ask = round(px + half, 2)
                moneyness = abs(K / S - 1.0)
                oi = int(max(0, rng.normal(3000 * np.exp(-8 * moneyness), 300)))
                rows.append((kind, float(K), bid, ask, iv, int(oi * 0.2), oi))
        return pd.DataFrame(rows, columns=CHAIN_COLUMNS)


class YahooProvider:
    """Live data via yfinance. Untested in the build sandbox (market-data hosts were blocked there)."""

    name = "Yahoo Finance via yfinance (delayed, unofficial)"
    synthetic = False

    def __init__(self, default_risk_free: float = 0.04):
        import yfinance as yf  # imported lazily so tests run without it

        self._yf = yf
        self.asof = date.today()
        self._cache: dict[str, object] = {}
        self.risk_free = self._fetch_risk_free(default_risk_free)

    def _t(self, ticker: str):
        if ticker not in self._cache:
            self._cache[ticker] = self._yf.Ticker(ticker)
        return self._cache[ticker]

    def _fetch_risk_free(self, default: float) -> float:
        try:
            h = self._yf.Ticker("^IRX").history(period="5d")["Close"].dropna()
            return float(h.iloc[-1]) / 100.0
        except Exception:
            return default

    def spot(self, ticker: str) -> float:
        return float(self.history(ticker, 5).iloc[-1])

    def div_yield(self, ticker: str) -> float:
        try:
            v = self._t(ticker).info.get("dividendYield") or 0.0
            return float(v) / 100.0 if v > 0.5 else float(v)  # yfinance has switched between % and fraction
        except Exception:
            return 0.0

    def history(self, ticker: str, days: int = 252) -> pd.Series:
        h = self._t(ticker).history(period=f"{max(days, 5) * 2}d")["Close"].dropna()
        return h.tail(days)

    def expiries(self, ticker: str) -> list[date]:
        return [date.fromisoformat(e) for e in self._t(ticker).options]

    def chain(self, ticker: str, expiry: date) -> pd.DataFrame:
        oc = self._t(ticker).option_chain(expiry.isoformat())
        frames = []
        for kind, df in (("call", oc.calls), ("put", oc.puts)):
            d = df.rename(columns={"impliedVolatility": "iv"}).copy()
            d["type"] = kind
            for c in ("volume", "openInterest"):
                d[c] = d[c].fillna(0)
            frames.append(d[CHAIN_COLUMNS])
        return pd.concat(frames, ignore_index=True)


class TradierProvider:
    """Tradier market data (options chains with greeks). Optional Finnhub for dividend yield.

    Env: TRADIER_TOKEN (required), TRADIER_ENV=prod|sandbox (default prod), FINNHUB_API_KEY (optional).
    Written to Tradier's documented REST API but UNTESTED here: the build sandbox could not reach
    api.tradier.com. Run `python -m asym_brief.cli --provider tradier --dry-run` once from your own
    machine and fix any field-name drift before scheduling.
    """

    name = "Tradier market data (+ Finnhub dividend yield if configured)"
    synthetic = False

    def __init__(self, default_risk_free: float = 0.04):
        import os

        self._os = os
        self._token = os.environ["TRADIER_TOKEN"]
        base = "https://sandbox.tradier.com" if os.environ.get("TRADIER_ENV") == "sandbox" else "https://api.tradier.com"
        self._base = base + "/v1"
        self._finnhub = os.environ.get("FINNHUB_API_KEY")
        self.asof = date.today()
        self.risk_free = default_risk_free
        self._div_cache: dict[str, float] = {}

    def _get(self, url: str, params: dict | None = None, headers: dict | None = None) -> dict:
        import json
        import urllib.parse
        import urllib.request

        full = url + ("?" + urllib.parse.urlencode(params) if params else "")
        req = urllib.request.Request(full, headers=headers or {})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())

    def _tradier(self, path: str, params: dict) -> dict:
        return self._get(self._base + path, params, {"Authorization": f"Bearer {self._token}", "Accept": "application/json"})

    @staticmethod
    def _as_list(x):
        return x if isinstance(x, list) else ([x] if x else [])

    def spot(self, ticker: str) -> float:
        q = self._tradier("/markets/quotes", {"symbols": ticker})["quotes"]["quote"]
        return float(q["last"] if q.get("last") else (q["bid"] + q["ask"]) / 2)

    def div_yield(self, ticker: str) -> float:
        if ticker in self._div_cache:
            return self._div_cache[ticker]
        y = 0.0
        if self._finnhub:
            try:
                m = self._get("https://finnhub.io/api/v1/stock/metric",
                              {"symbol": ticker, "metric": "all", "token": self._finnhub})["metric"]
                y = float(m.get("currentDividendYieldTTM") or 0.0) / 100.0  # Finnhub reports percent
            except Exception:
                y = 0.0
        self._div_cache[ticker] = y
        return y

    def history(self, ticker: str, days: int = 252) -> pd.Series:
        start = (date.today() - timedelta(days=int(days * 1.6))).isoformat()
        d = self._tradier("/markets/history", {"symbol": ticker, "interval": "daily", "start": start})
        rows = self._as_list(d["history"]["day"])
        return pd.Series([r["close"] for r in rows], index=pd.to_datetime([r["date"] for r in rows])).tail(days)

    def expiries(self, ticker: str) -> list[date]:
        d = self._tradier("/markets/options/expirations", {"symbol": ticker})
        return [date.fromisoformat(x) for x in self._as_list(d["expirations"]["date"])]

    def chain(self, ticker: str, expiry: date) -> pd.DataFrame:
        d = self._tradier("/markets/options/chains",
                          {"symbol": ticker, "expiration": expiry.isoformat(), "greeks": "true"})
        rows = []
        for o in self._as_list(d["options"]["option"]):
            g = o.get("greeks") or {}
            rows.append((o["option_type"], float(o["strike"]), float(o.get("bid") or 0), float(o.get("ask") or 0),
                         float(g.get("mid_iv") or 0), int(o.get("volume") or 0), int(o.get("open_interest") or 0)))
        return pd.DataFrame(rows, columns=CHAIN_COLUMNS)


class SnapshotProvider:
    """Serves one real, saved ticker/expiry snapshot (e.g. pulled from a broker connector).

    Used to regression-test the screener on real prices without network access.
    """

    synthetic = False

    def __init__(self, path: str, risk_free: float = 0.04):
        import json

        s = json.load(open(path))
        self._s = s
        self.name = s["source"]
        self.asof = date.fromisoformat(s["asof"])
        self.risk_free = risk_free
        self.ticker = s["ticker"]
        self._expiry = date.fromisoformat(s["expiry"])
        self._chain = pd.DataFrame(s["chain"])[CHAIN_COLUMNS]

    def spot(self, ticker: str) -> float:
        return float(self._s["spot"])

    def div_yield(self, ticker: str) -> float:
        return float(self._s["div_yield"])

    def history(self, ticker: str, days: int = 252) -> pd.Series:
        c = self._s["closes"]
        return pd.Series(c, index=pd.bdate_range(end=pd.Timestamp(self.asof), periods=len(c))).tail(days)

    def expiries(self, ticker: str) -> list[date]:
        return [self._expiry]

    def chain(self, ticker: str, expiry: date) -> pd.DataFrame:
        return self._chain.copy()


def get_provider(name: str, **kw) -> Provider:
    if name == "fixture":
        return FixtureProvider(**kw)
    if name == "yahoo":
        return YahooProvider()
    if name == "tradier":
        return TradierProvider()
    if name.startswith("snapshot:"):
        return SnapshotProvider(name.split(":", 1)[1])
    raise ValueError(f"unknown provider: {name}")
