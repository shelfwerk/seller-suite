#!/usr/bin/env python3
"""ListingDoctor – Amazon listing checker (command line).

  python3 listingdoctor.py check   LISTINGS [--keywords REPORT] [--lang de|en] [--brand NAME] [--json] [--out FILE]
  python3 listingdoctor.py check   B0ASIN1,B0ASIN2 [--market de|com|uk|fr|it|es]   read public product pages
  python3 listingdoctor.py fetch   B0ASIN1 B0ASIN2 [--market de] --out listings.json   save public pages as JSON
  python3 listingdoctor.py inspect LISTINGS            show what was read (header row, columns, listing count)

Pro edition only (needs ld_pro.py next to this file):
  python3 listingdoctor.py check   LISTINGS --full               every finding, not only the top 5
  python3 listingdoctor.py brief   LISTINGS [--keywords REPORT] --out briefs.json   rewrite brief per listing
  python3 listingdoctor.py family  LISTINGS                      variation family check (parent/child)
  python3 listingdoctor.py compare ORIGINAL DRAFTS [--keywords REPORT]   score before/after
  python3 listingdoctor.py export  DRAFTS --template ORIGINAL --out upload.xlsx   partial-update flat file
  python3 listingdoctor.py report  LISTINGS [--keywords REPORT] --out report.xlsx  Excel report

LISTINGS: Amazon category listing report / flat file (.xlsx/.xlsm/.txt/.csv), JSON, or plain text with
'Title:', 'Bullet 1:', 'Backend:' lines. REPORT: search term report, Search Query Performance export
or a plain keyword list (one per line, most important first).
Nothing is uploaded or changed on Amazon – the script only reads files and writes the files you name.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ld_core as C  # noqa: E402

try:
    import ld_pro as P  # noqa: E402
    PRO = True
except ImportError:
    P = None
    PRO = False

VERSION = "1.2.0"
FREE_TOP = 5


def _ui_lang(args, results):
    if args.lang in ("de", "en"):
        return args.lang
    langs = [r["result"]["lang"] for r in results]
    return "de" if langs and langs.count("de") >= len(langs) / 2 else "en"


def _listing_lang(args):
    """language the listings are written in: --listing-lang, else detected per listing (never --lang, that is the report)."""
    v = getattr(args, "listing_lang", None)
    return v if v in ("de", "en", "fr", "it", "es") else None


def _report_lang(args):
    return args.lang if getattr(args, "lang", None) in ("de", "en") else None


def _is_asin_list(arg):
    return bool(re.fullmatch(r"\s*(B0[A-Z0-9]{8}|\d{9}[\dX])(\s*[,; ]\s*(B0[A-Z0-9]{8}|\d{9}[\dX]))*\s*", arg or "", re.I))


def _fetch(asins, market):
    import ld_fetch as F
    listings, problems = F.fetch_listings([a for a in re.split(r"[,; ]+", asins) if a], market,
                                          log=lambda m: print(m, file=sys.stderr))
    for p in problems:
        print("Note: " + p, file=sys.stderr)
    for l in listings:
        l["_no_backend"] = True
    return listings


def _load(args):
    if _is_asin_list(args.listings):
        listings = _fetch(args.listings, args.market)
        if not listings:
            sys.exit("No public product page could be read. Paste the listing text (Title:, Bullet 1:, …) or use "
                     "the category listing report from Seller Central instead.")
        meta = {"file": "public pages (%s)" % args.market, "format": "web"}
        kws = _keywords(args.keywords) if getattr(args, "keywords", None) else None
        return listings, meta, kws, _listing_lang(args)
    if not os.path.exists(args.listings):
        sys.exit("File not found: %s" % args.listings)
    listings, meta = C.load_listings(args.listings)
    if not listings:
        sys.exit("No listings found in %s – expected a category listing report / flat file, JSON, or text with "
                 "'Title:' and 'Bullet 1:' lines. Run 'inspect' to see what was read." % args.listings)
    kws = None
    if getattr(args, "keywords", None):
        if not os.path.exists(args.keywords):
            sys.exit("Keyword file not found: %s" % args.keywords)
        kws = _keywords(args.keywords)
        if not kws:
            print("Note: no search terms found in %s – keyword coverage skipped." % args.keywords, file=sys.stderr)
    return listings, meta, kws, _listing_lang(args)


def _keywords(path):
    """load_keywords plus its notes on stderr (ranking used, list longer than the cap, report without orders)."""
    notes = []
    kws = C.load_keywords(path, notes=notes)
    for n in notes:
        print("Note: " + n, file=sys.stderr)
    return kws


def _write(text, path):
    if path:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        print("Written: %s" % path)
    else:
        print(text)


def cmd_check(args):
    listings, meta, kws, lang = _load(args)
    results, skipped = C.check_batch(listings, meta, keywords=kws, lang=lang, brand=args.brand, ui=_report_lang(args))
    full = bool(args.full)
    if full and not PRO:
        print("Note: --full is a ListingDoctor Pro feature – showing the top %d fixes per listing." % FREE_TOP, file=sys.stderr)
        full = False
    if args.json:
        payload = {"version": VERSION, "edition": "pro" if PRO else "free", "meta": meta, "skipped_parents": skipped,
                   "listings": []}
        for r in results:
            res = r["result"]
            issues = res["issues"] if full else C.top_fixes(res["issues"], FREE_TOP)
            payload["listings"].append({
                "label": r["label"], "sku": r["listing"].get("sku"), "asin": r["listing"].get("asin"),
                "title": r["title"], "lang": res["lang"], "score": res["score"], "stats": res["stats"],
                "issues_total": len(res["issues"]),
                "issues": [{k: v for k, v in i.items() if not k.startswith("_")} for i in issues],
                "coverage": res["coverage"] if (full and res["coverage"]) else None})
        _write(json.dumps(payload, ensure_ascii=False, indent=1), args.out)
        return
    md = C.render_md(results, lang=_ui_lang(args, results), top=None if full else FREE_TOP,
                     per_listing=args.max_listings, edition="pro" if PRO else "free", meta=meta,
                     skipped_parents=skipped)
    if full and kws:
        md += "\n" + P.coverage_md(results, _ui_lang(args, results))
    _write(md, args.out)


def cmd_inspect(args):
    listings, meta, kws, lang = _load(args)
    parents = sum(1 for l in listings if C.is_parent(l))
    print("File:        %s" % meta.get("file"))
    for k in ("sheet", "header_row", "fields", "bullet_cols", "backend_cols", "image_cols", "required_attrs"):
        if k in meta:
            print("%-12s %s" % (k + ":", meta[k]))
    print("Listings:    %d (%d parent rows)" % (len(listings), parents))
    for l in listings[:3]:
        print(" - %s | %s | %d bullets | backend %d bytes" % (l.get("sku") or l.get("asin") or "?", (l.get("title") or "")[:70],
                                                            len(l.get("bullets", [])), len((l.get("backend") or "").encode("utf-8"))))
    if kws:
        print("Keywords:    %d (top: %s)" % (len(kws), ", ".join(k for k, _ in kws[:5])))


def cmd_fetch(args):
    import ld_fetch as F
    listings = _fetch(" ".join(args.asins), args.market)
    if not listings:
        sys.exit("Nothing read.")
    out = args.out or "listings_public.json"
    F.save_json(listings, out)
    print("Written: %s (%d listings; backend search terms are not public and are not checked)" % (out, len(listings)))


def _need_pro(name):
    if not PRO:
        sys.exit("'%s' is part of ListingDoctor Pro. The free edition checks listings and shows the top %d fixes "
                 "(command: check)." % (name, FREE_TOP))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="listingdoctor", description="Amazon listing checker – score, fixes, keyword coverage.")
    ap.add_argument("--version", action="version", version="ListingDoctor %s (%s)" % (VERSION, "pro" if PRO else "free"))
    sub = ap.add_subparsers(dest="cmd")

    def common(p, listings=True):
        if listings:
            p.add_argument("listings")
        p.add_argument("--keywords", "-k")
        p.add_argument("--lang", default="auto", help="language of the report: de, en or auto (= language of the listings)")
        p.add_argument("--listing-lang", default=None, help="force the language the listings are written in (default: detected per listing)")
        p.add_argument("--brand")
        p.add_argument("--market", default="de", help="marketplace for ASIN input: de, com, uk, fr, it, es, nl, pl, se (default de)")
        p.add_argument("--out", "-o")

    p = sub.add_parser("check")
    common(p)
    p.add_argument("--json", action="store_true")
    p.add_argument("--full", action="store_true", help="Pro: every finding instead of the top 5")
    p.add_argument("--max-listings", type=int, default=10, help="detail sections in the Markdown output (default 10)")
    p.set_defaults(fn=cmd_check)
    p = sub.add_parser("inspect")
    common(p)
    p.set_defaults(fn=cmd_inspect)
    p = sub.add_parser("fetch")
    p.add_argument("asins", nargs="+")
    p.add_argument("--market", default="de")
    p.add_argument("--out", "-o")
    p.set_defaults(fn=cmd_fetch)

    for name in ("brief", "family", "compare", "export", "report"):
        p = sub.add_parser(name)
        if name == "compare":
            p.add_argument("original")
            p.add_argument("drafts")
            common(p, listings=False)
        elif name == "export":
            p.add_argument("drafts")
            p.add_argument("--template", required=True, help="the original category listing report / flat file")
            p.add_argument("--format", choices=["xlsx", "txt"], default=None)
            p.add_argument("--allow-errors", action="store_true", help="also export drafts that still break hard rules")
            common(p, listings=False)
        else:
            common(p)
        p.set_defaults(fn=None, pro=name)

    args = ap.parse_args(argv)
    if not args.cmd:
        ap.print_help()
        return 1
    if getattr(args, "market", None):        # 'DE' (as KeywordShare writes it), 'GB', 'amazon.de' → de, uk, de
        import ld_fetch as F
        args.market = F.norm_market(args.market.strip().lower())
    if getattr(args, "pro", None):
        _need_pro(args.pro)
        return getattr(P, "cmd_" + args.pro)(args)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main() or 0)
