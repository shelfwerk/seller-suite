#!/usr/bin/env python3
"""Pre-push check: finds things that must not be in the public repo.

  python3 tools/privat_check.py            exit code 1 if anything is found

Always checks: local paths, private e-mail addresses, ASINs not on the allow list (tools/erlaubte-asins.txt),
API keys/tokens, report files. Additionally reads .privat-muster.txt (one regex per line, git-ignored) for
names that are private but cannot be listed publicly.
"""
import os
import re
import sys

WURZEL = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SKIP_DIRS = {".git", "__pycache__", "node_modules"}
SKIP_FILES = {".privat-muster.txt", "privat_check.py"}
ALLGEMEIN = [
    (r"/Users/[A-Za-z]", "lokaler Pfad"),
    (r"[A-Za-z]:\\\\Users\\\\", "lokaler Pfad (Windows)"),
    (r"Mobile Documents|com~apple~CloudDocs|AI_Builds", "iCloud-/Ablagepfad"),
    (r"sk-ant-[A-Za-z0-9_-]{10,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}", "Schlüssel/Token"),
    (r"[A-Za-z0-9._%+-]+@(gmail|gmx|outlook|hotmail|icloud|yahoo|web)\.[a-z]{2,}", "private E-Mail-Adresse"),
]
ASIN = re.compile(r"\bB0[0-9A-Z]{8}\b")
BERICHT_ENDUNGEN = (".csv", ".xlsx", ".xlsm", ".tsv")


def _liste(pfad):
    if not os.path.isfile(pfad):
        return []
    with open(pfad, encoding="utf-8") as f:
        return [z.strip() for z in f if z.strip() and not z.startswith("#")]


def main():
    muster = [(re.compile(m), grund) for m, grund in ALLGEMEIN]
    muster += [(re.compile(m, re.I), "privates Muster") for m in _liste(os.path.join(WURZEL, ".privat-muster.txt"))]
    erlaubt = set(_liste(os.path.join(WURZEL, "tools", "erlaubte-asins.txt")))
    funde = []
    for dp, dn, fn in os.walk(WURZEL):
        dn[:] = [d for d in dn if d not in SKIP_DIRS]
        for f in fn:
            if f in SKIP_FILES:
                continue
            pfad = os.path.join(dp, f)
            rel = os.path.relpath(pfad, WURZEL)
            if f.lower().endswith(BERICHT_ENDUNGEN) and not rel.startswith("plugins" + os.sep):
                funde.append((rel, 0, "Berichtsdatei außerhalb von plugins/"))
            try:
                with open(pfad, encoding="utf-8") as h:
                    zeilen = h.read().splitlines()
            except (UnicodeDecodeError, OSError):
                continue
            for nr, z in enumerate(zeilen, 1):
                for rx, grund in muster:
                    if rx.search(z):
                        funde.append((rel, nr, grund))
                for a in ASIN.findall(z):
                    if a not in erlaubt and not re.fullmatch(r"B0(X+|Y+)", a):
                        funde.append((rel, nr, "ASIN %s nicht auf der Erlaubt-Liste" % a))
    for rel, nr, grund in funde:
        print("✘ %s:%s  %s" % (rel, nr, grund))
    print("%d Fund(e)" % len(funde) if funde else "✔ nichts Privates gefunden")
    return 1 if funde else 0


if __name__ == "__main__":
    sys.exit(main())
