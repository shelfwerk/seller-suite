# ListingDoctor – Amazon listing rules reference (US / DE / EU)

As of **2026-10-21**. Read-only web research. Every rule carries: limit/list · scope · source + date · confidence.

- **verified** = primary source read (Amazon announcement or Amazon-staff forum post, law text).
- **likely** = Amazon text quoted second-hand, or several consistent secondary sources.
- **unclear** = sources conflict or no confirmation found. Treat as *warning/info*, never as hard error.

Amazon help pages (`sellercentral.amazon.*/gp/help/...`) need a login and could not be fetched. They are cited
by help ID; their content comes from forum quotes or third-party copies. Re-check after every Amazon policy email.

---

## 1. Title (`item_name`)

> **Biggest change:** since **2026-07-27** the title limit is **75 characters**, not 200. The Jan-2025 200-char rule is
> superseded for every category except media. Implemented in `ld_rules.py` (`TITLE_MAX = 75`, `TITLE_MAX_MEDIA = 200`,
> `HIGHLIGHTS_MAX = 125`); confirmed independently on 2026-10-21 (Lengow, Händlerbund, amalytix, ppc.land).
> In the category listing report the Item Highlights field is the column `title_differentiation` (seen in a real 2026 DE report).

| ID | Rule | Limit / list | Applies to | Source (date) | Conf. |
|---|---|---|---|---|---|
| T1 | Max. title length incl. spaces | **75 chars** | All categories **except media** (books, music, video/DVD; software listed by some DE sources); US + DE confirmed | Amazon forum "Updates to improve your product titles begin on July 27" US: https://sellercentral.amazon.com/seller-forums/discussions/t/145b6d0f-999c-4555-896c-c694bda2e470 · DE: https://sellercentral.amazon.de/seller-forums/discussions/t/d24be94b-9ca5-437f-a7c2-1f4f7462a15f (posted/updated 2026-06-10) | verified |
| T1a | Brand name counts toward the 75 | brand + product type + key attribute fit into 75 | as T1 | secondary: ppc.land 2026-06-13, goatconsulting 06/2026 (example titles); Amazon post silent | likely |
| T1b | Over-limit titles after 2026-07-27 | Amazon gradually replaces them with an AI-generated title; listing stays active; brand owners get 14 days in "Review listing changes" | as T1 | Amazon forum posts above | verified |
| T1c | Other EU stores (FR/IT/ES/NL/PL/SE/BE/IE) | assume same 75-char rule | EU | ppc.land says "Seller Central globally"; not checked per store | likely |
| T2 | **Item Highlights** (DE: "Artikel-Highlights") – new field | **≤ 125 chars**, searchable, shown under the title in search and on the detail page. Content: material, use case, compatibility, age range. No promo, no keyword stuffing, no repeat of title words | as T1 | Amazon forum posts above (2026-06-10); sellersprite 2026-08-01; adsmasters.de 2026-10-17 (bulk via category listing report) | verified (limit) |
| T2a | Attribute key for flat file / JSON | not documented publicly; sellers report error `100476: attribute 'Item Highlight' is currently unsupported` | – | ppc.land, Amazon DE forum thread | unclear |
| T3 | Media titles | 200 chars incl. spaces (Jan-2025 rule) | media categories | Amazon forum "New product title requirements effective January 21, 2025": https://sellercentral.amazon.com/seller-forums/discussions/t/533f9cf7-3b5e-4974-b523-02e4a1a42c5f · EU copy: https://sellercentral-europe.amazon.com/seller-forums/discussions/t/3781c84d-4778-40fe-9dde-30039a0948f6 | likely (still in force for media) |
| T4 | Forbidden characters | `! $ ? _ { } ^ ¬ ¦` – allowed only if part of the brand name | all titles, US + EU (posted on US, UK/EU, CA, IN forums) | Jan-2025 announcement (above) | verified |
| T4a | Restricted characters | `~ # < > *` only inside identifiers/measurements; `\| - , / . & ( )` are fine | all | help GYTR6SYGFA5E3EQC (quoted second-hand); SellerLabs KB 2026-09-20 | likely |
| T4b | Still valid after the 75-char change? | Amazon did not revoke T4/T5/T6 and links the same help page | all | Amazon 2026 posts link GYTR6SYGFA5E3EQC | likely |
| T5 | Word repetition | same word **max. 2×**; prepositions, articles, conjunctions exempt. Singular/plural counted together per one guide | all | Jan-2025 announcement | verified (rule) / unclear (plural) |
| T6 | No promotional / seller wording | e.g. "free shipping", "100% quality guaranteed", "best seller", "#1", "sale", "% off", shipping/returns info, contact data, URLs | all | help GYTR6SYGFA5E3EQC (quoted); SellerLabs KB 2026-09-20 | likely |
| T7 | No subjective claims, no competitor brands | "best", "amazing", "best quality"; other brands | all | SellerLabs KB 2026-09-20 | likely |
| T8 | Format | no ALL CAPS (except a legally capitalized brand); capitalize the first letter of each word except short articles/prepositions/conjunctions; numerals, not spelled-out numbers; no emoji, no HTML, avoid ® ™ © | all | SellerLabs KB 2026-09-20; category style guides (G200270100) | likely |
| T9 | Order (recommendation) | brand → product line/type → key attribute → colour → size/pack count → model no. | all | SellerLabs KB; Amazon style guides | likely |

Implementation: count **Unicode characters** (not bytes) for titles. Error if > 75 (non-media). Info if > 60 (mobile).

## 2. Bullet points (`bullet_point`, "key product features")

| ID | Rule | Limit / list | Applies to | Source (date) | Conf. |
|---|---|---|---|---|---|
| B1 | Number | up to **5** for sellers (vendors up to 10); Amazon recommends ≥ 3 | all | amalytix 2025-01-03; emplicit; wisepim 2026-10-11 | likely |
| B2 | Length per bullet | guidance **10–255 chars**; hard max is per product type (template/PTD `maxLength`, often 500) | all | emplicit, sellersprite (10–255); flywheel/emplicit (500); wisepim 2026-10-11 ("real limit = template") | likely (10–255) / unclear (hard max) |
| B3 | Start with a capital letter; sentence fragments; separate phrases with semicolons; space between number and unit ("60 ml") | – | all | Amazon staff post "Let your product's bullet points do the talking" (Joey_Amazon): https://sellercentral.amazon.com/seller-forums/discussions/t/1f79ab03-8444-4b8c-be69-b1939be89121 | verified |
| B3a | No end punctuation | – | all | secondary only (emplicit, sellersprite) | likely |
| B4 | No emoji, no special characters | Amazon names "special characters, emojis". Common list: `™ ® € … † ‡ º ¢ £ ¥ © ± ~ â` and ☺ ☹ ✅ ❌ | all, effective **2024-08-15** | Amazon announcement (News_Amazon): https://sellercentral.amazon.com/seller-forums/discussions/t/65f8e647-977d-49ac-9036-2049b96720b2 ; list: estorefactory 2024-10-01 | verified (rule) / likely (list) |
| B5 | Prohibited phrases | Amazon examples: **"eco-friendly", "anti-bacterial"**, refund-related guarantees. Also reported: "environmentally friendly", "anti-microbial", "made from bamboo", "contains soy" (unless certified), "full refund", "unconditional guarantee" | all | Joey_Amazon post + News_Amazon 2024 post (above); estorefactory | verified (examples) / likely (rest) |
| B6 | No company info, contact data, URLs, ASINs, references to other products | – | all | Joey_Amazon post | verified |
| B7 | No placeholders | "N/A", "n/a", "not applicable", "TBD", "to be decided", "yet to decide", "COPY PENDING", "not eligible" | all | estorefactory; wisepim | likely |
| B8 | No repetition across bullets or other fields; no subjective claims or competitor comparisons; no vague/misleading wording | – | all | Joey_Amazon post | verified |
| B9 | Enforcement | Amazon may rewrite/remove non-compliant bullets with generative AI; suggestions shared for review | all | News_Amazon 2024 post | verified |
| B10 | Manufacturer warranty | stating a real warranty ("2 years manufacturer warranty") is product information, not a promo guarantee | all | wisepim FAQ | unclear |

EU/DE: no separate bullet policy found; Amazon's announcements are global. Treat B1–B9 as valid on amazon.de (likely).

## 3. Description (`product_description`)

| ID | Rule | Limit / list | Applies to | Source (date) | Conf. |
|---|---|---|---|---|---|
| D1 | Length | **≤ 2,000 chars** (template may differ) | all | typecount 2026; viral-launch; storeautomator | likely |
| D2 | HTML | **not supported** since **2021-07-30**; tags are stripped or the line is removed. `<br>` reported to still render by sellers | all | Amazon announcement (News_Amazon): https://sellercentral.amazon.com/seller-forums/discussions/t/d2712113d23ba4ccaede5a1bfd81f945 | verified (no HTML) / unclear (`<br>`) |
| D3 | Content | same bans as bullets: promo, pricing, contact, URLs, prohibited claims | all | product detail page rules, help G202024200 (quoted) | likely |
| D4 | A+ content | when A+ is live, the plain description is usually not displayed (still indexed) | brand owners | secondary | unclear |

## 4. Backend search terms (`generic_keyword`)

| ID | Rule | Limit / list | Applies to | Source (date) | Conf. |
|---|---|---|---|---|---|
| K1 | Byte limit | **< 250 bytes** total over all generic-keyword fields (max. 5 attributes). IN < 200, JP 500. **Enforce ≤ 249 bytes** | US, all EU stores, UK, CA … | help G23501 quoted on Amazon forums: https://sellercentral.amazon.ca/seller-forums/discussions/t/0ae10d05-66d2-406b-b336-16791df2bce8 ; Amazon staff quick tip (250 bytes): https://sellercentral-europe.amazon.com/seller-forums/discussions/t/93c61d8c-5c4d-43bf-9b5a-6b3e48213aa2 | likely |
| K2 | Over the limit | **whole entry rejected / not indexed** (not just the overflow) | as K1 | help text quoted on forum (above) | likely |
| K3 | Byte counting | UTF-8: a–z, 0–9 = 1 byte; **ä ö ü ß = 2**, £ = 2, € = 3, emoji 3–4. Amazon: spaces and punctuation don't count – but count them anyway (conservative) and report both values | as K1 | forum quote (above) | likely |
| K4 | Don't include | brand names (own and competitors), ASINs/other identifiers, words already in title/brand/other fields, repeated words, stop words (a, an, and, by, for, of, the, with; DE: und, mit, für, der/die/das, ein/eine), punctuation (`; : -`, commas), misspellings | as K1 | Amazon staff quick tip (above); forum quote | verified (repeats, stop words, redundancy, punctuation, misspellings) / likely (brands, ASINs) |
| K5 | Also exclude | temporary terms ("new", "on sale", "neu", "Angebot"), subjective claims ("best", "cheapest", "amazing"), offensive/abusive terms | as K1 | sellersonar 2026-10-15; tool4seller | likely |
| K6 | Do include | synonyms, spelling variants, abbreviations, other-language terms used by local shoppers; words separated by single spaces | as K1 | Amazon staff quick tip | verified |
| K7 | Open questions | sellersonar (2026-10-15) reports US moderator guidance of **200 bytes**; AMALYZE news 04/2026 claims backend keywords are being removed in the US. Neither confirmed by Amazon | US | https://sellersonar.com/blog/amazon-backend-keywords/ ; https://amalyze.com/news/april-2026 | unclear |

US vs EU: same limit and rules. Practical difference on .de/.fr/.it/.es: umlauts/accents cost 2 bytes.
Implementation: error > 249 bytes; info > 200 bytes ("US guidance may be 200").

## 5. Prohibited claims (titles, bullets, description, Item Highlights, backend, images, A+)

Amazon publishes **no single banned-word list**; context and documents decide (sellersonar 2026-10-06). Use two severities:
**block** = remove unless registered/certified; **evidence** = allowed only with proof shown in the same listing.

| ID | Group | EN examples | DE examples | Basis | Conf. |
|---|---|---|---|---|---|
| C1 | Pesticide / biocide (block) | antibacterial, antimicrobial, antiviral, antifungal, disinfectant, sanitizes, kills 99.9% of germs, mold-resistant, insect repellent, repels mosquitoes, pest control | antibakteriell, antimikrobiell, antiviral, desinfizierend, keimtötend, tötet 99,9 % der Bakterien, schimmelresistent, Mückenschutz, insektenabweisend, Schädlingsbekämpfung | US: FIFRA/EPA, Amazon pest-control policy help G202115120 (EPA reg. no. or exemption needed); EU: Biocidal Products Reg. (EU) 528/2012 Art. 58 (treated articles: claim → label with active substance) and Art. 72(3) (biocide ads must not say "low-risk", "non-toxic", "harmless", "natural", "environmentally friendly", "animal friendly") https://eur-lex.europa.eu/eli/reg/2012/528/oj | likely |
| C2 | Medical / drug / health (block) | cures, treats, heals, prevents disease, relieves pain, anti-inflammatory, FDA approved/cleared, clinically proven, detox, COVID, boosts immunity, weight loss | heilt, behandelt, lindert Schmerzen, beugt Krankheiten vor, entzündungshemmend, FDA-zugelassen, klinisch bewiesen, entgiftend, gegen Corona, stärkt das Immunsystem, zum Abnehmen | US: FD&C Act, Amazon restricted-products policy; DE/EU: Heilmittelwerbegesetz (HWG §§ 3, 11), Health-Claims-Reg. (EC) 1924/2006 for food/supplements, MDR (EU) 2017/745 for medical devices | likely |
| C3 | Promotion / price / guarantee (block in title & bullets) | free shipping, best seller, #1, top rated, hot item, sale, % off, limited time, buy now, money-back guarantee, 100% satisfaction guaranteed, full refund, unconditional/lifetime guarantee | kostenloser Versand, versandkostenfrei, Bestseller, Nr. 1, Testsieger (without source), Angebot, Rabatt, nur für kurze Zeit, jetzt kaufen, Geld-zurück-Garantie, 100 % Zufriedenheitsgarantie | Amazon title rules (T6), bullet rules (B5) | verified ("free shipping", refund guarantees) / likely |
| C4 | Subjective / comparative (warn) | best, cheapest, perfect, amazing, highest quality, better than [brand] | beste, billigste, perfekt, höchste Qualität, besser als [Marke] | T7, B8 | likely |
| C5 | Environmental (EU: block unless proven; Amazon: warn) | eco-friendly, environmentally friendly, green, sustainable, climate neutral, carbon neutral, CO2 neutral, climate friendly, biodegradable, nature friendly, ecological | umweltfreundlich, umweltschonend, nachhaltig, klimaneutral, CO2-neutral, klimafreundlich, grün, ökologisch, biologisch abbaubar, naturfreundlich, energieeffizient | Amazon B5; EU EmpCo (section 6) | verified (Amazon "eco-friendly"; UWG text) |
| C6 | Safety absolutes (evidence) | non-toxic, harmless, safe, non-poisonous, all natural, BPA-free, recyclable, compostable | ungiftig, unschädlich, 100 % sicher, rein natürlich, BPA-frei, recycelbar, kompostierbar | sellersonar 2026 (high-risk / needs substantiation) | likely |

## 6. EU law that shows up in listings

### 6.1 EmpCo – Directive (EU) 2024/825 ("Empowering Consumers for the Green Transition")

| ID | Item | Content | Source (date) | Conf. |
|---|---|---|---|---|
| E1 | Dates | OJ 2024-03-06; transposition by **2026-03-27**; **applies from 2026-09-27** (in force now) | https://eur-lex.europa.eu/eli/dir/2024/825/oj ; IHK Ostthüringen 2026-03-31 https://www.ihk.de/gera/recht-und-steuern/fokus-empco/kt1-umweltaussagen-7015108 | verified |
| E2 | Germany | "Drittes Gesetz zur Änderung des UWG", **BGBl. 2026 I Nr. 43** (promulgated 2026-02-19), rules apply from 2026-09-27. Austria: UWG/KSchG/FAGG, same date | Osborne Clarke 2026-06-09 (upd. 2026-09-28) https://www.osborneclarke.com/de/insights/greenwashing-verbot-was-die-uwg-reform-fuer-umweltbezogene-werbeaussagen-bedeutet ; WKO https://www.wko.at/oe/oesterreich/uwg-verbraucherrecht-umwelt-nachhaltigkeit | likely |
| E3 | Transition | **§ 15b UWG** (decided 2026-09-24): injunctions for products placed on the market before 2026-09-27 only after case-by-case review, until 2028-09-27 – **not for digital communication** → Amazon listings must comply now | Osborne Clarke update 2026-09-28 | likely |
| E4 | Blacklist (UWG Annex no.) | **2a** sustainability label not based on a certification scheme or set by a public authority (self-made seals) · **4a** generic environmental claim without proof of *recognised excellent environmental performance* (EU Ecolabel, Blauer Engel, ISO 14024 type-I labels) · **4b** claim about the whole product/business when it concerns one aspect only (e.g. "made from recycled material" when only the packaging is) · **4c** "climate neutral / reduced / positive" based on offsetting (product claims) · **10a** presenting legal requirements as a special feature (e.g. "CE-certified" as USP) · **23d** misleading durability/repair/software-update claims | UWG Anhang: https://www.gesetze-im-internet.de/uwg_2004/anhang.html | verified |
| E5 | Definition "generic claim" | environmental claim not on a sustainability label whose **specification is not given clearly and prominently in the same medium** (§ 2(2) no. 1 UWG). → a concrete, verifiable spec in the same listing (e.g. "outer shell 80 % recycled PET") is the fix | https://www.gesetze-im-internet.de/uwg_2004/__2.html | verified |
| E6 | Future claims | "climate neutral by 2030" only with a public, independently monitored implementation plan (§ 5(3) no. 4 UWG) | Osborne Clarke | likely |
| E7 | Sanctions | warning letters (Abmahnung) by competitors/associations, injunctions; fines up to 4 % of EU turnover in coordinated cases | Osborne Clarke | likely |
| E8 | Green Claims Directive | not adopted; Commission announced withdrawal 06/2025 – status disputed. Not applicable law | verso.de 06/2026; osapiens 07/2026 | unclear |

### 6.2 GPSR – Regulation (EU) 2023/988 (applies since 2024-12-13)

| ID | Item | Content | Source | Conf. |
|---|---|---|---|---|
| G1 | Art. 19 – every online offer must show | (a) manufacturer name / registered trade name or trademark + **postal and electronic address**; (b) if manufacturer outside EU: **EU responsible person** (Art. 4(1) Reg. 2019/1020) name + postal + electronic address; (c) product identification incl. **picture**, type, other identifier (batch/serial/model); (d) **warnings and safety information** in a language easily understood by consumers of the member state (DE for amazon.de) | https://eur-lex.europa.eu/eli/reg/2023/988/oj ; GS1 Sweden guideline 12/2024 https://gs1.se/wp-content/uploads/sites/2/2024/12/gpsr-guideline-en.pdf | verified |
| G2 | On Amazon | manufacturer + RP contacts entered in Seller Central (Account Health → Regulatory compliance / Manage your compliance) and linked per ASIN; warnings/safety info as attribute, image or PDF; bulk via inventory file template; missing data → listing blocked/deactivated, cases opened | SP-API changelog https://developer-docs.amazon.com/sp-api/changelog/developers-can-use-attributes-in-their-programmatic-listings-submissions-to-comply-with-gpsr ; Lengow help; eselt.de | likely |
| G3 | Plugin check | flag missing manufacturer / RP / safety-info columns in the flat file; flag warnings not in the marketplace language | derived | – |

### 6.3 Textile labelling – Regulation (EU) No 1007/2011 (apparel, home textiles)

| ID | Item | Content | Source | Conf. |
|---|---|---|---|---|
| X1 | Online | fibre composition must be **visible before purchase**, also for online sales (Art. 16(1)); DE: § 4(5) TextilKennzG | https://eur-lex.europa.eu/eli/reg/2011/1007/oj ; WKO (2018) https://www.wko.at/oe/handel/mode-freizeitartikel/textilkennzeichnungsverordnung ; https://www.gesetze-im-internet.de/textilkennzg_2016/__4.html | verified |
| X2 | Format | only fibre names from **Annex I**, in the official language of the store (DE: Baumwolle, Polyester, Elasthan, Polyamid, Viskose, Wolle …); **% by weight, descending**; trade names alone ("Lycra") not allowed | WKO; Reg. 1007/2011 Art. 5, 9 | likely |
| X3 | "100 %", "rein", "pure" | only if the product consists solely of that fibre (2 % tolerance for unavoidable foreign fibres) | Reg. 1007/2011 Art. 7 | likely |
| X4 | "Other fibres" | single fibre ≤ 5 % or several ≤ 15 % together may be "sonstige Fasern" when hard to determine; decorative fibres ≤ 7 % need not be listed | WKO | likely |

## 7. Images and video

| ID | Rule | Limit / list | Applies to | Source (date) | Conf. |
|---|---|---|---|---|---|
| I1 | Main image background | **pure white RGB 255,255,255** | all | Amazon staff post "Product Image Requirements and Best Practices" (TaylorR_Amazon, ~12/2025): https://sellercentral.amazon.com/seller-forums/discussions/t/13af96ea-6b07-4bf9-8dbe-a13292c2e3b1 | verified |
| I2 | Product fill | **≥ 85 %** of the frame; not cropped at the edge (necklaces excepted) | all | same; Jungle Scout 2024-04-05 (help 1881) | verified |
| I3 | Main image content | no text, graphics, logos, watermarks, borders, colour blocks, badges; no illustrations/mock-ups; no props or accessories not included; product out of its packaging; one product, one view | all | Amazon staff post (text, graphics, watermarks, illustrations, props); Jungle Scout (rest) | verified / likely |
| I4 | Resolution | **≥ 1000 px longest side** (enables zoom); ≥ 500 px to display; 1600+ px recommended; max 10,000 px | all | Amazon staff post (1000 px); Jungle Scout (500/1600/10,000) | verified / likely |
| I5 | Format | JPEG (preferred), TIFF, PNG; GIF non-animated; RGB/sRGB or CMYK | all | Amazon staff post; Jungle Scout | verified |
| I6 | Number | up to 9 uploadable; 7 shown (6 if a video is present). Recommend ≥ 7: main, details, in use, dimensions, what's in the box, infographic, safety/warnings if required | all | Jungle Scout 2024-04-05 | likely |
| I7 | Apparel / shoes | adult apparel on a standing model; kids/baby and multipacks flat; no visible mannequins (socks/hosiery excepted); single shoe facing left at 45° | apparel, shoes | Jungle Scout (help 1881) | likely |
| I8 | Claims in images/A+ | the claim rules of section 5 also apply to image text and A+ (pesticide words in images get flagged) | all | sellersonar 2026 | likely |
| I9 | Video | Brand Registry usually required; MP4/MOV, ≥ 720p (1080p recommended), 15–60 s recommended in the image carousel; no URLs, contact data, prices/promotions, reviews or star ratings | brand owners | gliacloud 2026; goatconsulting 2026; revenuegeeks (BR not always required) | unclear |

## 8. Variations (parent/child)

| ID | Rule / typical error | Content | Source | Conf. |
|---|---|---|---|---|
| V1 | Only true variants | same product, differing only in theme attributes (size, colour, scent, pack count …). Different products, mixed bundles, other brands, condition, or "review merging" = **variation abuse** → ASIN-creation or selling privileges removed | Amazon variation policy quoted on forum https://sellercentral.amazon.com/forums/t/account-has-been-temporarily-deactivated-policy-violation-variation-abuse/521876 ; amalyze guide | likely |
| V2 | Variation theme | must be valid for the product type (e.g. `SizeColor`, `Color`, `Size`); identical across the family; deprecated themes → families get split | amalyze; sellersonar glossary | likely |
| V3 | Parent row | non-buyable (no price/qty); parent title **without** size/colour; same brand and product type as children | amalyze; goatconsulting 06/2026 | likely |
| V4 | Child rows | `parent_child = Child`, `parent_sku` = parent SKU, `relationship_type = Variation`; every theme attribute filled (`size_name`, `color_name` + `size_map`/`color_map` where used); no duplicate attribute combinations | Amazon flat-file templates | likely |
| V5 | Title consistency | child title = parent base title + variant values in the same order and spelling ("…, Blau, XL"); all within 75 chars (T1) | goatconsulting 06/2026 | likely |
| V6 | Frequent upload errors | 8008 (other product's ASIN used as parent), 8032 (child already in another family), 20002 (value conflicts with theme) | amzadvisers / error-code guides | likely |

## 9. Severity mapping for the plugin (proposal)

- **error**: T1, T4, T5, B4 (emoji), B6, B7, D2, K1, C1–C3, E4/E5 hits on .de/.fr/.it/.es/.nl/.pl/.se/.be, G1 fields missing, X1 missing (apparel), I1–I3 if image metadata available, V1–V4.
- **warning**: T6–T8, B2 (> 255), B3/B3a, B5 phrases, B8, C4–C6, K4–K5, E6, X2–X3, V5.
- **info**: T9, title > 60, K7 (> 200 bytes), I6 (< 7 images), I9.

Always show rule ID + source + "as of" date, and the line "This is a checklist, not legal advice."

## 10. Category rules (beauty, electronics, toys, food, apparel)

As of **2026-10-22**. Applies **in addition** to sections 1–9; the global lists of section 5 / `ld_rules.py` (e.g. "fda approved",
"clinically proven", "detox", "hypoallergenic", "klinisch getestet", "stärkt das Immunsystem", "CE-certified" → E4 10a) still
apply and are not repeated here. Word lists, patterns and product types: `docs/03_kategorie-regeln_vorschlag.json` (proposal,
not yet wired into `ld_rules.py`). Category detection: `product_type` of the category listing report first, fallback words for pasted text.

> **Finding:** Amazon published **no category-specific title formula, style guide or Item Highlights guide since 2026-07** and
> **no official new banned-word list in 2026**. The only 2026 Amazon texts are the generic 75/125 announcement + FAQ (CA1–CA2).
> New category restrictions in 2026 come from Amazon's US supplement policy (CF9) and from law (EmpCo, CE6 laptops, CT5).

### 10.1 Beauty / cosmetics / personal care (CB)

| ID | Rule | Limit / list | Applies to | Source (date) | Conf. |
|---|---|---|---|---|---|
| CB1 | EU common criteria for cosmetic claims: no claim that the product is approved/authorised by an authority; no "benefit" that is mere legal compliance (e.g. "free from" a substance banned anyway); an ingredient's property must not be attributed to the product unless true; no denigration of competitors or legally used ingredients | error: "behördlich zugelassen/geprüft", "EU-zugelassen", "dermatologisch zugelassen", "frei von Kortison/Hydrochinon/Quecksilber" | EU cosmetics | Reg. (EU) 655/2013 Annex https://eur-lex.europa.eu/eli/reg/2013/655/oj (Art. 20 Reg. 1223/2009); EUR-Lex not machine-readable on 2026-10-22, content per CTPA/biorius summaries | likely |
| CB2 | "Free from" claims (Technical Document on cosmetic claims, Annex III, applied since 2019-07-01; guidance, not binding): not for ingredients the law bans, not where they denigrate legally used ingredients (classic: "paraben-free"); OK if true and helpful to a target group ("ohne tierische Inhaltsstoffe" for vegans) | warn: "parabenfrei", "frei von Parabenen", "ohne Konservierungsstoffe" (if substances with preservative function are present) | EU | CTPA https://www.ctpa.org.uk/blog/cosmetic-claims-focus-on-free-from-claims-4115 ; HBW 2019-07-16 https://hbw.pharmaintelligence.informa.com/articles/2019/07/16/european-guidelines-now-in-effect-for-free-from-hypoallergenic-cosmetic-claims | likely |
| CB3 | "Hypoallergenic" (Annex IV): only if designed to minimise allergenic potential and evidence shows a very low potential. "Allergiefrei / allergy-free / non-allergenic" promise zero risk | error (DE): allergiefrei, frei von Allergenen; warn (US): allergy-free, non-allergenic | EU (US: no FDA definition → substantiation) | as CB2 | likely |
| CB4 | Test / expert claims need study data at hand (655/2013 "evidential support"); Amazon may request documents | warn: dermatologist tested/approved/recommended, clinically tested, ophthalmologist tested; dermatologisch getestet/bestätigt, von Dermatologen empfohlen, augenärztlich getestet | all | 655/2013; canopymanagement 01/2026 (H&B suppressions mostly copy-driven) https://canopymanagement.com/amazon-health-beauty-listing-compliance-copywriting-guide/ | likely |
| CB5 | Drug claims turn a cosmetic into a drug; intended use is judged from labelling **and internet claims**. US OTC-drug groups: acne, dandruff, seborrheic dermatitis/psoriasis, sunscreen; also drug claims: restore hair growth, reduce cellulite, increase/decrease melanin, regenerate cells. EU: therapeutic claims = medicinal product (Dir. 2001/83/EC; DE: HWG). Amazon bans cure/prevention claims on cosmetics unless labelled as drug. Appearance claims ("anti-aging", "reduces the appearance of wrinkles") are not flagged | error: treats eczema/psoriasis/rosacea, regrows hair, stops hair loss, removes cellulite, regenerates cells; gegen Neurodermitis/Schuppenflechte, lässt Haare nachwachsen, stoppt Haarausfall | US + EU | FDA "Is It a Cosmetic, a Drug, or Both?" https://www.fda.gov/cosmetics/laws-regulations/it-cosmetic-drug-or-both-or-it-soap (hair/cellulite/melanin examples only in the older page version); Amazon cosmetics policy help G200164470 (third-party quotes) | verified (FDA) / likely (Amazon, lists) |
| CB6 | Sunscreen terms (only when text mentions SPF/LSF/sunscreen – "waterproof mascara" is fine). **US** 21 CFR 201.327: "sunblock", "sweatproof", "waterproof" = misbranding; water resistance only "Water Resistant (40 minutes)" / "(80 minutes)"; skin-cancer claim only for Broad Spectrum SPF ≥ 15. **EU** Rec. 2006/647/EC: no "sunblock/Sunblocker", "total protection/Vollschutz", "100 % protection", no "no need to reapply / all-day protection"; labelled SPF only 6–50 and "50+" (no "SPF 100"); UVA protection ≥ 1/3 of SPF (UVA logo) | error list + pattern SPF > 50 (EU) | sunscreen + any product with SPF | https://www.law.cornell.edu/cfr/text/21/201.327 ; Rec. 2006/647/EC (OJ L 265, 26.9.2006, p. 39); LGL Bayern https://www.lgl.bayern.de/produkte/kosmetika/kosmetische_mittel/et_sonnenschutz_anforderungen.htm | verified (US) / likely (EU, recommendation enforced via 655/2013 + UWG) |
| CB7 | Ingredient list online (DE): the INCI list is "essential information" of an online offer (misleading by omission); a general link to the manufacturer site is not enough, a deep link may be. Reg. 1223/2009 itself has no explicit online rule | required: INCI in description or ingredients attribute | amazon.de cosmetics | OLG Karlsruhe 2018-09-26, 6 U 84/17 (it-recht-kanzlei 2018-11-08) https://www.it-recht-kanzlei.de/olg-karlsruhe-inhaltsstoffe-kosmetika-online-kennzeichnen.html ; Händlerbund https://www.haendlerbund.de/de/wissen/kosmetikverordnung | likely |
| CB8 | "Organic" (US): products "sold, labeled or represented as organic" need USDA organic certification (or USDA-recognised equivalent), certifier named, brand on the certificate; deleting the word does not always lift the block | warn: organic, certified organic, USDA organic | amazon.com (beauty + grocery) | Amazon policy text quoted in Seller Forums, e.g. https://sellercentral.amazon.com/seller-forums/discussions/t/f9a248bc-db14-4640-94f3-03897362e524 , https://sellercentral.amazon.com/seller-forums/discussions/t/99e15726-9635-4f79-b527-3d4ec8be051d | likely |
| CB9 | "Naturkosmetik", "Bio-Kosmetik": no legal definition in the EU; must be true and specific; name the standard (COSMOS, NATRUE, BDIH). Self-made seals → E4 (2a) | warn | EU | 655/2013; OLG Karlsruhe (CB7, "Naturkosmetik" case) | likely |
| CB10 | Skin lightening: Amazon policy (help GC37KSM44NPNZED6) requires documented third-party tests per ASIN (heavy metals incl. mercury, adulterant panel incl. hydroquinone + corticosteroids) in "Manage your compliance"; undocumented ASINs removed. US: OTC hydroquinone lighteners unapproved drugs since 2020; EU: hydroquinone banned in cosmetics | error: hydroquinone (not "…-free"); warn: skin lightening/whitening/bleaching, Hautaufhellung, Bleichcreme | US (+ EU) | Amazon staff reply https://sellercentral.amazon.com/seller-forums/discussions/t/44176991-0598-4040-bbe9-2d728da92606 ; NSF https://www.nsf.org/knowledge-library/skin-lightener-product-risks-what-you-need-to-know | likely |
| CB11 | Amazon US cosmetics bans: products under FDA recall/safety alert, with prohibited ingredients, > 12 % hydrogen peroxide, acetone products > 16 oz; **CBD/cannabinoid products incl. topicals** | error (US): CBD, cannabidiol, full spectrum hemp | amazon.com | help G200164470 (search excerpt 2026); CBD policy quoted by press https://www.postbulletin.com/business/amazon-prohibits-cbd-sales-but-its-still-easy-to-buy-on-the-site | likely (EU stance on CBD cosmetics: unclear) |

### 10.2 Electronics (CE)

| ID | Rule | Limit / list | Applies to | Source (date) | Conf. |
|---|---|---|---|---|---|
| CE1 | Other brands only referentially. Amazon format: **[own brand] [product] for / compatible with / fits / intended for [other brand + model]**; other brand never in `brand`, no logos, must be true; no "original/genuine/OEM" for third-party parts. Law allows use to show the intended purpose (accessory, spare part) if in line with honest practices | check: third-party brand in title/highlights must follow a connector (für, kompatibel mit, passend für, geeignet für, Ersatz für / for, compatible with, fits, intended for, replacement for) | all, esp. phone/console accessories, cartridges | Amazon help G201361070 "Title format for branded compatible products" (quoted in Seller Forums) https://sellercentral-europe.amazon.com/seller-forums/discussions/t/22f11a1e-acc9-4c57-ac25-cc73870517d1 ; Amazon device accessories https://sellercentral-europe.amazon.com/gp/help/external/200500100 ; § 23 Abs. 1 Nr. 3, Abs. 2 MarkenG https://www.gesetze-im-internet.de/markeng/__23.html (EU: Art. 14(1)(c) Reg. 2017/1001) | likely (Amazon) / verified (law) |
| CE2 | Licence badges as text ("Made for iPhone", "MFi certified", "Works with Alexa", "Qi certified", "USB-IF certified") only with the licence; "1:1 replica / Nachbau / Kopie" = counterfeit risk | warn (replica/Kopie: error) | all | no Amazon text found; program trademarks | unclear |
| CE3 | WEEE: producer must state its **registration number when offering** and on invoices (§ 6(3) ElektroG); marketplaces must not enable offers of unregistered producers (§ 6(2)); Amazon.de suspends non-compliant EEE listings since 2023-01-01 (number goes into Amazon's EPR compliance section) | required: WEEE-Reg.-Nr. "DE" + 8 digits | amazon.de, all EEE | https://www.gesetze-im-internet.de/elektrog_2015/__6.html ; News_Amazon https://sellercentral-europe.amazon.com/seller-forums/discussions/t/201e408219f3987b10b1c69c039aab85 | verified |
| CE4 | Batteries: BattDG replaced BattG in 2025 (Battery Reg. (EU) 2023/1542). Only batteries of registered producers may be offered (§ 4 BattDG); distance sellers must show the take-back notice incl. crossed-out wheelie bin clearly visible (§ 24(3)). Label (Art. 13): bin symbol since 2025-08-18; capacity on label not before 2026-08-18 (depends on implementing act); QR code from 2027-02-18 | required info | DE/EU, batteries + devices with batteries | xictron 2026-08-01 https://www.xictron.com/de/blog/eu-batterieverordnung-battdg-online-shop-2026/ ; BattDG https://www.buzer.de/31_BattDG.htm (entry-into-force date differs between sources) | likely |
| CE5 | Energy label: for labelled groups (TVs/displays, light sources, fridges, washers, dryers, dishwashers …; **smartphones/tablets since 2025-06-20**) the online offer must show label (class) and product information sheet at the offer. Amazon attributes: EPREL registration number, EU energy efficiency class, label image (image locator GLEE/EEGL, ≥ 500 px), data sheet (DEPF) | required info | EU | Reg. (EU) 2017/1369 + delegated regs (Annex VIII) https://europa.eu/youreurope/business/product-requirements/labels-markings/energy-labels/indexamp_de.htm ; it-recht-kanzlei; channelpilot 2026-03-17 https://help.channelpilot.com/en/articles/14088666-adding-eek-energy-efficacy-labels-to-your-listing | likely |
| CE6 | Common charger (RED 2014/53/EU as amended by Dir. (EU) 2022/2380): pictogram "charger included / not included" + label with power range (W) and USB PD; in distance selling **close to the price**. Phones, tablets, cameras, headphones/headsets/earbuds, handheld consoles, portable speakers, e-readers, keyboards, mice, portable navigation since 2024-12-28; **laptops since 2026-04-28** | required info | EU | ComReg https://www.comreg.ie/industry/product-safety/common-charger-directive-ccd/ ; directive text https://lawplayer.com/eu/act/32022L2380 | verified |
| CE7 | FDA claims on electronics: FDA does not approve consumer electronics; registration "does not in any way denote approval", implying it is misbranding (devices) | error: FDA certified / registered / listed (C2 covers "approved/cleared") | US | 21 CFR 807.39 https://www.law.cornell.edu/cfr/text/21/807.39 | verified |
| CE8 | "Military grade", "MIL-STD-810G/H": self-declared, partial tests allowed → name method, drop height, number of drops, or drop the claim | warn | cases, phones, outdoor | BGR https://www.bgr.com/2176763/military-grade-phone-cases-doesnt-mean-what-you-think/ ; no Amazon rule found | unclear |
| CE9 | Capacity/power claims: power banks give rated capacity in **mAh and Wh**; no "PMPO/peak" watts without RMS; > 100 Wh = dangerous-goods review. No Amazon plausibility rule found | info | power banks, speakers | vendor blogs only (contradictory) | unclear |
| CE10 | Test marks ("TÜV geprüft", "GS geprüft", "LGA tested") in DE: the offer must say where the test criteria can be found (essential information, § 5a UWG) | warn: mark without source / URL / certificate no. | DE, all (often electronics, toys) | BGH 2016-07-21, I ZR 26/15 "LGA tested" https://betriebs-berater.ruw.de/wirtschaftsrecht/nachrichten/Werbung-mit-Pruefzeichen--Vorenthalten-von-Informationen--LGA-tested-30492 | verified (BGH) |

### 10.3 Toys (CT)

| ID | Rule | Limit / list | Applies to | Source (date) | Conf. |
|---|---|---|---|---|---|
| CT1 | Warnings that decide the purchase (min./max. age, other Annex V warnings) must be on the packaging **or clearly visible before purchase, also when bought online** | required: age + warnings in the offer | DE/EU toys | § 11(4) 2. ProdSV https://www.gesetze-im-internet.de/gpsgv_2/__11.html (= Art. 11(2) Dir. 2009/48/EC) | verified |
| CT2 | Warnings start with "Achtung" (EN "Warning"), in German on amazon.de | – | DE | § 11(3), (5) 2. ProdSV | verified |
| CT3 | Fixed wordings (Annex V Part B): "Nicht für Kinder unter 36 Monaten geeignet." / "…unter drei Jahren…" (or pictogram) · "Nur für den Hausgebrauch." · "Benutzung unter unmittelbarer Aufsicht von Erwachsenen." · chemical toys "Nicht geeignet für Kinder unter … Jahren. Benutzung unter Aufsicht von Erwachsenen." · "Mit Schutzausrüstung zu benutzen. Nicht im Straßenverkehr zu verwenden." · "Nur im flachen Wasser unter Aufsicht von Erwachsenen verwenden." · "Enthält Spielzeug. Beaufsichtigung durch Erwachsene empfohlen." · "Dieses Spielzeug bietet keinen Schutz." · cradle toys "Um mögliche Verletzungen durch Verheddern zu verhindern …" · "Enthält Duftstoffe, die Allergien auslösen können" | – | DE/EU | Dir. 2009/48/EC Annex V (DE text) https://gesetze.legal/eu/rl_2009_48_eg/anhang_v | verified |
| CT4 | Under-3 warning needs the specific hazard ("Erstickungsgefahr durch verschluckbare Kleinteile") and **must not be used on toys intended for children under 36 months** → "ab 6 Monaten" + "nicht für Kinder unter 3 Jahren" = contradiction | error (pattern) / warn (hazard missing) | EU | Annex V B.1 (above); Commission guidance (TIE copy) | verified (rule) / likely (guidance) |
| CT5 | New Toy Safety Regulation (EU) 2025/2509: OJ 2025-12-12, in force 2026-01-01, **applies 2030-08-01** (Dir. 2009/48 until 2030-07-31; compliant toys placed earlier may stay). Online: CE marking, warnings and the digital-product-passport data carrier visible before purchase (Art. 6(3), 19(7), 14(3)); PFAS ban; generic warning symbol (≥ 10 mm) may replace "Warning" | info until 2030 | EU | Noerr 2026-02-04 https://www.noerr.com/en/insights/new-european-toy-safety-regulation-2025-2509-comes-into-force-key-points-at-a-glance ; Bureau Veritas https://www.cps.bureauveritas.com/newsroom/eu-toy-safety-regulation-20252509-published ; text https://lawplayer.com/eu/act/32025R2509 | verified (text) / likely (dates) |
| CT6 | US: choking-hazard cautionary statements required **in internet ads** since 2008-12-12 – small parts (ages 3–<6), latex balloons, small balls + marbles (3–<8). On Amazon via `cpsia_cautionary_statement1–4`, shown in a yellow "Warning" box above the description; missing/wrong → deactivation | required | amazon.com toys ≤ 12 y | 16 CFR 1500.20 https://www.law.cornell.edu/cfr/text/16/1500.20 ; Amazon help G200292910 (search excerpt); Seller Forums | verified (law) / likely (Amazon) |
| CT7 | US wording (16 CFR 1500.19), e.g. "WARNING: CHOKING HAZARD—Small parts. Not for children under 3 yrs." | – | US | 16 CFR 1500.19 (not re-read) | likely |
| CT8 | Certification wording: CPSC certifies nothing – manufacturer/importer issues the Children's Product Certificate (CPC) from CPSC-accepted lab tests; CPSC de-accredited 4 labs (01/2026) and started a crackdown on counterfeit safety/certification marks (05/2026). Same logic for "EN 71 zertifiziert" (EN 71 = test standard) | warn: CPSC certified/approved, EN71 certified, kindersicher, child-safe | US/EU | CPSC statement 01/2026 https://www.cpsc.gov/About-CPSC/Chairman/Peter-A-Feldman/Statement/CPSC-Immediately-Withdraws-Accreditation-from-Chinese-Laboratories-to-Protect-American-Families ; freyr 05/2026 | likely |

### 10.4 Food and supplements (CF)

| ID | Rule | Limit / list | Applies to | Source (date) | Conf. |
|---|---|---|---|---|---|
| CF1 | Health claims only if authorised (EU Register) and in their authorised meaning (Art. 10(1), 13, 14). Immune: authorised e.g. "trägt zu einer normalen Funktion des Immunsystems bei" (vit. C, D, zinc …); "stärkt/boostet das Immunsystem", "Immunbooster" are not that wording | warn | EU food | Reg. (EC) 1924/2006 https://eur-lex.europa.eu/eli/reg/2006/1924/oj ; EU Register https://ec.europa.eu/food/food-feed-portal/screen/health-claims/eu-register | likely |
| CF2 | Non-specific health claims ("gut für die Gesundheit", "Wohlbefinden", "vitalisierend", "entschlackend") only with an accompanying authorised specific claim shown together (Art. 10(3); CJEU 2020-01-30 C-524/18 Schwabe); "Detox" on herbal tea unlawful (BGH 2017-12-06, I ZR 167/16) | warn | EU | BGH https://rewis.io/urteile/urteil/mvk-05-12-2017-i-zr-16716/ ; CJEU https://www.haufe.de/id/entscheidung/eugh-urteil-vom-30012020-c-52418-HI13881252.html | verified (case law) |
| CF3 | Banned claim types (Art. 12): health suffers if not eaten; **rate or amount of weight loss**; recommendations of individual doctors/health professionals. Disease prevention/treatment claims for food banned anyway (LMIV Art. 7(3)) | error: "5 kg in 2 Wochen" (pattern), von Ärzten empfohlen, gegen Erkältung | EU (US: doctor claims need substantiation) | Reg. 1924/2006 Art. 12; Reg. 1169/2011 Art. 7(3) | likely |
| CF4 | Nutrition claims only under Annex conditions: "zuckerfrei" ≤ 0.5 g/100 g, "fettarm" ≤ 3 g/100 g (1.5 g/100 ml), "Proteinquelle" ≥ 12 % / "hoher Proteingehalt" ≥ 20 % of energy, "reich an Ballaststoffen" ≥ 6 g/100 g, "leicht/light" −30 % | warn (check values) | EU | Reg. 1924/2006 Annex | likely |
| CF5 | Distance selling: all mandatory particulars (Art. 9 LMIV) **except best-before date** available on the offer page before purchase (name, ingredients with highlighted allergens, net quantity, nutrition declaration, operator name + address …); text only readable by zooming a photo is risky | required info | EU food | Reg. (EU) 1169/2011 Art. 14(1)(a); it-recht-kanzlei https://www.it-recht-kanzlei.de/achtung-abmahnung-pflichtinformationen-lebensmittel-gut-sichtbar.html ; Händlerbund | likely |
| CF6 | Supplements DE: name "Nahrungsergänzungsmittel"; characterising nutrient categories; recommended daily dose; "Die angegebene empfohlene tägliche Verzehrsmenge darf nicht überschritten werden."; not a substitute for a balanced and varied diet; store out of reach of small children | required phrases | amazon.de supplements | § 4 NemV https://www.gesetze-im-internet.de/nemv/__4.html | verified |
| CF7 | Organic food: "Bio/Öko/organic" reserved for certified products (Reg. (EU) 2018/848); **online sellers need their own organic certification** (CJEU 2017-10-12, C-289/16 Kamin und Grill Shop); offers show the control-body code (e.g. "DE-ÖKO-0xx") | warn: Bio/Öko token without code | EU food | otto-schmidt 2017-10-13 https://www.otto-schmidt.de/news/wirtschaftsrecht/online-verkauf-von-bio-produkten-nur-mit-zertifizierung-2017-10-13.html ; it-recht-kanzlei https://www.it-recht-kanzlei.de/eugh-bio-lebensmittel-zertifizierungspflicht.html | likely |
| CF8 | US supplements: structure/function claims need "This statement has not been evaluated by the Food and Drug Administration. This product is not intended to diagnose, treat, cure, or prevent any disease." (plural "These statements…"), adjacent or linked by asterisk; disease claims incl. signs/symptoms of a disease not allowed; FDA notice within 30 days | required if S/F claim | amazon.com supplements | 21 CFR 101.93 https://www.law.cornell.edu/cfr/text/21/101.93 | verified |
| CF9 | Amazon US supplements 2026: from **2026-03-31** the detail page must match the label (ingredient names/amounts as in Supplement Facts, no inflated "equivalent" doses); cGMP via Amazon-approved TIC for **all** supplements (90 days after contact); images show the full label; prohibited: "FDA approved", disease names (also backend), comparisons with Rx drugs, drug-like names ("GLP-1"), peptides (BPC-157), steroid claims, "tester / not for retail sale" | error list | amazon.com supplements | ecomcrew (upd. 2026-01-21) https://www.ecomcrew.com/amazons-new-supplement-rules-could-take-down-thousands-of-listings/ ; NutraIngredients 2025-12-22 https://www.nutraingredients.com/Article/2025/12/22/amazon-expands-tic-cgmp-requirement-to-all-supplement-products ; foodlabelmaker 2026-06-10 https://foodlabelmaker.com/regulatory-hub/fda/dietary-supplements/amazon-supplement-update-2026/ | likely |
| CF10 | CBD: Amazon US prohibits CBD/cannabinoid and full-spectrum hemp-oil products (hemp seed oil without CBD OK); EU: CBD foods are unauthorised novel foods | error | US + EU food | press quoting Amazon policy (postbulletin, see CB11); EU Novel Food Catalogue | likely |

### 10.5 Apparel / Amazon style 2026 (CA)

| ID | Rule | Limit / list | Applies to | Source (date) | Conf. |
|---|---|---|---|---|---|
| CA1 | No category-specific title formula or Item Highlights guide since 2026-07. Amazon FAQ: keep the **brand in Item name**; put the **most important variating attributes** in Item name, move the rest to Item Highlights; 75 + 125 = the former 200 chars | – | all incl. apparel/shoes | News_Amazon "Answers to your product title update questions" https://sellercentral.amazon.com/seller-forums/discussions/t/302aaac6-6f2b-4d86-bcd2-36fe24f0e6cd (2026) | verified |
| CA2 | Item Highlights shown beneath Item name on desktop + mobile since **2026-08-10**; Item name and Highlights are equal search inputs; bulk edit via Category Listings report (live in ~8 h) | – | all | same | verified |
| CA3 | Apparel Item Highlights: fibre composition (Annex-I names, X2), care, fit, gender – e.g. "95 % Baumwolle, 5 % Elasthan · Maschinenwäsche · Relaxed Fit" | – | apparel | sellersprite 2026-08-01 https://www.sellersprite.com/en/blog/amazon-item-highlights-2026 | likely |
| CA4 | Claimed category-specific title caps ("beauty and grocery tighter") contradict Amazon's 75-for-all-non-media post → ignore until Amazon confirms | – | – | novadata 2026-06-10 https://novadata.io/resources/news/amazon-product-title-rules-overhaul-july-27-2026 | unclear |
| CA5 | Agency "2026 restricted keyword lists" recycle C1–C4 terms; no Amazon list exists | – | – | bebolddigital, salesduo (2026) | unclear |

### 10.6 Severity mapping (addition to section 9)

- **error**: CB1, CB3 (allergiefrei), CB5, CB6 (in SPF context), CB10 (hydroquinone), CB11 (CBD, US), CE1 (third-party brand without connector; "original" + foreign brand), CE2 (replica), CE7, CT4 (contradiction), CF3, CF9 list, CF10.
- **warning**: CB2, CB4, CB8, CB9, CB10 (lightening words), CE2, CE8, CE10, CT1/CT2 (age or "Achtung" missing), CT4 (hazard missing), CT8, CF1, CF2, CF4, CF6 (phrase missing), CF7, CF8 (S/F claim without disclaimer).
- **info / required-info hint**: CB7, CE3–CE6, CE9, CT5, CT6, CF5, CA1–CA3; CA4–CA5 not checked.
