"""Read supplier offers (MargenCheck template, supplier Excel/CSV, JSON) into normalized positions.

Column headers are recognized in German and English, including typical proforma-invoice headers
("Item No.", "Unit Price", "PRICE/$", "Qty", "MOQ", "N.W.", "Carton size", "PCS/CTN", "CBM").
Anything that cannot be recognized can be mapped explicitly with --map feld="Spaltenname".
"""
import csv
import io
import json
import os
import re

from mc_tables import InputError, zoll_lookup
import mc_xlsx

FIELDS = {
    "pos": ["pos", "position", "nr", "no", "itemno", "item", "artnr", "artikelnr", "artikelnummer", "modelno",
            "model", "style", "styleno", "ref", "code", "itemcode", "productno"],
    "sku": ["sku", "msku", "sellersku"],
    "name": ["name", "bezeichnung", "beschreibung", "description", "desc", "product", "produkt", "productname",
             "artikel", "itemname", "goodsdescription", "titel", "title"],
    "ek": ["ek", "ekpreis", "einkaufspreis", "preis", "price", "unitprice", "priceusd", "pricepcs", "priceperpcs",
           "fob", "fobprice", "fobusd", "exw", "exwprice", "cost", "stueckpreis", "stuckpreis", "preisjestueck", "usd",
           "ekjeeinheit", "einzelpreis", "ekusd", "ekeur", "ekcny", "unitpriceusd", "unitpriceeur"],
    "ek_je_teil": ["ekjeteil", "preisjeteil"],
    "waehrung": ["waehrung", "wahrung", "currency", "cur", "whg"],
    "menge": ["menge", "qty", "quantity", "anzahl", "bestellmenge", "orderqty", "orderquantity", "stueck", "stuck"],
    "moq": ["moq", "mindestmenge", "minorder", "minimumorder", "minqty"],
    "vk_brutto": ["vk", "vkbrutto", "verkaufspreis", "preisbrutto", "sellingprice", "retailprice", "zielpreis",
                  "targetprice", "amazonpreis", "vkamazon", "vkeur", "listprice"],
    "vk_shopify": ["vkshopify", "shopifypreis", "shoppreis"],
    "masse": ["masse", "mase", "packmass", "packmas", "abmessungen", "dimensions", "dimension", "size", "productsize",
              "packingsize", "packagesize", "verpackungsmass", "lxbxh", "lwh", "packmasscm", "massecm", "groesse"],
    "laenge": ["laenge", "lange", "length", "lcm", "laengecm"],
    "breite": ["breite", "width", "wcm", "bcm", "breitecm"],
    "hoehe": ["hoehe", "hohe", "height", "hcm", "hoehecm", "dicke", "thickness"],
    "gewicht": ["gewicht", "gewichtg", "weight", "weightg", "nw", "netweight", "unitweight", "stueckgewicht",
                "gewichtkg", "weightkg", "nwkg", "nwg"],
    "stueck_je_karton": ["stueckjekarton", "pcsctn", "qtyctn", "pcspercarton", "unitspercarton", "packing",
                         "stkkarton", "pcsperctn", "ctnqty"],
    "karton_masse": ["kartonmass", "kartonmasse", "cartonsize", "ctnsize", "meas", "measurement", "cartondimensions",
                     "cartonmeas", "outercarton"],
    "karton_kg": ["kartonkg", "kartongewicht", "gw", "grossweight", "ctngw", "cartonweight", "gwkg"],
    "cbm_gesamt": ["cbm", "volume", "volumen", "totalcbm", "m3"],
    "kategorie": ["kategorie", "category", "amazonkategorie", "gebuehrenkategorie"],
    "hs_code": ["hs", "hscode", "hstariff", "kn", "kncode", "zolltarifnummer", "taric", "customscode", "hsnr"],
    "zollsatz": ["zollsatz", "zoll", "dutyrate", "duty", "zollprozent"],
    "retourenquote": ["retourenquote", "retouren", "returnrate", "retoure"],
    "monatsabsatz": ["monatsabsatz", "absatz", "absatzmonat", "salespermonth", "unitspermonth", "monthlysales",
                     "stkmonat"],
    "teile_je_einheit": ["teilejeeinheit", "setgroesse", "setsize", "packof", "stueckjeset", "teile"],
    "incoterm": ["incoterm", "incoterms", "lieferbedingung", "terms"],
    "fba_gebuehr": ["fba", "fbagebuehr", "fbafee", "fbaversandgebuehr"],
    "staffel": ["staffel", "staffelpreise", "tierprices", "pricebreaks", "mengenstaffel"],
    "notiz": ["notiz", "bemerkung", "remark", "remarks", "note", "notes", "kommentar"],
    "annahmen": ["annahmen", "geschaetzt", "estimated", "schaetzung"],
    "urteil": ["urteil", "bewertung", "verdict"],
    "begruendung": ["begruendung", "grund", "reason"],
    "gefahrgut": ["gefahrgut", "dangerous", "hazmat"],
    "fracht_je_einheit": ["frachtjeeinheit", "freightperunit", "frachtstk"],
    "tacos_plan": ["tacos", "tacosplan"],
    "retourengebuehr_je_retoure": ["retourengebuehr"],
    "zusatzkosten_je_einheit": ["zusatzkosten", "extracost", "pruefkosten"],
}
NUMERIC = {"ek", "ek_je_teil", "menge", "moq", "vk_brutto", "vk_shopify", "laenge", "breite", "hoehe", "gewicht",
           "stueck_je_karton", "karton_kg", "cbm_gesamt", "zollsatz", "retourenquote", "monatsabsatz",
           "teile_je_einheit", "fba_gebuehr", "fracht_je_einheit", "tacos_plan", "retourengebuehr_je_retoure",
           "zusatzkosten_je_einheit"}
RATES = {"zollsatz", "retourenquote", "tacos_plan"}
PREIS = {"ek", "ek_je_teil", "vk_brutto", "vk_shopify", "fba_gebuehr", "fracht_je_einheit", "retourengebuehr_je_retoure",
         "zusatzkosten_je_einheit"}
PREIS_NAME = {"ek": "EK", "ek_je_teil": "EK je Teil", "vk_brutto": "VK", "vk_shopify": "VK Shopify", "fba_gebuehr": "FBA-Gebühr",
              "fracht_je_einheit": "Fracht je Einheit", "retourengebuehr_je_retoure": "Retourengebühr",
              "zusatzkosten_je_einheit": "Zusatzkosten", "staffel": "Staffelpreis"}
_MEHRDEUTIG = re.compile(r"-?[1-9]\d{0,2},\d{3}")  # '1,780': decimal comma (1.78) or thousands (1780)?


def norm_header(h):
    h = str(h or "").strip().lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss"), ("³", "3")):
        h = h.replace(a, b)
    return re.sub(r"[^a-z0-9]", "", h)


def parse_num(v, int_like=False, dezimal_komma=None):
    """'$0.40', '0,40', '1.234,56', '1,234.56', '12 %', '50pcs' -> float (percent stays as written).

    int_like: quantities -- '1.000' and '1,000' mean one thousand.
    dezimal_komma: True = a single comma is always the decimal separator ('1,780' -> 1.78), for price cells of a
    table that writes decimal commas; None = guess from the value alone ('1,780' -> 1780).
    """
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    m = re.search(r"-?\d[\d.,' ]*", s)
    if not m:
        return None
    t = m.group(0).replace(" ", "").replace("'", "").rstrip(".,")
    if "," in t and "." in t:
        if t.rfind(",") > t.rfind("."):
            t = t.replace(".", "").replace(",", ".")
        else:
            t = t.replace(",", "")
    elif "," in t:
        head, tail = t.rsplit(",", 1)
        if dezimal_komma and not int_like and t.count(",") == 1:
            t = head + "." + tail
        elif t.count(",") > 1 or (len(tail) == 3 and head not in ("", "0", "-0") and (int_like or len(head) <= 3)):
            t = t.replace(",", "")
        else:
            t = head + "." + tail
    elif "." in t:
        head, tail = t.rsplit(".", 1)
        if t.count(".") > 1 or (int_like and len(tail) == 3 and head not in ("", "0")):
            t = t.replace(".", "")
    try:
        return float(t)
    except ValueError:
        return None


def zahlformat(recs):
    """Decimal separator of a whole offer, judged from its price cells: True = decimal comma ('0,40', '1.234,56'),
    False = decimal point ('0.40', '1,234.56'), None = no evidence. Hand-overs from SupplierPilot <1.0.1 wrote
    prices as '1,780' (= 1.78)."""
    komma = punkt = 0
    for r in recs:
        if not isinstance(r, dict):
            continue
        if "supplierpilot" in str(r.get("notiz") or "").lower():
            komma += 1
        werte = [r.get(k) for k in PREIS]
        for part in re.split(r"[|;]", str(r.get("staffel") or "")):
            m = re.match(r"\s*[\d.,]+\s*[:=]\s*\$?\s*([\d.,]+)", part)
            if m:
                werte.append(m.group(1))
        for v in werte:
            if v is None or isinstance(v, (int, float)):
                continue
            s = re.sub(r"[^\d.,]", "", str(v))
            if re.fullmatch(r"\d+,\d{1,2}|0,\d+|\d{1,3}(\.\d{3})+,\d+", s):
                komma += 1
            elif re.fullmatch(r"\d+\.\d{1,2}|0\.\d+|\d+\.\d{4,}|\d{1,3}(,\d{3})+\.\d+", s):
                punkt += 1
    if komma and not punkt:
        return True
    if punkt and not komma:
        return False
    return None


def parse_preis(v, dezimal_komma=None, feld="ek", hinweise=None):
    """Price cell. Without evidence from the table, '1,780' is read as 1.78 – unit prices above 1,000 are rare, and
    reading 1.78 as 1780 silently turned every position into NEIN – and the reading is reported in hinweise."""
    if dezimal_komma is None and isinstance(v, str) and "." not in v and _MEHRDEUTIG.fullmatch(re.sub(r"[^\d,\-]", "", v.strip())):
        x = parse_num(v, dezimal_komma=True)
        if hinweise is not None:
            hinweise.append("%s „%s“ als %s gelesen (Komma mit drei Nachkommastellen ist mehrdeutig) – bitte prüfen; "
                            "Preise am besten mit Punkt oder zwei Nachkommastellen angeben"
                            % (PREIS_NAME.get(feld, feld), v.strip(), ("%.3f" % x).rstrip("0").replace(".", ",")))
        return x
    return parse_num(v, dezimal_komma=dezimal_komma)


def parse_rate(v):
    x = parse_num(v)
    if x is None:
        return None
    return x / 100.0 if (x > 1.0 or "%" in str(v)) else x


def parse_dims(v):
    """'25x18x4', '25 × 18 × 4 cm', '250*180*40mm', '25/18/4' -> [25, 18, 4] in cm, else None."""
    if v is None:
        return None
    s = str(v).lower().replace(",", ".")
    nums = re.findall(r"\d+(?:\.\d+)?", s)
    if len(nums) < 3:
        return None
    d = [float(x) for x in nums[:3]]
    if "mm" in s:
        d = [x / 10.0 for x in d]
    elif re.search(r"\bm\b", s) and max(d) < 3:
        d = [x * 100.0 for x in d]
    return d


def parse_weight_g(v, header=""):
    if v is None:
        return None
    s = str(v).lower()
    x = parse_num(v)
    if x is None:
        return None
    h = norm_header(header)
    if "kg" in s or (h.endswith("kg") and "g" not in s.replace("kg", "")) or h in ("nw", "nwkg", "weightkg", "gewichtkg") and x < 30:
        return x * 1000.0
    return x


def parse_staffel(v, dezimal_komma=None, hinweise=None):
    """'500:0.40|1000:0.36' or '500=0,40; 1000=0,36' -> [(500, 0.40), (1000, 0.36)]."""
    if v is None or v == "":
        return []
    if isinstance(v, list):
        return sorted((float(a), float(b)) for a, b in v)
    out = []
    for part in re.split(r"[|;]", str(v)):
        if not part.strip():
            continue
        m = re.match(r"\s*([\d.,]+)\s*[:=]\s*\$?\s*([\d.,]+)", part)
        if m:
            out.append((parse_num(m.group(1), int_like=True), parse_preis(m.group(2), dezimal_komma, "staffel", hinweise)))
    return sorted(out)


def detect_currency(text, default):
    s = str(text or "")
    if "$" in s or "usd" in s.lower():
        return "USD"
    if "€" in s or "eur" in s.lower():
        return "EUR"
    if "¥" in s or "rmb" in s.lower() or "cny" in s.lower():
        return "CNY"
    return default


# ---------------------------------------------------------------- reading files
def read_table(path, sheet=None):
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xlsm"):
        sheets = mc_xlsx.read_xlsx(path)
        if not sheets:
            raise InputError("%s has no sheets" % path)
        if sheet:
            for name, rows in sheets:
                if name == sheet:
                    return rows
            raise InputError("sheet %s not found (available: %s)" % (sheet, ", ".join(n for n, _ in sheets)))
        best = max(sheets, key=lambda s: _header_score(s[1])[0])
        return best[1]
    if ext in (".csv", ".txt", ".tsv"):
        with io.open(path, encoding="utf-8-sig", errors="replace") as f:
            data = f.read()
        first = data.split("\n", 1)[0]
        delim = max([";", ",", "\t"], key=lambda d: first.count(d))
        return [row for row in csv.reader(io.StringIO(data), delimiter=delim)]
    if ext == ".xls":
        raise InputError("old .xls format – please save the file as .xlsx or .csv")
    raise InputError("unsupported file type %s (use .xlsx, .csv or .json)" % ext)


def _match(header, mapping=None):
    h = norm_header(header)
    if mapping:
        for field, col in mapping.items():
            if norm_header(col) == h:
                return field
    if not h:
        return None
    for field, syns in FIELDS.items():
        if h in syns:
            return field
    for field, syns in FIELDS.items():
        for s in syns:
            if len(s) >= 4 and h.startswith(s):
                return field
    return None


def _header_score(rows, mapping=None):
    best = (0, None)
    for i, row in enumerate(rows[:40]):
        fields = [f for f in (_match(c, mapping) for c in row) if f]
        score = len(set(fields)) + (3 if "ek" in fields else 0)
        if score > best[0]:
            best = (score, i)
    return best


def table_to_records(rows, mapping=None):
    score, hi = _header_score(rows, mapping)
    if hi is None or score < 4:
        raise InputError("no header row recognised (need at least a price column). Run 'inspect' and use --map feld=\"Spalte\".")
    header = rows[hi]
    cols = {}
    raw_headers = {}
    for j, h in enumerate(header):
        f = _match(h, mapping)
        if f and f not in cols:
            cols[f] = j
            raw_headers[f] = str(h)
    recs = []
    for row in rows[hi + 1:]:
        if not any(str(c or "").strip() for c in row):
            continue
        rec = {}
        for f, j in cols.items():
            rec[f] = row[j] if j < len(row) else None
        label = " ".join(str(rec.get(k) or "") for k in ("pos", "name")).lower()
        if re.search(r"\b(total|summe|gesamt|subtotal)\b", label) and rec.get("ek") in (None, ""):
            continue
        recs.append(rec)
    return recs, raw_headers


def inspect(path, mapping=None, sheet=None):
    rows = read_table(path, sheet)
    score, hi = _header_score(rows, mapping)
    out = {"datei": os.path.basename(path), "kopfzeile": (hi + 1) if hi is not None else None, "spalten": []}
    if hi is not None:
        for h in rows[hi]:
            out["spalten"].append({"spalte": h, "feld": _match(h, mapping)})
    return out


def load_offer(path, tables, mapping=None, sheet=None):
    """Return (settings, raw records) from a JSON, CSV or XLSX offer."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".json":
        with io.open(path, encoding="utf-8") as f:
            try:
                doc = json.load(f)
            except ValueError as e:
                raise InputError("%s is not valid JSON: %s" % (path, e))
        if isinstance(doc, list):
            return {}, doc, {"_zahlformat": zahlformat(doc)}
        return doc.get("einstellungen") or {}, doc.get("positionen") or [], {"_zahlformat": zahlformat(doc.get("positionen") or [])}
    recs, raw_headers = table_to_records(read_table(path, sheet), mapping)
    raw_headers["_zahlformat"] = zahlformat(recs)
    return {}, recs, raw_headers


# ---------------------------------------------------------------- normalizing
def normalize(rec, tables, defaults=None, raw_headers=None, idx=0):
    """Turn one raw record into a position dict. Returns (position, missing_fields)."""
    defaults = defaults or {}
    raw_headers = raw_headers or {}
    fmt = raw_headers.get("_zahlformat")
    zahl_hinweise = []
    p = {}
    for k, v in rec.items():
        if k in NUMERIC:
            if k in RATES:
                p[k] = parse_rate(v)
            elif k == "gewicht":
                p["gewicht_g"] = parse_weight_g(v, raw_headers.get("gewicht", ""))
            elif k in PREIS:
                p[k] = parse_preis(v, fmt, k, zahl_hinweise)
            else:
                p[k] = parse_num(v, int_like=k in ("menge", "moq", "stueck_je_karton", "monatsabsatz"))
        else:
            p[k] = v
    for k in ("masse_cm", "karton_masse_cm", "gewicht_g", "staffel", "bewertung", "annahmen", "niedrigpreis"):
        if k in rec and k not in p:
            p[k] = rec[k]
    if rec.get("masse_cm") is not None:
        p["masse_cm"] = parse_dims(rec["masse_cm"]) if not isinstance(rec["masse_cm"], list) else [float(x) for x in rec["masse_cm"]]
    elif rec.get("masse") is not None:
        p["masse_cm"] = parse_dims(rec["masse"])
    if not p.get("masse_cm") and all(p.get(k) for k in ("laenge", "breite", "hoehe")):
        p["masse_cm"] = [p["laenge"], p["breite"], p["hoehe"]]
    if rec.get("karton_masse_cm") is not None and isinstance(rec["karton_masse_cm"], list):
        p["karton_masse_cm"] = [float(x) for x in rec["karton_masse_cm"]]
    elif rec.get("karton_masse") is not None:
        p["karton_masse_cm"] = parse_dims(rec["karton_masse"])
    if "gewicht_g" in rec and isinstance(rec["gewicht_g"], (int, float, str)):
        p["gewicht_g"] = parse_num(rec["gewicht_g"])
    p["pos"] = str(rec.get("pos") if rec.get("pos") not in (None, "") else (rec.get("sku") or idx + 1)).strip()
    if isinstance(rec.get("pos"), float) and rec["pos"].is_integer():
        p["pos"] = str(int(rec["pos"]))
    p["name"] = str(rec.get("name") or rec.get("sku") or "Position %s" % p["pos"]).strip()
    cur_default = str(defaults.get("waehrung") or tables.user.get("waehrung_ek") or "USD").upper()
    if rec.get("waehrung"):
        p["waehrung"] = detect_currency(rec["waehrung"], str(rec["waehrung"]).strip().upper())
    else:
        p["waehrung"] = detect_currency(rec.get("ek") if isinstance(rec.get("ek"), str) else "",
                                        detect_currency(raw_headers.get("ek", ""), cur_default))
    teile = int(p.get("teile_je_einheit") or 1)
    p["teile_je_einheit"] = teile
    if p.get("ek") is None and p.get("ek_je_teil") is not None:
        p["ek"] = p["ek_je_teil"] * teile
    p["staffel"] = parse_staffel(rec.get("staffel"), fmt, zahl_hinweise)
    if zahl_hinweise:
        p["zahl_hinweise"] = zahl_hinweise
    if not p.get("menge"):
        p["menge"] = p.get("moq") or defaults.get("menge")
    for k in ("kategorie", "incoterm", "hs_code"):
        if p.get(k) is None and defaults.get(k) is not None:
            p[k] = defaults[k]
    for k in ("retourenquote", "monatsabsatz", "vk_brutto", "tacos_plan"):
        if p.get(k) is None and defaults.get(k) is not None:
            p[k] = defaults[k]
    p["kategorie"] = _category_key(p.get("kategorie"), tables)
    if isinstance(p.get("annahmen"), str):
        p["annahmen"] = [a.strip() for a in re.split(r"[,;|]", p["annahmen"]) if a.strip()]
    if isinstance(p.get("gefahrgut"), str):
        p["gefahrgut"] = p["gefahrgut"].strip().lower() in ("1", "ja", "yes", "true", "x")
    if rec.get("urteil") and not p.get("bewertung"):
        p["bewertung"] = {"urteil": rec.get("urteil"), "begruendung": rec.get("begruendung") or ""}
    # customs
    if p.get("zollsatz") is not None:
        p["zoll_quelle"] = "eingabe"
    else:
        hit = zoll_lookup(tables.zoll, p.get("hs_code"))
        if hit:
            p["zollsatz"] = hit["satz"]
            p["zoll_quelle"] = "tabelle"
            p["zoll_hinweis"] = "%s (%s, %s)" % (hit["name"], hit["status"], hit["hinweis"])
        else:
            p["zollsatz"] = tables.cfg["zoll"]["standard_satz"]
            p["zoll_quelle"] = "standard"
    missing = [k for k in ("ek", "vk_brutto", "menge", "masse_cm", "gewicht_g") if not p.get(k)]
    if p.get("menge") is not None:
        p["menge"] = int(round(p["menge"]))
    return p, missing


def _category_key(value, tables):
    cats = tables.amazon["referral"]["kategorien"]
    if not value:
        return "sonstige"
    v = norm_header(value)
    for key, rule in cats.items():
        if norm_header(key) == v or norm_header(rule.get("name", "")) == v:
            return key
    for key, rule in cats.items():
        if v and (v in norm_header(rule.get("name", "")) or norm_header(key).startswith(v)):
            return key
    raise InputError("unknown category '%s' – run 'kategorien' for the list" % value)


def price_for_qty(p, qty):
    """Unit price for a quantity from price breaks (staffel), else the quoted price."""
    price = p["ek"]
    for q, pr in p.get("staffel") or []:
        if qty >= q:
            price = pr * (p["teile_je_einheit"] if p.get("staffel_je_teil") else 1)
    return price
