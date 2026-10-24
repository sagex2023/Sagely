"""Black-Scholes helpers (European approximation; fine for ranking, not for execution)."""
from __future__ import annotations

from math import erf, exp, log, sqrt


def _cdf(x: float) -> float:
    return 0.5 * (1.0 + erf(x / sqrt(2.0)))


def _d1_d2(S: float, K: float, T: float, r: float, q: float, sigma: float):
    sigma = max(sigma, 1e-6)
    T = max(T, 1e-6)
    d1 = (log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * sqrt(T))
    return d1, d1 - sigma * sqrt(T)


def bs_price(kind: str, S: float, K: float, T: float, r: float, q: float, sigma: float) -> float:
    """Price a European call/put with continuous dividend yield q."""
    if T <= 0:
        return max(S - K, 0.0) if kind == "call" else max(K - S, 0.0)
    d1, d2 = _d1_d2(S, K, T, r, q, sigma)
    if kind == "call":
        return S * exp(-q * T) * _cdf(d1) - K * exp(-r * T) * _cdf(d2)
    return K * exp(-r * T) * _cdf(-d2) - S * exp(-q * T) * _cdf(-d1)


def prob_finish_above(S: float, K: float, T: float, r: float, q: float, sigma: float) -> float:
    """Risk-neutral probability that the underlying finishes above K at expiry."""
    _, d2 = _d1_d2(S, K, T, r, q, sigma)
    return _cdf(d2)


def prob_finish_below(S: float, K: float, T: float, r: float, q: float, sigma: float) -> float:
    """Risk-neutral probability that the underlying finishes below K at expiry."""
    return 1.0 - prob_finish_above(S, K, T, r, q, sigma)
