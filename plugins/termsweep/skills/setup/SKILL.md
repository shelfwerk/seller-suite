---
name: setup
description: Sets TermSweep's target ACOS, protected terms (brand, own product names, core keywords) and display currency by writing termsweep.json in the working folder. Use before the first audit or when the user says "set my target ACOS", "protect my brand keywords", "TermSweep einrichten" or "Ziel-ACOS festlegen".
argument-hint: "[target ACOS %] [protected terms]"
allowed-tools: 'Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/termsweep.py" *), Bash(python "${CLAUDE_PLUGIN_ROOT}/scripts/termsweep.py" *), Bash(py -3 "${CLAUDE_PLUGIN_ROOT}/scripts/termsweep.py" *), Read'
---

# TermSweep setup

Collect three settings in **one** message (skip what `$ARGUMENTS` or the conversation already
answers), then write them with the script.

1. **Target ACOS.** If the user does not know it, help derive it from one typical product:
   break-even ACOS = (price − product cost incl. shipping to Amazon − Amazon fees − VAT share if
   prices include VAT) ÷ price. Suggest a target of about 70–80 % of break-even; use the user's
   number if they have one. Show the arithmetic so it can be checked.
2. **Protected terms**: brand name(s), own product names, core words that must never be negated —
   comma-separated. Matching is by whole words, case-insensitive: a brand word protects every search
   term containing it; `=<search term>` protects exactly that search term (e.g. a core query whose
   longer variants may still be negated). A protect list file such as KeywordShare's
   `keywordshare-protect-<date>.txt` (one entry per line) is imported with `--protect-file "<file>"`.
3. **Currency** for display (EUR, USD, GBP …) — optional, the report usually contains it.

Write or update the file (existing protected terms are kept):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/termsweep.py" init --target-acos <n> --protect "<term1>, <term2>" [--protect-file "<file>"] --currency <CODE>
```

Run it as one plain command (no `cd`/`&&`; pass `--config <reports folder>/termsweep.json` to write it next
to the reports — the audit finds it there too). On Windows use `python` or `py -3` instead of `python3`.
Show the saved settings and offer to run the audit next.
