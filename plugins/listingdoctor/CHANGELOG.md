# Changelog

## 1.2.1 – 2026-10-24

Directory review fixes, no change to the checks:
- Skills pre-approve only their own script (`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/listingdoctor.py" …`, plus `python`/`py -3`)
  instead of any Python command. File writes are limited to the working folder (`Edit(./**)`).
- `plugin.json`: homepage, repository and support e-mail; plugin icon.

## 1.2.0 – 2026-10-22

Keyword input aligned with TermSweep and KeywordShare (integration chain B: the same search term report feeds both checks).

- Search term reports are now read with TermSweep's reader (`scripts/ld_ads.py`, copy of `ts_report.py` 1.0.1, the same
  copy KeywordShare uses) and ranked by **orders**: amazon.de console up to 2026 ("7 Tage, Aufträge gesamt (#)"), DE/EN 2026
  ("Käufe", "Purchases"), API/camelCase exports (`searchTerm` instead of the targeting column), bulk tab, Sellerboard export,
  CSV/TSV/TXT/XLSX. Search terms without orders are never used as keywords; a report without any orders skips coverage with a note.
  Before, German reports were weighted by clicks (money-burning terms showed up as "missing keywords") and API exports read
  the targeting column.
- Other tables and lists: Windows-1252 and UTF-16 files (Excel "Unicode text") are read instead of garbling umlauts or crashing;
  camelCase headers are split; German Search Query Performance labels ("Suchabfrage", "Volumen der Suchabfrage") added.
- Plain `.txt` lists (e.g. from KeywordShare) are read line by line — a comma inside a search query no longer discards the list.
- Notes instead of silent truncation: which ranking was used, and "N search terms; the first 50 are used" when a list is longer.
- `--market` accepts upper case and domains ("DE" as KeywordShare writes it, "GB", "amazon.co.uk").
- Script version string now matches the manifests.

## 1.1.0 – 2026-10-22

- Category rules (beauty/cosmetics, electronics, toys, food & supplements) from `references/category_rules.json`, detected by
  product type or product words in the title; required-information checks (e.g. INCI list for cosmetics).
- Public pages: the title customers see is checked; if Amazon shows a shorter title than the one on file, ListingDoctor reports the
  likely AI replacement (T_REWRITTEN). Bullets found on fashion pages, apparel size codes removed from titles.
- New checks: subjective superlatives (C_SUBJ), non-EU fibre names such as "Bambusfaser"/"Spandex" (E_FIBRE3), more than 5 bullets
  (B_MANY), "UPF 50+"/"hypoallergen" as claims needing proof, return/refund promises ("bei Nichtgefallen"), "jetzt bestellen".
- German word endings are matched for claims ("umweltfreundlichen"); fibre compounds parsed ("85% Bambus-Viskose").
- Textiles recognised by product words when no product type is given (pasted text, public pages).
- Fix: `--lang` sets only the report language; listings are always checked in their own language (before, `--lang en`
  on a German report skipped the German claim lists). New `--listing-lang` to force it.
- Fixes: "top" no longer flagged in backend terms (garment), "reduziert" only in price context; drafts that only change title/highlights
  of a title-only row are no longer judged on content they don't touch.
- Skills: every script call as one plain command (works where only `python3` is allowed); rewrite skill describes borrowed sibling facts.
- Eval suite for `claude plugin eval` (free 6 cases, Pro 4 cases); build no longer deletes folders.

## 1.0.0 – 2026-10-21

First release (free and Pro).

- Rule check for Amazon listings (US + EU): 75-character titles (since 2026-07-27, media 200),
  Item Highlights ≤ 125, forbidden title characters, word repetition, bullets 10–255/500, emojis and
  special characters, backend search terms ≤ 249 bytes (UTF-8), duplicates, placeholders, contact data,
  ASINs in text, HTML in descriptions.
- Claims: promotional wording, health/biocide claims, generic eco claims (EU Directive 2024/825, from
  2026-09-27), absolute safety claims.
- EU: GPSR contact data in the file, textile fibre composition (Reg. (EU) 1007/2011) for textile product types.
- Required attributes read from the template's Data Definitions sheet; title-only rows and Amazon Grade &
  Resell SKUs recognised.
- Inputs: category listing report (.xlsm/.xlsx), flat file (.txt/.csv), JSON, labelled text, public product
  pages by ASIN (amazon.de/.com/.co.uk/.fr/.it/.es/.nl/.pl/.se).
- Keyword coverage from a search term report, Search Query Performance export or keyword list.
- Pro: every finding, Excel report, rewrite briefs, draft comparison, variation family check, backend
  clean-up, partial-update upload file in the seller's own template (refuses drafts with hard errors).
