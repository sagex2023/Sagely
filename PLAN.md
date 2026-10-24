# Sagely: Data Driven Investing, operating plan

Brand: **Sagely** (newsletter: **The Sagely Sniper Trading Report**), working title. It was chosen after "Even Keel" turned up a live conflict (Even Keel Financial Services, Marion MA) and after "The Sage Investor" (an existing retirement-finance podcast from Sage Wealth Design) and "Sage-X Wealth" (many Sage Wealth firms and trademark filings, plus Sage X3) proved worse. Sagely is not clear either: it sounds close to the many Sage names in finance, so an attorney may treat it as confusingly similar. A quick web search found no finance use of "Sagely" itself, but that was not a clearance search and domains were not checked. Get a trademark attorney search before spending money on the name. Avoid "Wealth" in the brand: it suggests a wealth-management firm and works against the impersonal publisher position. Earlier working titles: Convex Brief, Rain or Shine, Even Keel. Prong names were Waiting Room / Rent Check / Rain Gear, then renamed by you to Entry Optimizer / Rent Check / Risk Limiter. Note that "Entry Optimizer" and "Risk Limiter" sound a bit more promising than the products deliver (a Risk Limiter still has a real worst case; an Entry Optimizer can still buy a falling stock), so every card states the worst case beside the name. Names considered and set aside: "Pre-Retirement Portfolio Protection Protocol (P4)" and "Protect Your Portfolio" (both promise protection that only one of the three jobs delivers and sound like personal advice).

## What it is

Positioning: **Sagely, Data Driven Investing. Transparent, statistical, no hype.** Every number comes from a stated method and published assumptions, mathematical worst case first, every pick logged, no predictions (statistics describe odds, not results). We say this is rare in options content rather than "unique": verify that before leaning on it harder, since competitors such as The Multiplier cover related ground.

A weekly newsletter and daily screener built around one proprietary, three-part method for people who own stocks:

<details>
<summary>See the three jobs</summary>

| Job | Name | Structure | Promise | What you give up |
|---|---|---|---|---|
| Getting in | **Entry Optimizer** | Cash-secured put | Get paid to wait for your price | Rallies while you wait; a hard fall still leaves you owning the stock (cushion, not a floor) |
| Holding | **Rent Check** | Covered call | Get paid while you own it | Gains above the strike; the rent is a small cushion, not a floor |
| Protecting | **Risk Limiter** | Collar | Choose your worst case | Gains above the ceiling; usually a small cost |

</details>

**Not one trade, a repeating process.** Rent Check and Entry Optimizer are meant to be run again every cycle: collect the rent again as long as you keep the shares, or get paid again while you keep waiting; if you end up buying, you move from Entry Optimizer to Rent Check, and if you are called away you can go back to Entry Optimizer. The landing page shows this with a four-cycle example. Copy says "collect the rent again and again" but always adds that amounts change, nothing is guaranteed, and a stock that keeps falling still costs you.

**Track record.** Every idea in an issue is appended to a log and marked later; each run writes a public track-record page (ideas logged, settled, open; typical, best and worst result) that you host and link from every issue and the landing page. It shows no history until real issues have been published, and the log file must be committed after each run. Income ideas can win often and still lose a lot occasionally, so the page leads with the worst result, not just the share that finished positive.

A daily rules-based "forecast" reads each stock (trend, recent run-up, volatility, how rich premiums look) and says which job fits it, or to sit out. Each issue features **two vignettes with payoff charts**: the best-protected Risk Limiter setup and the best income setup (Entry Optimizer or Rent Check), then lists the rest. A scheduled job pulls option chains, screens, renders the issue and charts, logs every pick to a public track record, and drops a draft into the email platform. You review for about 5 minutes and send.

The landing page includes a floor-setting dial that shows the trade-off between floor and ceiling using one illustrative options model (25% volatility, 4% rates, 90 days, fills 7.5 cents worse than the middle price). In that model a near-zero-cost collar with a floor at the stock price leaves only about a 2% ceiling, and a floor 6% below allows about 9%. That is the honest reason a floor at zero with large upside is rare.

Only Risk Limiter sets a floor. Entry Optimizer and Rent Check are income and are labelled that way everywhere. Collars are tiered honestly: Capital-protected (floor at zero or better after costs, ignoring dividends; rare), Protected only if dividends are paid, and Near-protected. Nothing is called risk-free.

**Numbers shown on every pick and in the landing-page tool:** worst case, best case, and **reward/risk** (best case divided by worst case, shown as a multiple like 1.4x; higher is better). For Rent Check and Entry Optimizer the worst case is the stock going to zero, and a second figure shows a 30% fall.

## Why this fits your constraints

<details>
<summary>See how the design meets your limits</summary>

| Constraint you gave | How the design meets it |
|---|---|
| Fully passive, no client calls | Self-serve subscription; acquisition is content and newsletter swaps |
| Under 5 hours a week | Review 1h, social 1h, swaps 1h, improvements 2h |
| Under $500 to start | Domain about $15/yr, hosting and scheduling free (GitHub), email free to 100 subscribers, then paid tiers |
| Avoid employer conflict | Sells to retail stock owners, not government customers; defense names left out of the default universe; exclude list; no non-public information |
| Use your options expertise | The screener and the three-part method |

</details>

## Who it is for and why now

Audience: stock owners, especially those nearing or in retirement, who want income and a worst case they can see, and who find options confusing. Market research supports the demand but not every detail:

- Options-income funds are mainstream: JEPQ drew about $5.7B and JEPI about $3.5B of inflows in the first months of 2025, and both lagged in strong rallies (etf.com, May 2025).
- Downside-protection funds are the fastest-growing: buffer ETFs held roughly $69B to $78B in late 2025, with forecasts of $250B to $334B by 2030 (Cerulli, CFRA; Morningstar called the high end "quite ambitious"). Preference for downside protection rises with age (Cerulli, September 2025: 61% of investors 50 to 59, 83% at age 70).
- Complexity is the barrier: in a 2023 US survey (Global X, 1,061 respondents), 39% of non-users said they do not know enough about options and 44% were interested in learning. Among users, the main goals were risk management and income.
- Caveats: the 2023 survey is dated; a 2026 survey of one issuer's mostly European community (154 respondents) found 61% want a balance of income and price stability; no recent US data on collars or cash-secured puts specifically was found. Treat demand for the exact structures as inferred, and test it.

Positioning against funds: control and clarity. A fund decides for you; here you see each setup's worst case, best case and cost in dollars. Funds are simpler and diversified, and the page says so.

## Pricing and economics

Market norm for paid newsletters is about $10/month or $100/year; annual billing now outsells monthly and churns less (beehiiv 2026 report, self-reported). The earlier $29/month assumption was too high. Starting test prices: **Free**, and **Pro at $12/month or $120/year**, with annual as the default. Pro (later): daily screen, full candidate list, alerts, CSV.

Illustrative only. Conversion rates are assumptions to test, not benchmarks. Beehiiv reports a median free-to-paid rate of 0.62% overall and 0.78% in finance, with the top 10% far higher.

<details>
<summary>See the revenue by list size</summary>

| Free subscribers | Paid at 2% | Paid at 4% | Monthly revenue at $12 (2% / 4%) |
|---|---|---|---|
| 1,000 | 20 | 40 | $240 / $480 |
| 2,500 | 50 | 100 | $600 / $1,200 |
| 5,000 | 100 | 200 | $1,200 / $2,400 |
| 10,000 | 200 | 400 | $2,400 / $4,800 |
| 25,000 | 500 | 1,000 | $6,000 / $12,000 |

</details>

At the finance-median 0.78%, 10,000 free subscribers is about 78 payers, or roughly $940 a month. To reach $17,000 a month you would need about 1,400 paying subscribers at $12. That is a multi-year build for most niche newsletters, and money newsletters see shorter subscriber lifetimes (about six months in beehiiv's data). So treat this as a side-income engine and audience asset first, not a one-year W2 replacement. The route to a salary is stacking: annual plans, a data/API tier, sponsorships, and later a higher-priced offer once employer rules are clear.

## Guardrails (read before launch)

This is a planning summary, not legal advice. Book a one-hour consult with a securities attorney before charging money.

1. **Publisher's exclusion.** US law carves out bona fide, general-circulation publications from the definition of investment adviser (*Lowe v. SEC*, 1985: impersonal content, genuine and disinterested commentary, regular general circulation). Never tailor an answer to an individual's portfolio in replies or DMs, never tout positions you hold without disclosure, and send the same content to everyone. The daily "forecast" describes each stock's behaviour; it must never become "you should do this". The risk-profile setting in `config.json` is the publication's stance, not a reader's.
2. **Employer.** Read your employment agreement and any outside-activity, conflict-of-interest and securities-trading policies, and get written pre-clearance. Defense and aerospace names are out of the default universe; add your employer, competitors, teaming partners and any name where you hold non-public information to `universe.exclude`. Do not use employer time, equipment or confidential knowledge. Check whether the author line may reference your background.
3. **Data licensing.** Free or unofficial feeds (including yfinance) generally do not permit commercial redistribution. Confirm Tradier's and Finnhub's terms for publishing derived analytics in a paid product. The Robinhood connector was used only to test the screener on real prices; do not publish its data.
4. **No promises.** Never write "guaranteed," "risk-free," or "can't lose." Entry Optimizer and Rent Check are never described as protection. A test in the suite fails the build if the issue contains those phrases.
5. **Disclose and don't front-run.** Keep the position disclosure in every issue. Do not trade a pick ahead of publication.
6. **Taxes and entity.** Talk to an accountant about an LLC and sales tax on digital subscriptions. Collars and covered calls can have tax consequences (straddle rules, assignment, holding periods); the issue says so and gives no tax advice.
7. **Broker approvals.** Each strategy needs a broker options-approval level; levels differ by broker. Every featured card says to confirm yours.

## 90-day plan

**Weeks 0-2: set up (about 8 hours total)**
- Attorney consult, employer pre-clearance, exclude list finalized
- Domain, Buttondown account, GitHub repo, landing page live on a free static host
- Add `TRADIER_TOKEN`, `FINNHUB_API_KEY`, `BUTTONDOWN_API_KEY` as GitHub Actions secrets
- Run the connector check in the README, then a dry run; check the universe's option liquidity and what gets skipped
- Host chart images (see README) so email charts display; keep the email platform in draft mode

**Weeks 3-6: soft launch**
- Send the first four weekly issues as drafts you review. Post the auto-generated social posts
- Send 5 swap emails a week
- Publish the track-record page
- Target: 150 free subscribers

**Weeks 7-12: refine**
- Review reply emails; tune filters (`config.json`) based on what readers ask for
- Publish two evergreen articles
- Turn on the welcome sequence
- Target: 300-500 free subscribers; open Pro only if there is demand (replies asking for the daily screen)

## Kill and pivot criteria

- By day 90, under 150 free subscribers after steady weekly effort: change the angle or the channel before changing the product.
- By day 180, under 25 paying subscribers while the free list is over 1,000: test price, test the Pro features, or pivot the audience asset to sponsorships.
- Any compliance or employer objection: stop and fix before sending another issue.

## What I could not test

- Live data providers (Yahoo, Tradier, Finnhub), the Treasury yield-curve download and the Buttondown API were unreachable from the build environment. They are written to documented APIs but have not been run. Until the curve fetch works, the screen falls back to the flat rate in `config.json` or a static `bill_curve` you set.
- The collar math was tested on a real LMT chain (Robinhood connector) and checked by hand. The cash-secured put and covered call math is tested on hand-worked examples and synthetic chains; they have not been run on real chains because the saved real chain has only one expiry, 98 days out, outside their 21 to 75 day window.
- The default universe has not been checked for option liquidity.
- The forecast thresholds (run-up, volatility, pullback) are reasonable defaults, not calibrated.
- Models are Black-Scholes approximations with a yield-times-time dividend estimate. This is a screening tool, not an execution tool.
- Email charts need hosted PNGs; the hosting step is described in the README but not built into the workflow.
