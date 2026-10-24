"""(Copied from TermSweep ts_report.py — keep in sync.) Load an Amazon Ads Sponsored Products search term report (CSV/TSV/XLSX, any console language).

Column names differ between the classic report, the newer reporting center, API-style exports
and localized consoles (DE/FR/IT/ES/NL…). Headers are matched by scored patterns on a
normalized form; anything that cannot be matched can be forced with --map field=Header.
"""
import csv
import io
import os
import re
import unicodedata

from ks_xlsx import read_xlsx


class ReportError(Exception):
    pass


FIELDS = ["term", "campaign", "ad_group", "targeting", "match_type", "impressions", "clicks",
          "spend", "sales", "orders", "units", "cpc", "currency", "date", "start_date", "end_date",
          "portfolio", "country", "keyword_text", "target_expr", "campaign_id", "ad_group_id",
          "keyword_id", "target_id", "bid"]
REQUIRED = ["term", "clicks", "spend", "sales", "orders"]
NUMERIC = ["impressions", "clicks", "spend", "sales", "orders", "units", "cpc"]

# (field, pattern, score). Patterns run on the normalized header (lowercase, no accents,
# punctuation -> space, camelCase split). Higher score wins; EXCLUDE vetoes a field.
PATTERNS = [
    ("term", r"\bcustomer search term\b", 10), ("term", r"\bsearch term\b", 8),
    ("term", r"\bsuchbegriff", 9), ("term", r"\bkundensuchbegriff", 10),
    ("term", r"\bterme de recherche", 9), ("term", r"\btermine di ricerca", 9),
    ("term", r"\btermino de busqueda", 9), ("term", r"\bzoekterm", 9), ("term", r"\bsokterm", 9),
    ("term", r"\bhaslo wyszukiwania|\bfraza wyszukiwania", 9),
    ("campaign", r"\bcampaign name\b", 10), ("campaign", r"\bcampaign\b", 6),
    ("campaign", r"\bkampagnenname\b", 10), ("campaign", r"\bkampagne\b", 6),
    ("campaign", r"\bnom de la campagne\b", 10), ("campaign", r"\bcampagne\b", 6),
    ("campaign", r"\bnome (della )?campagna\b", 10), ("campaign", r"\bcampagna\b", 6),
    ("campaign", r"\bnombre de la campana\b", 10), ("campaign", r"\bcampana\b", 6),
    ("campaign", r"\bcampagnenaam\b", 10), ("campaign", r"\bkampanj", 6), ("campaign", r"\bkampania\b", 6),
    ("ad_group", r"\bad group name\b", 10), ("ad_group", r"\bad group\b", 7),
    ("ad_group", r"\banzeigengruppenname\b", 10), ("ad_group", r"\banzeigengruppe\b", 7),
    ("ad_group", r"\bgroupe d annonces\b", 9), ("ad_group", r"\bgruppo di annunci\b", 9),
    ("ad_group", r"\bgrupo de anuncios\b", 9), ("ad_group", r"\badvertentiegroep", 9),
    ("ad_group", r"\bannonsgrupp", 9), ("ad_group", r"\bgrupa reklam", 9),
    ("targeting", r"^targeting$", 10), ("targeting", r"\btargeting\b", 6), ("targeting", r"^keyword$", 7),
    ("targeting", r"\bausrichtung\b", 9), ("targeting", r"\bciblage\b", 9),
    ("targeting", r"\bsegmentacion\b", 9), ("targeting", r"\btargeting\b", 6),
    ("match_type", r"\bmatch type\b", 10), ("match_type", r"\bubereinstimmungstyp\b", 10),
    ("match_type", r"\bubereinstimmung\b", 7), ("match_type", r"\btype de correspondance\b", 10),
    ("match_type", r"\btipo di corrispondenza\b", 10), ("match_type", r"\btipo de concordancia\b", 10),
    ("match_type", r"\bzoekwoordtype|\bmatchtype\b", 9),
    ("impressions", r"\bimpressions?\b", 9), ("impressions", r"\bimpressionen\b", 9),
    ("impressions", r"\bimpressioni\b", 9), ("impressions", r"\bimpresiones\b", 9),
    ("impressions", r"\bvertoningen\b", 9), ("impressions", r"\bvisningar\b", 9), ("impressions", r"\bwyswietlenia\b", 9),
    ("clicks", r"\bclicks?\b", 9), ("clicks", r"\bklicks?\b", 9), ("clicks", r"\bclics?\b", 9),
    ("clicks", r"\bclic\b", 9), ("clicks", r"\bklikken\b", 9), ("clicks", r"\bklick\b", 8), ("clicks", r"\bklikniecia\b", 9),
    ("spend", r"^spend$", 10), ("spend", r"\bspend\b", 9), ("spend", r"^cost$", 9), ("spend", r"\bcost\b", 5),
    ("spend", r"\bausgaben\b", 9), ("spend", r"\bkosten\b", 6), ("spend", r"\bdepenses?\b", 9),
    ("spend", r"\bspesa\b", 9), ("spend", r"\bspese\b", 8), ("spend", r"\bgastos?\b", 9),
    ("spend", r"\buitgaven\b", 9), ("spend", r"\bkostnad\b", 8), ("spend", r"\bwydatki\b", 9),
    ("sales", r"\btotal sales\b", 10), ("sales", r"\bsales\b", 7), ("sales", r"\bumsatz\b", 8),
    ("sales", r"\bumsatze\b", 8), ("sales", r"\bverkaufe\b", 6), ("sales", r"\bventes\b", 8),
    ("sales", r"\bvendite\b", 8), ("sales", r"\bventas\b", 8), ("sales", r"\bverkopen\b", 8),
    ("sales", r"\bomzet\b", 8), ("sales", r"\bforsaljning", 8), ("sales", r"\bsprzedaz", 8),
    ("orders", r"\btotal orders\b", 10), ("orders", r"\borders?\b", 7), ("orders", r"\bpurchases?\b", 7),
    ("orders", r"\bbestellungen\b", 8), ("orders", r"\bcommandes\b", 8), ("orders", r"\bordini\b", 8),
    ("orders", r"\bpedidos\b", 8), ("orders", r"\bbestellingen\b", 8), ("orders", r"\bbestallningar\b", 8),
    ("orders", r"\bzamowienia\b", 8),
    ("units", r"\btotal units\b", 10), ("units", r"\bunits?\b", 6), ("units", r"\beinheiten\b", 7),
    ("units", r"\bunites\b", 7), ("units", r"\bunita\b", 7), ("units", r"\bunidades\b", 7),
    ("units", r"\beenheden\b", 7), ("units", r"\bunits sold\b", 8),
    ("cpc", r"\bcost per click\b", 10), ("cpc", r"\bcpc\b", 9), ("cpc", r"\bkosten pro klick\b", 10),
    ("cpc", r"\bcout par clic\b", 10), ("cpc", r"\bcosto per clic\b", 10), ("cpc", r"\bcoste por clic\b", 10),
    ("currency", r"\bcurrency\b", 10), ("currency", r"\bwahrung\b", 10), ("currency", r"\bdevise\b", 10),
    ("currency", r"\bvaluta\b", 10), ("currency", r"\bmoneda\b", 10),
    ("start_date", r"\bstart date\b", 10), ("start_date", r"\bstartdatum\b", 10), ("start_date", r"\bdate de debut\b", 10),
    ("start_date", r"\bdata di inizio\b", 10), ("start_date", r"\bfecha de inicio\b", 10),
    ("end_date", r"\bend date\b", 10), ("end_date", r"\benddatum\b", 10), ("end_date", r"\bdate de fin\b", 10),
    ("end_date", r"\bdata di fine\b", 10), ("end_date", r"\bfecha de finalizacion|\bfecha de fin\b", 10),
    ("date", r"^date$", 10), ("date", r"^datum$", 10), ("date", r"^data$", 9), ("date", r"^fecha$", 10),
    ("portfolio", r"\bportfolio", 9),
    ("country", r"^country$", 10), ("country", r"^land$", 9), ("country", r"\bmarketplace\b", 7),
    # 2026 renamed metrics (help G3HEFZYWZF84NPS9) and localized consoles
    ("term", r"\bterme de recherche client\b", 10), ("term", r"\btermine di ricerca del cliente\b", 10),
    ("term", r"\btermino de busqueda del cliente\b", 10),
    ("ad_group", r"\bname der anzeigengruppe\b", 10), ("ad_group", r"\bgroupe de publicites\b", 9),
    ("ad_group", r"\bnom du groupe de publicites\b", 10), ("ad_group", r"\bnome del gruppo di annunci\b", 10),
    ("ad_group", r"\bnombre del grupo de anuncios\b", 10),
    ("campaign", r"\bnome della campagna\b", 10),
    ("match_type", r"\btipo de coincidencia\b", 10),
    ("spend", r"\binversion\b", 9),
    ("sales", r"^sales$", 10), ("sales", r"\b14 day total sales\b", 9), ("sales", r"\bverkaufe\b", 8),
    ("sales", r"\bgesamtsumme der verkaufe\b", 9),
    ("orders", r"\bpurchases? #", 10), ("orders", r"\bkaufe\b", 8), ("orders", r"\bachats?\b", 8),
    ("orders", r"\bacquisti\b", 8), ("orders", r"\bcompras\b", 8), ("orders", r"\bgesamtbestellungen\b", 8),
    ("units", r"\bunits sold\b", 9), ("units", r"\bverkaufte einheiten\b", 9), ("units", r"\bunites vendues\b", 9),
    ("units", r"\bunita vendute\b", 9), ("units", r"\bunidades vendidas\b", 9),
    ("cpc", r"\bcout par clic\b", 10), ("cpc", r"\bcosto per clic\b", 10), ("cpc", r"\bcoste por clic\b", 10),
    # bulk file "SP Search Term Report" tab and bulk exports (carry the IDs)
    ("keyword_text", r"\bkeyword text\b", 10), ("keyword_text", r"\bkeyword text\b", 10),
    ("target_expr", r"\bproduct targeting expression\b", 10),
    ("campaign_id", r"\bcampaign id\b", 10), ("ad_group_id", r"\bad group id\b", 10),
    ("keyword_id", r"\bkeyword id\b", 10), ("target_id", r"\bproduct targeting id\b", 10),
    ("bid", r"^bid$", 10),
    # verified on real exports (amazon.de console 2020-2026, campaign manager UI, third-party tools)
    ("orders", r"\bauftrage\b", 8), ("impressions", r"\bsichtkontakte\b", 9), ("impressions", r"^impr$", 8),
    ("campaign", r"\bkampagnen ?name\b", 10),
    ("term", r"\bubereinstimmendes produkt\b", 7), ("targeting", r"\bproduktausrichtungen?\b", 8),
]

EXCLUDE = {
    "term": r"\bimpression|\brank\b|\bshare\b|\banteil\b",
    "campaign": r"\bid\b|\bbudget|\btype\b|\bstatus\b|\bstate\b|\bbidding\b|\bstrateg|\btyp\b",
    "ad_group": r"\bid\b|\bbid\b|\bdefault\b|\bgebot\b",
    "targeting": r"\btype\b|\bmatch\b|\btyp\b|\bexpression\b|\bid\b",
    "impressions": r"\bshare\b|\brank\b|\btop of search\b|\banteil\b|\bper\b|\bcpm\b|\bcost\b|\bkosten\b|\bviewable\b",
    "clicks": r"\bper click\b|\bthru\b|\bthrough\b|\brate\b|\bctr\b|\bpro klick\b|\bpar clic\b|\bper clic\b|\bpor clic\b|\bklickrate\b|\btaux\b|\bunits?\b|\bsold\b|\bsales\b|\bpurchase|\bacos\b|\broas\b|\bcost\b|\borders?\b",
    "spend": r"\bper\b|\bpro\b|\bacos\b|\bof sales\b|\bumsatzkosten\b|\broas\b|\bpar\b|\bpor\b",
    "sales": r"\bacos\b|\bcost\b|\bkosten\b|\broas\b|\badvertised\b|\bother\b|\bbrand\b|\bhalo\b|\bunits?\b|\beinheiten\b|\brate\b|\bcout\b|\bcosto\b|\bcoste\b|\bbeworben|\bander|\bmarke\b|\brentabilit|\bpromoted\b|\bhalo\b|\bsponsoris|\bpubblicizz|\bpromocionad|\balone\b|\bper\b|\bpro\b",
    "orders": r"\bnew to brand\b|\bunits?\b|\brate\b|\bconversion\b|\bother\b|\badvertised\b|\beinheiten\b|\bkonversion|\bneukunden\b|\bbeworben|\bander|\bper\b|\bpro\b|\bcost\b|\bkosten\b|\bkaufrate\b|\btaux\b|\btasso\b|\bindice\b",
    "units": r"\badvertised\b|\bother\b|\bbeworben|\bander|\bper\b|\bpro\b|\bpromoted\b|\bhalo\b|\bsponsoris|\bpubblicizz|\bpromocionad|\balone\b",
    "target_expr": r"\bresolved\b",
    "keyword_text": r"\bnative\b",
    "cpc": r"\bacos\b",
}

AUTO_TARGETS = {"close-match", "loose-match", "substitutes", "complements", "*",
                "close match", "loose match", "enge ubereinstimmung", "weitgehende ubereinstimmung",
                "ersatzprodukte", "erganzungsprodukte"}
MATCH_MAP = {
    "broad": "broad", "weitgehend": "broad", "weit gefasst": "broad", "large": "broad", "requete large": "broad",
    "generica": "broad", "amplia": "broad", "breed": "broad", "bred": "broad", "szerokie": "broad",
    "phrase": "phrase", "wortgruppe": "phrase", "passend zur wortgruppe": "phrase", "expression": "phrase",
    "frase": "phrase", "woordgroep": "phrase", "fras": "phrase", "fraza": "phrase",
    "exact": "exact", "genau": "exact", "exakt": "exact", "exacte": "exact", "esatta": "exact", "exacta": "exact",
    "exact match": "exact", "exakte ubereinstimmung": "exact", "dokladne": "exact",
}
ASIN_RE = re.compile(r"^b0[0-9a-z]{8}$", re.I)
ASIN_TARGET_RE = re.compile(r'asin(?:-expanded)?\s*=\s*"?([a-z0-9]{10})"?', re.I)


def norm_header(h):
    h = "" if h is None else str(h)
    h = re.sub(r"([a-z])([A-Z])", r"\1 \2", h)          # camelCase -> camel Case
    h = re.sub(r"([A-Za-z])(\d)", r"\1 \2", h)
    h = unicodedata.normalize("NFKD", h)
    h = "".join(ch for ch in h if not unicodedata.combining(ch)).lower()
    h = h.replace("ß", "ss")
    h = re.sub(r"[^a-z0-9#]+", " ", h)
    return re.sub(r"\s+", " ", h).strip()


def norm_text(s):
    """Normalize a search term / keyword for comparisons (keeps umlauts)."""
    s = "" if s is None else str(s)
    s = unicodedata.normalize("NFC", s).lower().strip()
    return re.sub(r"\s+", " ", s)


def map_headers(headers, overrides=None):
    """Return {field: column_index}. overrides = {field: header text} from --map."""
    mapping = {}
    normed = [norm_header(h) for h in headers]
    if overrides:
        for field, header in overrides.items():
            if field not in FIELDS:
                raise ReportError("Unknown field in --map: %s (allowed: %s)" % (field, ", ".join(FIELDS)))
            target = norm_header(header)
            hits = [i for i, n in enumerate(normed) if n == target]
            if not hits:
                raise ReportError('--map %s="%s": no such column. Columns: %s' % (field, header, "; ".join(map(str, headers))))
            mapping[field] = hits[0]
    best = {}
    for i, n in enumerate(normed):
        if not n or i in mapping.values():
            continue
        for field, pat, score in PATTERNS:
            if field in mapping:
                continue
            ex = EXCLUDE.get(field)
            if ex and re.search(ex, n):
                continue
            if re.search(pat, n):
                # prefer the attribution window sellers use (7 day) over 14/30 day columns
                bonus = 0.5 if field in ("sales", "orders", "units") and re.search(r"\b7 ?d(ay)?\b|\b7 tage", n) else 0
                cand = score + bonus
                if field not in best or cand > best[field][0]:
                    best[field] = (cand, i)
    used = set(mapping.values())
    for field, (score, i) in sorted(best.items(), key=lambda kv: -kv[1][0]):
        if i in used:
            continue
        mapping[field] = i
        used.add(i)
    return mapping


# ---------------------------------------------------------------- reading

def _read_rows(path, overrides=None):
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xlsm"):
        try:
            sheets = read_xlsx(path)
        except Exception:  # zipfile.BadZipFile, KeyError, XML errors: a damaged or renamed file
            raise ReportError("%s is not a readable Excel file (damaged or not really .xlsx). Download the report "
                              "again, or export it as .csv." % os.path.basename(path))
        # pick the sheet whose header row maps a search-term column
        for name, rows in sheets:
            hdr_idx = _find_header_row(rows, overrides)
            if hdr_idx is not None:
                return rows[hdr_idx], rows[hdr_idx + 1:], name
        raise ReportError("No sheet with a search term column found in %s (sheets: %s)"
                          % (os.path.basename(path), ", ".join(n for n, _ in sheets)))
    if ext == ".xls":
        raise ReportError("Old .xls format is not supported. Download the report as .xlsx or .csv.")
    with open(path, "rb") as f:
        raw = f.read()
    text = None
    for enc in ("utf-8-sig", "utf-16", "cp1252", "latin-1"):
        try:
            text = raw.decode(enc)
            if enc == "utf-16" and "\x00" in text:
                continue
            break
        except UnicodeDecodeError:
            continue
    sample = text[:20000]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        delim = dialect.delimiter
    except csv.Error:
        delim = "\t" if sample.count("\t") > sample.count(",") else ("," if sample.count(",") >= sample.count(";") else ";")
    rows = list(csv.reader(io.StringIO(text), delimiter=delim))
    hdr_idx = _find_header_row(rows, overrides)
    if hdr_idx is None:
        raise ReportError("No search term column found in %s. First row: %s"
                          % (os.path.basename(path), rows[0] if rows else "(empty file)"))
    return rows[hdr_idx], rows[hdr_idx + 1:], None


def _looks_like_term_export(path, sheet, headers):
    """Tools like Sellerboard export search terms as 'Name' when grouped by search term."""
    normed = [norm_header(h) for h in headers]
    hint = norm_header(os.path.basename(path)) + " " + norm_header(sheet or "")
    termish = re.search(r"search ?terms?|suchbegriff", hint)
    return "name" in normed and bool(termish) and any(re.search(r"\bspend\b|\bausgaben\b|\bkosten\b", n) for n in normed)


def _find_header_row(rows, overrides=None):
    wanted = set(norm_header(h) for h in (overrides or {}).values())
    for i, row in enumerate(rows[:15]):
        cells = [("" if c is None else c) for c in row]
        if wanted and wanted <= set(norm_header(c) for c in cells):
            return i
        m = map_headers(cells, None)
        if "term" in m and ("clicks" in m or "spend" in m):
            return i
        if "spend" in m and "clicks" in m and "name" in [norm_header(c) for c in cells]:
            return i
    return None


def detect_decimal(values, default="."):
    """Vote over raw number strings: ',' (German style), '.' — or `default` when nothing decides."""
    comma = dot = 0
    for v in values:
        if not isinstance(v, str):
            continue
        s = re.sub(r"[^\d.,]", "", v)
        if not s:
            continue
        if re.search(r"\d\.\d{3},\d", s) or re.search(r",\d{1,2}$", s) and "." not in s:
            comma += 1
        elif re.search(r"\d,\d{3}\.\d", s) or re.search(r"\.\d{1,2}$", s) and "," not in s:
            dot += 1
        elif re.search(r",\d+$", s) and "." not in s and not re.search(r",\d{3}$", s):
            comma += 1
    if comma == dot:
        return default
    return "," if comma > dot else "."


def parse_number(v, decimal="."):
    if v is None:
        return 0.0
    if isinstance(v, bool):
        return float(v)
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if s in ("", "-", "—", "–", "n/a", "N/A", "null", "None"):
        return 0.0
    neg = s.startswith("-") or (s.startswith("(") and s.endswith(")"))
    pct = s.endswith("%")
    s = re.sub(r"[^\d.,]", "", s)
    if not s:
        return 0.0
    if decimal == ",":
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", "")
    try:
        x = float(s)
    except ValueError:
        return 0.0
    if pct:
        x = x / 100.0
    return -x if neg else x


def id_str(v):
    """Bulk IDs are long integers; Excel may hand them over as floats."""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def norm_match(m):
    k = norm_header(m)
    if k in MATCH_MAP:
        return MATCH_MAP[k]
    if "target" in k or "predefined" in k:
        return "-"
    for key in ("broad", "phrase", "exact", "weitgehend", "wortgruppe", "genau"):
        if key in k:
            return MATCH_MAP[key]
    return "-"


def target_kind(targeting, match):
    t = norm_text(targeting)
    if match in ("broad", "phrase", "exact"):
        return "keyword"
    if ASIN_TARGET_RE.search(t) or t.startswith("asin") or t.startswith("category"):
        return "product"
    if t in AUTO_TARGETS or norm_header(t) in AUTO_TARGETS:
        return "auto"
    return "auto" if t else "unknown"


def load_report(path, overrides=None):
    """Return dict(rows=[aggregated rows], meta={...}). Raises ReportError."""
    if not os.path.exists(path):
        raise ReportError("File not found: %s" % path)
    headers, data, sheet = _read_rows(path, overrides)
    headers = [("" if h is None else str(h)) for h in headers]
    mapping = map_headers(headers, overrides)
    notes = []
    if "term" not in mapping and _looks_like_term_export(path, sheet, headers):
        mapping["term"] = [norm_header(h) for h in headers].index("name")
        notes.append('Search term column taken from "Name" (export grouped by search term).')
    missing = [f for f in REQUIRED if f not in mapping]
    normed = [norm_header(h) for h in headers]
    if missing and any("conversion" in n for n in normed) and not any(re.search(r"\bsales\b|\bumsatz|\bverkaufe", n) for n in normed):
        raise ReportError("This looks like a Google Ads search terms report. TermSweep reads Amazon Sponsored Products "
                          "search term reports (Amazon Ads console → Reports → Search term).")
    if missing:
        raise ReportError(
            "Could not find column(s) %s. Columns in file: %s. Use --map field=\"Column header\"."
            % (", ".join(missing), "; ".join(h for h in headers if h)))
    # decimal separator per column: some UI exports mix "40,00" (CTR) with 0.57 (spend). Count columns
    # ("1.393" clicks) carry no decimals, so they follow the money columns unless they decide themselves.
    def column(f):
        return [row[mapping[f]] for row in data[:2000] if mapping[f] < len(row)]
    money = [detect_decimal(column(f), None) for f in ("spend", "sales", "cpc", "bid") if f in mapping]
    money = [d for d in money if d]
    decimal = "," if money and money.count(",") > len(money) / 2.0 else "."
    decimals = {f: detect_decimal(column(f), decimal) for f in NUMERIC + ["bid"] if f in mapping}

    def cell(row, field):
        i = mapping.get(field)
        if i is None or i >= len(row):
            return None
        return row[i]

    agg = {}
    dates = []
    currency = marketplace = None
    raw_rows = 0
    for row in data:
        if not row or all(c in (None, "") for c in row):
            continue
        term = cell(row, "term")
        if term is None or str(term).strip() == "":
            continue
        raw_rows += 1
        term_s = str(term).strip()
        if isinstance(term, float) and term.is_integer():
            term_s = str(int(term))
        if term_s == "*":           # detail-page placements without a search query
            continue
        campaign = str(cell(row, "campaign") or "").strip()
        ad_group = str(cell(row, "ad_group") or "").strip()
        targeting = str(cell(row, "targeting") or cell(row, "keyword_text") or cell(row, "target_expr") or "").strip()
        match = norm_match(cell(row, "match_type") or "")
        key = (campaign, ad_group, norm_text(targeting), match, norm_text(term_s))
        rec = agg.get(key)
        if rec is None:
            rec = agg[key] = {"term": norm_text(term_s), "term_raw": term_s, "campaign": campaign,
                              "ad_group": ad_group, "targeting": targeting, "match": match,
                              "kind": target_kind(targeting, match),
                              "impressions": 0.0, "clicks": 0.0, "spend": 0.0, "sales": 0.0,
                              "orders": 0.0, "units": 0.0}
        for f in ("impressions", "clicks", "spend", "sales", "orders", "units"):
            if f in mapping:
                rec[f] += parse_number(cell(row, f), decimals.get(f, decimal))
        for f in ("campaign_id", "ad_group_id", "keyword_id", "target_id"):
            v = cell(row, f)
            if v not in (None, "") and not rec.get(f):
                rec[f] = id_str(v)
        if "bid" in mapping and cell(row, "bid") not in (None, ""):
            rec["bid"] = parse_number(cell(row, "bid"), decimals.get("bid", decimal))
        for f in ("date", "start_date", "end_date"):
            d = cell(row, f)
            if d not in (None, ""):
                dates.append(d)
        if currency is None and cell(row, "currency"):
            currency = str(cell(row, "currency")).strip()
        if marketplace is None and cell(row, "country"):
            marketplace = str(cell(row, "country")).strip()
    rows = list(agg.values())
    currency = currency or _currency_from_marketplace(marketplace)
    dayfirst = _slash_dayfirst(dates, currency)
    dkey = lambda d: _date_key(d, dayfirst)
    for r in rows:
        r["spend"] = abs(r["spend"])
        r["is_asin"] = bool(ASIN_RE.match(r["term"]))
    meta = {"file": os.path.basename(path), "sheet": sheet, "columns": {f: headers[i] for f, i in mapping.items()},
            "decimal": decimal, "raw_rows": raw_rows, "rows": len(rows), "currency": currency,
            "date_from": _date_key(min(dates, key=dkey), dayfirst) if dates else None,
            "date_to": _date_key(max(dates, key=dkey), dayfirst) if dates else None,
            "has_campaign": "campaign" in mapping, "has_ad_group": "ad_group" in mapping,
            "has_match": "match_type" in mapping, "has_ids": "ad_group_id" in mapping and "campaign_id" in mapping,
            "notes": notes}
    if not rows:
        raise ReportError("The report contains no search term rows (%s)." % os.path.basename(path))
    return {"rows": rows, "meta": meta}


_MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
_MONTHS.update({"mär": 3, "mrz": 3, "mai": 5, "okt": 10, "dez": 12, "dic": 12, "ene": 1, "abr": 4, "ago": 8,
                "set": 9, "giu": 6, "lug": 7, "gen": 1, "mag": 5, "ott": 10})


MARKETPLACE_CURRENCY = [(".com.be", "EUR"), ("com.tr", "TRY"), ("com.br", "BRL"), (".sa", "SAR"), (".eg", "EGP"),
                        ("co.uk", "GBP"), ("united kingdom", "GBP"), (".ca", "CAD"), ("canada", "CAD"),
                        ("com.au", "AUD"), ("australia", "AUD"), (".se", "SEK"), ("sweden", "SEK"), (".pl", "PLN"),
                        ("poland", "PLN"), ("polen", "PLN"), ("com.mx", "MXN"), ("co.jp", "JPY"), (".ae", "AED"),
                        ("amazon.com", "USD"), ("united states", "USD"), ("usa", "USD"),
                        (".de", "EUR"), (".fr", "EUR"), (".it", "EUR"), (".es", "EUR"), (".nl", "EUR"),
                        ("deutschland", "EUR"), ("germany", "EUR"), ("frankreich", "EUR"), ("france", "EUR"),
                        ("italien", "EUR"), ("italy", "EUR"), ("spanien", "EUR"), ("spain", "EUR")]


def _currency_from_marketplace(marketplace):
    """Currency from 'Amazon.de' / 'Deutschland' style marketplace or country columns (Sellerboard, console)."""
    m = (marketplace or "").lower()
    for key, cur in MARKETPLACE_CURRENCY:
        if key in m:
            return cur
    return None


def _slash_dayfirst(dates, currency):
    """Order of a/b/yyyy dates: decided by any part > 12, else US = month first, elsewhere day first."""
    for d in dates:
        m = re.match(r"\s*(\d{1,2})/(\d{1,2})/\d{2,4}", str(d)) if isinstance(d, str) else None
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if a > 12:
                return True
            if b > 12:
                return False
    return (currency or "").upper() not in ("USD", "$", "")


def _date_key(d, dayfirst=False):
    """Sort key for the many date spellings found in reports (serials, ISO, US, DE)."""
    if isinstance(d, (int, float)):
        return _serial_to_iso(d)
    s = str(d).strip()
    m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        return "%04d-%02d-%02d" % tuple(int(x) for x in m.groups())
    m = re.match(r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})", s)
    if m:
        d_, mo, y = (int(x) for x in m.groups())
        return "%04d-%02d-%02d" % (y + 2000 if y < 100 else y, mo, d_)
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", s)
    if m:
        a, b, y = (int(x) for x in m.groups())
        mo, d_ = (b, a) if (dayfirst or a > 12) and b <= 12 else (a, b)
        return "%04d-%02d-%02d" % (y + 2000 if y < 100 else y, mo, d_)
    m = re.match(r"([A-Za-zäÄ]{3})[a-zä]*\.? (\d{1,2}),? (\d{4})", s)
    if m and m.group(1).lower() in _MONTHS:
        return "%04d-%02d-%02d" % (int(m.group(3)), _MONTHS[m.group(1).lower()], int(m.group(2)))
    m = re.match(r"(\d{1,2})\.? ([A-Za-zäÄ]{3})[a-zä]*\.? (\d{4})", s)
    if m and m.group(2).lower() in _MONTHS:
        return "%04d-%02d-%02d" % (int(m.group(3)), _MONTHS[m.group(2).lower()], int(m.group(1)))
    return s


def _serial_to_iso(x):
    import datetime
    return (datetime.date(1899, 12, 30) + datetime.timedelta(days=int(x))).isoformat()
