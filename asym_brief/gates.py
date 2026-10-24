"""Safety gates that decide whether an issue may be sent automatically.

If any gate fails the issue is only saved as a Buttondown draft and the workflow run is marked failed,
so Andrew is alerted and can review it by hand. Gates never edit the issue.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

BANNED = ("risk-free", "guaranteed", "can't lose", "cannot lose")
MAX_SKIPPED_SHARE = 0.5
MAX_DATA_AGE_DAYS = 4


def check_issue(result: dict, cfg: dict, curve_source: str, issue_text: str, today: date | None = None) -> list[str]:
    """Return the reasons the issue must not be auto-sent (empty list = all gates passed)."""
    today = today or date.today()
    reasons = []
    for key, label in (("collars", "Risk Limiter"), ("puts", "Entry Optimizer"), ("covered_calls", "Rent Check")):
        if not result.get(key):
            reasons.append(f"no {label} picks")
    if curve_source == "flat default":
        reasons.append("Treasury rate unavailable (flat default used)")
    n_tickers = max(len(cfg["universe"]["tickers"]), 1)
    if len(result.get("skipped", [])) / n_tickers > MAX_SKIPPED_SHARE:
        reasons.append(f"{len(result['skipped'])} of {n_tickers} tickers skipped")
    age = (today - result["asof"]).days
    if age > MAX_DATA_AGE_DAYS:
        reasons.append(f"market data is {age} days old")
    lowered = issue_text.lower()
    for word in BANNED:
        if word in lowered:
            reasons.append(f"banned wording: {word}")
    return reasons


def write_report(out_dir: Path, reasons: list[str]) -> Path:
    path = Path(out_dir) / "gate.json"
    path.write_text(json.dumps({"ok": not reasons, "reasons": reasons}, indent=2))
    return path


def read_report(out_dir: Path) -> dict:
    path = Path(out_dir) / "gate.json"
    if not path.exists():
        return {"ok": False, "reasons": ["gate report missing"]}
    return json.loads(path.read_text())
