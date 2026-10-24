# Changelog

## 1.1.1 — 2026-10-24

Directory review fixes, no change to the audit:
- Skills pre-approve only their own script (`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/termsweep.py" …`, plus `python`/`py -3`)
  instead of any Python command.
- `plugin.json`: homepage, repository and support e-mail, clearer wording (the plugin reads report files only, no account access); plugin icon.

## 1.1.0 — 2026-10-22

Protect lists that work with KeywordShare (integration chain B).

- `--protect-file <file>` for `audit`, `bulk` and `init`: one entry per line (blank lines and `#` comments ignored),
  e.g. KeywordShare's `keywordshare-protect-<date>.txt`. A file path passed to `--protect` is now read as a file
  (with a note) — before, it protected nothing, silently.
- Exact protection: `=core query` protects exactly that search term; plain entries keep protecting every search
  term that contains them (brand words). Works in `--protect`, `--protect-file` and `termsweep.json`.
- `termsweep.json` is also found next to the report and in `--out` (before: working folder only, so settings saved in
  the reports folder were ignored when TermSweep ran from elsewhere).
- Pro, money-burning words: protected search terms no longer count towards a word's cost; only brand words are
  off limits as a whole; a phrase that would block an exact protected core query is suggested only for campaigns
  where that core query does not run (before: every word of every protected term blocked all n-grams).
- Too expensive protected terms that are isolated (moved to an exact keyword) are marked "protected: moved, not blocked".

## 1.0.1 — 2026-10-22
- UK and other day-first marketplaces: dates like 13/09/2026 decide the order; currency taken from a
  Marketplace/Country column when the file has no currency column (e.g. sellerboard exports).
- Damaged Excel files and Google Ads reports get a clear explanation instead of an error.
- Pro: the "did last week's negatives go live?" check now looks only at negatives (ad group exact,
  campaign phrase, ASIN) — newly harvested keywords no longer count as "still spending".
- Skills: run the engine as one plain command (no `cd`/`&&`), find files with Glob — fewer permission
  prompts and works in locked-down sessions.
- Eval suite: 9 cases (US, UK, DE legacy headers, sellerboard, damaged file, Google Ads, bulk, no report).

## 1.0.0 — 2026-10-21
Tested on real seller reports (DACH account: Amazon.de console exports 2020–2026, daily and summary,
Sellerboard and third-party exports, up to 91,000 rows) in addition to synthetic fixtures.

- **Formats:** real amazon.de console headers (`Suchbegriff des Kunden`, `7 Tage, Aufträge gesamt (#)`,
  `Sichtkontakte`, `Kampagnen-Name`), 2026 renamed metrics (`Purchases`, `Käufe`, `Verkäufe`), old campaign
  manager UI exports, Sellerboard "search terms" exports, campaign-level third-party exports; decimal
  separator detected per column; Excel date serials; Google Ads files recognised and explained.
- **Rules:** bleeder threshold = clicks after which an average-converting term would have sold with
  90 % probability (2.3 ÷ CVR, 10–60) or 2 target CPAs; search terms that sell in another ad group are
  listed as "funnel" decisions instead of negatives; ASIN winners that are already targeted are skipped.
- **Pro:** n-grams group spelling and plural variants (schweiss/schweiß) and never touch words from own
  keywords, protected terms or campaign/ad group names; winners go automatically to a manual ad group
  advertising the same product (product ads in the bulk export) — a destination for another product is
  refused; bid changes capped at −30 % / +25 % per run; trend shows spend per 30 days.
- Windows: skills fall back to `python` / `py -3`.

## 0.1.0 — 2026-10-21
First version: audit (bleeders, too expensive, winners, watch list), setup, Pro bulk file, n-grams, history.
