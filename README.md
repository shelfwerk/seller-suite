
# Shelfwerk Seller Suite: free Claude plugins for Amazon sellers

[Deutsch](README.de.md) · [Website](https://shelfwerk.com) · MIT License

Four free plugins for Claude. Download a report from Seller Central, drop it into Claude, ask a question. A small local Python
script does the maths, and Claude explains the result. There are no API keys and no account access, and nothing changes in your account.

| Plugin | Report you need | What you get |
|---|---|---|
| **TermSweep** | Sponsored Products search term report | Search terms that cost money without orders, converting terms that are too expensive, winners to add as exact keywords |
| **KeywordShare** | Brand Analytics → Search Query Performance | Your share of impressions, clicks, cart adds and purchases per query; where the funnel leaks; queries to defend; a keyword list |
| **ListingDoctor** | Category listing report, flat file or ASINs | Rule check (75-character titles, Item Highlights, 249-byte backend, EU textile names, eco claims): score + top 5 fixes |
| **MargenCheck** | Supplier offer (price, size, weight) | Landed cost, Amazon EU fees 2026, margin, break-even ACOS, max purchase price (answers in German) |

Works with English and German reports; other console languages are detected. Answers in English or German.

## Install

**Claude Code**

```
/plugin marketplace add shelfwerk/seller-suite
/plugin install termsweep@shelfwerk
```

Install `keywordshare`, `listingdoctor` and `margencheck` the same way. To try a plugin for one session without installing it:
`claude --plugin-dir ./plugins/termsweep`.

**Claude desktop app / Cowork:** download a plugin ZIP from [Releases](https://github.com/shelfwerk/seller-suite/releases) → **Customize → Plugins → Add → Upload plugin**.

Requires a paid Claude plan. Python 3 is needed for the bundled scripts: it's normally already there in Cowork and on macOS; on Windows
with Claude Code, install it once from python.org.

## First steps

- "Where am I wasting ad spend? Target ACOS 30 %." (search term report) → `/termsweep:audit`
- "Where do I lose purchases?" (Search Query Performance) → `/keywordshare:audit`
- "Check my listings" (category listing report) or "Check B0…, B0…" → `/listingdoctor:check`
- "Is this worth it? 2000 pcs at 3.20 USD FOB, price 24.99 €" → `/margencheck:rechner`

## Pro

The Pro editions add upload files (Amazon bulk sheets, listing partial updates), money-burning word analysis, ASIN matrix and trends,
rule-checked rewrites, and supplier-offer comparisons. Details and pricing: **https://shelfwerk.com**.

## Privacy

- The scripts read local files and make **no network calls**, with one exception: ListingDoctor fetches the public Amazon product page if you
  give it ASINs. There is no telemetry and no account login.
- What you show Claude is processed by Claude like any other file in your chat, under your Claude plan's terms.
- More in [PRIVACY.md](PRIVACY.md).

## Checks

Every plugin passes `claude plugin validate --strict`. See `tools/pruefen.sh` and `.github/workflows/pruefen.yml`.

## Support

support@shelfwerk.com. Not affiliated with Amazon or Anthropic. "Amazon" and "Seller Central" are trademarks of Amazon.com, Inc. or its affiliates.
