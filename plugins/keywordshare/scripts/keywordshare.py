#!/usr/bin/env python3
"""KeywordShare — your share of Amazon search demand (Brand Analytics).

Usage:
  python3 keywordshare.py audit  SQP_FILE [SQP_FILE …] [--lang de] [--out DIR] [--top 10]
                                 [--min-purchases 5] [--target-share 15] [--brand-terms "acme,acme pro"]
                                 [--market DE] [--keywords 50] [--focus "headband,sweatband"] [--exclude "cup"]
                                 [--ads SEARCH_TERM_REPORT]
         several files / --ads: KeywordShare Pro (trend, ASIN comparison, organic estimate, PPC hand-off)
  python3 keywordshare.py trend  SQP_FILE SQP_FILE [...]        share over weeks/months (Pro)
  python3 keywordshare.py market TST_FILE [--sqp SQP_FILE] [--brand NAME] [--terms "a,b"]
                                 competition per search term from Top Search Terms (Pro)
  python3 keywordshare.py inspect FILE                          show how the file was recognised
  python3 keywordshare.py init   [--target-share 15] [--brand-terms "..."] [--min-purchases 5]

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

from ks_ads import ReportError, norm_text  # noqa: E402
from ks_core import (T, ConfigError, analyze, apply_focus, as_fraction, listing_keywords, load_config,  # noqa: E402
                     note_text, render_audit, review_sheets)
from ks_report import load_sqp, load_tst, sniff_kind  # noqa: E402
from ks_xlsx import write_xlsx  # noqa: E402

try:
    import ks_pro  # noqa: E402  (only shipped with KeywordShare Pro)
except ImportError:
    ks_pro = None

VERSION = "1.0.3"


def build_cfg(args):
    cfg = load_config(getattr(args, "config", None), cwd=os.getcwd())
    if getattr(args, "min_purchases", None) is not None:
        cfg["min_market_purchases"] = args.min_purchases
    if getattr(args, "target_share", None):
        cfg["target_share"] = as_fraction(args.target_share)
    if getattr(args, "brand_terms", None):
        cfg["brand_terms"] += [norm_text(t) for t in args.brand_terms.split(",") if t.strip()]
    if getattr(args, "keywords", None):
        cfg["keywords"] = args.keywords
    return cfg


def out_dir(args):
    d = args.out or os.getcwd()
    os.makedirs(d, exist_ok=True)
    return d


def load_all(paths, market=None):
    loaded = []
    for p in paths:
        kind = sniff_kind(p) if os.path.exists(p) else "sqp"
        if kind == "tst":
            raise ReportError("%s is a Top Search Terms report — use: keywordshare.py market %s (Pro). The audit "
                              "needs the Search Query Performance report." % (os.path.basename(p), os.path.basename(p)))
        loaded.append(load_sqp(p, market))
    return loaded


def newest(loaded):
    def key(rep):
        ends = [r["period_end"] or "" for r in rep["rows"]]
        return max(ends) if ends else ""
    return max(loaded, key=key)


def cmd_audit(args):
    cfg = build_cfg(args)
    loaded = load_all(args.files, args.market)
    notes = []
    if ks_pro is None:
        if args.ads:
            print("The organic estimate with --ads is part of KeywordShare Pro.", file=sys.stderr)
            return 3
        rep = newest(loaded)
        if len(loaded) > 1:
            notes.append(T[args.lang]["n_free_multi"] % (len(loaded) - 1))
        rows, meta = rep["rows"], rep["meta"]
    else:
        rows, meta, more = ks_pro.merge_for_audit(loaded, args.lang)
        notes += more
    rows, more = apply_focus(rows, args.focus, args.exclude)
    if not rows:
        raise ReportError(T["en"]["n_focus_empty"])
    notes += more
    res = analyze(rows, meta, cfg)
    stamp = datetime.date.today().isoformat()
    d = out_dir(args)
    L = T[args.lang]
    sections, sheets, handoff, files = [], [], [], []
    if ks_pro is not None:
        sections, sheets, handoff, files, more = ks_pro.audit_extras(res, loaded, args, d, stamp)
        notes += more
    book = os.path.join(d, "keywordshare-%s.xlsx" % stamp)
    write_xlsx(book, review_sheets(res, args.lang) + sheets)
    kw = listing_keywords(res)
    kw_path = os.path.join(d, "keywordshare-listing-keywords-%s.txt" % stamp)
    with open(kw_path, "w", encoding="utf-8") as f:
        f.write("\n".join(kw) + ("\n" if kw else ""))
    handoff.insert(0, L["ho_listing"] % (os.path.basename(kw_path), len(kw), os.path.basename(kw_path)))
    if ks_pro is None:
        handoff.append(L["ho_ts_free"])
    files = [(book, L["f_book"]), (kw_path, L["f_kw"])] + files
    print(render_audit(res, args.lang, files=files, top=args.top, extra_sections=sections, handoff=handoff, notes=notes))
    if ks_pro is not None:
        ks_pro.save_history(loaded, state_dir=args.state or d)
    return 0


def cmd_trend(args):
    if ks_pro is None:
        print("Trends over several weeks are part of KeywordShare Pro. The free audit reads one report at a time.",
              file=sys.stderr)
        return 3
    print(ks_pro.cmd_trend(args, build_cfg(args), out_dir(args)))
    return 0


def cmd_market(args):
    if ks_pro is None:
        print("The competition view from Top Search Terms is part of KeywordShare Pro.", file=sys.stderr)
        return 3
    print(ks_pro.cmd_market(args, build_cfg(args), out_dir(args)))
    return 0


def cmd_inspect(args):
    kind = sniff_kind(args.file) if os.path.exists(args.file) else None
    if kind == "tst":
        rep = load_tst(args.file, limit=5)
        meta = rep["meta"]
        print("File: %s — Top Search Terms report (%s)" % (meta["file"], meta["period"] or "period not stated"))
        print("Columns: term ← %s · rank ← %s · %d positions (#1–#%d)" % (
            meta["columns"]["term"], meta["columns"]["rank"], meta["columns"]["positions"], meta["columns"]["positions"]))
        for r in rep["rows"][:3]:
            print("  %s (rank %s): %s" % (r["term_raw"], r["rank"], ", ".join(
                "%s %.1f%%/%.1f%%" % (t["brand"] or t["asin"], t["click"] * 100, t["conv"] * 100) for t in r["top"])))
        return 0
    if kind == "ads":
        print("File: %s — advertising search term report (paid clicks). Use it with: audit SQP_FILE --ads %s (Pro), "
              "or with TermSweep." % (os.path.basename(args.file), os.path.basename(args.file)))
        return 0
    rep = load_sqp(args.file, args.market)
    meta = rep["meta"]
    print("File: %s%s — Search Query Performance, %s view%s" % (
        meta["file"], (" (sheet %s)" % meta["sheet"]) if meta["sheet"] else "", meta["view"],
        (" (%s)" % meta["entity"]) if meta["entity"] else ""))
    print("Rows: %d raw → %d query rows · periods: %s · market: %s · cart adds: %s · prices: %s" % (
        meta["raw_rows"], meta["rows"], ", ".join(meta["periods"][:6]) + (" …" if len(meta["periods"]) > 6 else ""),
        meta["market"] or "?", "yes" if meta["has_cart"] else "no", "yes" if meta["has_price"] else "no"))
    print("Columns recognised:")
    for f, h in meta["columns"].items():
        print("  %-14s ← %s" % (f, h))
    for n in meta["notes"]:
        print("Note: " + note_text(n, "en"))
    return 0


def cmd_init(args):
    path = args.config or os.path.join(os.getcwd(), "keywordshare.json")
    cfg = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
    if args.target_share:
        cfg["target_share"] = round(as_fraction(args.target_share) * 100, 2)
    if args.min_purchases is not None:
        cfg["min_market_purchases"] = args.min_purchases
    if args.brand_terms:
        old = cfg.get("brand_terms", [])
        cfg["brand_terms"] = old + [t.strip() for t in args.brand_terms.split(",") if t.strip() and t.strip() not in old]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print("Saved %s:\n%s" % (path, json.dumps(cfg, ensure_ascii=False, indent=2)))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="keywordshare", description=__doc__.split("\n")[1])
    p.add_argument("--version", action="version", version="KeywordShare %s%s" % (VERSION, " Pro" if ks_pro else ""))
    sub = p.add_subparsers(dest="cmd")

    def common(sp):
        sp.add_argument("--config", help="keywordshare.json (default: ./keywordshare.json if present)")
        sp.add_argument("--lang", choices=["en", "de"], default="en")
        sp.add_argument("--out", help="output folder (default: current folder)")
        sp.add_argument("--state", help="folder for KeywordShare Pro history (default: output folder)")
        sp.add_argument("--top", type=int, default=10, help="rows per table in the summary")
        sp.add_argument("--min-purchases", type=int, help="market purchases a query needs to be judged (default 5)")
        sp.add_argument("--target-share", help="target impression share, e.g. 15 or 0.15 (default: your top quartile)")
        sp.add_argument("--brand-terms", help="comma-separated brand words (your own brand queries are marked)")
        sp.add_argument("--market", help="marketplace to analyse when a file holds several (e.g. DE)")
        sp.add_argument("--keywords", type=int, help="length of the ListingDoctor keyword list (default 50 = what ListingDoctor reads)")
        sp.add_argument("--focus", help="only search queries containing one of these words, e.g. \"headband,sweatband\"")
        sp.add_argument("--exclude", help="leave out search queries containing one of these words")

    a = sub.add_parser("audit", help="share, funnel and opportunities from Search Query Performance")
    a.add_argument("files", nargs="+", help="Search Query Performance report(s) (.csv, .xlsx, SP-API .json)")
    a.add_argument("--ads", help="Sponsored Products search term report of the same period (Pro: organic estimate)")
    common(a)
    t = sub.add_parser("trend", help="share over several weeks/months (Pro)")
    t.add_argument("files", nargs="*", help="Search Query Performance reports of different periods")
    common(t)
    m = sub.add_parser("market", help="competition per search term from Top Search Terms (Pro)")
    m.add_argument("tst", help="Top Search Terms report (.csv/.xlsx)")
    m.add_argument("--sqp", help="Search Query Performance report: analyse its queries")
    m.add_argument("--brand", help="your brand name as shown in Top Search Terms (comma-separated for several)")
    m.add_argument("--asins", help="your ASINs (comma-separated)")
    m.add_argument("--terms", help="comma-separated search terms to look at")
    common(m)
    i = sub.add_parser("inspect", help="show recognised columns")
    i.add_argument("file")
    i.add_argument("--market")
    n = sub.add_parser("init", help="create or update keywordshare.json")
    n.add_argument("--config")
    n.add_argument("--target-share")
    n.add_argument("--min-purchases", type=int)
    n.add_argument("--brand-terms")

    args = p.parse_args(argv)
    if not args.cmd:
        p.print_help()
        return 2
    try:
        return {"audit": cmd_audit, "trend": cmd_trend, "market": cmd_market, "inspect": cmd_inspect,
                "init": cmd_init}[args.cmd](args)
    except (ReportError, ConfigError) as e:
        print("KeywordShare: %s" % e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
