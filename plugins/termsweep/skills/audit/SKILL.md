---
name: audit
description: Audits an Amazon Sponsored Products search term report and shows where ad spend leaks — search terms with clicks but no orders (negative keyword candidates), converting terms that are too expensive, and winners to add as exact keywords. Use when the user mentions a search term report, negative keywords, wasted PPC spend, ACOS too high, an Amazon PPC audit, "Suchbegriffbericht", "negative Keywords", "Werbekosten ohne Verkäufe", or shares an Amazon Ads report file.
argument-hint: "[report file] [target ACOS %]"
allowed-tools: Bash(python3:*), Bash(python:*), Bash(py:*), Read, Glob
---

# TermSweep audit

Find where Amazon Sponsored Products spend leaks, using the seller's own search term report.
All numbers come from `scripts/termsweep.py` — never do the arithmetic yourself, never estimate
or invent figures, and never claim that anything was changed in the ad account (TermSweep only
reads files).

## 1. Find the report

- `$ARGUMENTS` may contain a file path and/or a target ACOS (a number such as `25` or `25%`).
- No path given: look in the working folder (in Claude Code also `~/Downloads`) for recent
  `*.xlsx`, `*.csv` or `*.txt` files whose names contain `Search`, `Term`, `Suchbegriff` or
  `search_term`. Several candidates → list them newest first and ask which one.
- Nothing found → explain how to download the report (`references/download-report.md`, three short
  steps in the user's language) and stop.

## 2. Settings

- `termsweep.json` holds the target ACOS, protected terms (brand name, own product names, core
  keywords) and the display currency. The script finds it in the working folder or next to the report
  (or in `--out`), no `--config` needed.
- No target ACOS anywhere → the script uses 30 % and says so; mention the setup skill (`/termsweep:setup`) once.
- A target ACOS in `$ARGUMENTS` or in the user's message → pass it with `--target-acos`.
- Brand names or terms the user says must never be negated → pass them on the **first** run with
  `--protect "<term1>, <term2>"` (and offer to save them with setup). A brand word protects every
  search term containing it; `=<search term>` protects exactly that search term.
- A protect list file — e.g. `keywordshare-protect-<date>.txt` from KeywordShare (one entry per line,
  `=` = exact core query) → `--protect-file "<file>"`.
- If a bleeder obviously contains the seller's brand, point it out and suggest protecting it via
  `/termsweep:setup` — never recommend negating the own brand.

## 3. Run

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/termsweep.py" audit "<report>" --lang <en|de> --out "<folder>" [--target-acos <n>] [--protect "<terms>"] [--protect-file "<file>"]
```

- Run the script as **one plain command** — no `cd`, `&&`, `;`, pipes or `2>&1` around it — so it matches
  the `python3` permission and needs no extra approval. Find files with Glob and read `termsweep.json`
  with Read instead of shell commands. Always let the script open the file, even if it looks unusual:
  it recognises unsupported files (Google Ads, damaged Excel) and says why.
- `--lang de` when the user writes German, otherwise `en`.
- `--out` = the folder the report is in (in Cowork: the session's output folder), so the result
  files land next to the report.
- Exit code 2 = input problem; the reason is on stderr — show it plainly. If required columns were
  not recognised, run `… termsweep.py inspect "<report>"`, compare the header list and retry with
  `--map field="Header"` (fields: `term`, `campaign`, `ad_group`, `targeting`, `match_type`,
  `clicks`, `spend`, `sales`, `orders`).
- `python3` not found → try `python` (Windows) or `py -3` with the same arguments. Still nothing → tell
  the user TermSweep needs Python 3 (python.org, or Claude Cowork, which has it built in). Do not fall
  back to computing by hand.

## 4. Present the result

Never call the "spend on terms without a single order" total a leak: most of it sits in terms with a
few clicks each — the normal cost of testing search terms (the table shows that share). The
actionable money is in the bleeders, the too-expensive terms and (Pro) the money-burning words.

1. Two to four sentences first: the monthly leak from bleeders, the single biggest item, and what
   to do first.
2. Then the script's Markdown output **exactly as printed** — all tables, campaign and ad group
   names in full, same order, same numbers. Do not shorten, merge, re-sort or recompute anything.
3. Link the two files it wrote: the review workbook (`termsweep-review-<date>.xlsx`) and the
   negatives list (`termsweep-negatives-<date>.csv`).
4. New to PPC? Explain the actions in one line each: *negative exact* blocks exactly this search
   term in that ad group; *isolate* means adding the term as an exact keyword with a lower bid and
   negating it where it came from; *watch* means not enough clicks yet to judge.
5. Next steps: add the negatives in Campaign Manager (the CSV lists campaign, ad group and term).
   In one sentence, without pressure: TermSweep Pro turns the same audit into a ready-to-upload
   Amazon bulk file with the right IDs, finds words that burn money across many search terms and
   tracks the trend week by week.

Why was something flagged, or how are the thresholds set? → `references/method.md`.
