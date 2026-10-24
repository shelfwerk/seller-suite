# KeywordShare — your share of Amazon search demand (free)

How much of the demand for your keywords do you actually win? KeywordShare reads the **Search Query
Performance** report from Brand Analytics and tells you, per search query:

- your share of **impressions, clicks, cart adds and purchases** — and where the funnel leaks,
- **seen but not clicked** (main image, price, reviews) and **clicked but not bought** (detail page, price),
- the biggest **visibility gaps**, with an estimate of the extra purchases,
- your **strong queries** to defend and queries that **do not fit** your product,
- a **keyword list for your listing** (plain list, most important first — ready for ListingDoctor).

It writes a workbook (`.xlsx`) and the keyword list (`.txt`). Nothing is changed on Amazon —
KeywordShare only reads files.

## Use

| Command | What it does |
|---|---|
| `/keywordshare:audit [report]` | Analyses a Search Query Performance report |
| `/keywordshare:setup` | Saves your brand words, target share and minimum purchases |

Or just ask: *"Here is my Search Query Performance report — where am I losing share?"* /
*„Hier ist meine Suchanfragen-Leistung — wo verliere ich Marktanteil?"*

Reads the brand view and the ASIN view (CSV download from Seller Central, with or without the
`Brand=[…]` first line), Excel copies, the SP-API JSON report and tool exports with *My …/Total …*
columns. Answers in English or German.

## Install

- **Claude Code** (2.1.275 or later):
  ```
  /plugin install keywordshare --marketplace shelfwerk/seller-suite
  ```
  To try without installing: `claude --plugin-dir ./keywordshare`.
- **Claude Desktop / Cowork:** Customize → Plugins → upload `keywordshare-<version>.zip`.

Requires Python 3 (built into Cowork and macOS; on Windows from python.org). No extra packages, no
API keys. Brand Analytics needs Amazon Brand Registry.

## Privacy

The analysis runs locally in `scripts/keywordshare.py` and makes **no network calls**. Your report
stays on your machine; Claude sees the summary the script prints, as part of your conversation.

## How it decides

Shares are your counts divided by the market's counts for each query; several weeks are combined by
adding counts. Click index = your click-through rate vs. the market's, conversion index = your
conversion vs. the market's. "+ purchases" are estimates for the same period. Details:
`skills/audit/references/method.md`.

## KeywordShare Pro

Pro adds the **trend over weeks**, **which ASIN wins which query**, **competition per search term**
from Top Search Terms, an **organic vs. paid estimate** from your ads search term report, and the
**PPC hand-off** (protect list for TermSweep + a PPC to-do list per query).

## License

MIT — see `LICENSE`. Estimates and suggestions only; you decide what to change in your listings and ads.
