"""ListingDoctor: read the public product page of an ASIN (no login, no API) into a listing dict.

Best effort: Amazon sometimes answers scripted requests with a captcha page. Then the caller falls back to the
seller pasting the listing text or downloading the category listing report. Backend search terms are never
public, so fetched listings carry backend=None and the backend checks are skipped.
"""
import html as _html
import json
import re
import time
import urllib.request

MARKETS = {"de": "www.amazon.de", "com": "www.amazon.com", "us": "www.amazon.com", "uk": "www.amazon.co.uk",
           "fr": "www.amazon.fr", "it": "www.amazon.it", "es": "www.amazon.es", "nl": "www.amazon.nl",
           "pl": "www.amazon.pl", "se": "www.amazon.se", "ca": "www.amazon.ca"}
LANG_HDR = {"de": "de-DE,de;q=0.9", "fr": "fr-FR,fr;q=0.9", "it": "it-IT,it;q=0.9", "es": "es-ES,es;q=0.9",
            "nl": "nl-NL,nl;q=0.9", "pl": "pl-PL,pl;q=0.9", "se": "sv-SE,sv;q=0.9"}
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
MAX_ASINS = 20


class Blocked(Exception):
    pass


def _text(fragment):
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", fragment, flags=re.S | re.I)
    t = re.sub(r"<br\s*/?>", "\n", t, flags=re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"[ \t\r\f\v]+", " ", _html.unescape(t)).strip()


def norm_market(market):
    """'DE', 'de', 'amazon.de', 'GB'/'co.uk' → keys of MARKETS (KeywordShare uses upper-case country codes)."""
    k = re.sub(r"^(https?://)?(www\.)?amazon\.", "", (market or "de").strip().lower())
    return {"gb": "uk", "co.uk": "uk"}.get(k, k)


def fetch_html(asin, market="de", timeout=20):
    market = norm_market(market)
    host = MARKETS.get(market, market)
    req = urllib.request.Request("https://%s/dp/%s" % (host, asin), headers={
        "User-Agent": UA, "Accept": "text/html,application/xhtml+xml", "Accept-Language": LANG_HDR.get(market, "en-US,en;q=0.9")})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        enc = r.headers.get_content_charset() or "utf-8"
    page = raw.decode(enc, errors="replace")
    if "validateCaptcha" in page or "api-services-support@amazon.com" in page:
        raise Blocked("Amazon answered with a captcha page")
    return page


def parse_page(page, asin=None):
    """returns a listing dict (title, highlights?, bullets, description, brand, asin, image_count)."""
    lst = {"asin": asin, "backend": None, "_public": True}
    m = re.search(r'<meta name="title" content="([^"]*)"', page)
    meta_title = _html.unescape(m.group(1)) if m else ""
    m = re.search(r'id="productTitle"[^>]*>(.*?)</span>', page, re.S)
    shown = _text(m.group(1)) if m else ""
    stored = ""
    if meta_title:
        left = re.sub(r"^\s*Amazon\.[\w.]+\s*:\s*", "", meta_title)                    # US: "Amazon.com : Title : Category"
        left = re.split(r"\s:\s(?:Amazon|amazon)\.", left)[0]                            # EU: "Title : Amazon.de: Category"
        if re.match(r"^\s*Amazon\.", meta_title) and " : " in left:
            left = left.rsplit(" : ", 1)[0]
        parts = left.split(" | ", 1)
        stored = re.sub(r"\s*\((?:as\d|numeric)[^)]*\)\s*$", "", parts[0]).strip()   # apparel size codes
        if len(parts) > 1:
            lst["highlights"] = parts[1].strip()
    # the title customers see; the meta title is what was submitted (they differ after Amazon's AI rewrite)
    lst["title"] = shown or stored
    if stored and shown and stored != shown and len(stored) > len(shown):
        lst["title_submitted"] = stored
    lst["bullets"] = []
    starts = [m.start() for m in re.finditer(r'id="feature-bullets"', page)]
    starts += [m.start() for m in re.finditer(r"(Info zu diesem Artikel|Über diesen Artikel|About this item|À propos de cet article|"
                                                r"Informazioni su questo articolo|Acerca de este producto|Over dit artikel)", page)]
    for st in starts:
        end = page.find("</ul>", st)
        if end < 0 or end - st > 40000:
            continue
        items = re.findall(r'<span class="a-list-item[^"]*">(.*?)</span>', page[st:end], re.S)
        found = [b for b in (_text(i) for i in items) if b and len(b) > 3]
        if found:
            lst["bullets"] = found[:10]
            break
    m = re.search(r'id="productDescription"[^>]*>(.*?)</div>\s*</div>', page, re.S)
    if m:
        lst["description"] = _text(m.group(1))[:5000]
    m = re.search(r'<a id="bylineInfo"[^>]*>(.*?)</a>', page, re.S)
    if m:
        by = _text(m.group(1))
        b = re.search(r"(?:Besuche den|Visit the|Visitez la boutique|Visita lo Store di|Visita la tienda de)\s+(.+?)(?:-Store|\s+Store|\s+boutique)?$", by)
        b = b or re.search(r"(?:Marke|Brand|Marque|Marca)\s*:\s*(.+)$", by)
        lst["brand"] = (b.group(1) if b else by).strip()
    m = re.search(r"'colorImages'\s*:\s*\{\s*'initial'\s*:\s*A\.\$\.parseJSON\('(.*?)'\)", page, re.S)
    if m:
        lst["image_count"] = len(re.findall(r'"hiRes"\s*:', m.group(1)))
    else:
        i = page.find('id="altImages"')
        if i >= 0:
            lst["image_count"] = len(re.findall(r"imageThumbnail", page[i:i + 30000]))
    if not asin:
        m = re.search(r'data-csa-c-asin="(B0[A-Z0-9]{8})"', page)
        lst["asin"] = m.group(1) if m else None
    return lst


def fetch_listings(asins, market="de", delay=2.0, log=None):
    """returns (listings, problems). Polite: one request every `delay` seconds, max. MAX_ASINS per run."""
    out, problems = [], []
    for n, a in enumerate(asins[:MAX_ASINS]):
        a = a.strip().upper()
        if not re.fullmatch(r"B0[A-Z0-9]{8}|\d{9}[\dX]", a):
            problems.append("%s: not an ASIN" % a)
            continue
        if n:
            time.sleep(delay)
        try:
            lst = parse_page(fetch_html(a, market), a)
            if not lst.get("title"):
                problems.append("%s: page read, but no title found (layout change or unavailable)" % a)
                continue
            out.append(lst)
            if log:
                log("read %s: %s" % (a, lst["title"][:60]))
        except Blocked as e:
            problems.append("%s: %s – paste the listing text instead" % (a, e))
        except Exception as e:  # network errors, 404, 503
            problems.append("%s: %s" % (a, e))
    if len(asins) > MAX_ASINS:
        problems.append("only the first %d ASINs were read" % MAX_ASINS)
    return out, problems


def save_json(listings, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"listings": [dict({k: v for k, v in l.items() if not k.startswith("_")}, public_page=True)
                                for l in listings]}, f, ensure_ascii=False, indent=1)
