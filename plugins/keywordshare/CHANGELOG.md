# Changelog

## 1.0.2 — 2026-10-22

- Protect list in TermSweep's format (TermSweep ≥ 1.1): brand words (`--brand-terms`) as plain lines, every core
  query as `=query` (protected exactly — longer variants like "<query> for kids" can still be negated). Hand-off
  text names the direct import `termsweep audit … --protect-file <file>`.

## 1.0.1 — 2026-10-22

Hand-offs aligned with ListingDoctor 1.2.0 and TermSweep (integration chain B).

- ListingDoctor keyword list: 50 lines by default (`--keywords`), which is what ListingDoctor reads.
- Hand-off texts name the Pro commands too (`/listingdoctor-pro:check`, `/termsweep-pro:setup`).
- Protect list: "never block as money-burners — moving a query into an exact campaign stays allowed"; how to enter the terms
  in TermSweep setup (comma-separated).
- `keywordshare-ppc-<date>.csv` is described as a PPC to-do list for the ads console (no plugin reads it; TermSweep's audit
  adds the cost side).

## 1.0.0 — 2026-10-22

First release (not published yet).

- Reads Search Query Performance: brand and ASIN view from Seller Central (CSV with or without the
  `Brand=[…]`/`ASIN or Product=[…]` first line, Excel copies), SP-API JSON (`dataByAsin`), tool exports
  with *My …/Total …* columns (several marketplaces per file), German console labels (decimal comma,
  semicolon). Period from the first line, the reporting date (ISO, DD-MM-YYYY, DD.MM.YYYY) or the file name.
- "Basket adds" (English label on amazon.de/.co.uk) read as cart adds; German Top Search Terms (old layout,
  verified headers "Suchfrequenz-Rang", "#1 der angeklickten ASINs", "Klickrate #1", "Umsatzrate #1",
  period from "Wird angezeigt=[…]").
- Shares per funnel stage, click and conversion index, three levers in estimated extra purchases
  (visibility, click rate, conversion; leak located at cart or checkout with cart data; price vs. median).
- Labels: strong, visibility gap, click leak, conversion leak, probably not a fit; targets from the
  seller's own upper quartile; `--focus`/`--exclude` for one product line.
- Workbook (summary, opportunities, funnel, strong) and the ListingDoctor keyword list. EN/DE output.
- Pro: several files (weeks added, ASINs compared, "tie" when no ASIN leads clearly), `trend` with history
  and a one-line summary (identical exports flagged), `market` from Top Search Terms (current and old layout,
  streamed; summary line with open/medium/dominated counts and what to attack first), `--ads` organic
  estimate from the Sponsored Products search term report (period mismatch noted), TermSweep hand-off
  (protect list + PPC action CSV).
