# KeywordShare — method

All figures are computed by `scripts/keywordshare.py`. This page explains them so you can answer
"why was this flagged?" without recomputing anything.

## What the report contains

Amazon's **Search Query Performance** report (Brand Analytics, brand-registered sellers) lists, per
search query and period, the funnel of the whole market and of your brand (brand view) or one ASIN
(ASIN view): impressions → clicks → cart adds → purchases. Brand view: up to the top 1,000 queries of
your brand. Counts include **organic and sponsored** results together.

## Shares and indices

| Figure | Formula | Reads as |
|---|---|---|
| Share per stage | your count ÷ market count | impression, click, cart-add, purchase share |
| Click index | your CTR ÷ market CTR = click share ÷ impression share | > 1: shoppers pick you more often than average once they see you |
| Conversion index | your CVR ÷ market CVR = purchase share ÷ click share | > 1: your clicks turn into purchases more often than average |

Several weeks or files are combined by **adding the raw counts** (never by averaging percentages).
Several ASINs in one period: market totals are taken once, your counts are added.

## The three levers ("+ purchases")

Estimated extra purchases **for the same period**, per query. Queries with fewer market purchases
than `min_market_purchases` (default 5) are listed but not judged.

1. **Visibility** — more impressions up to the *target impression share*:
   `(target × market impressions − your impressions) × market CTR × market CVR × relevance`.
   Target = the impression share you already reach on queries where you sell (upper quartile,
   3–60 %), or the value set with `--target-share`.
2. **Click rate** — seen but clicked less often than the market:
   `(your impressions × market CTR − your clicks) × market CVR × min(1, conversion index)`.
   Judged when you would expect ≥ 5 clicks at market CTR.
3. **Conversion** — clicked but bought less often than the market:
   `your clicks × market CVR − your purchases`. Judged when you would expect ≥ 2 purchases.
   With cart-add data the leak is located: *detail page → cart* or *cart → purchase*.
   Your median price vs. the market median is shown when you are > 10 % above it.

**Relevance** = min(1, click index) × min(1, conversion index) on that query; not judged yet →
account-wide indices × 0.5; never clicked → × 0.25. This keeps big generic queries you have not
proven yourself from dominating the list.

## Labels

| Label | Rule |
|---|---|
| strong (defend) | purchase share ≥ upper quartile of your purchase shares (min. 5 %) and ≥ 3 purchases |
| probably not a fit | ≥ 3 purchases expected from your clicks, but 0 purchases or conversion index < 0.15 |
| visibility gap / click leak / conversion leak | the largest lever (≥ 0.5 purchases) |
| proven | ≥ 1 own purchase, or conversion index ≥ 0.5 where judged |

## Hand-offs

- **ListingDoctor** — `keywordshare-listing-keywords-<date>.txt`: proven, relevant queries (no ASINs,
  nothing "not a fit"), ranked by market purchases × relevance plus your own purchases; 50 lines by
  default (`--keywords`), which is what ListingDoctor reads. Use `--focus`/`--exclude` to keep one product
  line when the brand sells several. Command: `/listingdoctor:check` (Pro: `/listingdoctor-pro:check`).
- **TermSweep** (Pro) — `keywordshare-protect-<date>.txt`: strong queries plus your 10 biggest sellers;
  never block them as money-burners (moving one into an exact campaign stays allowed). Written in
  TermSweep's format: your brand words (`--brand-terms`) as plain lines — every search term containing
  them is protected — and each core query as `=query` — exactly that search term, longer variants can
  still be negated. Use it with `termsweep audit … --protect-file <file>` (TermSweep ≥ 1.1) or save it
  with `/termsweep:setup` (Pro: `/termsweep-pro:setup`).
- **PPC to-do list** (Pro) — `keywordshare-ppc-<date>.csv`, for the ads console (no plugin reads it): one action per query —
  `check_negative` (not a fit), `protect` (strong), `add_exact` / `raise_bid` (proven visibility gap,
  `raise_bid` when an exact keyword already exists in the ads report), `fix_listing` (click or
  conversion leak: fix the listing before buying more traffic), `protect` (top seller), `test`
  (visibility gap not proven yet: small budget first).

## Pro

- **Trend** (`trend`): queries present in every period; purchase-share change first → last period,
  impact = change × market purchases of the last period; alert when search volume rose ≥ 15 % while your
  share fell ≥ 1 pp. Audits save `keywordshare-history.json`, so `trend` also works from earlier runs.
  Two files with identical numbers (the same window exported twice) are reported as such.
- **Organic estimate** (`--ads`): organic purchases ≈ your SQP purchases − 7-day ad orders on the
  same customer search term (Sponsored Products search term report). Rough by nature: attribution
  windows differ, ad orders can include other ASINs of the brand. Best with the same period.
- **Competition** (`market`): Top Search Terms gives the three most-clicked products per term.
  Open = top-3 click share < 35 %; medium; dominated = ≥ 60 % or one product ≥ 40 %.
  Priority with `--sqp`: attack (visibility gap, not dominated), fix listing first, defend, hard
  (gap in a dominated market), watch, not a fit.

## Limits

- No search volume forecast and no keyword discovery outside the queries Amazon lists for you.
- Shares are per period; a weekly report of a seasonal product swings.
- Nothing is sent anywhere and nothing is changed in Seller Central or Amazon Ads.
