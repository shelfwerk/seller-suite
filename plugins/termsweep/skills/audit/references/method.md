# How TermSweep decides

All rules use the account's own numbers from the report, so they fit a €5 product and a $300
product alike. Everything is a suggestion; the seller decides and uploads. The rules were tuned on
real seller reports (a DACH account, 64 days, 19,000 rows) so that they flag clear waste and leave
statistical noise alone.

## Account figures

- **Conversion rate (CVR)** = orders ÷ clicks over the whole report.
- **Average order value (AOV)** = ad sales ÷ orders.
- **Target ACOS** = from `termsweep.json`, `--target-acos`, or 30 % by default.
- **Target CPA** (what one order may cost in ads) = target ACOS × AOV.

## Click threshold — "90 % sure"

A search term that converts like the account average would have sold at least once after
**2.3 ÷ CVR** clicks with 90 % probability. TermSweep only calls a term a bleeder after that many
clicks without an order (kept between 10 and 60). Example: CVR 11 % → 21 clicks.
Fewer zero-order clicks are often just bad luck — those terms go to the watch list.

## Buckets

| Bucket | Rule | Suggested action |
|---|---|---|
| **Bleeder** | 0 orders **and** (clicks ≥ click threshold **or** spend ≥ 2 × target CPA with at least a third of the click threshold) | Negative exact in the ad group where it bled; ASIN search terms → negative product target |
| Own keyword/target bleeding | the search term *is* the seller's own exact keyword or ASIN target | Pause or lower the bid (negating it would block your own keyword) |
| **Sells elsewhere** | bleeds in this ad group but has orders in another ad group | Negate here only to *funnel* the traffic to the converting ad group — sensible when both advertise the same product. Never in the bulk file automatically. |
| Protected | bleeder that contains a protected term (brand, core words) or equals an exact protected query (`=query`) | Listed for manual review, never negated. A protected, too expensive term may still be *isolated* (moved to an exact keyword) — marked "protected: moved, not blocked" |
| **Watch** | 0 orders, at least half the click threshold or one target CPA spent | Wait for more data |
| **Too expensive** | ≥ 1 order and ACOS ≥ 1.5 × target and spend ≥ one CPA | Own exact keyword/target → lower bid (max −30 % per run); otherwise isolate as exact keyword at a lower bid and negate it in the source ad group |
| **Winner** | ≥ 2 orders over all ad groups and ACOS ≤ target, not yet an exact keyword or ASIN target | Add as exact keyword (ASIN → product target), bid ≈ current CPC adjusted toward target ACOS (between −20 % and +25 %) |

## Words that burn money (Pro, n-grams)

A word or two-word phrase is flagged when it appears in at least 3 search terms, none of them —
in any spelling variant — converted, it is not part of an own keyword, a protected brand word, or a
campaign/ad group name, and together the terms crossed the click threshold or 2 target CPAs.
Spelling variants are grouped (umlauts and ß folded, plural endings dropped), so "schweiss" is
judged together with "schweiß" and "sweatbands" with "sweatband". Suggested action: a negative
phrase in each campaign where the word cost money.

Protected search terms never count towards a word's cost. A negative phrase blocks every search
that contains it, so a phrase found inside an exact protected core query (`=water bottle with straw`
→ "straw") is only suggested for campaigns where that core query does not run in the report — and not
at all if the core query is not in the report.

## Protected entries

`termsweep.json → protected_terms`, `--protect "a, b"` or `--protect-file <file>` (one entry per line,
e.g. KeywordShare's `keywordshare-protect-<date>.txt`):

- `brand` — every search term containing the word(s) is protected (whole words, case-insensitive);
  the words are also off limits for n-grams.
- `=core query` — exactly this search term is protected; longer variants ("core query for kids")
  can still be negated.

`termsweep.json` is read from `--config`, else the working folder, else the report's folder or `--out`.

## Bulk file (Pro)

- Winners go into a **manual ad group that advertises the same product** (from the product ads in
  the bulk export; the group with the most exact keywords wins). If the source ad group advertises
  more than 3 products, the product is unclear and the winner stays in the review file.
- Bid changes are made per keyword/target (search terms have no bids): no orders after the click
  threshold → −30 %; ACOS ≥ 1.5 × target → toward target, max −30 %; ACOS ≤ 0.6 × target with
  ≥ 3 orders → up to +25 %. Minimum bid 0.02; paused targets are left alone.

## Money figures in the summary

- *Clear bleeders*: spend on the bleeder list — the realistic saving.
- *Bleeding here, but selling elsewhere*: candidates for funneling, not counted as waste.
- *Spend on terms without a single order*: all zero-order spend, including terms with too little
  data. Much of it is the normal cost of testing search terms, not waste.
- *Overspend above target ACOS*: on too-expensive converting terms, spend minus target ACOS × sales.
- *≈ per 30 days*: scaled from the report period when the report has dates.

## Limits

- The search term report only covers search terms with at least one click and goes back about 65
  days. Run TermSweep weekly or every two weeks.
- Amazon attributes sales for 7 days (sellers) or 14 days (vendors); very recent days can still gain
  orders. Leave the last 2–3 days out when downloading if possible.
- Negative keywords take about 72 hours to take effect, negative product targets about 96 hours.
