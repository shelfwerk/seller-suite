# TermSweep — Amazon PPC search term audit (free)

Stop paying for search terms that never sell. TermSweep reads the Sponsored Products **search
term report** you download from Amazon and tells you, in a minute:

- which search terms burned money without a single order → **negative keywords**,
- which converting terms are too expensive → **isolate them at a lower bid**,
- which search terms sell profitably → **add them as exact keywords**,
- how much that is per month.

It writes a review workbook (`.xlsx`) and a negatives list (`.csv`) you can work through in
Campaign Manager. Nothing is changed in your account — TermSweep only reads files.

## Use

| Command | What it does |
|---|---|
| `/termsweep:audit [report] [target ACOS]` | Runs the audit on a search term report |
| `/termsweep:setup` | Saves your target ACOS, protected terms (brand, product names) and currency |

Or just ask: *"Here is my search term report — where am I wasting ad spend?"* /
*„Hier ist mein Suchbegriffbericht — wo verbrenne ich Werbegeld?"*

Answers in English or German. Accepts report downloads from any Amazon marketplace and console
language (English and German verified with the 2025 and 2026 column names; FR/IT/ES/NL/SE/PL
headers recognised), as `.xlsx`, `.csv` or `.txt`, summary or daily.

## Install

- **Claude Code** (2.1.275 or later):
  ```
  /plugin install termsweep --marketplace shelfwerk/seller-suite
  ```
  To try without installing: `claude --plugin-dir ./termsweep`.
- **Claude Desktop / Cowork:** Customize → Plugins → upload `termsweep-<version>.zip`.

Requires Python 3 (built into Cowork and macOS; on Windows install it from python.org).
No extra Python packages, no API keys, no Amazon developer account.

## Privacy

The analysis runs locally in `scripts/termsweep.py` and makes **no network calls**. Your report
stays on your machine; Claude sees the summary the script prints, as part of your conversation.

## How it decides

Thresholds come from your own account: a term is a bleeder when a term converting like your
account average would have sold by then with 90 % probability (2.3 ÷ conversion rate clicks), or
after spending what two orders may cost at your target ACOS. Terms that sell in another ad group
are listed separately instead of being negated. Details: `skills/audit/references/method.md`.

## TermSweep Pro

Pro turns the audit into a **ready-to-upload Amazon bulk file** (negatives, harvested keywords,
bid changes — with the correct campaign and ad group IDs), finds **words that burn money across
many search terms**, and shows the **trend week by week**.

## License

MIT — see `LICENSE`. Suggestions only; you are responsible for changes you make to your campaigns.
