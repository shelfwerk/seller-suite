# Getting listings into ListingDoctor

ListingDoctor only reads files or public product pages. It never logs in, never uploads, never changes a listing.

## Best: category listing report (all listings, incl. backend search terms)

Seller Central → **Catalog → Add products via upload** (*Katalog → Produkte über Upload hinzufügen*)
→ tab **Download an inventory file / Spreadsheet** → **Category listings report**
(*Kategorie-Angebotsbericht*) → request → download the `.xlsm`/`.xlsx`.

- Contains every listing you contributed: title, Item Highlights (`title_differentiation`), bullets,
  backend search terms (`generic_keyword`), description, images, variation data, GPSR fields.
- The sheet **Data Definitions** (*Datendefinitionen*) marks required fields – ListingDoctor uses it
  for the required-attribute check.
- Rows with SKUs starting `amzn.gr.` (Amazon Grade & Resell) and Amazon's example row (`ABC123`) are skipped.
- A row that holds only Amazon's live title (`::title`) and none of your values means another seller
  contributed the content – only the title is checked there.

Classic flat files (`.txt` tab-delimited or `.xlsx`, header row with `item_sku`, `item_name`,
`bullet_point1`…`5`, `generic_keywords`) work the same way.

## Quick: ASINs (public product page)

`check B0XXXXXXXX,B0YYYYYYYY --market de` reads the public page (amazon.de/.com/.co.uk/.fr/.it/.es/.nl/.pl/.se).
Backend search terms are not public and are not checked. Max. 20 ASINs per run, one request every
2 seconds. If Amazon answers with a captcha, paste the text instead. Variation children sometimes
open a sibling's page – compare the ASIN in the result.

## Anything else: text or JSON

Text, one listing per block, blocks separated by a line `---`:

```
ASIN: B0XXXXXXXX
Brand: Example
Title: …
Highlights: …
Bullet 1: …
Bullet 2: …
Backend: …
Description: …
Images: 7
Product type: HAT
```

JSON: `{"listings": [{"sku": "…", "asin": "…", "brand": "…", "title": "…", "highlights": "…",
"bullets": ["…"], "backend": "…", "description": "…", "image_count": 7, "category": "HAT"}]}` – the
same format is used for drafts in ListingDoctor Pro.

## Keywords (optional, for coverage)

- **Search term report** from Amazon Ads (Sponsored Products → Reports → Search term), `.xlsx`/`.csv`/`.txt`,
  any console language (old and 2026 column names, e.g. "7 Tage, Aufträge gesamt (#)", "Käufe", "Purchases"),
  API/camelCase exports, the bulk file's search term tab, Sellerboard's search term export. Read with the
  same reader as TermSweep (`scripts/ld_ads.py`) and ranked by **orders**; terms without orders are never
  used. A report without any orders skips coverage with a note.
- **Search Query Performance** export from Brand Analytics, English or German labels (ranked by search
  query volume) — or, better, KeywordShare's keyword list, which keeps only queries with proven fit.
- **Plain list** (`.txt`): one keyword per line, most important first (commas inside a query are fine).

At most 50 search terms are used (the most important); a note says when a list is longer.
The same search term report also feeds TermSweep (PPC) – one download, two checks.
