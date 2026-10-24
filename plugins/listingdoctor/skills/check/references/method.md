# How ListingDoctor scores a listing

Every check is a fixed rule in `scripts/ld_rules.py` (limits and word lists) and `scripts/ld_core.py`
(the checks). Same input → same result. Sources and dates for each rule: `rules.md`.

## Score

Start at 100. Each finding costs points: **error 12**, **warning 5**, **info 1**. One area can lose at
most: title 35 · compliance 30 · bullets 30 · attributes 20 · backend 15 · keywords 15 · images 10 ·
description 10. Grade: A ≥ 90 · B ≥ 80 · C ≥ 70 · D ≥ 55 · F below.

Parent rows (non-buyable) are skipped; Pro's `family` command checks them.

## Severity

- **error** – breaks an Amazon rule or EU law, or Amazon rewrites/suppresses the content
  (title > 75 characters, forbidden characters, emojis in bullets, backend > 249 bytes,
  promotional claims, contact data, placeholders, empty required attributes).
- **warning** – costs ranking or conversion, or is legally risky (health/biocide claims, generic eco
  claims, duplicate titles, missing fibre composition, bullets > 255 characters, words repeated in the backend).
- **info** – polish (end punctuation in bullets, brand not first, unused backend bytes, GPSR data not in the file).

## Codes

| Area | Codes |
|---|---|
| title | T_LEN, T_SHORT, T_CHAR, T_CHAR2, T_REPEAT, T_CAPS, T_BRAND, T_EMPTY, T_DUPL, T_REWRITTEN (page shows Amazon's shorter title) |
| highlights | H_LEN, H_EMPTY, H_REPEAT |
| bullets | B_COUNT, B_MANY, B_LONG, B_TOOLONG, B_SHORT, B_LOWER, B_CHAR, B_DUP, B_END, B_CAPS |
| backend | K_BYTES, K_EMPTY, K_LOW, K_DUPTB, K_DUP, K_PUNCT, K_SUBJ, K_BRAND |
| description | D_LEN, D_HTML |
| compliance | C_PROMO, C_PROMO2, C_HEALTH, C_ECO, C_EVID, C_SUBJ, C_CONTACT, C_PLACE, C_ASIN (German word endings are matched: *umweltfreundlichen*) |
| attributes | A_REQ (from the template's Data Definitions), A_BRAND, A_LIVE |
| images | I_MAIN, I_COUNT, I_FILE |
| EU | E_GPSR, E_FIBRE, E_FIBRE2, E_FIBRE3 (non-EU fibre names such as *Bambusfaser*, *Spandex*) – EU marketplaces only; textiles are recognised by product type or, without one, by product words in the title |
| categories | G_ERR, G_WARN (category word lists), G_PAT (category patterns, e.g. EU SPF > 50, toy under-3 contradiction, weight-loss amounts), G_MISSING (required statements, e.g. NemV), G_BRAND (third-party brand without "for/kompatibel mit"), G_HINT (checklist) – from `category_rules.json`, rules.md section 10 |
| keywords | W_MISS, W_WEAK (only with a search term report / keyword list) |
| Pro families | F_THEME, F_ATTR, F_COMBO, F_TITLE, F_BRAND, F_PTYPE, F_PTITLE, F_NOPARENT, F_SINGLE |

## Keyword coverage

A search term counts as covered when every content word (stop words removed, simple stemming,
German compounds: *Laufstirnband* covers *Stirnband*) appears in one field: title → highlights →
bullets → backend, or spread across fields. The top 15 terms by orders are scored: uncovered terms
are W_MISS, top-5 terms that are not in title or highlights are W_WEAK.

## Limits of a rule check

- Word lists catch the usual wording, not every paraphrase. A claim that passes can still be refused by Amazon.
- Health, biocide and eco rules depend on proof you hold – ListingDoctor flags the wording, it cannot see certificates.
- This is a checklist, not legal advice.
