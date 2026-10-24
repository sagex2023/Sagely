# Sagely: instructions for Claude Code

Sagely (newsletter "The Sagely Report", "Data Driven Investing") is an automated options newsletter and screener run by SAGE-X, LLC. Owner: Andrew. Repo: sagex2023/Sagely. Goal: passive (<5 hrs/week), no client calls, no employer conflict.

Read first: README.md, PLAN.md, LAUNCH_CHECKLIST.md.

## Current state
- Code and 23 tests are done. Run `python -m pytest -q`.
- The workflow `.github/workflows/daily.yml` (build, deploy to Pages, draft to Buttondown) has NEVER run on real data.
- Next job: push the repo, set secrets TRADIER_TOKEN, FINNHUB_API_KEY, BUTTONDOWN_API_KEY with `gh secret set` (Andrew types the values; never ask him to paste keys in chat), enable Pages with source "GitHub Actions", run `daily-brief` with dry_run, read the log with `gh run view --log`, fix failures (likely Tradier field names, Treasury CSV fetch, thin-liquidity filters), then run without dry_run (creates a Buttondown DRAFT only).
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
