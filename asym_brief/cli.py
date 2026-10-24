"""Command line entry: python -m asym_brief.cli --provider yahoo --out out --publish"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .providers import get_provider
from .render import render_issue
from .screener import run_screen
from .track import log_picks, mark_log


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Generate the daily options brief")
    ap.add_argument("--provider", default="fixture", help="fixture | yahoo | tradier | snapshot:<path.json>")
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--out", default="out")
    ap.add_argument("--log", default="data/picks_log.csv")
    ap.add_argument("--publish", action="store_true", help="push to Buttondown (draft unless config says otherwise)")
    ap.add_argument("--dry-run", action="store_true", help="screen and print counts, write nothing")
    ap.add_argument("--push-only", action="store_true", help="push the newest rendered issue in --out to Buttondown, skip screening")
    ap.add_argument("--send", action="store_true",
                    help="with --push-only: send to subscribers if every safety gate passed, else save a draft and exit 2")
    ap.add_argument("--tickers", help="comma-separated override of the configured universe")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    cfg = json.loads(Path(args.config).read_text())
    if args.tickers:
        cfg["universe"]["tickers"] = [t.strip().upper() for t in args.tickers.split(",")]
    if args.push_only:
        from .publish import push_draft

        latest = sorted(Path(args.out).glob("issue-*.html"))
        if not latest:
            print("no rendered issue found in", args.out)
            return 1
        stamp = latest[-1].stem.replace("issue-", "")
        status = cfg["publish"]["buttondown_status"]
        gate = None
        if args.send:
            from .gates import read_report

            gate = read_report(Path(args.out))
            status = "about_to_send" if gate["ok"] else "draft"
        resp = push_draft(f"{cfg['brand']['name']} - {stamp}", latest[-1], status)
        print(("sent:" if status == "about_to_send" else "draft saved:"), resp.get("id", resp))
        if gate is not None and not gate["ok"]:
            print("NOT SENT, needs your review. Failed gates:", "; ".join(gate["reasons"]))
            return 2
        return 0
    provider = get_provider(args.provider)
    from .rates import load_curve

    curve = load_curve(cfg, live=not provider.synthetic and not args.provider.startswith("snapshot"))
    result = run_screen(provider, cfg, curve)

    print(f"{result['asof']}: {result['n_candidates']} candidates, "
          f"{len(result['collars'])} Risk Limiter, {len(result['puts'])} Entry Optimizer, {len(result['covered_calls'])} Rent Check, "
          f"{len(result['skipped'])} skipped")
    if args.dry_run:
        return 0

    log_path = Path(args.log)
    scorecard = mark_log(log_path, provider)
    paths = render_issue(result, cfg, provider, scorecard, Path(args.out))
    print("wrote", ", ".join(str(p) for p in paths.values()))

    if provider.synthetic:
        print("Synthetic data: pick log NOT updated, publish disabled.")
        return 0
    n = log_picks(log_path, result["collars"] + result["puts"] + result["covered_calls"] + result["call_spreads"], result["asof"])
    print(f"logged {n} new picks to {log_path}")
    from .track import render_track_record

    print("wrote", render_track_record(mark_log(log_path, provider), cfg, result["asof"], Path(args.out) / "track-record.html"))
    from .gates import check_issue, write_report

    reasons = check_issue(result, cfg, curve.source, paths["txt"].read_text())
    write_report(Path(args.out), reasons)
    print("safety gates:", "all passed" if not reasons else "FAILED: " + "; ".join(reasons))
    if args.publish:
        from .publish import push_draft

        subject = f"{cfg['brand']['name']} - {result['asof']:%b %d}"
        resp = push_draft(subject, paths["html"], cfg["publish"]["buttondown_status"])
        print("published:", resp.get("id", resp))
    return 0


if __name__ == "__main__":
    sys.exit(main())
