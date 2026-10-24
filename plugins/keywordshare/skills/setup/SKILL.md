---
name: setup
description: Sets KeywordShare's brand words (own brand queries are marked), the target impression share and the minimum market purchases per query by writing keywordshare.json in the working folder. Use before the first analysis or when the user says "set up KeywordShare", "my brand is …", "target share", "KeywordShare einrichten" or "Ziel-Anteil festlegen".
argument-hint: "[brand words] [target share %]"
allowed-tools: 'Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/keywordshare.py" *), Bash(python "${CLAUDE_PLUGIN_ROOT}/scripts/keywordshare.py" *), Bash(py -3 "${CLAUDE_PLUGIN_ROOT}/scripts/keywordshare.py" *), Read'
---

# KeywordShare setup

Ask for these in **one** message (skip what `$ARGUMENTS` or the conversation already answers):

1. **Brand words** — the brand name(s) as shoppers type them (e.g. `acme, acme pro`). Queries
   containing them are marked as own-brand queries and left out of the target calculation.
2. **Target impression share** (optional) — leave empty to use the seller's own upper quartile
   (recommended). A number such as `15` means 15 % of the market's impressions per query.
3. **Minimum market purchases** per query (optional, default 5) — raise it for very large
   accounts, lower it (2–3) for small niches.

Write or update the file (existing brand words are kept):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/keywordshare.py" init --brand-terms "<word1>, <word2>" [--target-share <n>] [--min-purchases <n>]
```

Run it as one plain command (no `cd`/`&&`; add `--config <folder>/keywordshare.json` to write into
the reports folder). On Windows use `python` or `py -3` instead of `python3`. Show the saved settings
and offer to run the analysis next.
