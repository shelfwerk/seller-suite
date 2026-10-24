---
name: audit
description: Analyses an Amazon Brand Analytics Search Query Performance report and shows the brand's share of search demand — impression, click, cart-add and purchase share per search query, where the funnel leaks (seen but not clicked, clicked but not bought), the biggest visibility gaps, strong queries to defend, queries that do not fit, and a keyword list for the listing. Use when the user mentions Search Query Performance, SQP, Brand Analytics, search query share, market share or impression share on Amazon, "Suchanfragen-Leistung", "Suchanfragenleistung", "Markenanalyse", "Marktanteil je Suchbegriff", or shares such a report file.
argument-hint: "[report file]"
allowed-tools: 'Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/keywordshare.py" *), Bash(python "${CLAUDE_PLUGIN_ROOT}/scripts/keywordshare.py" *), Bash(py -3 "${CLAUDE_PLUGIN_ROOT}/scripts/keywordshare.py" *), Read, Glob'
---

# KeywordShare audit

Show the seller's share of Amazon search demand from their own Search Query Performance report.
All numbers come from `scripts/keywordshare.py` — never do the arithmetic yourself, never estimate or
invent figures, and never claim that anything was changed on Amazon (KeywordShare only reads files).

## 1. Find the report

- `$ARGUMENTS` may contain a file path.
- No path: look in the working folder (in Claude Code also `~/Downloads`) for recent `*.csv`, `*.xlsx`
  or `*.json` files whose names contain `Search_Query`, `Search-Query`, `SQP`, `Suchanfrage` or
  `Brand_Analytics`. Several candidates → list them newest first and ask which one.
- Nothing found → explain the download (`references/download-report.md`, three short steps in the
  user's language) and stop.
- The free edition reads **one** report. Several weeks, the competition view (Top Search Terms) and the
  organic estimate from the ads report are KeywordShare Pro — say so in one line if asked.

## 2. Settings

- `keywordshare.json` in the working folder (brand words, target share, minimum purchases) is picked
  up automatically; offer `/keywordshare:setup` once if it is missing and the user named a brand.
- Brand words from the conversation → `--brand-terms "<word1>, <word2>"`.
- The brand sells several product lines and the user asks about one → `--focus "<word1>, <word2>"`
  (queries containing any of the words); unrelated lines → `--exclude`.
- A file with several marketplaces → the script picks the largest and says so; `--market <code>` for another.

## 3. Run

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/keywordshare.py" audit "<report>" --lang <en|de> --out "<folder>" [--brand-terms "<words>"] [--focus "<words>"]
```

- Run the script as **one plain command** — no `cd`, `&&`, `;`, pipes or `2>&1` around it — so it matches
  the `python3` permission. Find files with Glob and read `keywordshare.json` with Read, not with shell
  commands. Always let the script open the file, even if it looks unusual: it recognises Top Search
  Terms files, ad reports, damaged Excel files and says what to do.
- `--lang de` when the user writes German, otherwise `en`. `--out` = the folder the report is in
  (in Cowork: the session's output folder).
- Exit code 2 = input problem: show the stderr message plainly. Columns not recognised → run
  `… keywordshare.py inspect "<report>"` and show what was found.
- `python3` not found → try `python` (Windows) or `py -3` with the same arguments. Still nothing →
  KeywordShare needs Python 3 (python.org, or Claude Cowork). Do not compute by hand.

## 4. Present the result

1. Two to four sentences first: purchase share overall, where the funnel loses most (click index /
   conversion index), the single biggest opportunity and the main strong query.
2. The script's Markdown output **exactly as printed** — all tables, same order, same numbers.
   Do not shorten, re-sort or recompute anything.
3. Link the files: workbook (`keywordshare-<date>.xlsx`, sheets *Summary/Übersicht*,
   *Opportunities/Chancen*, *Funnel/Trichter*, *Strong/Stark*) and the keyword list for ListingDoctor.
4. Explain briefly when useful: **share** = your part of all impressions/clicks/purchases for that
   search; **click index** 0.5 = half as many clicks as an average offer with the same visibility;
   counts include ads (organic and sponsored together).
5. Next steps: listing work for click/conversion leaks (ListingDoctor with the keyword list if
   installed), PPC for visibility gaps (TermSweep for the paid side). Never promise a ranking.

Why was something flagged, how are "+ purchases" estimated? → `references/method.md`.
