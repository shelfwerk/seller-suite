#!/usr/bin/env python3
"""TermSweep — clean up Amazon Sponsored Products search terms.

Usage:
  python3 termsweep.py audit  REPORT [--target-acos 25] [--protect "brand,core term"] [--lang de]
                              [--config termsweep.json] [--out DIR] [--map field="Header"] [--top 15]
  python3 termsweep.py bulk   REPORT --bulk-export BULKFILE [same options]  [--harvest-to "Campaign/Ad group"]
                              (TermSweep Pro)
  python3 termsweep.py groups --bulk-export BULKFILE   list ad groups (Pro; pick a harvest destination)
  python3 termsweep.py inspect REPORT [--map …]     show how the columns were recognised
  python3 termsweep.py init   [--target-acos 25] [--protect "..."] [--protect-file FILE] [--currency EUR]   write termsweep.json

termsweep.json is taken from --config, else the working folder, else the report's folder or --out.
Protected entries: "brand" protects every search term containing it, "=core query" exactly that search term.

Reads local files only, makes no network calls, never changes anything on Amazon.
Exit codes: 0 ok, 2 input problem (message on stderr), 3 Pro feature not installed.
"""
import argparse
import datetime
import json
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ts_core import (ConfigError, analyze, load_config, negatives_csv_rows, norm_protected,  # noqa: E402
                     read_protect_file, render_audit, review_sheets)
from ts_report import ReportError, load_report  # noqa: E402
from ts_xlsx import write_xlsx  # noqa: E402

try:
    import ts_pro  # noqa: E402  (only shipped with TermSweep Pro)
except ImportError:
    ts_pro = None

VERSION = "1.1.1"


def parse_map(items):
    out = {}
    for it in items or []:
        if "=" not in it:
            raise ReportError('--map expects field="Column header", got: %s' % it)
        k, v = it.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def protect_entries(args):
    """Entries from --protect "a, =b" and --protect-file FILE. A --protect value that is an existing file is read
    as a file (passing the KeywordShare list there used to protect nothing, silently)."""
    out = []
    for item in (getattr(args, "protect", None) or "").split(","):
        item = item.strip()
        if not item:
            continue
        if os.path.isfile(item):
            print("Note: --protect got a file (%s); read it as --protect-file." % item, file=sys.stderr)
            out += read_protect_file(item)
        else:
            out.append(item)
    if getattr(args, "protect_file", None):
        if not os.path.isfile(args.protect_file):
            raise ConfigError("--protect-file not found: %s" % args.protect_file)
        out += read_protect_file(args.protect_file)
    return out


def build_cfg(args):
    near = [os.path.dirname(os.path.abspath(args.report))] if getattr(args, "report", None) else []
    if getattr(args, "out", None):
        near.append(args.out)
    cfg = load_config(args.config, cwd=os.getcwd(), near=near)
    if getattr(args, "target_acos", None) is not None:
        from ts_core import _as_fraction
        cfg["target_acos"] = _as_fraction(args.target_acos)
        cfg["target_acos_set"] = True
    cfg["protected_terms"] += [norm_protected(t) for t in protect_entries(args) if t.strip("= ")]
    if getattr(args, "currency", None):
        cfg["currency"] = args.currency
    return cfg


def out_dir(args):
    d = args.out or os.getcwd()
    os.makedirs(d, exist_ok=True)
    return d


def write_csv(path, rows):
    import csv
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        csv.writer(f).writerows(rows)


def cmd_audit(args):
    cfg = build_cfg(args)
    report = load_report(args.report, parse_map(args.map))
    res = analyze(report, cfg)
    stamp = datetime.date.today().isoformat()
    d = out_dir(args)
    extra, extra_sheets = [], []
    if ts_pro is not None:
        extra, extra_sheets = ts_pro.audit_extras(res, args.lang, state_dir=args.state or d)
    review = os.path.join(d, "termsweep-review-%s.xlsx" % stamp)
    write_xlsx(review, review_sheets(res, args.lang) + extra_sheets)
    neg = os.path.join(d, "termsweep-negatives-%s.csv" % stamp)
    write_csv(neg, negatives_csv_rows(res))
    from ts_core import T
    L = T[args.lang]
    files = [(review, L["f_review"]), (neg, L["f_neg"])]
    print(render_audit(res, args.lang, files=files, top=args.top, extra_sections=extra))
    if ts_pro is not None:
        ts_pro.save_history(res, state_dir=args.state or d)
    return 0


def cmd_bulk(args):
    if ts_pro is None:
        print("The bulk upload file is part of TermSweep Pro. The free audit already wrote "
              "termsweep-negatives-<date>.csv, which you can paste into Campaign Manager by hand.",
              file=sys.stderr)
        return 3
    cfg = build_cfg(args)
    report = load_report(args.report, parse_map(args.map))
    res = analyze(report, cfg)
    print(ts_pro.cmd_bulk(res, args, out_dir(args)))
    return 0


def cmd_groups(args):
    if ts_pro is None:
        print("Listing ad groups is part of TermSweep Pro.", file=sys.stderr)
        return 3
    print(ts_pro.cmd_groups(args.bulk_export))
    return 0


def cmd_inspect(args):
    report = load_report(args.report, parse_map(args.map))
    meta = report["meta"]
    print("File: %s%s" % (meta["file"], (" (sheet %s)" % meta["sheet"]) if meta["sheet"] else ""))
    print("Rows: %d raw → %d search term/target combinations" % (meta["raw_rows"], meta["rows"]))
    print("Decimal separator: %s · Currency: %s · Dates: %s – %s" % (
        meta["decimal"], meta["currency"] or "?", meta["date_from"] or "?", meta["date_to"] or "?"))
    print("Columns recognised:")
    for f, h in sorted(meta["columns"].items()):
        print("  %-12s ← %s" % (f, h))
    kinds = {}
    for r in report["rows"]:
        kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
    print("Targeting kinds: %s" % ", ".join("%s %d" % kv for kv in sorted(kinds.items())))
    return 0


def cmd_init(args):
    path = args.config or os.path.join(os.getcwd(), "termsweep.json")
    cfg = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
    if args.target_acos is not None:
        try:
            cfg["target_acos"] = float(str(args.target_acos).replace("%", "").replace(",", ".").strip())
        except ValueError:
            raise ConfigError("--target-acos must be a number like 25 or 0.25, got: %s" % args.target_acos)
    new = protect_entries(args)
    if new:
        old = cfg.get("protected_terms", [])
        cfg["protected_terms"] = old + [t for t in new if t not in old]
    if args.currency:
        cfg["currency"] = args.currency
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print("Saved %s:\n%s" % (path, json.dumps(cfg, ensure_ascii=False, indent=2)))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="termsweep", description=__doc__.split("\n")[1])
    p.add_argument("--version", action="version", version="TermSweep %s%s" % (VERSION, " Pro" if ts_pro else ""))
    sub = p.add_subparsers(dest="cmd")

    def common(sp, report=True):
        if report:
            sp.add_argument("report", help="search term report (.xlsx, .csv, .tsv, .txt)")
        sp.add_argument("--config", help="termsweep.json (default: ./termsweep.json if present)")
        sp.add_argument("--target-acos", help="target ACOS, e.g. 25 or 0.25")
        sp.add_argument("--protect", help="comma-separated terms that must never be negated (brand, core terms); "
                                          "'=term' protects exactly that search term")
        sp.add_argument("--protect-file", help="file with one protected entry per line, e.g. keywordshare-protect-<date>.txt "
                                               "('=term' = exactly this search term, otherwise every search term containing it)")
        sp.add_argument("--currency", help="currency code for display, e.g. EUR")
        sp.add_argument("--lang", choices=["en", "de"], default="en")
        sp.add_argument("--out", help="output folder (default: current folder)")
        sp.add_argument("--state", help="folder for TermSweep Pro history (default: output folder)")
        sp.add_argument("--map", action="append", help='force a column: field="Header" (repeatable)')
        sp.add_argument("--top", type=int, default=15, help="rows per table in the summary")

    common(sub.add_parser("audit", help="find wasted spend, winners and bid problems"))
    b = sub.add_parser("bulk", help="write an Amazon bulk upload file (Pro)")
    common(b)
    b.add_argument("--bulk-export", help="bulk file downloaded from Amazon Ads (provides campaign/ad group IDs)")
    b.add_argument("--harvest-to", help='"Campaign/Ad group" that receives harvested exact keywords')
    b.add_argument("--harvest-asin-to", help='"Campaign/Ad group" (product targeting) that receives harvested ASINs')
    b.add_argument("--no-ngrams", action="store_true", help="skip phrase negatives from n-gram analysis")
    b.add_argument("--no-bids", action="store_true", help="skip bid changes")
    g = sub.add_parser("groups", help="list campaigns/ad groups in a bulk export (Pro)")
    g.add_argument("--bulk-export", required=True)
    i = sub.add_parser("inspect", help="show recognised columns")
    i.add_argument("report")
    i.add_argument("--map", action="append")
    n = sub.add_parser("init", help="create or update termsweep.json")
    n.add_argument("--config")
    n.add_argument("--target-acos")
    n.add_argument("--protect")
    n.add_argument("--protect-file")
    n.add_argument("--currency")

    args = p.parse_args(argv)
    if not args.cmd:
        p.print_help()
        return 2
    try:
        return {"audit": cmd_audit, "bulk": cmd_bulk, "inspect": cmd_inspect, "init": cmd_init,
                "groups": cmd_groups}[args.cmd](args)
    except (ReportError, ConfigError) as e:
        print("TermSweep: %s" % e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
