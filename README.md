# Sagely pipeline

Automated daily screen for the three-part Sagely method (Entry Optimizer = cash-secured puts, Rent Check = covered calls, Risk Limiter = collars) that renders a newsletter issue with two featured payoff-chart vignettes, auto-generated social posts, and a public pick log. See `PLAN.md` for the business plan and guardrails, and `launch/` for the landing page, outreach kit, and welcome emails.

## Quick start (local)

```bash
pip install -r requirements.txt
python -m pytest -q                                   # 18 tests, no network needed
python -m asym_brief.cli --provider fixture           # synthetic demo; watermarked, never logged or published
python -m asym_brief.cli --provider snapshot:tests/data/lmt_2027-01-15_snapshot.json --tickers LMT --out out_lmt --log /tmp/lmt_log.csv
```

Output lands in `out/`: `issue-DATE.html` (email body), `issue-DATE.txt`, `social-DATE.txt`, and `charts/*.png` (one payoff chart per featured setup).

### Email charts

Gmail and many clients strip inline SVG and data URIs, so the email uses the PNGs by URL. Host `out/charts/` anywhere public (for example GitHub Pages or Cloudflare Pages), then set `chart_base_url` in `config.json` to that folder's URL. With it empty, the HTML falls back to inline SVG, which is right for the web archive and local previews but will not show in most email clients. This hosting step is not built into the workflow yet.

## Go live

1. Create a GitHub repo from this folder.
2. Add repository secrets: `TRADIER_TOKEN`, `FINNHUB_API_KEY` (dividend yield), `BUTTONDOWN_API_KEY`. Optional repo variable `PROVIDER` (default `tradier`).
3. **One-time connector check, from your own machine** (the build sandbox could not reach these APIs):

   ```bash
   export TRADIER_TOKEN=...  FINNHUB_API_KEY=...
   python -m asym_brief.cli --provider tradier --tickers LMT --dry-run
   ```

   You should see a line like `2026-xx-xx: N candidates, ...` with `0 skipped`. If LMT is skipped, run again with `--provider tradier` and print the exception from the log; the most likely cause is a field-name difference in `TradierProvider.chain`.
4. Run the `daily-brief` workflow manually (Actions tab, "Run workflow"). A **draft** appears in Buttondown. Review it, then send.
5. The workflow now publishes the landing page, privacy and terms pages, charts and track-record page to GitHub Pages (set Pages source to "GitHub Actions"), saves `data/picks_log.csv` and `public/charts/` back to the repo, and only then pushes the draft to Buttondown. The signup form already uses the Buttondown username `sagexFinancial`. Fill in the business name, mailing address, contact email, state and date in the footer, `privacy.html` and `terms.html`. Use the workflow's **dry run** option first to test your data connection. See `LAUNCH_CHECKLIST.md` for the full order.

## Configuration (`config.json`)

- `brand`: names of the umbrella and the three prongs (working titles).
- `universe.tickers` and `universe.exclude`: a mixed-sector default with defense names left out; add your employer, competitors and partners to `exclude`. Option liquidity for the default list is unchecked.
- `collar.min_floor_return`: the worst-case loss you will list (default -3%).
- `cash_secured_put`: strike range, days to expiry, minimum discount to today's price, and the highest model chance of being assigned.
- `covered_call`: strike range, days to expiry, minimum return if called away, and the highest model chance of being called.
- `forecast`: the mode-switch thresholds (trend window, pullback, run-up, volatility, premium richness) and `risk_profile` (`balanced` or `cautious`; cautious always points to Risk Limiter).
- `bill_curve`: optional static `{days: annual_yield}` for the same-length T-bill benchmark; otherwise the Treasury par curve is fetched (untested), then a flat `risk_free_default`.
- `call_spread.enabled`: off by default; call debit spreads are an optional extra, not part of the method.
- `newsletter` prices: test prices, not commitments.
- `fill_slippage`: how far from mid toward the unfavorable side prices are assumed (0.5 = halfway to the bid or ask).
- `min_open_interest`, `max_spread_pct`: liquidity filters. Far out-of-the-money options often fail the percentage spread test; loosen it deliberately if you want more spread candidates.

## How the screen works

- **Entry Optimizer (cash-secured put):** premium, effective buy price (strike minus premium), discount to today's price, yield on the cash, model chance of assignment. The worst case (stock to zero) is shown and the tier says it is not capital-protected.
- **Rent Check (covered call):** premium, cushion breakeven, return if called away, model chance of being called. Labelled as a cushion, not a floor.
- **Mode switch:** `forecast()` tags each stock with Risk Limiter, Entry Optimizer, Rent Check or sit out, using trend vs the 50-day average, the 3-month run-up, realized volatility, and implied vs realized vol.
- **Featured vignettes:** the best-protected collar (strongest tier, then highest floor) and the best income setup (highest annualized yield), each with a plain-dollar card, scenario table and payoff chart. All payoffs come from one function in `charts.py`.
- **Same-length T-bill:** each position is compared with a bill matched to its days to expiry, not a flat rate and never a long-bond ETF.
- **Collar:** long 100 shares, long put, short call. Floor and cap are computed per share after option costs and expected dividends (yield x time). The label "Capital-protected" requires the floor to clear zero even with dividends ignored; otherwise it reads "Protected only if modelled dividends are paid."
- **Call debit spread:** reward/risk, breakeven move, risk-neutral probability of profit, and implied vs 60-day realized volatility drive the ranking.
- **Track record:** every published pick is appended to `data/picks_log.csv` and marked to market on later runs. Synthetic runs never write to the log. Each real run also writes `out/track-record.html`, a public page with ideas logged, settled and open, plus typical, best and worst results. Host it next to the chart PNGs and set `brand.track_record_url` in `config.json` so every issue links to it. The automation must commit `data/picks_log.csv` back to the repository after each run, or the history is lost between runs.

## Known limits

- Black-Scholes (European) approximations; short calls are American-style, so watch early assignment near ex-dividend dates.
- Yield-times-time dividend estimate; replace with discrete dividend dates for precision. The collar tier also reports the floor if the dividend were cut to zero.
- Cash-secured put and covered call math is tested on hand examples and synthetic chains only; run them against real chains before publishing.
- Yahoo data is unofficial and not licensed for commercial redistribution; Tradier/Finnhub terms should be checked before charging for derived data.
- This is a screening and publishing tool, not trading advice or an execution system.


## Reward/risk

Each pick card includes `reward_risk` (max gain divided by max loss, shown like `1.4x`, higher is better). Max loss is the true worst case (stock to zero for covered calls and cash-secured puts), with a -30% variant.
