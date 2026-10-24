"""Load Amazon Brand Analytics reports.

Search Query Performance (SQP): brand view or ASIN view, downloaded from Seller Central (CSV/XLSX,
any console language, with or without the `Brand=[…],Reporting Range=[…]` metadata line), SP-API
JSON (GET_BRAND_ANALYTICS_SEARCH_QUERY_PERFORMANCE_REPORT) and tool exports that use
"My … / Total …" columns (e.g. AMALYTIX).

Top Search Terms (TST): old (`#1 Clicked ASIN`) and current (`Top Clicked Product #1: ASIN`) layouts,
streamed so a full marketplace download does not have to fit in memory.

Every SQP row is normalised to counts per funnel stage: impressions (imp), clicks (clk), cart adds
(cart) and purchases (pur), each as market total (_t) and yours (_m, brand or ASIN).
"""
import csv
import io
import json
import os
import re

from ks_ads import ReportError, _currency_from_marketplace, _date_key, detect_decimal, norm_header, norm_text, parse_number
from ks_xlsx import read_xlsx

STAGES = ("imp", "clk", "cart", "pur")
COUNTS = ["%s_%s" % (s, k) for s in STAGES for k in ("t", "m")]

# Stage words on the normalised header (lowercase, no accents, punctuation -> space).
# "cart" is tested before "clk"/"pur": German "Einkaufswagen" contains "kauf".
STAGE_RE = [
    # "Basket adds" is the English label on amazon.de / .co.uk
    ("cart", re.compile(r"\bcart\b|\bcart adds?\b|\bbasket\b|\bbasket adds?\b|warenkorb|einkaufswagen|\bpanier\b|"
                        r"\bcarrello\b|\bcarrito\b|winkelwagen")),
    ("imp", re.compile(r"\bimpression|\bimpressionen\b|sichtkontakt|\bimpresion|\bimpressioni\b|\bvertoning")),
    ("clk", re.compile(r"\bclicks?\b|\bklicks?\b|\bclics?\b|\bklikken\b")),
    ("pur", re.compile(r"\bpurchases?\b|\bkaufe\b|\bkauf\b|\bachats?\b|\bacquisti\b|\bcompras\b|\baankopen\b")),
]
PRICE_RE = re.compile(r"\bprice\b|preis|\bprix\b|\bprezzo\b|\bprecio\b|\bprijs\b")
SKIP_RE = re.compile(r"shipping|versand|\bspeed\b|lieferung|livraison|spedizion|\benvio\b|"
                     r"rate\b|quote\b|\btaux\b|\btasso\b|\btasa\b|\bctr\b|\bcar\b|\bcr\b|difference|differenz|\bindex\b")
SHARE_RE = re.compile(r"\bshare\b|anteil|\bpart\b|\bquota\b|\bcuota\b|aandeel")
MINE_RE = re.compile(r"\bbrand\b|\bmarke\b|\bmarken|\basin\b|\bmy\b|\bmeine?\b|\beigene?\b|\bmarque\b|\bmarca\b|\bmerk\b")
TOTAL_RE = re.compile(r"\btotal\b|gesamt|\binsgesamt\b|\btotale\b|\bcount\b|\banzahl\b|\bnombre\b|\bnumero\b|\baantal\b")

# German labels as quoted from the DE console UI (CSV headers in German not verified; English is canonical)
QUERY_RE = [(re.compile(r"^search query$|^suchanfrage$|^suchabfrage$|^requete de recherche$|^query di ricerca$|"
                        r"^consulta de busqueda$|^zoekopdracht$"), 10),
            (re.compile(r"\bsearch query\b|\bsuchanfrage\b|\bsuchabfrage\b|\brequete\b|\bconsulta\b"), 8),
            (re.compile(r"^query$|^search term$|^suchbegriff$|^keyword$"), 6)]
QUERY_EXCLUDE = re.compile(r"score|volume|volumen|rank|rang|bewertung|ergebnis|wert\b|count|anzahl|share|anteil|punt")
SCORE_RE = re.compile(r"\bscore\b|bewertung|punktzahl|punteggio|puntuacion|\bwert\b|ergebnis")
VOLUME_RE = re.compile(r"volume|volumen|suchvolumen")
DATE_RE = re.compile(r"^reporting date$|^berichtsdatum$|^date$|^datum$|^end ?date$|^enddatum$|^week ?end|^date de fin$|^data di fine$")
START_RE = re.compile(r"^start ?date$|^startdatum$|^date de debut$|^data di inizio$|^fecha de inicio$")
ASIN_COL_RE = re.compile(r"^asin$|^child asin$|^\(child\) asin$|^asin or product$")
MARKET_RE = re.compile(r"^market$|^marketplace$|^marktplatz$|^country$|^land$|^marketplace id$")

ISO_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
META_RE = re.compile(r'([A-Za-z][^=\[\],"]*?)\s*=\s*\[([^\]]*)\]')


# ---------------------------------------------------------------- header mapping

def classify_header(h):
    """Map one SQP header to a field name or None.

    Fields: query, score, volume, date, start, asin, market, <stage>_t, <stage>_m, <stage>_share,
    <stage>_price_t, <stage>_price_m.
    """
    n = norm_header(h)
    if not n:
        return None
    for rx, _ in QUERY_RE:
        if rx.search(n) and not QUERY_EXCLUDE.search(n):
            return "query"
    stage = None
    for s, rx in STAGE_RE:
        if rx.search(n):
            stage = s
            break
    if stage is None:
        if SCORE_RE.search(n):
            return "score"
        if VOLUME_RE.search(n):
            return "volume"
        if DATE_RE.search(n):
            return "date"
        if START_RE.search(n):
            return "start"
        if ASIN_COL_RE.search(n):
            return "asin"
        if MARKET_RE.search(n):
            return "market"
        return None
    if PRICE_RE.search(n):
        return "%s_price_%s" % (stage, "m" if MINE_RE.search(n) else "t")
    if SKIP_RE.search(n):
        return None
    if SHARE_RE.search(n):
        return "%s_share" % stage
    if MINE_RE.search(n):
        return "%s_m" % stage
    if TOTAL_RE.search(n):
        return "%s_t" % stage
    return None


def map_sqp_headers(headers):
    mapping, query_score = {}, -1
    for i, h in enumerate(headers):
        f = classify_header(h)
        if f is None:
            continue
        if f == "query":
            n = norm_header(h)
            score = max(s for rx, s in QUERY_RE if rx.search(n))
            if score > query_score:
                mapping["query"], query_score = i, score
            continue
        mapping.setdefault(f, i)
    return mapping


def _is_sqp_header(row):
    m = map_sqp_headers(row)
    stages = sum(1 for s in STAGES if "%s_t" % s in m or "%s_m" % s in m or "%s_share" % s in m)
    return "query" in m and stages >= 2


# ---------------------------------------------------------------- generic reading

def _decode(raw):
    for enc in ("utf-8-sig", "utf-16", "cp1252", "latin-1"):
        try:
            text = raw.decode(enc)
        except UnicodeDecodeError:
            continue
        if enc == "utf-16" and "\x00" in text:
            continue
        return text
    return raw.decode("latin-1", "replace")


def _delimiter(sample):
    lines = [l for l in sample.splitlines()[:6] if l.strip()]
    body = "\n".join(lines[1:] if len(lines) > 1 and "=[" in lines[0] else lines)
    try:
        return csv.Sniffer().sniff(body, delimiters=",;\t|").delimiter
    except csv.Error:
        return "\t" if body.count("\t") > body.count(",") else ("," if body.count(",") >= body.count(";") else ";")


def read_table(path):
    """Return [(sheet or None, rows)] for csv/tsv/txt/xlsx files."""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xlsm"):
        try:
            return read_xlsx(path)
        except Exception:
            raise ReportError("%s is not a readable Excel file (damaged or not really .xlsx). Download it again "
                              "or export it as .csv." % os.path.basename(path))
    if ext == ".xls":
        raise ReportError("Old .xls format is not supported. Save the file as .xlsx or .csv.")
    with open(path, "rb") as f:
        text = _decode(f.read())
    if not text.strip():
        raise ReportError("%s is empty." % os.path.basename(path))
    delim = _delimiter(text[:20000])
    return [(None, list(csv.reader(io.StringIO(text), delimiter=delim)))]


def parse_meta(cells):
    """`Brand=["Acme"],Reporting Range=["Weekly"],Select week=["Week 6 | 2026-02-01 - 2026-02-07 2026"]`."""
    line = ",".join("" if c is None else str(c) for c in cells)
    out = {}
    for k, v in META_RE.findall(line):
        vals = [x.strip().strip('"').strip() for x in v.split('","')]
        out[norm_header(k)] = ", ".join(x for x in vals if x)
    return out


def period_from_meta(meta):
    """(label, end_iso, start_iso, range) from SQP/TST metadata, or None."""
    if not meta:
        return None
    rng = meta.get("reporting range", "")
    for key in ("select week", "select month", "select quarter", "select year", "select date"):
        if key in meta:
            v = meta[key]
            dates = ["%s-%s-%s" % m for m in ISO_RE.findall(v)]
            year = meta.get("select year", "")
            if len(dates) >= 2:
                return ("%s – %s" % (dates[0], dates[-1]), dates[-1], dates[0], rng)
            if key == "select month":
                months = ["january", "february", "march", "april", "may", "june", "july", "august",
                          "september", "october", "november", "december"]
                mon = norm_header(v)
                for i, name in enumerate(months):
                    if mon.startswith(name[:3]):
                        label = "%s-%02d" % (year or "?", i + 1)
                        return (label, label + "-28", label + "-01", rng or "Monthly")
                return ("%s %s" % (v, year), None, None, rng)
            if key == "select quarter":
                q = re.sub(r"\D", "", v) or v
                end = {"1": "03-31", "2": "06-30", "3": "09-30", "4": "12-31"}.get(q)
                return ("Q%s %s" % (q, year), ("%s-%s" % (year, end)) if (end and year) else None, None, rng or "Quarterly")
            if key == "select year" and not any(k in meta for k in ("select month", "select quarter", "select week")):
                return (v, "%s-12-31" % v if re.match(r"^\d{4}$", v) else None, None, rng or "Yearly")
            if dates:
                return (dates[0], dates[0], None, rng)
    # older downloads: `Viewing=[…]` / German `Wird angezeigt=[01.02.19 - 28.02.19]`
    for v in meta.values():
        dates = ["%s-%s-%s" % m for m in ISO_RE.findall(v)] or [
            "%04d-%02d-%02d" % ((int(y) + 2000 if len(y) == 2 else int(y)), int(mo), int(d))
            for d, mo, y in re.findall(r"\b(\d{1,2})\.(\d{1,2})\.(\d{2,4})\b", v)]
        if len(dates) >= 2:
            return ("%s – %s" % (dates[0], dates[-1]), dates[-1], dates[0], meta.get("auswertungsbereich") or rng)
    return None


# ---------------------------------------------------------------- SQP

def load_sqp(path, market=None):
    """Return {"rows": [...], "meta": {...}} for one SQP file. Raises ReportError."""
    if not os.path.exists(path):
        raise ReportError("File not found: %s" % path)
    if os.path.splitext(path)[1].lower() == ".json":
        return _load_sqp_json(path)
    sheets = read_table(path)
    for sheet, rows in sheets:
        for i, row in enumerate(rows[:15]):
            if _is_sqp_header(row):
                meta_line = {}
                for prev in rows[:i]:
                    meta_line.update(parse_meta(prev))
                return _sqp_from_rows(path, sheet, rows[i], rows[i + 1:], meta_line, market)
    kind = sniff_kind_rows(sheets)
    if kind == "tst":
        raise ReportError("%s is a Top Search Terms report. Use it with the market command (KeywordShare Pro); "
                          "the audit needs a Search Query Performance report." % os.path.basename(path))
    if kind == "ads":
        raise ReportError("%s is an advertising search term report (paid clicks only). KeywordShare reads the "
                          "Brand Analytics Search Query Performance report; for the paid side use TermSweep, "
                          "or pass this file with --ads (KeywordShare Pro)." % os.path.basename(path))
    first = next((r for _, rows in sheets for r in rows if any(c not in (None, "") for c in r)), [])
    raise ReportError("No Search Query Performance columns found in %s. First row: %s. Expected columns like "
                      "\"Search Query\", \"Impressions: Total Count\", \"Impressions: Brand Count\" (Seller Central → "
                      "Brands → Brand Analytics → Search Query Performance → Download)."
                      % (os.path.basename(path), "; ".join(str(c) for c in first[:12]) or "(empty)"))


def sniff_kind_rows(sheets):
    for _, rows in sheets:
        for row in rows[:15]:
            n = " | ".join(norm_header(c) for c in row)
            if _is_sqp_header(row):
                return "sqp"
            if re.search(r"frequency rank|haufigkeit|suchfrequenz|click share|klickanteil|klickrate #", n):
                return "tst"
            if re.search(r"customer search term|suchbegriff des kunden|kundensuchbegriff", n) or (
                    re.search(r"\bspend\b|\bausgaben\b|\bkosten\b", n) and re.search(r"\bclicks?\b|\bklicks\b", n)):
                return "ads"
    return None


def sniff_kind(path):
    """'sqp', 'tst', 'ads' or None (for routing in the CLI)."""
    if os.path.splitext(path)[1].lower() == ".json":
        return "sqp"
    try:
        return sniff_kind_rows(read_table(path))
    except ReportError:
        return None


def _iso(d):
    """Reporting dates: ISO, Excel serials, DE/US spellings and DD-MM-YYYY (seen in re-saved exports)."""
    m = re.match(r"^\s*(\d{1,2})-(\d{1,2})-(\d{4})\s*$", str(d)) if isinstance(d, str) else None
    if m:
        return "%s-%02d-%02d" % (m.group(3), int(m.group(2)), int(m.group(1)))
    return _date_key(d, True)


def _filename_date(path):
    m = ISO_RE.search(os.path.basename(path))
    return "%s-%s-%s" % m.groups() if m else None


def _sqp_from_rows(path, sheet, headers, data, meta_line, market_filter):
    headers = ["" if h is None else str(h) for h in headers]
    m = map_sqp_headers(headers)
    notes = []
    missing = [s for s in ("imp", "clk", "pur") if not ("%s_t" % s in m and ("%s_m" % s in m or "%s_share" % s in m))]
    if missing:
        names = {"imp": "impressions", "clk": "clicks", "pur": "purchases"}
        raise ReportError("Found a search query column but no total + own counts for %s in %s. Columns: %s"
                          % (", ".join(names[s] for s in missing), os.path.basename(path), "; ".join(h for h in headers if h)))

    def col(f):
        return [r[m[f]] for r in data[:3000] if m[f] < len(r)]

    numeric = [f for f in m if f not in ("query", "date", "start", "asin", "market")]
    dec_votes = [detect_decimal(col(f), None) for f in numeric]
    dec_votes = [d for d in dec_votes if d]
    decimal = "," if dec_votes and dec_votes.count(",") > len(dec_votes) / 2.0 else "."
    decimals = {f: detect_decimal(col(f), decimal) for f in numeric}
    # share columns: Seller Central writes percent numbers (15 = 15 %), tools often fractions (0.15)
    share_scale = {}
    for s in STAGES:
        f = "%s_share" % s
        if f in m:
            vals = [parse_number(v, decimals[f]) for v in col(f) if v not in (None, "")]
            pct_marked = any(isinstance(v, str) and "%" in v for v in col(f))
            share_scale[f] = 1.0 if pct_marked else (100.0 if vals and max(vals) > 1.0 else 1.0)

    period_meta = period_from_meta(meta_line)
    entity = meta_line.get("asin or product") or meta_line.get("asin oder produkt") or meta_line.get("brand") \
        or meta_line.get("marke") or ""
    view = "asin" if ("asin or product" in meta_line or "asin oder produkt" in meta_line) else (
        "brand" if ("brand" in meta_line or "marke" in meta_line) else None)
    if view is None:
        hdr = " ".join(norm_header(h) for h in headers)
        view = "asin" if re.search(r"\basin (count|share)", hdr) or "asin" in m else (
            "brand" if re.search(r"\b(brand|marke|marken)\w* (count|share|anzahl|anteil)", hdr) else "mine")
    file_date = _filename_date(path)
    if not period_meta and "date" not in m and file_date:
        notes.append(("n_file_date", (file_date,)))

    def cell(row, f):
        i = m.get(f)
        if i is None or i >= len(row):
            return None
        return row[i]

    def num(row, f):
        v = cell(row, f)
        if v in (None, ""):
            return None
        return parse_number(v, decimals.get(f, decimal))

    agg, markets, raw = {}, {}, 0
    for row in data:
        if not row or all(c in (None, "") for c in row):
            continue
        q = cell(row, "query")
        if q is None or str(q).strip() == "":
            continue
        q_raw = str(int(q)) if isinstance(q, float) and q.is_integer() else str(q).strip()
        raw += 1
        mk = str(cell(row, "market") or "").strip()
        markets[mk] = markets.get(mk, 0) + 1
        ent = str(cell(row, "asin") or "").strip() or entity
        if period_meta:
            label, end, start = period_meta[0], period_meta[1], period_meta[2]
        else:
            d = cell(row, "date")
            if d not in (None, ""):
                end = _iso(d)
                st = cell(row, "start")
                start = _iso(st) if st not in (None, "") else None
                label = ("%s – %s" % (start, end)) if start else end
            else:
                label, end, start = (("Export %s" % file_date), file_date, None) if file_date else (os.path.basename(path), None, None)
        rec = {"query": norm_text(q_raw), "query_raw": q_raw, "market": mk, "entity": ent,
               "period": label, "period_end": end, "period_start": start,
               "score": num(row, "score"), "volume": num(row, "volume") or 0.0}
        for s in STAGES:
            t = num(row, "%s_t" % s)
            mine = num(row, "%s_m" % s)
            if mine is None and "%s_share" % s in m and t is not None:
                sh = num(row, "%s_share" % s)
                mine = (sh or 0.0) / share_scale["%s_share" % s] * t
            rec["%s_t" % s] = t or 0.0
            rec["%s_m" % s] = mine or 0.0
        for s in ("pur", "clk"):
            for k in ("t", "m"):
                v = num(row, "%s_price_%s" % (s, k))
                if v is not None and not rec.get("price_%s" % k):
                    rec["price_%s" % k] = v
        key = (rec["period"], rec["entity"], rec["market"], rec["query"])
        old = agg.get(key)
        if old is None:
            agg[key] = rec
        else:       # duplicate query line (some tool exports repeat rows): add counts
            for f in COUNTS:
                old[f] += rec[f]
            old["volume"] = max(old["volume"], rec["volume"])
    rows = list(agg.values())
    if not rows:
        raise ReportError("The Search Query Performance report %s contains no search query rows." % os.path.basename(path))
    has_cart = "cart_t" in m and ("cart_m" in m or "cart_share" in m)
    if not has_cart:
        for r in rows:
            r["cart_t"] = r["cart_m"] = None
    # several marketplaces in one export (tools): keep one
    real_markets = [k for k in markets if k]
    chosen = None
    if len(real_markets) > 1:
        chosen = market_filter or max(real_markets, key=lambda k: markets[k])
        if market_filter and not any(k.lower() == market_filter.lower() for k in real_markets):
            raise ReportError("Market %s not in %s (markets: %s)." % (market_filter, os.path.basename(path), ", ".join(sorted(real_markets))))
        rows = [r for r in rows if r["market"].lower() == chosen.lower()]
        notes.append(("n_markets", (", ".join("%s %d" % (k, markets[k]) for k in sorted(real_markets)), chosen)))
    elif real_markets:
        chosen = real_markets[0]
    currency = _currency_from_marketplace(_market_domain(chosen)) if chosen else None
    meta = {"file": os.path.basename(path), "sheet": sheet, "kind": "sqp", "view": view, "entity": entity,
            "columns": {f: headers[i] for f, i in sorted(m.items())}, "decimal": decimal,
            "raw_rows": raw, "rows": len(rows), "market": chosen, "currency": currency,
            "periods": sorted(set(r["period"] for r in rows)), "range": period_meta[3] if period_meta else None,
            "has_cart": has_cart, "has_price": any(r.get("price_m") or r.get("price_t") for r in rows),
            "meta_line": meta_line, "notes": notes, "source": "seller central" if meta_line else "export"}
    return {"rows": rows, "meta": meta}


_MARKET_DOMAIN = {"de": "amazon.de", "fr": "amazon.fr", "it": "amazon.it", "es": "amazon.es", "nl": "amazon.nl",
                  "uk": "amazon.co.uk", "gb": "amazon.co.uk", "us": "amazon.com", "se": "amazon.se", "pl": "amazon.pl",
                  "be": "amazon.com.be", "ca": "amazon.ca", "mx": "amazon.com.mx", "jp": "amazon.co.jp",
                  "au": "amazon.com.au", "ae": "amazon.ae", "tr": "amazon.com.tr", "br": "amazon.com.br"}


def _market_domain(mk):
    k = (mk or "").strip().lower()
    return _MARKET_DOMAIN.get(k, k)


def _load_sqp_json(path):
    """SP-API GET_BRAND_ANALYTICS_SEARCH_QUERY_PERFORMANCE_REPORT (dataByAsin)."""
    try:
        with open(path, encoding="utf-8-sig") as f:
            doc = json.load(f)
    except (ValueError, UnicodeDecodeError):
        raise ReportError("%s is not valid JSON." % os.path.basename(path))
    items = doc.get("dataByAsin") if isinstance(doc, dict) else doc
    if not isinstance(items, list) or not items:
        raise ReportError("%s has no dataByAsin list (expected the SP-API Search Query Performance report)."
                          % os.path.basename(path))

    def pick(d, want_total, *words):
        if not isinstance(d, dict):
            return None
        for k, v in d.items():
            kl = k.lower()
            if isinstance(v, (int, float)) and ("count" in kl) and all(w in kl for w in words) \
                    and (("total" in kl) == want_total) and "shipping" not in kl and "speed" not in kl:
                return float(v)
        return None

    def price(d, want_total):
        if not isinstance(d, dict):
            return None
        for k, v in d.items():
            kl = k.lower()
            if "median" in kl and "price" in kl and (("total" in kl) == want_total) and isinstance(v, dict):
                return v.get("amount")
        return None

    stage_keys = {"imp": "impressionData", "clk": "clickData", "cart": "cartAddData", "pur": "purchaseData"}
    agg, currency = {}, None
    spec = doc.get("reportSpecification", {}) if isinstance(doc, dict) else {}
    for it in items:
        sq = it.get("searchQueryData", {})
        q = str(sq.get("searchQuery", "")).strip()
        if not q:
            continue
        start, end = it.get("startDate"), it.get("endDate")
        rec = {"query": norm_text(q), "query_raw": q, "market": "", "entity": it.get("asin", ""),
               "period": ("%s – %s" % (start, end)) if start else (end or "?"), "period_end": end, "period_start": start,
               "score": sq.get("searchQueryScore"), "volume": float(sq.get("searchQueryVolume") or 0)}
        for s, key in stage_keys.items():
            d = it.get(key, {})
            rec["%s_t" % s] = pick(d, True) or 0.0
            rec["%s_m" % s] = pick(d, False, "asin") or pick(d, False, "brand") or 0.0
        pd = it.get("purchaseData", {})
        rec["price_t"], rec["price_m"] = price(pd, True), price(pd, False)
        for v in pd.values() if isinstance(pd, dict) else []:
            if isinstance(v, dict) and v.get("currencyCode") and not currency:
                currency = v["currencyCode"]
        key = (rec["period"], rec["entity"], rec["market"], rec["query"])
        if key in agg:
            for f in COUNTS:
                agg[key][f] += rec[f]
        else:
            agg[key] = rec
    rows = list(agg.values())
    meta = {"file": os.path.basename(path), "sheet": None, "kind": "sqp", "view": "asin",
            "entity": ", ".join(sorted(set(r["entity"] for r in rows if r["entity"]))),
            "columns": {"json": "dataByAsin"}, "decimal": ".", "raw_rows": len(items), "rows": len(rows),
            "market": ", ".join(spec.get("marketplaceIds", []) or []) or None, "currency": currency,
            "periods": sorted(set(r["period"] for r in rows)), "range": (spec.get("reportOptions") or {}).get("reportPeriod"),
            "has_cart": True, "has_price": any(r.get("price_m") for r in rows), "meta_line": {}, "notes": [],
            "source": "sp-api"}
    return {"rows": rows, "meta": meta}


# ---------------------------------------------------------------- Top Search Terms

TST_RANK_RE = re.compile(r"frequency rank|haufigkeit|\brang\b|\brank\b|classement|frequenza|frecuencia")
TST_TERM_RE = re.compile(r"^search term$|^suchbegriff$|^terme de recherche$|^termine di ricerca$|^termino de busqueda$|^zoekterm$")
# German old layout headers (verified on a 2019 amazon.de download): Abteilung, Suchbegriff, "Suchfrequenz-Rang ",
# "#1 der angeklickten ASINs", "Produkttitel #1", "Klickrate #1", "Umsatzrate #1"
POS_RE = re.compile(r"#\s*(\d)")


def map_tst_headers(headers):
    m = {"top": {}}
    for i, h in enumerate(headers):
        n = norm_header(h)
        if not n:
            continue
        pos = POS_RE.search(n)
        if pos:
            p = int(pos.group(1))
            slot = m["top"].setdefault(p, {})
            # verified German old layout (2019): "Klickrate #1" = click share, "Umsatzrate #1" = conversion share
            if re.search(r"click share|klickanteil|klickrate|part des clics|quota (di )?clic|cuota de clics|klikaandeel", n):
                slot["click"] = i
            elif re.search(r"conversion|konversion|conversione|umsatzrate", n):
                slot["conv"] = i
            elif re.search(r"\basins?\b", n):
                slot["asin"] = i
            elif re.search(r"title|titel|titre|titolo|titulo", n):
                slot["title"] = i
            elif re.search(r"categor|kategorie", n):
                slot.setdefault("category", i)
            elif re.search(r"brand|marke|marque|marca|merk", n):
                slot["brand"] = i
            continue
        if TST_RANK_RE.search(n) and "rank" not in m:
            m["rank"] = i
        elif (TST_TERM_RE.search(n) or (re.search(r"search term|suchbegriff", n) and not TST_RANK_RE.search(n))) and "term" not in m:
            m["term"] = i
        elif re.search(r"^department$|^abteilung$|^kategorie$|^rayon$", n):
            m["department"] = i
        elif re.search(r"^reporting date$|^berichtsdatum$|^date$", n):
            m["date"] = i
    return m


def _share_num(v):
    """30.85 / "30,85" / "30.85%" -> float (scale decided later over the whole file)."""
    if v is None or isinstance(v, (int, float)):
        return float(v or 0)
    s = str(v).strip()
    if re.match(r"^-?\d+,\d+%?$", s):
        s = s.replace(",", ".")
    x = parse_number(s)
    return x * 100.0 if s.endswith("%") else x      # parse_number already divided "%" values by 100


def _is_tst_header(row):
    m = map_tst_headers(["" if c is None else str(c) for c in row])
    return "term" in m and any("click" in s for s in m["top"].values())


def _iter_table_rows(path):
    """Yield rows; CSV is streamed (Top Search Terms downloads can be very large)."""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xlsm", ".xls"):
        for _, rows in read_table(path):
            for r in rows:
                yield r
        return
    with open(path, "rb") as fb:
        head = fb.read(65536)
    enc = "utf-8-sig"
    try:
        head.decode("utf-8-sig")
    except UnicodeDecodeError:
        enc = "cp1252"
    delim = _delimiter(head.decode(enc, "replace"))
    with open(path, encoding=enc, errors="replace", newline="") as f:
        for r in csv.reader(f, delimiter=delim):
            yield r


def load_tst(path, terms=None, brands=None, asins=None, limit=2000):
    """Return {"rows": [...], "meta": {...}}. Keeps rows whose term is in `terms`, or whose top-3 contains
    one of `brands` / `asins`; without filters the first `limit` rows (best search frequency rank)."""
    if not os.path.exists(path):
        raise ReportError("File not found: %s" % path)
    terms = set(norm_text(t) for t in terms) if terms else None
    brands = set(norm_text(b) for b in brands) if brands else None
    asins = set(a.strip().upper() for a in asins) if asins else None
    it = _iter_table_rows(path)
    meta_line, m, headers = {}, None, None
    for i, row in enumerate(it):
        if _is_tst_header(row):
            headers = ["" if c is None else str(c) for c in row]
            m = map_tst_headers(headers)
            break
        meta_line.update(parse_meta(row))
        if i > 15:
            break
    if m is None:
        raise ReportError("%s is not a Top Search Terms report (no \"Search Term\" + \"#1 … Click Share\" columns)."
                          % os.path.basename(path))
    period = period_from_meta(meta_line)
    out, raw, scale_votes = [], 0, []
    for row in it:
        if not row or m["term"] >= len(row):
            continue
        term = str(row[m["term"]] or "").strip()
        if not term:
            continue
        raw += 1
        top = []
        for p in sorted(m["top"]):
            s = m["top"][p]

            def g(k):
                j = s.get(k)
                return row[j] if j is not None and j < len(row) else None
            click, conv = _share_num(g("click")), _share_num(g("conv"))
            scale_votes.extend(v for v in (click, conv) if v)
            top.append({"pos": p, "asin": str(g("asin") or "").strip().upper(), "title": str(g("title") or "").strip(),
                        "brand": str(g("brand") or "").strip(), "category": str(g("category") or "").strip(),
                        "click": click, "conv": conv})
        nt = norm_text(term)
        keep = False
        if terms is not None and nt in terms:
            keep = True
        if brands is not None and any(norm_text(t["brand"]) in brands for t in top):
            keep = True
        if asins is not None and any(t["asin"] in asins for t in top):
            keep = True
        if terms is None and brands is None and asins is None:
            if len(out) >= limit:
                break
            keep = True
        if keep:
            rank = re.sub(r"\D", "", str(row[m["rank"]])) if "rank" in m and m["rank"] < len(row) else ""
            out.append({"term": nt, "term_raw": term, "rank": int(rank) if rank else None, "top": top,
                        "department": str(row[m["department"]]).strip() if "department" in m and m["department"] < len(row) else ""})
    # shares: Seller Central writes 30.85 for 30.85 %
    scale = 100.0 if scale_votes and max(scale_votes) > 1.0 else 1.0
    for r in out:
        for t in r["top"]:
            t["click"] /= scale
            t["conv"] /= scale
    meta = {"file": os.path.basename(path), "kind": "tst", "raw_rows": raw, "rows": len(out),
            "period": period[0] if period else None, "meta_line": meta_line,
            "columns": {"term": headers[m["term"]], "rank": headers[m["rank"]] if "rank" in m else None,
                        "positions": len(m["top"])}}
    return {"rows": out, "meta": meta}
