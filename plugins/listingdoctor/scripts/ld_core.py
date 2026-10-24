"""ListingDoctor core: read listings, run the rule checks, score, keyword coverage, Markdown output.

Standard library only (runs on macOS system Python 3.9, Windows, the Cowork sandbox).
"""
import csv
import io
import json
import os
import re
import unicodedata

import ld_rules as R
from ld_xlsx import read_xlsx

# ---------------------------------------------------------------- text helpers
_WORD = re.compile(r"[\w][\w'\-./]*", re.UNICODE)


def norm(s):
    return re.sub(r"\s+", " ", str(s if s is not None else "").replace(" ", " ")).strip()


def fold(s):
    """lower-case, ß→ss, umlauts → ae/oe/ue, strip other accents."""
    s = (s or "").lower().replace("ß", "ss").replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def words(s):
    """words as written (hyphenated compounds stay one word) – used for the title repetition rule."""
    return [w.strip(".-/'") for w in _WORD.findall((s or "").lower()) if w.strip(".-/'")]


def tokens(s):
    """words plus the parts of hyphenated/slashed compounds – used for coverage and duplicate checks."""
    out = []
    for w in words(s):
        out.append(w)
        if "-" in w or "/" in w:
            out.extend(p for p in re.split(r"[-/]", w) if p)
    return out


def stem(w):
    w = fold(w)
    for suf in ("innen", "ern", "en", "er", "es", "e", "s", "n"):
        if len(w) > 4 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def has_phrase(text, phrase, inflect=False):
    """whole-word / whole-phrase match, case-insensitive. inflect=True also accepts German endings on the last
    word ('umweltfreundlichen', 'nachhaltiges')."""
    tail = r"(?:e|en|er|es|em|n|s)?" if inflect and phrase[-1:].isalpha() else ""
    pat = r"(?<![\w])" + re.escape(phrase.lower()) + tail + r"(?![\w])"
    return re.search(pat, (text or "").lower()) is not None


def is_emoji(ch):
    o = ord(ch)
    return any(a <= o <= b for a, b in R.EMOJI_RANGES)


def detect_lang(text):
    ws = set(words(text))
    best, score_ = "en", 0
    for lang, hints in R.LANG_HINTS.items():
        sc = len(ws & hints)
        if sc > score_:
            best, score_ = lang, sc
    return best


# ---------------------------------------------------------------- input
FIELD_ALIASES = {
    "title": ["item_name", "title", "product name", "produktname", "titel", "item-name", "artikelname", "product title"],
    "sku": ["contribution_sku", "item_sku", "sku", "seller-sku", "seller sku", "händler-sku", "verkäufer-sku"],
    "asin": ["asin", "asin1", "merchant_suggested_asin", "amzn1.volt.ca.product_id_value", "product-id", "external_product_id"],
    "brand": ["brand", "brand_name", "marke", "markenname"],
    "description": ["product_description", "description", "produktbeschreibung", "item-description", "beschreibung"],
    "backend": ["generic_keyword", "generic_keywords", "search terms", "search_terms", "suchbegriffe", "backend",
                "backend keywords", "allgemeine schlüsselwörter"],
    "parent_sku": ["child_parent_sku_relationship", "parent_sku", "parent sku", "übergeordnete sku"],
    "parentage": ["parentage_level", "parent_child", "parentage", "abstammungsgrad"],
    "variation_theme": ["variation_theme", "variationsthema", "variationsthemabezeichnung"],
    "color": ["color", "color_name", "farbe"],
    "size": ["size", "size_name", "größe"],
    "category": ["product_type", "feed_product_type", "produkttyp"],
    "status": ["::listing_status", "status"],
    "display_title": ["::title"],
    "highlights": ["title_differentiation", "item_highlights", "item highlights", "item_highlight", "artikel-highlights",
                   "artikel-highlight", "highlights"],
    "manufacturer": ["manufacturer", "hersteller"],
    "gpsr_manufacturer": ["gpsr_manufacturer_reference"],
    "responsible_person": ["dsa_responsible_party_address"],
    "material_composition": ["material_composition", "materialzusammensetzung"],
    "fabric": ["fabric_type", "gewebeart"],
}
GPSR_FIELDS = ("gpsr_manufacturer", "responsible_person")
BULLET_KEYS = ["bullet_point", "bullet point", "bullet", "aufzählungspunkt", "key product features", "stichpunkt"]
IMAGE_KEYS = ["main_product_image_locator", "main_image_url", "main-image-url", "other_product_image_locator",
              "other_image_url", "hauptbild-url"]


def _parse_header(h):
    """'item_name[marketplace_id=..][language_tag=de_DE]#1.value' -> ('item_name', 1, 'value')."""
    h = norm(h).lower()
    idx, suffix = None, ""
    m = re.search(r"#(\d+)(?:\.(\w+))?", h)
    if m:
        idx, suffix = int(m.group(1)), (m.group(2) or "")
    base = re.split(r"[\[#]", h)[0].strip()
    m2 = re.match(r"^(.*?)[\s_]?(\d+)$", base)
    if m2 and not base.isdigit() and m2.group(1):
        base, idx = m2.group(1).strip(" _"), int(m2.group(2))
    return base, idx, suffix


def map_header(headers):
    """returns (fields {field: col}, bullets {n: col}, backends {n: col}, images [col])."""
    fields, bullets, backends, images = {}, {}, {}, []
    for i, h in enumerate(headers):
        if h is None or not str(h).strip():
            continue
        base, idx, suffix = _parse_header(h)
        if not base:
            continue
        if suffix and suffix not in ("value", "name", "parent_sku", "media_location") \
                and base not in ("gpsr_manufacturer_reference", "dsa_responsible_party_address"):
            continue          # e.g. color#1.standardized_values – keep the plain .value column
        if any(base == k or base.startswith(k + " ") for k in BULLET_KEYS):
            bullets.setdefault(idx or (len(bullets) + 1), i)
            continue
        if any(base == k or base.startswith(k) for k in IMAGE_KEYS):
            images.append(i)
            continue
        for field, aliases in FIELD_ALIASES.items():
            if base in aliases:
                if field == "backend":
                    backends.setdefault(idx or (len(backends) + 1), i)
                elif field not in fields:
                    fields[field] = i
                break
    return fields, bullets, backends, images


def _cell(row, i):
    return norm(row[i]) if i is not None and i < len(row) and row[i] is not None else ""


def _row_to_listing(row, fields, bullets, backends, images):
    lst = {f: _cell(row, c) for f, c in fields.items()}
    if not lst.get("title") and lst.get("display_title"):
        lst["title"] = lst["display_title"]
        lst["_title_only"] = True   # report shows Amazon's live title, but none of your attribute values
    lst.pop("display_title", None)
    if lst.get("asin") and not re.fullmatch(r"B0[A-Z0-9]{8}|\d{9}[\dX]", lst["asin"], re.I):
        lst["product_id"] = lst.pop("asin")      # EAN/UPC in the product-id column, not an ASIN
    lst["bullets"] = [_cell(row, bullets[n]) for n in sorted(bullets) if _cell(row, bullets[n])]
    lst["backend"] = " ".join(_cell(row, backends[n]) for n in sorted(backends) if _cell(row, backends[n]))
    if images:
        lst["images"] = [_cell(row, c) for c in images if _cell(row, c)]
        lst["_images_from_file"] = True   # the file lists only images contributed through it
    return lst


REQUIRED_TO_FIELD = {"item_name": "title", "bullet_point": "bullets", "product_description": "description",
                     "generic_keyword": "backend", "title_differentiation": "highlights", "brand": "brand",
                     "fabric_type": "fabric", "material_composition": "material_composition"}


def apply_draft(original, draft):
    """original listing + the fields a draft sets (a partial update leaves the rest as it is)."""
    m = dict(original)
    m.update({k: v for k, v in draft.items() if v not in (None, "", [])})
    attr = original.get("_required_empty_attr") or {}
    if attr:
        filled = {lbl for lbl, base in attr.items() if draft.get(REQUIRED_TO_FIELD.get(base, "-")) not in (None, "", [])}
        m["_required_empty"] = [lbl for lbl in original.get("_required_empty", []) if lbl not in filled]
    if draft.get("backend"):
        m.pop("_no_backend", None)
    if draft.get("title"):
        m.pop("title_submitted", None)  # the new title replaces whatever Amazon shows now
    if any(draft.get(k) not in (None, "", []) for k in ("bullets", "backend", "description")):
        m.pop("_title_only", None)      # the draft now contributes content, so judge it in full
    return m


def is_parent(lst):
    return (lst.get("parentage") or "").strip().lower() in R.PARENT_VALUES


def _table_listings(rows, required=None):
    """pick the header row with the most recognised columns, read the data rows below it."""
    best = None
    for hi, row in enumerate(rows[:12]):
        fields, bullets, backends, images = map_header(row)
        if "title" not in fields:
            continue
        n = len(fields) + len(bullets) + len(backends) + len(images)
        if best is None or n >= best[0]:
            best = (n, hi, fields, bullets, backends, images)
    if not best:
        return [], None
    _, hi, fields, bullets, backends, images = best
    headers = rows[hi]
    req_cols = []
    if required:
        for i, h in enumerate(headers):
            if h and str(h).strip() in required:
                req_cols.append((i, required[str(h).strip()], _parse_header(h)[0]))
    out, resell = [], 0
    for rn, r in enumerate(rows[hi + 1:], hi + 2):
        if not any(str(c or "").strip() for c in r):
            continue
        lst = _row_to_listing(r, fields, bullets, backends, images)
        key = (lst.get("sku") or lst.get("asin") or "").lower()
        if key.startswith("amzn.gr."):
            resell += 1     # Amazon Grade & Resell offer SKU – not a listing you write content for
            continue
        if key in R.EXAMPLE_SKUS or any(k in key for k in ("example", "beispiel")):
            continue
        if (lst.get("title") or "").lower().startswith(("example", "beispiel")):
            continue
        if not (lst.get("title") or lst.get("bullets") or lst.get("sku")):
            continue
        lst["_row"] = rn
        if req_cols:
            empty = [(lbl, base) for i, lbl, base in req_cols if not _cell(r, i)]
            lst["_required_empty"] = list(dict.fromkeys(lbl for lbl, _ in empty))
            lst["_required_empty_attr"] = {lbl: base for lbl, base in empty}
        out.append(lst)
    mkt = None
    for h in headers:
        mm = re.search(r"marketplace_id=(\w+)", str(h or ""))
        if mm:
            mkt = mm.group(1)
            break
    info = {"header_row": hi + 1, "mapped": best[0], "marketplace_id": mkt, "fields": sorted(fields), "bullet_cols": len(bullets),
            "backend_cols": len(backends), "image_cols": len(images), "required_attrs": len(req_cols),
            "skipped_resell_skus": resell}
    return out, info


def _data_definitions(sheets):
    """Amazon templates/category reports carry a 'Data Definitions' sheet: field name + 'Required?'.
    Returns {field_name: local_label} of the required fields."""
    req = {}
    for name, rows in sheets:
        for hi, row in enumerate(rows[:6]):
            hdr = [norm(c).lower() for c in row]
            rcol = next((j for j, h in enumerate(hdr) if any(w in h for w in ("pflicht", "required", "obligatoire", "obbligatorio", "obligatorio"))), None)
            fcol = next((j for j, h in enumerate(hdr) if h in ("feldname", "field name", "nom du champ", "nome campo", "nombre del campo")), None)
            if rcol is None or fcol is None:
                continue
            lcol = fcol + 1
            for r in rows[hi + 1:]:
                if len(r) > rcol and r[fcol] and norm(r[rcol]).lower() in R.REQUIRED_WORDS:
                    f = norm(r[fcol])
                    if f.startswith("::"):
                        continue
                    req[f] = norm(r[lcol]) if len(r) > lcol and r[lcol] else f
            break
        if req:
            break
    return req


def _text_listings(text):
    """'Title: … / Bullet 1: … / Backend: …' blocks, separated by '---'."""
    blocks = re.split(r"\n\s*-{3,}\s*\n", text)
    out = []
    lab = {
        "title": r"(title|titel|item[ _]name|produktname)",
        "asin": r"(asin)", "sku": r"(sku)", "brand": r"(brand|marke)",
        "backend": r"(backend|search terms|suchbegriffe|generic[ _]keywords?)",
        "description": r"(description|beschreibung)",
        "image_count": r"(images|bilder|image count|anzahl bilder)",
        "highlights": r"(highlights|item highlights|artikel-highlights|artikel highlights)",
        "category": r"(product type|produkttyp|category|kategorie)",
    }
    for block in blocks:
        lst = {"bullets": []}
        mode = None
        for line in block.splitlines():
            raw = line.strip()
            if not raw:
                continue
            m = re.match(r"^(?:[*#>\s]*)([A-Za-zÄÖÜäöüß \-_]+?)\s*(\d+)?\s*[:：]\s*(.*)$", raw)
            if m:
                label_, val = m.group(1).strip().lower(), m.group(3).strip()
                if re.fullmatch(r"(bullet|bullet point|bullets|bullet points|aufzählungspunkt|aufzählungspunkte|stichpunkt|key features)", label_):
                    mode = "bullets"
                    if val:
                        lst["bullets"].append(norm(val))
                    continue
                hit = next((f for f, p in lab.items() if re.fullmatch(p, label_)), None)
                if hit:
                    mode = hit
                    lst[hit] = norm(val)
                    continue
            if mode == "bullets" and re.match(r"^([-•*·▪●]|\d+[.)])\s+", raw):
                lst["bullets"].append(norm(re.sub(r"^([-•*·▪●]|\d+[.)])\s+", "", raw)))
            elif mode in ("description", "backend", "highlights") and mode in lst:
                lst[mode] = norm(lst[mode] + " " + raw)
        if "image_count" in lst:
            try:
                lst["image_count"] = int(re.findall(r"\d+", lst["image_count"])[0])
            except (IndexError, ValueError):
                lst.pop("image_count")
        if lst.get("title") or lst["bullets"]:
            out.append(lst)
    return out


def _json_listing(it):
    lst = {}
    for f, aliases in FIELD_ALIASES.items():
        for k in [f] + aliases + [a.replace(" ", "_") for a in aliases]:
            if k in it and it[k] not in (None, ""):
                lst[f] = norm(it[k]) if not isinstance(it[k], (list, dict)) else it[k]
                break
    b = it.get("bullets") or it.get("bullet_points") or [it[k] for k in sorted(it) if k.startswith("bullet_point")]
    lst["bullets"] = [norm(x) for x in (b or []) if norm(x)]
    lst["title"] = norm(it.get("title") or it.get("item_name") or "")
    bk = it.get("backend") or it.get("generic_keywords") or it.get("search_terms") or ""
    lst["backend"] = norm(" ".join(bk) if isinstance(bk, list) else bk)
    if isinstance(it.get("images"), list):
        lst["images"] = [x for x in it["images"] if x]
    if isinstance(it.get("image_count"), (int, float)):
        lst["image_count"] = int(it["image_count"])
    if it.get("title_submitted"):
        lst["title_submitted"] = norm(it["title_submitted"])
    if it.get("public_page") or ("backend" in it and it["backend"] is None):
        lst["_no_backend"] = True   # read from the public product page – backend search terms are not visible
    return lst


def load_listings(path):
    """returns (listings, meta). Supported: .json, .xlsx/.xlsm (category listing report, flat file),
    .csv/.tsv/.txt (table or labelled text), .md"""
    ext = os.path.splitext(path)[1].lower()
    meta = {"file": os.path.basename(path), "format": ext.lstrip(".")}
    if ext == ".json":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        items = data.get("listings", data) if isinstance(data, dict) else data
        if isinstance(items, dict):
            items = [items]
        return [_json_listing(it) for it in items], meta
    if ext in (".xlsx", ".xlsm"):
        sheets = read_xlsx(path)
        required = _data_definitions(sheets)
        best = ([], None, (0, 0))
        for name, rows in sheets:
            lst, info = _table_listings(rows, required)
            rank = (info["mapped"], len(lst)) if lst else (0, 0)
            if rank > best[2]:
                best = (lst, dict(info, sheet=name), rank)
        meta.update(best[1] or {})
        return best[0], meta
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        text = f.read()
    first = text.splitlines()[0] if text.strip() else ""
    if ext in (".csv", ".tsv", ".txt") and ("\t" in first or first.count(",") >= 2 or first.count(";") >= 2):
        delim = "\t" if "\t" in first else (";" if first.count(";") > first.count(",") else ",")
        rows = list(csv.reader(io.StringIO(text), delimiter=delim))
        lst, info = _table_listings(rows)
        if lst:
            meta.update(info)
            return lst, meta
    return _text_listings(text), meta


# ---------------------------------------------------------------- keywords (search term report, SQP, or plain list)
# Advertising search term reports are read with TermSweep's reader (ld_ads.py) and ranked by orders. The lists below
# are the fallback for everything else: Search Query Performance exports, other tables, plain lists.
KW_TERM = ["customer search term", "customersearchterm", "kundensuchbegriff", "suchbegriff", "search term", "searchterm",
           "search query", "searchquery", "suchanfrage", "suchabfrage", "keyword", "term"]   # 'keyword' = targeting: last resort
KW_WEIGHT = ["7 day total orders (#)", "7 tage, bestellungen insgesamt (#)", "7 tage, aufträge gesamt", "14 day total orders (#)",
             "orders", "bestellungen", "gesamtbestellungen", "purchases", "käufe", "search query volume",
             "suchanfragevolumen", "volumen der suchabfrage", "search volume", "suchvolumen", "volume",
             "7 day total sales", "sales", "umsatz", "clicks", "klicks", "impressions", "impressionen"]
KW_DROP = re.compile(r"^(asin=|b0[a-z0-9]{8}$|category=|\*|loose-match|close-match|substitutes|complements)")
KW_ENCODINGS = ("utf-8-sig", "cp1252")


def _num(v):
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace("€", "").replace("$", "").replace("%", "").strip()
    if re.fullmatch(r"-?\d{1,3}(\.\d{3})+(,\d+)?", s) or ("," in s and "." not in s):
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", "")
    return float(s)


def _read_text(path):
    """Text of a CSV/TSV/TXT file: UTF-8 (with or without BOM), UTF-16 (Excel 'Unicode text'), else Windows-1252."""
    with open(path, "rb") as f:
        raw = f.read()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff") or raw[:4096].count(b"\x00") > 10:
        try:
            return raw.decode("utf-16")
        except UnicodeDecodeError:
            pass
    for enc in KW_ENCODINGS:
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")


def _split_camel(h):
    return re.sub(r"([a-z])([A-Z])", r"\1 \2", str(h if h is not None else ""))


def _is_term_header(cell):
    """a header cell naming the search term column ('Customer Search Term', 'Suchbegriff des Kunden', 'searchTerm' …)."""
    h = norm(_split_camel(cell)).lower().strip('"')
    return any(h == k or (k not in ("keyword", "term") and h.startswith(k + " ")) for k in KW_TERM)


def _keywords_from_ads_report(path, top, notes):
    """Sponsored Products search term report (any console language, CSV/XLSX, bulk tab, API/camelCase, Sellerboard):
    read with TermSweep's reader, ranked by orders. None = not a search term report."""
    import ld_ads
    try:
        rep = ld_ads.load_report(path)
    except Exception:   # ReportError (not a search term report) or a damaged file: let the generic reader try
        return None
    agg = {}
    for r in rep["rows"]:
        term = norm(r["term"]).lower()
        if not term or KW_DROP.match(term):
            continue
        a = agg.setdefault(term, [0.0, 0.0, 0.0])
        a[0] += r["orders"]
        a[1] += r["sales"]
        a[2] += r["clicks"]
    sold = sorted(((t, v) for t, v in agg.items() if v[0] > 0), key=lambda kv: (-kv[1][0], -kv[1][1], -kv[1][2], kv[0]))
    if notes is not None:
        if not sold:
            notes.append("%s is a search term report without orders – keyword coverage skipped (search terms without "
                         "orders are not proven demand)." % os.path.basename(path))
        else:
            notes.append("Search term report: %d of %d search terms had orders and are ranked by orders%s." % (
                len(sold), len(agg), "; the top %d are used" % top if len(sold) > top else ""))
    return [(t, v[0]) for t, v in sold[:top]]


def load_keywords(path, top=50, notes=None):
    """returns [(term, weight)] sorted by weight. Reads search term reports (EN/DE, ranked by orders), SQP exports
    or a plain list (most important first). `notes` (a list) receives messages for the user."""
    ext = os.path.splitext(path)[1].lower()
    from_report = _keywords_from_ads_report(path, top, notes)
    if from_report is not None:
        return from_report
    rows = []
    if ext in (".xlsx", ".xlsm"):
        for _, r in read_xlsx(path):
            if len(r) > len(rows):
                rows = r
    else:
        text = _read_text(path)
        lines = [l for l in text.splitlines() if l.strip()]
        first = lines[0] if lines else ""
        headerish = any(_is_term_header(c) for l in lines[:12] for c in re.split(r"[\t;,]", l))
        if ext == ".txt" and not headerish:     # plain list: one term per line, most important first (commas allowed)
            return _plain_list([[l] for l in lines], top, notes, path)
        delim = "\t" if "\t" in first else (";" if first.count(";") > first.count(",") else ",")
        try:
            rows = list(csv.reader(io.StringIO(text.replace("\x00", "")), delimiter=delim))
        except csv.Error:
            return []
        if rows and max(len(r) for r in rows[:5]) == 1:
            return _plain_list(rows, top, notes, path)
    hi, tcol, wcol = None, None, None
    for i, row in enumerate(rows[:12]):
        hdr = [norm(_split_camel(c)).lower() for c in row]
        t = next((j for k in KW_TERM for j, h in enumerate(hdr) if h == k or h.startswith(k)), None)
        if t is not None:
            hi, tcol = i, t
            wcol = next((j for k in KW_WEIGHT for j, h in enumerate(hdr) if h == k or h.startswith(k)), None)
            break
    if hi is None:
        return []
    agg = {}
    for r in rows[hi + 1:]:
        if tcol >= len(r) or not r[tcol]:
            continue
        term = norm(r[tcol]).lower()
        if not term or KW_DROP.match(term):
            continue
        try:
            w = _num(r[wcol]) if wcol is not None and wcol < len(r) and r[wcol] not in (None, "") else 1.0
        except ValueError:
            w = 1.0
        agg[term] = agg.get(term, 0) + w
    ranked = sorted(agg.items(), key=lambda kv: -kv[1])
    if any(w > 0 for _, w in ranked):
        ranked = [kv for kv in ranked if kv[1] > 0]   # search terms without orders are not proven demand
    if notes is not None and len(ranked) > top:
        notes.append("%s has %d search terms; the top %d are used." % (os.path.basename(path), len(ranked), top))
    return ranked[:top]


def _plain_list(rows, top, notes, path):
    terms = []
    for r in rows:
        t = norm(r[0]).lower() if r else ""
        if t and not KW_DROP.match(t) and t not in terms:
            terms.append(t)
    if notes is not None and len(terms) > top:
        notes.append("%s lists %d search terms; the first %d (most important) are used." % (os.path.basename(path), len(terms), top))
    return [(t, float(len(terms) - i)) for i, t in enumerate(terms)][:top]


CAT_LABEL = {"beauty": ("Cosmetics", "Kosmetik"), "electronics": ("Electronics", "Elektronik"), "toys": ("Toys", "Spielzeug"),
             "food": ("Food & supplements", "Lebensmittel/NEM")}


REQ_LABEL = {"designation": ("designation 'Nahrungsergänzungsmittel'", "Bezeichnung „Nahrungsergänzungsmittel“"),
             "daily_dose": ("recommended daily dose", "empfohlene tägliche Verzehrmenge"),
             "do_not_exceed": ("'do not exceed' warning", "Warnhinweis „nicht überschreiten“"),
             "balanced_diet": ("balanced diet statement", "Hinweis auf ausgewogene Ernährung"),
             "children": ("keep out of reach of children", "Hinweis „außerhalb der Reichweite von kleinen Kindern“")}


def detect_categories(lst):
    """category keys of references/category_rules.json that apply: by product type, else by product words in the title."""
    ptype = (lst.get("category") or "").strip().upper()
    title = lst.get("title", "") or ""
    hits = []
    for key, rule in R.CATEGORY_RULES.items():
        if key.startswith("_") or not isinstance(rule, dict):
            continue
        if ptype:
            if ptype in {p.upper() for p in rule.get("product_types", [])}:
                hits.append(key)
        elif any(has_phrase(title, w, inflect=True) for lg in ("de", "en") for w in rule.get("product_words", {}).get(lg, [])):
            hits.append(key)
    return hits


def _brand_refs(rule, text, own_brand, lang_keys):
    """third-party brand names in title/highlights without 'for/kompatibel mit …' before or 'kompatibel' after."""
    low = (text or "").lower()
    own = (own_brand or "").lower()
    cons = [c for lg in lang_keys for c in rule.get("connectors", {}).get(lg, [])]
    bad = []
    for b in rule.get("third_party_brands", []):
        if own and b in own:
            continue
        for m in re.finditer(r"(?<![\w])" + re.escape(b) + r"(?![\w])", low):
            before = " ".join(re.findall(r"[\w'-]+", low[:m.start()])[-6:])   # 'for iPhone 15, Samsung Galaxy' lists
            after = low[m.end():m.end() + 14]
            if any(re.search(r"(?<![\w])" + re.escape(c) + r"(?![\w])", before) for c in cons) or \
                    re.match(r"\s*-?\s*(kompatibel|compatible)", after):
                continue
            bad.append(b)
            break
    return bad


def fibre_composition(text):
    """{'polyester': 93, 'elastan': 7} from '93% Polyester 7% Elastan' / 'Polyester: 93 %' (largest statement wins)."""
    fib = "|".join(re.escape(f) for f in sorted(R.FIBRES, key=len, reverse=True))
    low = (text or "").lower()
    found = {}
    for m in re.finditer(r"(\d+(?:[.,]\d+)?)\s*%\s*(?:[\w]+[\s-])?\w*?(" + fib + r")\b", low):
        found[m.group(2)] = max(found.get(m.group(2), 0), float(m.group(1).replace(",", ".")))
    for m in re.finditer(r"\b(" + fib + r")\s*:?\s*(\d+(?:[.,]\d+)?)\s*%", low):
        found.setdefault(m.group(1), float(m.group(2).replace(",", ".")))
    return found


def coverage(listing, keywords, lang):
    """which keyword terms are covered by title / bullets / backend (all content words present)."""
    stop = R.STOPWORDS.get(lang, R.STOPWORDS["en"])
    fields = {"title": listing.get("title", ""), "highlights": listing.get("highlights", "") or "",
              "bullets": " ".join(listing.get("bullets", [])), "backend": listing.get("backend", "")}
    stems = {f: {stem(w) for w in tokens(t)} for f, t in fields.items()}

    def has(st, s):
        # German compounds: 'laufstirnband' covers 'stirnband'
        return st in s or (len(st) >= 5 and any(st in x for x in s if len(x) > len(st)))

    allst = set().union(*stems.values())
    res = []
    for term, w in keywords:
        toks = [stem(t) for t in words(term) if t not in stop]
        if not toks:
            continue
        where = next((f for f in ("title", "highlights", "bullets", "backend") if all(has(t, stems[f]) for t in toks)), None)
        if where is None and all(has(t, allst) for t in toks):
            where = "spread"
        res.append({"term": term, "weight": w, "where": where, "missing": [t for t in toks if not has(t, allst)]})
    return res


# ---------------------------------------------------------------- messages (en, de)
MSG = {
    "T_LEN": ("Title is {n} characters – Amazon allows max. {max} (since 27 Jul 2026); longer titles get rewritten by Amazon's AI.", "Titel hat {n} Zeichen – Amazon erlaubt seit 27.07.2026 max. {max}; längere Titel schreibt Amazon per KI um."),
    "H_LEN": ("Item Highlights are {n} characters – max. {max}.", "Artikel-Highlights haben {n} Zeichen – max. {max}."),
    "H_EMPTY": ("Item Highlights are empty – {max} searchable characters unused.", "Artikel-Highlights leer – {max} durchsuchbare Zeichen ungenutzt."),
    "H_REPEAT": ("Item Highlights mostly repeat the title: {ev}", "Artikel-Highlights wiederholen großteils den Titel: {ev}"),
    "C_EVID": ("Absolute safety/material claim – keep proof ready: {ev}", "Absolute Sicherheits-/Materialaussage – Nachweis bereithalten: {ev}"),
    "C_SUBJ": ("Subjective superlative – Amazon asks for facts, not rankings: {ev}", "Subjektiver Superlativ – Amazon verlangt Fakten statt Rangordnungen: {ev}"),
    "G_ERR": ("{cat}: claim not allowed without registration/approval: {ev}", "{cat}: Aussage ohne Zulassung/Registrierung nicht erlaubt: {ev}"),
    "G_WARN": ("{cat}: claim needs proof or is restricted: {ev}", "{cat}: Aussage braucht Nachweis oder ist eingeschränkt: {ev}"),
    "G_INFO": ("{cat}: check this wording: {ev}", "{cat}: Formulierung prüfen: {ev}"),
    "G_MISSING": ("{cat}: required statements not found in the text: {ev}", "{cat}: Pflichtangaben im Text nicht gefunden: {ev}"),
    "G_PAT": ("{cat}: {ev}", "{cat}: {ev}"),
    "G_BRAND": ("{cat}: third-party brand in the title without 'for'/'compatible with': {ev}", "{cat}: Fremdmarke im Titel ohne „für“/„kompatibel mit“: {ev}"),
    "G_HINT": ("{cat} – check by hand: {ev}", "{cat} – manuell prüfen: {ev}"),
    "E_GPSR": ("GPSR: no manufacturer / EU responsible person contact in the listing data.", "GPSR: kein Hersteller- bzw. EU-Verantwortlichen-Kontakt in den Listingdaten."),
    "E_FIBRE": ("Textile without a visible fibre composition in % (share per fibre, descending, EU fibre names).", "Textil ohne sichtbare Faserzusammensetzung in % (Anteil je Faser, absteigend, EU-Faserbezeichnungen)."),
    "E_FIBRE2": ("Fibre composition incomplete: {ev} (sum {n} %).", "Faserangabe unvollständig: {ev} (Summe {n} %)."),
    "E_FIBRE3": ("Fibre names not allowed in the EU: {ev}", "In der EU unzulässige Faserbezeichnung: {ev}"),
    "B_MANY": ("{n} bullet points – Amazon shows only {rec}.", "{n} Aufzählungspunkte – Amazon zeigt nur {rec}."),
    "T_SHORT": ("Title is only {n} characters – room for product type, key attribute and use.", "Titel hat nur {n} Zeichen – Platz für Produktart, Hauptmerkmal und Einsatz ungenutzt."),
    "T_CHAR": ("Title contains forbidden characters: {ev}", "Titel enthält verbotene Zeichen: {ev}"),
    "T_CHAR2": ("Title contains discouraged characters: {ev}", "Titel enthält unerwünschte Zeichen: {ev}"),
    "T_REPEAT": ("Words used more than twice in the title: {ev}", "Wörter mehr als 2× im Titel: {ev}"),
    "T_CAPS": ("ALL-CAPS words in the title: {ev}", "Wörter in GROSSBUCHSTABEN im Titel: {ev}"),
    "T_BRAND": ("Title does not start with the brand ({ev}).", "Titel beginnt nicht mit der Marke ({ev})."),
    "T_EMPTY": ("Title is missing.", "Titel fehlt."),
    "T_DUPL": ("Same title as {ev}.", "Gleicher Titel wie {ev}."),
    "T_REWRITTEN": ("The page shows a different, shorter title than the {n}-character title on file – most likely Amazon's AI replacement. On file: “{ev}…”", "Die Seite zeigt einen anderen, kürzeren Titel als den hinterlegten ({n} Zeichen) – vermutlich Amazons KI-Ersatz. Hinterlegt: „{ev}…“"),
    "B_COUNT": ("{n} bullet points – use {rec}.", "{n} Aufzählungspunkte – {rec} nutzen."),
    "B_LONG": ("Bullet {i} has {n} characters (guideline ≤ {max}).", "Aufzählungspunkt {i} hat {n} Zeichen (Richtwert ≤ {max})."),
    "B_TOOLONG": ("Bullet {i} has {n} characters – over the field limit {max}.", "Aufzählungspunkt {i} hat {n} Zeichen – über dem Feldlimit {max}."),
    "B_SHORT": ("Bullet {i} is too short ({n} characters).", "Aufzählungspunkt {i} ist zu kurz ({n} Zeichen)."),
    "B_LOWER": ("Bullet {i} starts with a lower-case letter.", "Aufzählungspunkt {i} beginnt klein."),
    "B_CHAR": ("Bullet {i} contains special characters/emojis: {ev}", "Aufzählungspunkt {i} enthält Sonderzeichen/Emojis: {ev}"),
    "B_DUP": ("Bullets {ev} are (almost) identical.", "Aufzählungspunkte {ev} sind (fast) gleich."),
    "B_END": ("Bullet {i} ends with punctuation – the style guide asks for none.", "Aufzählungspunkt {i} endet mit Satzzeichen – laut Styleguide ohne Schlusspunkt."),
    "B_CAPS": ("Bullet {i} is written in capitals.", "Aufzählungspunkt {i} ist in Großbuchstaben geschrieben."),
    "K_BYTES": ("Backend search terms are {n} bytes – limit {max}; over it Amazon may ignore the whole field.", "Backend-Suchbegriffe haben {n} Bytes – Limit {max}; darüber ignoriert Amazon ggf. das ganze Feld."),
    "K_EMPTY": ("Backend search terms are empty – {max} bytes of free ranking room unused.", "Backend-Suchbegriffe leer – {max} Bytes Ranking-Platz ungenutzt."),
    "K_LOW": ("Backend search terms use only {n} of {max} bytes.", "Backend-Suchbegriffe nutzen nur {n} von {max} Bytes."),
    "K_DUPTB": ("Backend repeats words already in title/bullets: {ev}", "Backend wiederholt Wörter aus Titel/Bullets: {ev}"),
    "K_DUP": ("Backend repeats words: {ev}", "Backend enthält Wörter doppelt: {ev}"),
    "K_PUNCT": ("Backend contains commas/punctuation – spaces are enough.", "Backend enthält Kommas/Satzzeichen – Leerzeichen genügen."),
    "K_SUBJ": ("Subjective/temporary words in backend: {ev}", "Subjektive/zeitlich begrenzte Wörter im Backend: {ev}"),
    "K_BRAND": ("Backend contains a brand name or ASIN: {ev}", "Backend enthält Markenname oder ASIN: {ev}"),
    "D_LEN": ("Description has {n} characters – max. {max}.", "Beschreibung hat {n} Zeichen – max. {max}."),
    "D_HTML": ("Description contains HTML tags: {ev}", "Beschreibung enthält HTML-Tags: {ev}"),
    "C_PROMO": ("Promotional claim not allowed on Amazon: {ev}", "Werbeaussage auf Amazon nicht erlaubt: {ev}"),
    "C_PROMO2": ("Risky sales wording: {ev}", "Riskante Verkaufsformulierung: {ev}"),
    "C_HEALTH": ("Health/biocide claim needs proof or registration: {ev}", "Gesundheits-/Biozid-Aussage braucht Nachweis/Registrierung: {ev}"),
    "C_ECO": ("Generic environmental claim – banned in the EU without proof (EmpCo, from 27 Sep 2026): {ev}", "Pauschale Umweltaussage – in der EU ohne Nachweis verboten (EmpCo, ab 27.09.2026): {ev}"),
    "C_CONTACT": ("Contact data / URL in the listing: {ev}", "Kontaktdaten / URL im Listing: {ev}"),
    "C_PLACE": ("Placeholder text: {ev}", "Platzhaltertext: {ev}"),
    "C_ASIN": ("Mentions an ASIN: {ev}", "Nennt eine ASIN: {ev}"),
    "A_REQ": ("Required attributes empty: {ev}", "Pflichtattribute leer: {ev}"),
    "A_BRAND": ("Brand is missing.", "Marke fehlt."),
    "A_LIVE": ("The file holds only Amazon's live title – bullets, backend and attributes are not your contribution; only the title was checked.", "Die Datei enthält nur Amazons Live-Titel – Bullets, Backend und Attribute stammen nicht von dir; nur der Titel wurde geprüft."),
    "I_MAIN": ("No main image.", "Kein Hauptbild."),
    "I_FILE": ("No image URLs in this file – the live page may still have images.", "Keine Bild-URLs in dieser Datei – die Live-Seite kann trotzdem Bilder haben."),
    "I_COUNT": ("Only {n} images – Amazon shows up to 9; use at least {rec}.", "Nur {n} Bilder – Amazon zeigt bis zu 9; mindestens {rec} nutzen."),
    "W_MISS": ("Top search terms not covered anywhere: {ev}", "Wichtige Suchbegriffe nirgends abgedeckt: {ev}"),
    "W_WEAK": ("Top search terms only in backend/bullets, not in the title: {ev}", "Wichtige Suchbegriffe nur in Backend/Bullets, nicht im Titel: {ev}"),
}
FIX = {
    "T_LEN": ("Shorten to ≤ {max} characters: brand + product type + key attribute + variant; move the rest into Item Highlights (≤ 125).", "Auf ≤ {max} Zeichen kürzen: Marke + Produktart + Hauptmerkmal + Variante; den Rest in die Artikel-Highlights (≤ 125) verschieben."),
    "H_LEN": ("Cut to ≤ 125 characters: material, use, size/age – no promo.", "Auf ≤ 125 Zeichen kürzen: Material, Einsatz, Größe/Alter – keine Werbung."),
    "H_EMPTY": ("Fill the field (category listing report column 'title_differentiation'): material, use case, size/age range.", "Feld füllen (Kategorie-Angebotsbericht, Spalte „title_differentiation“ / Artikel-Highlight): Material, Einsatz, Größe/Alter."),
    "H_REPEAT": ("Use the highlights for facts not in the title (material, use, fit, what's included).", "Highlights für Fakten nutzen, die nicht im Titel stehen (Material, Einsatz, Passform, Lieferumfang)."),
    "C_EVID": ("Keep a test report/certificate; otherwise rephrase as a measurable fact.", "Prüfbericht/Zertifikat bereithalten, sonst als messbaren Fakt formulieren."),
    "C_SUBJ": ("Replace with the fact behind it (material, weight, measurement, test).", "Durch den Fakt dahinter ersetzen (Material, Gewicht, Maß, Test)."),
    "G_ERR": ("Remove the claim, or keep it only with the registration/approval it requires (see rules.md section 10).", "Aussage entfernen oder nur mit der nötigen Zulassung/Registrierung verwenden (rules.md Abschnitt 10)."),
    "G_WARN": ("Keep proof ready or rephrase as a measurable fact (see rules.md section 10).", "Nachweis bereithalten oder als messbaren Fakt formulieren (rules.md Abschnitt 10)."),
    "G_INFO": ("Check the wording against the category rules (rules.md section 10).", "Formulierung mit den Kategorie-Regeln abgleichen (rules.md Abschnitt 10)."),
    "G_MISSING": ("Add the statements (bullet, description or the matching attribute).", "Angaben ergänzen (Bullet, Beschreibung oder passendes Attribut)."),
    "G_PAT": ("See rules.md section 10 for the rule and its source.", "Regel und Quelle: rules.md Abschnitt 10."),
    "G_BRAND": ("Name other brands only as compatibility: 'for iPhone 15', 'kompatibel mit Samsung Galaxy'.", "Fremdmarken nur als Kompatibilität nennen: „für iPhone 15“, „kompatibel mit Samsung Galaxy“."),
    "G_HINT": ("These items cannot be checked from the text; tick them off in Seller Central.", "Diese Punkte lassen sich nicht aus dem Text prüfen; in Seller Central abhaken."),
    "E_GPSR": ("Link manufacturer and EU responsible person in Seller Central (Manage your compliance) or fill the GPSR columns – ignore if already linked account-wide.", "Hersteller und EU-Verantwortliche Person in Seller Central verknüpfen (Compliance verwalten) oder GPSR-Spalten füllen – ignorieren, falls kontoweit verknüpft."),
    "E_FIBRE": ("Add the fibre composition in % (descending, EU fibre names) to a bullet or the material composition attribute.", "Faserzusammensetzung in % (absteigend, EU-Faserbezeichnungen) in einen Bullet oder das Attribut Materialzusammensetzung schreiben."),
    "E_FIBRE2": ("State all fibres so the shares add up to 100 %.", "Alle Fasern angeben, sodass die Anteile 100 % ergeben."),
    "E_FIBRE3": ("Use the EU fibre names of Reg. (EU) 1007/2011 Annex I (e.g. 'viscose (bamboo)', 'elastane').", "EU-Faserbezeichnungen nach VO (EU) 1007/2011 Anhang I verwenden (z. B. „Viskose (Bambus)“, „Elasthan“)."),
    "B_MANY": ("Merge the extra bullets into the first five.", "Zusätzliche Aufzählungspunkte in die ersten fünf einarbeiten."),
    "T_SHORT": ("Add product type, key attribute and variant (aim for 55–75 characters).", "Produktart, Hauptmerkmal und Variante ergänzen (Ziel 55–75 Zeichen)."),
    "T_CHAR": ("Remove the characters (allowed only as part of the brand name).", "Zeichen entfernen (nur als Teil des Markennamens erlaubt)."),
    "T_CHAR2": ("Replace with words or commas.", "Durch Wörter oder Kommas ersetzen."),
    "T_REPEAT": ("Use each word max. twice; move synonyms to backend search terms.", "Jedes Wort max. 2×; Synonyme ins Backend verschieben."),
    "T_CAPS": ("Write in title case; capitals only for brand names/abbreviations.", "Normal schreiben; Großbuchstaben nur für Marke/Abkürzungen."),
    "T_BRAND": ("Start the title with the brand name.", "Titel mit dem Markennamen beginnen."),
    "T_EMPTY": ("Write a title.", "Titel schreiben."),
    "T_DUPL": ("Make each title unique – add the variant (colour, size, pack size).", "Jeden Titel eindeutig machen – Variante ergänzen (Farbe, Größe, Packungsgröße)."),
    "T_REWRITTEN": ("Write your own title within 75 characters (and review Amazon's suggestion in Seller Central) so you control the wording.", "Eigenen Titel mit ≤ 75 Zeichen hinterlegen (und Amazons Vorschlag in Seller Central prüfen) – sonst bestimmt Amazon den Wortlaut."),
    "B_COUNT": ("Write 5 bullets: benefit first, then the fact (size, material, use, care, what's included).", "5 Bullets schreiben: Nutzen zuerst, dann Fakt (Maße, Material, Einsatz, Pflege, Lieferumfang)."),
    "B_LONG": ("Cut to ≤ 255 characters – one idea per bullet.", "Auf ≤ 255 Zeichen kürzen – eine Aussage je Bullet."),
    "B_TOOLONG": ("Split or cut – the field rejects longer text.", "Aufteilen oder kürzen – das Feld lehnt längeren Text ab."),
    "B_SHORT": ("Add a concrete fact or benefit.", "Konkreten Fakt oder Nutzen ergänzen."),
    "B_LOWER": ("Start with a capital letter.", "Mit Großbuchstaben beginnen."),
    "B_CHAR": ("Remove emojis and special characters (™ ® © € … etc.).", "Emojis und Sonderzeichen (™ ® © € … usw.) entfernen."),
    "B_DUP": ("Replace the duplicate with a new fact (size, material, care, what's included).", "Doppelten Bullet durch neuen Fakt ersetzen (Maße, Material, Pflege, Lieferumfang)."),
    "B_END": ("Remove the final full stop.", "Schlusspunkt entfernen."),
    "B_CAPS": ("Only a short heading in capitals, then normal text.", "Nur kurze Überschrift in Großbuchstaben, dann normaler Text."),
    "K_BYTES": ("Cut to ≤ 249 bytes (umlauts count 2 bytes): drop words already in title/bullets first.", "Auf ≤ 249 Bytes kürzen (Umlaute = 2 Bytes): zuerst Wörter aus Titel/Bullets streichen."),
    "K_EMPTY": ("Fill with synonyms, other languages, uses and misspellings not in title/bullets.", "Mit Synonymen, Fremdsprache, Einsatzzwecken, Schreibvarianten füllen, die nicht in Titel/Bullets stehen."),
    "K_LOW": ("Add synonyms, uses and target groups not yet in the listing.", "Synonyme, Einsatzzwecke und Zielgruppen ergänzen, die noch fehlen."),
    "K_DUPTB": ("Delete these words from the backend – they are indexed already.", "Diese Wörter aus dem Backend löschen – sie sind schon indexiert."),
    "K_DUP": ("Keep each word once.", "Jedes Wort nur einmal."),
    "K_PUNCT": ("Separate words with spaces only.", "Wörter nur mit Leerzeichen trennen."),
    "K_SUBJ": ("Remove – these words are not indexed or not allowed.", "Entfernen – nicht indexiert bzw. nicht erlaubt."),
    "K_BRAND": ("Remove brand names and ASINs from search terms.", "Markennamen und ASINs aus den Suchbegriffen entfernen."),
    "D_LEN": ("Cut to ≤ 2000 characters.", "Auf ≤ 2000 Zeichen kürzen."),
    "D_HTML": ("Use plain text (line breaks only where the template allows).", "Reinen Text verwenden (Umbrüche nur wo die Vorlage es erlaubt)."),
    "C_PROMO": ("Delete the claim – describe facts instead.", "Aussage löschen – stattdessen Fakten beschreiben."),
    "C_PROMO2": ("Rephrase as a fact or remove.", "Als Fakt umformulieren oder entfernen."),
    "C_HEALTH": ("Remove unless you hold the registration/approval; describe the material instead.", "Entfernen, außer Zulassung liegt vor; stattdessen Material beschreiben."),
    "C_ECO": ("Replace with a specific, provable fact (e.g. '80% recycled polyester, GRS certified') or remove.", "Durch konkreten, belegbaren Fakt ersetzen (z. B. „80 % recyceltes Polyester, GRS-zertifiziert“) oder entfernen."),
    "C_CONTACT": ("Remove URLs, e-mail addresses and phone numbers.", "URLs, E-Mail-Adressen und Telefonnummern entfernen."),
    "C_PLACE": ("Replace with real content.", "Durch echten Inhalt ersetzen."),
    "C_ASIN": ("Remove ASINs from customer-facing text.", "ASINs aus sichtbaren Texten entfernen."),
    "A_REQ": ("Fill these fields – missing required attributes can suppress the listing or block uploads.", "Diese Felder füllen – fehlende Pflichtattribute können das Listing unterdrücken oder Uploads blockieren."),
    "A_BRAND": ("Enter the brand exactly as registered (or 'Generic' for unbranded goods).", "Marke genau wie registriert eintragen (bei No-Name-Ware „Generic“)."),
    "A_LIVE": ("Check the live page by ASIN, or contribute your own content with a full update.", "Live-Seite per ASIN prüfen oder eigene Inhalte per Vollaktualisierung beisteuern."),
    "I_MAIN": ("Add a main image: pure white background (RGB 255,255,255), product fills ≥ 85 %, ≥ 1000 px for zoom.", "Hauptbild ergänzen: rein weißer Hintergrund (RGB 255,255,255), Produkt füllt ≥ 85 %, ≥ 1000 px für Zoom."),
    "I_COUNT": ("Add infographic, size/fit, lifestyle, detail and packaging images.", "Infografik-, Größen-/Passform-, Lifestyle-, Detail- und Verpackungsbild ergänzen."),
    "I_FILE": ("Check the live page by ASIN (listingdoctor check B0…) for image count.", "Bildanzahl auf der Live-Seite per ASIN prüfen (listingdoctor check B0…)."),
    "W_MISS": ("Work the terms into title (most important), bullets or backend.", "Begriffe in Titel (wichtigste), Bullets oder Backend einbauen."),
    "W_WEAK": ("Move the highest-converting term into the title.", "Den stärksten Begriff in den Titel holen."),
}
AREA_ORDER = {"compliance": 0, "attributes": 1, "title": 2, "highlights": 3, "keywords": 4, "images": 5, "backend": 6,
              "bullets": 7, "description": 8, "eu": 9}
SEV_ORDER = {"error": 0, "warning": 1, "info": 2}
IMAGE_CHECKLIST = (
    ["Main image: pure white background, product only, fills ≥ 85 % of the frame",
     "No text, logos, badges or watermarks on the main image",
     "At least 1000 px on the longest side (enables zoom), 2000 px recommended",
     "6–9 images: infographic, size/fit, lifestyle in use, detail/material, what's included",
     "Each variant (colour/size) has its own main image",
     "No 'best seller', 'Amazon's choice' or rating badges in any image"],
    ["Hauptbild: rein weißer Hintergrund, nur das Produkt, füllt ≥ 85 % des Bildes",
     "Kein Text, Logo, Siegel oder Wasserzeichen auf dem Hauptbild",
     "Mindestens 1000 px an der längsten Seite (Zoom), empfohlen 2000 px",
     "6–9 Bilder: Infografik, Größe/Passform, Lifestyle im Einsatz, Detail/Material, Lieferumfang",
     "Jede Variante (Farbe/Größe) hat ihr eigenes Hauptbild",
     "Keine „Bestseller“-, „Amazon's Choice“- oder Bewertungs-Badges in Bildern"],
)


def _issue(lang, area, code, sev, field="", ev="", **kw):
    li = 1 if lang == "de" else 0
    kw.setdefault("ev", ev)
    msg = MSG[code][li].format(**kw)
    if field and area == "compliance":
        msg += " (%s)" % field
    fixkw = {k: v for k, v in kw.items() if k == "max"}
    return {"area": area, "code": code, "severity": sev, "field": field, "evidence": str(ev),
            "message": msg, "fix": FIX[code][li].format(**fixkw) if fixkw else FIX[code][li], "_lang": li, "_kw": kw}


# ---------------------------------------------------------------- checks
def check_listing(lst, lang=None, brand=None, keywords=None, has_brand_field=False, eu=None, ui=None):
    """eu: True/False = EU marketplace (GPSR, textile checks); None = decide from the language (de/fr/it/es → EU)."""
    title = lst.get("title", "") or ""
    highlights = lst.get("highlights", "") or ""
    bullets = lst.get("bullets", []) or []
    backend = lst.get("backend", "") or ""
    desc = lst.get("description", "") or ""
    lang = lang or detect_lang(" ".join([title] + bullets + [desc]))
    ui = ui if ui in ("de", "en") else ("de" if lang == "de" else "en")   # message language (report), not listing language
    brand = brand or lst.get("brand") or ""
    stop = R.STOPWORDS.get(lang, R.STOPWORDS["en"])
    parent = is_parent(lst)
    bb = len(backend.encode("utf-8"))
    category = (lst.get("category") or "").strip().lower()
    title_max = R.TITLE_MAX_MEDIA if category in R.MEDIA_PRODUCT_TYPES else R.TITLE_MAX
    if eu is None:
        eu = lang in ("de", "fr", "it", "es", "nl", "pl", "sv")
    iss = []
    add = lambda *a, **k: iss.append(_issue(ui, *a, **k))

    # --- title
    if not title:
        add("title", "T_EMPTY", "error")
    else:
        if len(title) > title_max:
            add("title", "T_LEN", "error", n=len(title), max=title_max)
        elif len(title) < R.TITLE_SHORT and not parent:
            add("title", "T_SHORT", "warning", n=len(title))
        brand_chars = set(brand)
        bad = sorted({c for c in title if c in R.TITLE_FORBIDDEN_CHARS and c not in brand_chars} | {c for c in title if is_emoji(c)})
        if bad:
            add("title", "T_CHAR", "error", ev=" ".join(bad))
        bad2 = sorted({c for c in title if c in R.TITLE_DISCOURAGED_CHARS and c not in brand_chars})
        if bad2:
            add("title", "T_CHAR2", "warning", ev=" ".join(bad2))
        cnt = {}
        for w in words(title):
            if w in stop or len(w) < 2 or re.fullmatch(r"[\d.,x×]+", w):
                continue
            cnt[w] = cnt.get(w, 0) + 1
        rep = ["%s (%d×)" % (w, c) for w, c in cnt.items() if c > R.TITLE_MAX_REPEAT]
        if rep:
            add("title", "T_REPEAT", "error", ev=", ".join(rep))
        caps = [w for w in re.findall(r"\b[A-ZÄÖÜ]{4,}\b", title)
                if fold(w) not in fold(brand) and w not in ("USB", "LED", "UV", "XXL", "BPA", "UVP", "HDMI", "LCD")]
        if caps:
            add("title", "T_CAPS", "warning", ev=", ".join(sorted(set(caps))[:6]))
        if brand and brand.lower() not in ("generic", "generisch") and not fold(title).startswith(fold(brand)):
            add("title", "T_BRAND", "info", ev=brand)

    title_only = bool(lst.get("_title_only"))
    if lst.get("title_submitted") and len(lst["title_submitted"]) > title_max >= len(title):
        add("title", "T_REWRITTEN", "warning", n=len(lst["title_submitted"]), ev=lst["title_submitted"][:90])
    if title_only and not parent:
        add("attributes", "A_LIVE", "info")
    if not parent and not title_only:
        # --- item highlights (only when the input has the field)
        if "highlights" in lst:
            if not highlights:
                add("highlights", "H_EMPTY", "warning", max=R.HIGHLIGHTS_MAX)
            else:
                if len(highlights) > R.HIGHLIGHTS_MAX:
                    add("highlights", "H_LEN", "error", n=len(highlights), max=R.HIGHLIGHTS_MAX)
                tw = {stem(w) for w in tokens(title) if w not in stop}
                hw = [stem(w) for w in tokens(highlights) if w not in stop and len(w) > 2]
                if len(hw) >= 4 and sum(1 for w in hw if w in tw) / len(hw) > 0.6:
                    add("highlights", "H_REPEAT", "info", ev=highlights[:60] + ("…" if len(highlights) > 60 else ""))

        # --- bullets
        if len(bullets) > R.BULLET_MAX_SHOWN:
            add("bullets", "B_MANY", "info", n=len(bullets), rec=R.BULLET_MAX_SHOWN)
        if len(bullets) < R.BULLET_RECOMMENDED:
            add("bullets", "B_COUNT", "warning" if bullets else "error", n=len(bullets), rec=R.BULLET_RECOMMENDED)
        seen = []
        for i, b in enumerate(bullets, 1):
            n = len(b)
            if n > R.BULLET_HARD_MAX:
                add("bullets", "B_TOOLONG", "error", i=i, n=n, max=R.BULLET_HARD_MAX)
            elif n > R.BULLET_SOFT_MAX:
                add("bullets", "B_LONG", "warning", i=i, n=n, max=R.BULLET_SOFT_MAX)
            elif n < R.BULLET_MIN_CHARS:
                add("bullets", "B_SHORT", "warning", i=i, n=n)
            if b[:1].islower():
                add("bullets", "B_LOWER", "info", i=i)
            bad = sorted({c for c in b if c in R.BULLET_FORBIDDEN_CHARS or is_emoji(c)})
            if bad:
                add("bullets", "B_CHAR", "error", i=i, ev=" ".join(bad))
            if b.rstrip()[-1:] in (".", "!"):
                add("bullets", "B_END", "info", i=i)
            letters = [c for c in b if c.isalpha()]
            if len(letters) > 25 and sum(c.isupper() for c in letters) / len(letters) > 0.7:
                add("bullets", "B_CAPS", "warning", i=i)
            key = {stem(w) for w in tokens(b) if w not in stop}
            for j, k2 in seen:
                if key and len(key & k2) / max(1, len(key | k2)) > 0.8:
                    add("bullets", "B_DUP", "warning", ev="%d & %d" % (j, i))
            seen.append((i, key))

        # --- backend
        if lst.get("_no_backend"):
            pass
        elif not backend:
            add("backend", "K_EMPTY", "warning", max=R.BACKEND_MAX_BYTES)
        else:
            if bb > R.BACKEND_MAX_BYTES:
                add("backend", "K_BYTES", "error", n=bb, max=R.BACKEND_MAX_BYTES)
            elif bb < 150:
                add("backend", "K_LOW", "info", n=bb, max=R.BACKEND_MAX_BYTES)
            vis = {stem(w) for w in tokens(title + " " + highlights + " " + " ".join(bullets)) if w not in stop}
            bw = [w for w in words(backend) if w not in stop]
            dup_tb = sorted({w for w in bw if stem(w) in vis})
            if dup_tb:
                add("backend", "K_DUPTB", "warning", ev=" ".join(dup_tb[:12]) + (" …" if len(dup_tb) > 12 else ""))
            c2 = {}
            for w in bw:
                c2[stem(w)] = c2.get(stem(w), 0) + 1
            d2 = sorted({w for w in bw if c2[stem(w)] > 1})
            if d2:
                add("backend", "K_DUP", "info", ev=" ".join(d2[:10]))
            if re.search(r"[,;|]", backend):
                add("backend", "K_PUNCT", "info")
            subj = [w for w in R.BACKEND_SUBJECTIVE.get(lang, R.BACKEND_SUBJECTIVE["en"]) if has_phrase(backend, w)]
            if subj:
                add("backend", "K_SUBJ", "warning", ev=", ".join(subj))
            br = re.findall(r"\bB0[A-Z0-9]{8}\b", backend, re.I)
            if brand and brand.lower() not in ("generic", "generisch") and has_phrase(backend, brand.lower()):
                br.append(brand)
            if br:
                add("backend", "K_BRAND", "warning", ev=", ".join(br))

        # --- description
        if len(desc) > R.DESCRIPTION_MAX:
            add("description", "D_LEN", "warning", n=len(desc), max=R.DESCRIPTION_MAX)
        tags = sorted(set(t.lower() for t in re.findall(r"</?([a-zA-Z]+)[^>]*>", desc)))
        if tags:
            add("description", "D_HTML", "info" if tags == ["br"] else "warning", ev=", ".join("<%s>" % t for t in tags[:6]))

        # --- images (only when the input says something about images)
        n_img = len(lst["images"]) if isinstance(lst.get("images"), list) else lst.get("image_count")
        if n_img is not None:
            if lst.get("_images_from_file"):
                if n_img == 0:
                    add("images", "I_FILE", "info")
            elif n_img == 0:
                add("images", "I_MAIN", "error")
            elif n_img < R.IMAGES_RECOMMENDED:
                add("images", "I_COUNT", "warning" if n_img < 4 else "info", n=n_img, rec=R.IMAGES_RECOMMENDED)

        # --- attributes (required fields from the template's Data Definitions sheet)
        req = lst.get("_required_empty") or []
        if req:
            add("attributes", "A_REQ", "error" if len(req) > 1 else "warning",
                ev=", ".join(req[:8]) + (" …" if len(req) > 8 else ""))
        # --- EU: GPSR contact data and textile fibre composition
        if eu:
            if all(k in lst for k in GPSR_FIELDS) and not any(lst.get(k) for k in GPSR_FIELDS):
                add("eu", "E_GPSR", "info")
            textile = category in R.TEXTILE_PRODUCT_TYPES or (
                not category and any(w in R.TEXTILE_WORDS for w in words(title)))
            if textile:
                comp = fibre_composition(" ".join([lst.get("material_composition") or "", lst.get("fabric") or "",
                                                   title, highlights, desc] + bullets))
                low_all = " ".join([title, highlights, desc, lst.get("fabric") or ""] + bullets).lower()
                bad_names = sorted({w for w in re.findall(r"\d+\s*%\s*([\w-]+)", low_all)
                                    if w in R.NON_EU_FIBRES or (w.startswith("bambus") and "viskose" not in w)})
                if bad_names:
                    add("eu", "E_FIBRE3", "warning", ev=", ".join("%s → %s" % (w, R.NON_EU_FIBRES.get(w, "Viskose (Bambus)"))
                                                                  for w in bad_names))
                if not comp:
                    add("eu", "E_FIBRE", "warning")
                elif not 98 <= sum(comp.values()) <= 102:
                    add("eu", "E_FIBRE2", "info", ev=", ".join("%g %% %s" % (v, k) for k, v in comp.items()), n="%g" % sum(comp.values()))
    req_names = " ".join(lst.get("_required_empty") or []).lower()
    if has_brand_field and not title_only and not lst.get("_no_backend") and not lst.get("brand") and "marke" not in req_names and "brand" not in req_names:
        add("attributes", "A_BRAND", "warning")

    # --- compliance over all text fields
    fields = [("title", title), ("highlights", highlights)] + [("bullet %d" % i, b) for i, b in enumerate(bullets, 1)] + \
             [("description", desc), ("backend", backend)]
    langs = [lang] if lang in ("en", "de") else []
    if "en" not in langs:
        langs.append("en")
    done = set()
    for fname, txt in fields:
        if not txt:
            continue
        low = txt.lower()
        for lg in langs:
            for code, lists, sev in (("C_PROMO", R.PROMO_STRONG, "error"), ("C_HEALTH", R.HEALTH, "warning"),
                                     ("C_ECO", R.ECO, "warning"), ("C_PROMO2", R.PROMO_SOFT, "warning"),
                                     ("C_EVID", R.EVIDENCE, "info"), ("C_SUBJ", R.SUBJECTIVE, "warning")):
                if fname == "backend" and code in ("C_ECO", "C_EVID", "C_SUBJ"):
                    continue
                for term in lists.get(lg, []):
                    key = (code, stem(term) if lg == "de" else term, fname)   # 'nachhaltig' + 'nachhaltige' = one finding
                    if key in done or not has_phrase(low, term, inflect=(lg == "de" and code != "C_PROMO2")):
                        continue
                    if code == "C_PROMO2" and any(term in t and has_phrase(low, t) for t in R.PROMO_STRONG.get(lg, [])):
                        continue   # 'guaranteed' inside 'satisfaction guaranteed' is already an error
                    done.add(key)
                    add("compliance", code, sev, field=fname, ev=term)
        if fname != "backend":
            m = re.search(r"(https?://\S+|www\.\S+|\b[\w.+-]+@[\w-]+\.[a-z]{2,}\b|(?<![\w.,])\+?\d{2,4}[ /-]\d{3,}[ /-]?\d{3,}(?![\w.,]))", txt, re.I)
            if m:
                add("compliance", "C_CONTACT", "error", field=fname, ev=m.group(0)[:40])
            a = re.search(r"\bB0[A-Z0-9]{8}\b", txt)
            if a:
                add("compliance", "C_ASIN", "warning", field=fname, ev=a.group(0))
        ph = next((p for p in R.PLACEHOLDERS if norm(low) == p or (p in ("tbd", "tba", "lorem ipsum", "placeholder", "platzhalter", "todo") and has_phrase(low, p))), None)
        if ph is None:
            mb = re.search(r"\[[A-ZÄÖÜ][A-ZÄÖÜ _]{2,}[^\]]*\]", txt)
            ph = mb.group(0) if mb else None
        if ph:
            add("compliance", "C_PLACE", "error", field=fname, ev=ph)

    # --- category rules (beauty, electronics, toys, food) from references/category_rules.json
    cats = [] if (parent or title_only) else detect_categories(lst)
    if cats:
        market = "EU" if eu else "US"
        vis = [("title", title), ("highlights", highlights)] + [("bullet %d" % i, b) for i, b in enumerate(bullets, 1)] + \
              [("description", desc)]
        blob = " ".join(t for _, t in vis)
        ptype = (lst.get("category") or "").strip().upper()
        # EU store: German lists as given, English lists as warnings; US store: English lists
        lists = [("de", None), ("en", "warning")] if eu else [("en", None)]
        for cat in cats:
            rule = R.CATEGORY_RULES[cat]
            lbl = CAT_LABEL.get(cat, (cat, cat))[1 if ui == "de" else 0]
            blocks = [rule] + [c for c in rule.get("conditional", []) if any(has_phrase(blob, w) for w in c.get("if_any", []))]
            active = {c.get("id") for c in blocks[1:]}
            for blk in blocks:
                for sev in ("error", "warning"):
                    for lg, force in lists:
                        for term in blk.get(sev, {}).get(lg, []):
                            if ("cat", term) in done:
                                continue
                            for fname, txt in vis + ([("backend", backend)] if cat == "food" and sev == "error" else []):
                                if txt and has_phrase(txt, term, inflect=(lg == "de")):
                                    done.add(("cat", term))
                                    sv = force or sev
                                    add("compliance", "G_ERR" if sv == "error" else "G_WARN", sv, field=fname, ev=term, cat=lbl)
                                    break
            for pat in rule.get("patterns", []):
                if market not in pat.get("markets", [market]):
                    continue
                if pat.get("only_if_conditional") and pat["only_if_conditional"] not in active:
                    continue
                if pat.get("only_product_types") and ptype not in {x.upper() for x in rule.get(pat["only_product_types"], [])}:
                    continue
                if pat.get("also_ok_if_attribute_filled") and any(lst.get(k) for k in pat["also_ok_if_attribute_filled"]):
                    continue
                if pat.get("if_regex") and not re.search(pat["if_regex"], blob, re.I):
                    continue
                if not re.search(pat["regex"], blob, re.I):
                    continue
                if pat.get("requires_missing"):
                    fl = 0 if pat.get("requires_missing_case_sensitive") else re.I
                    if re.search(pat["requires_missing"], blob, fl):
                        continue
                add("compliance", "G_PAT", pat.get("severity", "info"), ev=pat.get("message_de" if ui == "de" else "message", pat["id"]),
                    cat=lbl, rid=pat["id"])
            req = rule.get("required_phrases")
            if req and market in req.get("markets", [market]) and \
                    (not req.get("only_product_types") or ptype in {x.upper() for x in rule.get(req["only_product_types"], [])}):
                miss = [REQ_LABEL.get(k, (k, k))[1 if ui == "de" else 0] for k, rx in req.get("de_regex", {}).items()
                        if not re.search(rx, blob, re.I)]
                if miss:
                    add("compliance", "G_MISSING", req.get("severity", "warning"), ev=", ".join(miss), cat=lbl)
            brc = rule.get("brand_reference_check")
            if brc:
                bad = _brand_refs(brc, title + " " + highlights, brand, ["de", "en"] if eu else ["en"])
                if bad:
                    add("compliance", "G_BRAND", brc.get("severity", "error"), field="title", ev=", ".join(bad), cat=lbl)
            hint = rule.get("required_info_hint_de" if ui == "de" else "required_info_hint")
            if hint:
                add("compliance", "G_HINT", "info", ev=hint[:300], cat=lbl)

    # --- keyword coverage
    cov = None
    if keywords and not parent and not title_only:
        cov = coverage(lst, keywords, lang)
        top = cov[:15]
        miss = [c["term"] for c in top if c["where"] is None]
        weak = [c["term"] for c in top[:5] if c["where"] in ("backend", "bullets", "spread")]  # not in title/highlights
        if miss:
            add("keywords", "W_MISS", "warning" if len(miss) < 4 else "error", ev=", ".join(miss[:6]))
        if weak:
            add("keywords", "W_WEAK", "info", ev=", ".join(weak[:4]))

    iss.sort(key=lambda x: (SEV_ORDER[x["severity"]], AREA_ORDER[x["area"]]))
    return {"lang": lang, "parent": parent, "issues": iss, "score": score(iss), "coverage": cov,
            "stats": {"title_chars": len(title), "title_max": title_max, "highlights_chars": len(highlights),
                      "bullets": len(bullets), "backend_bytes": None if lst.get("_no_backend") else bb,
                      "max_bullet_chars": max([len(b) for b in bullets] or [0]), "description_chars": len(desc),
                      "images": (len(lst["images"]) if isinstance(lst.get("images"), list) else lst.get("image_count"))}}


def score(issues):
    lost = {}
    for i in issues:
        lost[i["area"]] = lost.get(i["area"], 0) + R.SEVERITY_POINTS[i["severity"]]
    total = sum(min(v, R.AREA_CAP.get(a, 20)) for a, v in lost.items())
    s = max(0, 100 - total)
    grade = "A" if s >= 90 else "B" if s >= 80 else "C" if s >= 70 else "D" if s >= 55 else "F"
    return {"points": s, "grade": grade, "lost_by_area": lost}


def label(lst, i):
    return lst.get("sku") or lst.get("asin") or ("#%d" % i)


def check_batch(listings, meta=None, keywords=None, lang=None, brand=None, include_parents=False, eu=None, ui=None):
    """lang = language of the listings (None: detect per listing); ui = language of the messages (None: listing language)."""
    """check every listing and add cross-listing checks (identical titles).
    Returns ([{"label", "title", "listing", "result"}], skipped_parent_count) in input order."""
    meta = meta or {}
    has_brand = "brand" in (meta.get("fields") or []) or any(l.get("brand") for l in listings)
    if eu is None and meta.get("marketplace_id"):
        eu = meta["marketplace_id"] in R.EU_MARKETPLACES
    out, skipped = [], 0
    for i, l in enumerate(listings, 1):
        r = check_listing(l, lang=lang, brand=brand, keywords=keywords, has_brand_field=has_brand, eu=eu, ui=ui)
        if r["parent"] and not include_parents:
            skipped += 1
            continue
        out.append({"label": label(l, i), "title": l.get("title", ""), "listing": l, "result": r})
    by_title = {}
    for o in out:
        t = fold(o["title"])
        if t and not o["result"]["parent"]:
            by_title.setdefault(t, []).append(o)
    for group in by_title.values():
        if len(group) < 2:
            continue
        for o in group:
            others = [g["label"] for g in group if g is not o]
            u2 = ui if ui in ("de", "en") else ("de" if o["result"]["lang"] == "de" else "en")
            o["result"]["issues"].append(_issue(u2, "title", "T_DUPL", "warning",
                                                ev=", ".join(others[:3]) + (" …" if len(others) > 3 else "")))
            o["result"]["issues"].sort(key=lambda x: (SEV_ORDER[x["severity"]], AREA_ORDER[x["area"]]))
            o["result"]["score"] = score(o["result"]["issues"])
    return out, skipped


def top_fixes(issues, n=5):
    """one line per problem type, most severe first; findings of the same type are merged."""
    groups, order = {}, []
    for i in issues:
        if i["code"] not in groups:
            groups[i["code"]] = []
            order.append(i["code"])
        groups[i["code"]].append(i)
    out = []
    for code in order:
        g = groups[code]
        first = g[0]
        if len(g) == 1:
            out.append(first)
        else:
            merged = dict(first)
            tpl = MSG[code][first["_lang"]]
            kw = {}
            for k in first["_kw"]:
                if k == "ev" and first["area"] == "compliance":
                    vals = [x["evidence"] + (" (%s)" % x["field"] if x["field"] else "") for x in g]
                else:
                    vals = [str(x["_kw"].get(k, "")) for x in g]
                vals = [v for v in dict.fromkeys(vals) if v]
                kw[k] = ("; " if k == "ev" else ", ").join(vals)
            try:
                merged["message"] = tpl.format(**kw)
            except (KeyError, IndexError):
                merged["message"] = first["message"] + " (+%d)" % (len(g) - 1)
            merged["count"] = len(g)
            out.append(merged)
        if len(out) >= n:
            break
    return out


# ---------------------------------------------------------------- Markdown
def render_md(results, lang="en", top=5, per_listing=10, edition="free", meta=None, skipped_parents=0, checklist=True):
    de = lang == "de"
    L = (lambda en, d: d if de else en)
    out = []
    n = len(results)
    full = [r for r in results if not r["listing"].get("_title_only")] if results and "listing" in results[0] else results
    avg = round(sum(r["result"]["score"]["points"] for r in full) / len(full)) if full else 0
    only_t = L(" (title only)", " (nur Titel)")
    errs = sum(1 for r in results for i in r["result"]["issues"] if i["severity"] == "error")
    out.append("## ListingDoctor – " + L("listing check", "Listing-Check"))
    out.append("")
    line = L("**%d listing(s)** · average score **%d/100** · %d rule violations (errors)" % (n, avg, errs),
             "**%d Listing(s)** · Durchschnitt **%d/100** · %d Regelverstöße (Fehler)" % (n, avg, errs))
    if skipped_parents:
        line += L(" · %d parent rows skipped" % skipped_parents, " · %d Eltern-Zeilen übersprungen" % skipped_parents)
    out.append(line)
    if meta and meta.get("required_attrs"):
        out.append("")
        out.append(L("Required attributes checked against the template's Data Definitions (%d fields)." % meta["required_attrs"],
                     "Pflichtattribute gegen die Datendefinitionen der Vorlage geprüft (%d Felder)." % meta["required_attrs"]))
    out.append("")
    if n > 1:
        out.append("| " + " | ".join(["Listing", "Score", L("Errors", "Fehler"), L("Warnings", "Warnungen"),
                                       L("Title chars", "Titel-Zeichen"), "Bullets", L("Backend bytes", "Backend-Bytes")]) + " |")
        out.append("|---|---|---|---|---|---|---|")
        for r in sorted(results, key=lambda r: r["result"]["score"]["points"]):
            res, st = r["result"], r["result"]["stats"]
            e = sum(1 for i in res["issues"] if i["severity"] == "error")
            w = sum(1 for i in res["issues"] if i["severity"] == "warning")
            out.append("| %s | %d (%s) | %d | %d | %d | %d | %s |" % (r["label"] + (only_t if r.get("listing", {}).get("_title_only") else ""),
                                                                 res["score"]["points"], res["score"]["grade"],
                                                                 e, w, st["title_chars"], st["bullets"],
                                                                 "–" if st["backend_bytes"] is None else st["backend_bytes"]))
        out.append("")
    shown = sorted(results, key=lambda r: r["result"]["score"]["points"])[:per_listing]
    sevt = {"error": L("error", "Fehler"), "warning": L("warning", "Warnung"), "info": "info"}
    for r in shown:
        res = r["result"]
        out.append("### %s – %d/100 (%s)%s" % (r["label"], res["score"]["points"], res["score"]["grade"],
                                              only_t if r.get("listing", {}).get("_title_only") else ""))
        if r.get("title"):
            out.append("> " + r["title"][:200])
        out.append("")
        fixes = top_fixes(res["issues"], top) if top else top_fixes(res["issues"], 999)
        if not fixes:
            out.append(L("No rule violations found.", "Keine Regelverstöße gefunden."))
            out.append("")
            continue
        out.append("| # | " + L("Severity", "Schwere") + " | Problem | " + L("Fix", "Lösung") + " |")
        out.append("|---|---|---|---|")
        for k, i in enumerate(fixes, 1):
            out.append("| %d | %s | %s | %s |" % (k, sevt[i["severity"]], i["message"].replace("|", "/"), i["fix"].replace("|", "/")))
        rest = len(res["issues"]) - sum(i.get("count", 1) for i in fixes)
        if rest > 0 and edition == "free":
            out.append("")
            out.append(L("*+ %d more findings – full list, rewritten drafts and flat-file export in ListingDoctor Pro.*" % rest,
                         "*+ %d weitere Befunde – vollständige Liste, umgeschriebene Entwürfe und Flatfile-Export in ListingDoctor Pro.*" % rest))
        if res.get("coverage"):
            cv = res["coverage"][:15]
            ok = sum(1 for c in cv if c["where"])
            out.append("")
            out.append(L("Keyword coverage (top %d terms): **%d/%d** covered." % (len(cv), ok, len(cv)),
                         "Keyword-Abdeckung (Top %d Begriffe): **%d/%d** abgedeckt." % (len(cv), ok, len(cv))))
        out.append("")
    if len(results) > per_listing:
        out.append(L("*Details shown for the %d weakest listings.*" % per_listing, "*Details für die %d schwächsten Listings.*" % per_listing))
        out.append("")
    if checklist:
        out.append("### " + L("Image checklist (check by eye)", "Bild-Checkliste (manuell prüfen)"))
        for c in IMAGE_CHECKLIST[1 if de else 0]:
            out.append("- [ ] " + c)
        out.append("")
    return "\n".join(out)
