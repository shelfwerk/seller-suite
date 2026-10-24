# ListingDoctor — Amazon listing check (free)

Is your listing still within Amazon's rules? Since **27 July 2026** Amazon allows only **75 characters**
in product titles (media: 200) and rewrites longer titles with AI. ListingDoctor checks every listing
against the current rules and EU law and tells you, per listing, a **score (0–100, A–F)** and the
**five fixes that matter most**:

- title: 75 characters, forbidden characters `! $ ? _ { } ^ ¬ ¦`, words used more than twice, ALL CAPS,
  duplicate titles across listings,
- **Item Highlights** (*Artikel-Highlights*, 125 characters),
- bullets: count, 10–255 characters, emojis and special characters, duplicates, placeholders,
- backend search terms: **249 bytes** (umlauts count 2), repeats, brands, ASINs, subjective words,
- claims: promotion ("free shipping", "#1", "Testsieger"), health/biocide ("antibacterial"), generic
  eco claims banned in the EU since 27 Sep 2026 ("umweltfreundlich", "nachhaltig"), contact data,
- category rules: cosmetics (medical claims, INCI list), electronics (FDA/military-grade/certification claims), toys, food and
  supplements (health claims),
- superlatives ("the best … you'll ever wear"), test claims that need proof ("UPF 50+", "hypoallergenic"),
- EU: GPSR contact data, fibre composition and EU fibre names for textiles ("Viskose (Bambus)", not "Bambusfaser"),
- public pages: detects when Amazon already shows a shorter, AI-written title instead of yours,
- required attributes (read from your own template), images, keyword coverage from your search term report.

Nothing is changed on Amazon — ListingDoctor only reads files and public product pages.

## Use

| Command | What it does |
|---|---|
| `/listingdoctor:check [file | ASINs | text] [search term report]` | Score + top 5 fixes per listing |

Or just ask: *"Check my listings"* + the **category listing report** (*Kategorie-Angebotsbericht*,
Seller Central → Catalog → Add products via upload → Download), ASINs (`B0…`, public page; backend
not visible) or pasted text. Answers in English or German; amazon.de/.com/.co.uk/.fr/.it/.es/.nl/.pl/.se.

## Install

- **Claude Code** (2.1.275 or later):
  ```
  /plugin install listingdoctor --marketplace shelfwerk/seller-suite
  ```
  To try without installing: `claude --plugin-dir ./listingdoctor`.
- **Claude Desktop / Cowork:** Customize → Plugins → upload `listingdoctor-<version>.zip`.

Requires Python 3 (built into Cowork and macOS; on Windows from python.org). No extra packages, no API
keys, no Amazon developer account.

## Privacy

Checks run locally in `scripts/listingdoctor.py`. Files never leave your machine. The only network
access is reading the **public** Amazon product page when you give ASINs (one request every 2 seconds,
max. 20 per run). Claude sees the summary the script prints, as part of your conversation.

## How it decides

Fixed rules with sources and dates: `skills/check/references/rules.md`. Scoring and all codes:
`skills/check/references/method.md`. It is a checklist, not legal advice.

## ListingDoctor Pro

Pro shows **every** finding with an Excel report, **writes rule-checked drafts** (title ≤ 75, Item
Highlights, 5 bullets, backend ≤ 249 bytes) and re-checks them until they pass, checks **variation
families**, and builds a **partial-update upload file** in the layout of your own category listing report.

## License

MIT — see `LICENSE`.
