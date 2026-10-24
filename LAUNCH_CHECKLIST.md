# Launch checklist

Work top to bottom. "You" means Andrew: these need your accounts, your decisions or a professional. "Done" items were finished in the files already.

## A. Name, professionals (set aside by your decision)

- Name: **Sagely** (newsletter **The Sagely Report**), subtitle "Data Driven Investing", run by SAGE-X, LLC. You chose to skip trademark/domain clearance and employer, attorney and data-provider sign-offs for now. Revisit them before you charge for Pro.

## C. Fill in the blanks (done)

- [x] Business name, address (1313 Coolridge Dr., Brandon, FL 33511), contact email (sage.x.llc@gmail.com), Florida law, date, DRAFT boxes removed.
- [x] Buttondown username `sagexFinancial` (change the form action in `launch/landing_page.html` if the real spelling differs).
- [x] `chart_base_url` = https://sagex2023.github.io/Sagely/charts
- [x] `track_record_url` = https://sagex2023.github.io/Sagely/track-record.html
- [x] Welcome email links filled. There is no Pro page yet, so that email asks readers to reply instead.
- [ ] Set the same mailing address as the footer in Buttondown (email law requires it in every email).

## D. Turn on the automation (you, once)

- [ ] Create the repository `sagex2023/Sagely` and push this folder to it. Keep it Public (free GitHub Pages needs that; the repo holds no secrets).
- [ ] Settings, Pages: set the source to "GitHub Actions".
- [ ] Settings, Secrets: add `TRADIER_TOKEN`, `FINNHUB_API_KEY`, `BUTTONDOWN_API_KEY`.
- [ ] Actions tab, run `daily-brief` by hand with **dry run** ticked. You should see a line like `N candidates, ... 0 skipped`. If tickers are skipped, read the log and send it to Claude.
- [ ] Run it again with dry run off. It builds the issue, saves the pick log and charts to the repo, publishes the site, then (only after the site is live) puts the issue in Buttondown as a **draft**. Nothing is sent automatically.

## E. Check the first real screens by hand (you, 1 to 2 weeks)

- [ ] For each featured idea, find the same contracts in your broker and compare the prices and the worst case.
- [ ] Look at cash-secured puts and covered calls most closely: they have had the least testing.
- [ ] Check the Treasury rate line matches the published Treasury yield for that week.
- [ ] Drop any ticker that keeps being filtered out for thin trading.
- [ ] Treat the daily forecast (protect, enter, hold, sit out) as a draft: its cutoffs are untested guesses.
- [ ] Send 4 to 6 issues to friends first. Open them in Gmail and Outlook on a phone and a laptop.

## F. Ongoing rules

- [ ] Review each draft before sending (about 5 minutes). This review is part of keeping the newsletter general and impersonal.
- [ ] Corrections: if a number is wrong, fix it, open the next issue with the correction, and correct the track-record page. Never quietly edit past results.
- [ ] Do not advertise any backtest or past performance you did not log. The track-record page starts empty on purpose.
- [ ] Keep the Pro tier on hold until you have real readers and a few weeks of history.
