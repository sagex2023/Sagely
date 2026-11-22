# Sagely: instructions for Claude Code

Sagely (newsletter "The Sagely Sniper Trading Report", "Data Driven Investing") is an automated options newsletter and screener run by SAGE-X, LLC. Owner: Andrew. Repo: sagex2023/Sagely. Goal: passive (<5 hrs/week), no client calls, no employer conflict.

Read first: README.md, PLAN.md, LAUNCH_CHECKLIST.md.

## Current state
- Code and 26 tests are done. Run `python -m pytest -q`.
- `.github/workflows/daily.yml` runs live: Tuesday cron builds, deploys Pages, and SENDS via Buttondown only if every gate in `asym_brief/gates.py` passes (else draft + GitHub issue alert). Manual runs make drafts unless `send` is ticked. Real sends worked on Nov 1, 3, 10, 17 2026 (Buttondown needs the live-send header; already in publish.py).
- Secrets set: TRADIER_TOKEN, FINNHUB_API_KEY, BUTTONDOWN_API_KEY (Andrew types values; never ask him to paste keys in chat). Gmail app passwords are unavailable (Advanced Protection), so alerts are GitHub issues.
- Known open issues: picks are logged at build time, so runs that were never sent (drafts, the failed Oct 27 send) are in data/picks_log.csv and on the public track record; the newsletter promises only published ideas. Decide how to correct that publicly (see wording rules: no quiet edits).
- Skipped by Andrew's decision: trademark/domain clearance and employer/attorney/data-provider sign-offs. Revisit before charging for Pro.

## Wording rules (a test enforces the banned words)
- Worst case first. Say "mathematical worst case" or "statistical"; "statistics describe odds, not promises".
- Never "risk-free", "guaranteed", "can't lose". Use "promised".
- Mention T-bills once, in the methodology only.
- Plain words, about 8th grade. Collapse tables (details toggles on web, text lines in email).
- Keep "rare in options writing" and the Pro price ($12/mo, $120/yr); both are Andrew's choices.
- Tagline: "Let statistics be your guide. Get paid to wait, get paid to hold, choose your risk."
- Corrections: fix the number, open the next issue with the correction, correct the track-record page. Never quietly edit past results.
- Synthetic runs never write to data/picks_log.csv.

## Business facts
SAGE-X, LLC, 1313 Coolridge Dr., Brandon, FL 33511, sage.x.llc@gmail.com, Florida law. Buttondown username sagexFinancial. Pages: https://sagex2023.github.io/Sagely/
