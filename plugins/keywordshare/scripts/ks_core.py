"""KeywordShare core: shares, funnel, levers and the audit summary (EN/DE).

All numbers are computed here; Claude only explains them. Method (see references/method.md):

  share per stage     = your count / market count  (impressions, clicks, cart adds, purchases)
  click index         = your CTR / market CTR       = click share / impression share
  conversion index    = your CVR / market CVR       = purchase share / click share

Three levers, each in estimated extra purchases for the same period:
  visibility  more impressions up to your target impression share (your own top-quartile share),
              converted like the market on that query, scaled by how well you click/convert there
  click       customers see you but click less often than the market
  conversion  customers click but buy less often than the market
"""
import json
import os
import re

from ks_ads import norm_text

DEFAULTS = {"min_market_purchases": 5, "target_share": None, "keywords": 50, "brand_terms": []}   # ListingDoctor reads 50
ASIN_Q = re.compile(r"^b0[0-9a-z]{8}$", re.I)


class ConfigError(Exception):
    pass


def as_fraction(v):
    if v is None:
        return None
    s = str(v).replace("%", "").replace(",", ".").strip()
    try:
        x = float(s)
    except ValueError:
        raise ConfigError("Expected a share like 15 or 0.15, got: %s" % v)
    x = x / 100.0 if x > 1 else x
    if not 0 < x < 1:
        raise ConfigError("Share must be between 0 and 100 %%, got: %s" % v)
    return x


def load_config(path=None, cwd=None):
    cfg = dict(DEFAULTS)
    cfg["brand_terms"] = []
    p = path or (os.path.join(cwd, "keywordshare.json") if cwd else None)
    if p and os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as f:
                user = json.load(f)
        except ValueError as e:
            raise ConfigError("%s is not valid JSON: %s" % (p, e))
        for k in ("min_market_purchases", "keywords"):
            if k in user:
                cfg[k] = int(user[k])
        if user.get("target_share") not in (None, ""):
            cfg["target_share"] = as_fraction(user["target_share"])
        cfg["brand_terms"] = [norm_text(t) for t in user.get("brand_terms", []) if str(t).strip()]
        cfg["config_file"] = p
    return cfg


# ---------------------------------------------------------------- aggregation

def combine(rows):
    """Aggregate SQP rows to one record per query.

    Several ASINs in one period: market totals are the same per query, so they are taken once (max)
    while your counts add up. Several periods: everything adds up.
    """
    per_period = {}
    for r in rows:
        k = (r["period"], r["query"])
        p = per_period.get(k)
        if p is None:
            p = per_period[k] = dict(r)
            p["entities"] = {r["entity"]}
            p["price_w"] = []
            continue
        for s in ("imp", "clk", "cart", "pur"):
            if p["%s_t" % s] is None or r["%s_t" % s] is None:
                continue
            p["%s_t" % s] = max(p["%s_t" % s], r["%s_t" % s])
            p["%s_m" % s] += r["%s_m" % s]
        p["volume"] = max(p["volume"], r["volume"])
        p["entities"].add(r["entity"])
    out = {}
    for (period, q), p in per_period.items():
        o = out.get(q)
        if o is None:
            o = out[q] = {"query": q, "query_raw": p["query_raw"], "score": p.get("score"), "volume": 0.0,
                          "periods": 0, "price_m": None, "price_t": None, "_pm": [], "_pt": []}
            for s in ("imp", "clk", "cart", "pur"):
                o["%s_t" % s] = 0.0 if p["%s_t" % s] is not None else None
                o["%s_m" % s] = 0.0 if p["%s_m" % s] is not None else None
        for s in ("imp", "clk", "cart", "pur"):
            if o["%s_t" % s] is not None and p["%s_t" % s] is not None:
                o["%s_t" % s] += p["%s_t" % s]
                o["%s_m" % s] += p["%s_m" % s]
        o["volume"] += p["volume"] or 0.0
        o["periods"] += 1
        if p.get("score") is not None and (o["score"] is None or p["score"] < o["score"]):
            o["score"] = p["score"]
        w = max(p["pur_m"], 1.0)
        if p.get("price_m"):
            o["_pm"].append((p["price_m"], w))
        if p.get("price_t"):
            o["_pt"].append((p["price_t"], max(p["pur_t"], 1.0)))
    for o in out.values():
        for k, src in (("price_m", "_pm"), ("price_t", "_pt")):
            vals = o.pop(src)
            if vals:
                o[k] = sum(v * w for v, w in vals) / sum(w for _, w in vals)
    return list(out.values())


def _div(a, b):
    return (a / b) if (a is not None and b) else 0.0


def percentile(vals, p):
    vals = sorted(v for v in vals if v is not None)
    if not vals:
        return None
    k = (len(vals) - 1) * p
    lo = int(k)
    hi = min(lo + 1, len(vals) - 1)
    return vals[lo] + (vals[hi] - vals[lo]) * (k - lo)


# ---------------------------------------------------------------- analysis

def analyze(rows, meta, cfg):
    qs = combine(rows)
    min_mp = cfg["min_market_purchases"]
    has_cart = any(q["cart_t"] for q in qs)
    tot = {k: 0.0 for k in ("imp_t", "imp_m", "clk_t", "clk_m", "cart_t", "cart_m", "pur_t", "pur_m", "volume")}
    for q in qs:
        for k in tot:
            tot[k] += q.get(k) or 0.0
        q["s_imp"] = _div(q["imp_m"], q["imp_t"])
        q["s_clk"] = _div(q["clk_m"], q["clk_t"])
        q["s_cart"] = _div(q["cart_m"], q["cart_t"]) if q["cart_t"] else None
        q["s_pur"] = _div(q["pur_m"], q["pur_t"])
        q["ctr_mkt"] = _div(q["clk_t"], q["imp_t"])
        q["cvr_mkt"] = _div(q["pur_t"], q["clk_t"])
        q["ctr_me"] = _div(q["clk_m"], q["imp_m"])
        q["cvr_me"] = _div(q["pur_m"], q["clk_m"])
        q["exp_clk"] = q["imp_m"] * q["ctr_mkt"]
        q["exp_pur"] = q["clk_m"] * q["cvr_mkt"]
        q["ctr_idx"] = _div(q["clk_m"], q["exp_clk"]) if q["exp_clk"] else None
        q["cvr_idx"] = _div(q["pur_m"], q["exp_pur"]) if q["exp_pur"] else None
        q["ctr_judged"] = q["imp_m"] >= 50 and q["exp_clk"] >= 5
        q["cvr_judged"] = q["exp_pur"] >= 2
        q["qualified"] = q["pur_t"] >= min_mp
        q["is_brand"] = any(b and b in q["query"] for b in cfg.get("brand_terms", []))
        q["is_asin"] = bool(ASIN_Q.match(q["query"]))

    # account-level indices on qualified queries (fallback: all)
    base = [q for q in qs if q["qualified"]] or qs
    s_imp_m = sum(q["imp_m"] for q in base)
    exp_clk = sum(q["exp_clk"] for q in base)
    exp_pur = sum(q["exp_pur"] for q in base)
    ctr_idx_all = _div(sum(q["clk_m"] for q in base), exp_clk) if exp_clk else 1.0
    cvr_idx_all = _div(sum(q["pur_m"] for q in base), exp_pur) if exp_pur else 1.0

    for q in qs:
        q["irrelevant"] = bool(q["cvr_judged"] and q["exp_pur"] >= 3 and (q["pur_m"] == 0 or (q["cvr_idx"] or 0) < 0.15))

    # targets from your own data: the impression share you already reach where you sell
    pool = [q for q in qs if q["qualified"] and q["pur_m"] >= 1 and q["s_imp"] > 0 and not q["irrelevant"]
            and not q["is_brand"]]
    auto_target = percentile([q["s_imp"] for q in pool], 0.75) if len(pool) >= 5 else None
    target_imp = cfg.get("target_share") or min(0.6, max(0.03, auto_target if auto_target is not None else 0.10))
    strong_pool = [q["s_pur"] for q in qs if q["qualified"] and q["pur_m"] >= 1]
    strong_share = percentile(strong_pool, 0.75) if len(strong_pool) >= 5 else None
    strong_share = max(0.05, strong_share) if strong_share is not None else 0.15

    for q in qs:
        # proven on this query, or account level with a discount for "not proven here yet"
        rel_ctr = min(1.0, q["ctr_idx"]) if q["ctr_judged"] else min(1.0, ctr_idx_all)
        rel_cvr = min(1.0, q["cvr_idx"]) if q["cvr_judged"] else min(1.0, cvr_idx_all)
        q["untested"] = q["clk_m"] < 1
        q["proven"] = q["pur_m"] >= 1 or (q["cvr_judged"] and (q["cvr_idx"] or 0) >= 0.5)
        discount = 1.0 if q["proven"] else (0.25 if q["untested"] else 0.5)
        q["relevance"] = rel_ctr * rel_cvr * discount
        lost_conv = max(0.0, q["exp_pur"] - q["pur_m"]) if q["cvr_judged"] else 0.0
        lost_click = max(0.0, q["exp_clk"] - q["clk_m"]) * q["cvr_mkt"] * rel_cvr if q["ctr_judged"] else 0.0
        add_imp = max(0.0, target_imp * q["imp_t"] - q["imp_m"])
        lost_vis = add_imp * q["ctr_mkt"] * q["cvr_mkt"] * q["relevance"]
        if q["irrelevant"] or q["is_asin"]:
            lost_vis = lost_click = 0.0
        if not q["qualified"]:
            lost_vis = lost_click = lost_conv = 0.0
        q["lost_vis"], q["lost_click"], q["lost_conv"] = lost_vis, lost_click, lost_conv
        q["lost"] = 0.0 if q["irrelevant"] else lost_vis + lost_click + lost_conv
        levers = {"vis": lost_vis, "click": lost_click, "conv": lost_conv}
        lever = max(levers, key=levers.get)
        q["lever"] = lever if levers[lever] >= 0.5 else None
        q["strong"] = q["qualified"] and q["pur_m"] >= 3 and q["s_pur"] >= strong_share
        if q["irrelevant"]:
            q["status"] = "irrelevant"
        elif q["strong"]:
            q["status"] = "strong"
        elif q["lever"]:
            q["status"] = q["lever"]
        elif not q["qualified"]:
            q["status"] = "thin"
        else:
            q["status"] = "ok"
        # where in the funnel a conversion leak sits (needs cart adds)
        q["leak_at"] = None
        if q["lever"] == "conv" and q["s_cart"] is not None and q["s_clk"]:
            cart_idx = q["s_cart"] / q["s_clk"]
            buy_idx = _div(q["s_pur"], q["s_cart"]) if q["s_cart"] else 0
            q["leak_at"] = "cart" if cart_idx < buy_idx else "checkout"
        q["price_idx"] = _div(q["price_m"], q["price_t"]) if (q.get("price_m") and q.get("price_t")) else None

    totals = dict(tot)
    totals.update({"queries": len(qs), "qualified": sum(1 for q in qs if q["qualified"]),
                   "s_imp": _div(tot["imp_m"], tot["imp_t"]), "s_clk": _div(tot["clk_m"], tot["clk_t"]),
                   "s_cart": _div(tot["cart_m"], tot["cart_t"]) if has_cart and tot["cart_t"] else None,
                   "s_pur": _div(tot["pur_m"], tot["pur_t"]),
                   "ctr_idx": ctr_idx_all, "cvr_idx": cvr_idx_all,
                   "lost": sum(q["lost"] for q in qs),
                   "lost_vis": sum(q["lost_vis"] for q in qs if not q["irrelevant"]),
                   "lost_click": sum(q["lost_click"] for q in qs if not q["irrelevant"]),
                   "lost_conv": sum(q["lost_conv"] for q in qs if not q["irrelevant"]),
                   "price_m": _wavg(qs, "price_m", "pur_m"), "price_t": _wavg(qs, "price_t", "pur_t"),
                   "s_imp_m": s_imp_m})
    periods = sorted(set(r["period"] for r in rows))
    entities = sorted(set(r["entity"] for r in rows if r["entity"]))
    starts = [r["period_start"] for r in rows if r.get("period_start")]
    ends = [r["period_end"] for r in rows if r.get("period_end")]
    return {"queries": qs, "totals": totals, "meta": meta, "cfg": cfg, "has_cart": has_cart,
            "periods": periods, "entities": entities,
            "bounds": (min(starts) if starts else None, max(ends) if ends else None),
            "thresholds": {"target_imp": target_imp, "target_auto": cfg.get("target_share") is None,
                           "strong_share": strong_share, "min_market_purchases": min_mp}}


def _wavg(qs, key, wkey):
    vals = [(q[key], max(q[wkey] or 0, 1.0)) for q in qs if q.get(key)]
    if not vals:
        return None
    return sum(v * w for v, w in vals) / sum(w for _, w in vals)


def opportunities(res):
    return sorted([q for q in res["queries"] if q["lost"] >= 1 and not q["strong"]],
                  key=lambda q: -q["lost"])


def by_status(res, status, key="lost"):
    qs = [q for q in res["queries"] if q["status"] == status]
    if status == "strong":
        return sorted(qs, key=lambda q: -q["pur_m"])
    if status == "irrelevant":
        return sorted(qs, key=lambda q: -q["clk_m"])
    if status in ("click", "conv"):
        k = "lost_click" if status == "click" else "lost_conv"
        return sorted(qs, key=lambda q: -q[k])
    return sorted(qs, key=lambda q: -q.get(key, 0))


def listing_keywords(res, limit=None):
    """Queries worth covering in the listing, most important first (ListingDoctor plain list)."""
    limit = limit or res["cfg"].get("keywords", 50)
    cand = [q for q in res["queries"] if not q["irrelevant"] and not q["is_asin"] and q["pur_t"] > 0 and q["proven"]]
    cand.sort(key=lambda q: (-(q["pur_t"] * q["relevance"] + 3 * q["pur_m"]), q["score"] or 1e9))
    return [q["query_raw"] for q in cand[:limit]]


def protect_terms(res, n=25):
    """Core queries you should never negate in PPC: strong ones plus your biggest sellers."""
    qs = [q for q in res["queries"] if not q["irrelevant"] and not q["is_asin"]]
    top = sorted(qs, key=lambda q: -q["pur_m"])
    out, seen = [], set()
    for q in [q for q in top if q["strong"]] + top[:10]:
        if q["query"] not in seen and q["pur_m"] > 0:
            seen.add(q["query"])
            out.append(q["query_raw"])
    return out[:n]


# ---------------------------------------------------------------- text

T = {
    "en": {
        "title": "KeywordShare — Search Query Performance",
        "brand": "brand", "asin": "ASIN", "mine": "your brand", "period": "period", "periods_n": "%d periods combined",
        "market": "marketplace",
        "headline": "**%s search queries · market purchases %s · yours %s → purchase share %s**",
        "funnel_h": "| Funnel | Market | You | Your share |", "funnel_sep": "|---|---:|---:|---:|",
        "st_imp": "Impressions", "st_clk": "Clicks", "st_cart": "Cart adds", "st_pur": "Purchases",
        "read_ctr_hi": "Shoppers click you **more often** than the market average (click index %s).",
        "read_ctr_lo": "Shoppers see you but click **less often** than other offers (click index %s) — main image, price, reviews, title start.",
        "read_ctr_eq": "Click-through is about market level (click index %s).",
        "read_cvr_hi": "Once clicked, you convert **better** than the market (conversion index %s).",
        "read_cvr_lo": "Clicks convert **worse** than the market (conversion index %s) — price, detail page, variants, reviews.",
        "read_cvr_eq": "Conversion is about market level (conversion index %s).",
        "read_vis": "Your purchase share (%s) is higher than your impression share (%s): more visibility should pay off.",
        "opp_h": "### 🎯 Biggest opportunities — about +%s purchases in this period",
        "opp_cols": "| # | Search query | Market purchases | Your share (impr. → purchase) | Lever | + Purchases | Next step |",
        "opp_sep": "|---:|---|---:|---|---|---:|---|",
        "lev_vis": "visibility", "lev_click": "click rate", "lev_conv": "conversion",
        "act_vis": "Put it in title/bullets, advertise exact",
        "act_vis_in_ads": "Raise exact bid / top-of-search",
        "act_click": "Main image, price, reviews, title start",
        "act_conv": "Price, detail page, variants, A+",
        "act_conv_cart": "Detail page → cart: price, delivery promise, variants",
        "act_conv_checkout": "Cart → purchase: final price, delivery date, coupon",
        "pricier": " (you are %s above the median price)",
        "click_h": "### 👀 Seen but not clicked (click leak)",
        "click_cols": "| Search query | Impr. share | Click share | Click index | Lost purchases |",
        "conv_h": "### 🛒 Clicked but not bought (conversion leak)",
        "conv_cols": "| Search query | Click share | Purchase share | Conversion index | Lost purchases |",
        "strong_h": "### 🛡️ Your strong search queries (defend)",
        "strong_cols": "| Search query | Market purchases | Your purchases | Purchase share |",
        "irr_h": "### ⚠️ Probably not a fit (clicks without purchases)",
        "irr_cols": "| Search query | Your clicks | Expected purchases | Your purchases |",
        "irr_note": "If the product really does not fit: check these as negatives in PPC (TermSweep shows the ad cost).",
        "none": "none",
        "handoff_h": "### Hand-offs",
        "ho_listing": "**ListingDoctor:** `%s` — %d search queries with proven fit, most important first; check the listing's "
                      "keyword coverage with `/listingdoctor:check <listing> --keywords %s` (Pro: `/listingdoctor-pro:check`).",
        "ho_ts": "**TermSweep:** `%s` — %d core queries to protect from negatives (`/termsweep:setup`), plus `%s` with PPC actions.",
        "ho_ts_free": "PPC hand-off (protect list for TermSweep + PPC to-do list per query): KeywordShare Pro.",
        "files_h": "### Files",
        "f_book": "workbook (summary, opportunities, full funnel, strong queries)", "f_kw": "keyword list for ListingDoctor",
        "f_ppc": "PPC actions for TermSweep", "f_protect": "core queries to protect",
        "notes_h": "### Notes",
        "n_paid": "Search Query Performance counts organic **and** sponsored impressions/clicks/purchases together. "
                  "For an organic estimate pass your search term report with `--ads` (Pro).",
        "n_paid_ads": "Search Query Performance counts organic and sponsored together; organic = your purchases minus "
                      "ad orders (7 days) on the same search term — an estimate, best with the same period in both files.",
        "n_target": "Target impression share %s = %s; strong = purchase share ≥ %s; queries with < %d market purchases are listed but not judged.",
        "n_target_auto": "your top-quartile share", "n_target_set": "set by you",
        "n_free_multi": "%d more file(s) ignored: trends over several weeks and ASIN comparison are part of KeywordShare Pro.",
        "n_estimate": "\"+ Purchases\" are estimates for the same period, assuming market conversion on that query.",
        "n_file_date": "No reporting period in the file; the date in the file name (%s) is used as its label.",
        "n_markets": "The file holds several marketplaces (%s); analysed: %s. Pick another with --market.",
        "n_focus": "Only search queries containing: %s.", "n_exclude": "Left out: search queries containing %s.",
        "n_focus_empty": "No search query matches --focus/--exclude.",
        "more": "… %d more in the workbook.",
    },
    "de": {
        "title": "KeywordShare — Suchanfragen-Leistung",
        "brand": "Marke", "asin": "ASIN", "mine": "deine Marke", "period": "Zeitraum", "periods_n": "%d Zeiträume zusammengefasst",
        "market": "Marktplatz",
        "headline": "**%s Suchanfragen · Marktkäufe %s · deine Käufe %s → Kaufanteil %s**",
        "funnel_h": "| Trichter | Markt | du | dein Anteil |", "funnel_sep": "|---|---:|---:|---:|",
        "st_imp": "Impressionen", "st_clk": "Klicks", "st_cart": "In den Warenkorb", "st_pur": "Käufe",
        "read_ctr_hi": "Kunden klicken dich **häufiger** an als der Marktdurchschnitt (Klick-Index %s).",
        "read_ctr_lo": "Kunden sehen dich, klicken aber **seltener** als bei anderen Angeboten (Klick-Index %s) — Hauptbild, Preis, Bewertungen, Titelanfang.",
        "read_ctr_eq": "Die Klickrate liegt etwa auf Marktniveau (Klick-Index %s).",
        "read_cvr_hi": "Nach dem Klick kaufen Kunden bei dir **öfter** als im Markt (Conversion-Index %s).",
        "read_cvr_lo": "Klicks werden **seltener** zu Käufen als im Markt (Conversion-Index %s) — Preis, Detailseite, Varianten, Bewertungen.",
        "read_cvr_eq": "Die Conversion liegt etwa auf Marktniveau (Conversion-Index %s).",
        "read_vis": "Dein Kaufanteil (%s) ist höher als dein Impressionsanteil (%s): Mehr Sichtbarkeit lohnt sich.",
        "opp_h": "### 🎯 Größte Chancen — etwa +%s Käufe im Zeitraum",
        "opp_cols": "| # | Suchanfrage | Marktkäufe | dein Anteil (Impr. → Kauf) | Hebel | + Käufe | Nächster Schritt |",
        "opp_sep": "|---:|---|---:|---|---|---:|---|",
        "lev_vis": "Sichtbarkeit", "lev_click": "Klickrate", "lev_conv": "Conversion",
        "act_vis": "In Titel/Bullets aufnehmen, exakt bewerben",
        "act_vis_in_ads": "Exaktes Gebot / Top-of-Search erhöhen",
        "act_click": "Hauptbild, Preis, Bewertungen, Titelanfang",
        "act_conv": "Preis, Detailseite, Varianten, A+",
        "act_conv_cart": "Detailseite → Warenkorb: Preis, Lieferversprechen, Varianten",
        "act_conv_checkout": "Warenkorb → Kauf: Endpreis, Liefertermin, Coupon",
        "pricier": " (du liegst %s über dem Medianpreis)",
        "click_h": "### 👀 Gesehen, aber nicht geklickt (Klick-Leck)",
        "click_cols": "| Suchanfrage | Impr.-Anteil | Klickanteil | Klick-Index | entgangene Käufe |",
        "conv_h": "### 🛒 Geklickt, aber nicht gekauft (Conversion-Leck)",
        "conv_cols": "| Suchanfrage | Klickanteil | Kaufanteil | Conversion-Index | entgangene Käufe |",
        "strong_h": "### 🛡️ Deine starken Suchanfragen (verteidigen)",
        "strong_cols": "| Suchanfrage | Marktkäufe | deine Käufe | Kaufanteil |",
        "irr_h": "### ⚠️ Passt vermutlich nicht (Klicks ohne Käufe)",
        "irr_cols": "| Suchanfrage | deine Klicks | erwartete Käufe | deine Käufe |",
        "irr_note": "Wenn das Produkt wirklich nicht passt: in PPC als Negativ prüfen (TermSweep zeigt die Werbekosten).",
        "none": "keine",
        "handoff_h": "### Übergabe",
        "ho_listing": "**ListingDoctor:** `%s` — %d Suchanfragen mit nachgewiesener Passung, wichtigste zuerst; Keyword-Abdeckung "
                      "des Listings prüfen mit `/listingdoctor:check <Listing> --keywords %s` (Pro: `/listingdoctor-pro:check`).",
        "ho_ts": "**TermSweep:** `%s` — %d Kern-Suchanfragen, die nie negativ gesetzt werden dürfen (`/termsweep:setup`), plus `%s` mit PPC-Aktionen.",
        "ho_ts_free": "PPC-Übergabe (Schutzliste für TermSweep + PPC-Aufgabenliste je Suchanfrage): KeywordShare Pro.",
        "files_h": "### Dateien",
        "f_book": "Arbeitsmappe (Übersicht, Chancen, kompletter Trichter, starke Suchanfragen)", "f_kw": "Keyword-Liste für ListingDoctor",
        "f_ppc": "PPC-Aktionen für TermSweep", "f_protect": "Kern-Suchanfragen zum Schützen",
        "notes_h": "### Hinweise",
        "n_paid": "Die Suchanfragen-Leistung zählt organische **und** gesponserte Impressionen/Klicks/Käufe zusammen. "
                  "Für eine organische Schätzung den Suchbegriffbericht mit `--ads` übergeben (Pro).",
        "n_paid_ads": "Die Suchanfragen-Leistung zählt organisch und gesponsert zusammen; organisch = deine Käufe minus "
                      "Werbebestellungen (7 Tage) auf denselben Suchbegriff — eine Schätzung, am besten mit gleichem Zeitraum in beiden Dateien.",
        "n_target": "Ziel-Impressionsanteil %s = %s; stark = Kaufanteil ≥ %s; Suchanfragen mit < %d Marktkäufen stehen in der Mappe, werden aber nicht bewertet.",
        "n_target_auto": "dein oberes Quartil", "n_target_set": "von dir gesetzt",
        "n_free_multi": "%d weitere Datei(en) nicht ausgewertet: Trend über mehrere Wochen und ASIN-Vergleich gehören zu KeywordShare Pro.",
        "n_estimate": "„+ Käufe\" sind Schätzungen für denselben Zeitraum, mit der Markt-Conversion der jeweiligen Suchanfrage.",
        "n_file_date": "Kein Berichtszeitraum in der Datei; das Datum im Dateinamen (%s) dient als Bezeichnung.",
        "n_markets": "Die Datei enthält mehrere Marktplätze (%s); ausgewertet: %s. Anderen mit --market wählen.",
        "n_focus": "Nur Suchanfragen mit: %s.", "n_exclude": "Ausgelassen: Suchanfragen mit %s.",
        "n_focus_empty": "Keine Suchanfrage passt zu --focus/--exclude.",
        "more": "… %d weitere in der Arbeitsmappe.",
    },
}


def fnum(x, lang, digits=0):
    if x is None:
        return "–"
    s = ("{:,.%df}" % digits).format(x)
    if lang == "de":
        s = s.replace(",", "§").replace(".", ",").replace("§", ".")
    return s


def fpct(x, lang, digits=1):
    if x is None:
        return "–"
    if 0 < abs(x) < 0.0001:
        return "<0,01 %" if lang == "de" else "<0.01%"
    if 0 < abs(x) < 0.001:
        digits = 2
    s = ("{:.%df}" % digits).format(x * 100)
    return (s.replace(".", ",") + " %") if lang == "de" else s + "%"


def fidx(x, lang):
    if x is None:
        return "–"
    s = "%.2f" % x
    return s.replace(".", ",") if lang == "de" else s


def md_cell(s):
    return str(s).replace("|", "/").replace("\n", " ")


def action_text(q, L, lang, in_ads=None):
    lv = q.get("lever")
    if lv == "vis":
        return L["act_vis_in_ads"] if in_ads else L["act_vis"]
    if lv == "click":
        t = L["act_click"]
    elif lv == "conv":
        t = L["act_conv_" + q["leak_at"]] if q.get("leak_at") else L["act_conv"]
    else:
        return ""
    if q.get("price_idx") and q["price_idx"] > 1.1:
        t += L["pricier"] % fpct(q["price_idx"] - 1, lang, 0)
    return t


def scope_line(res, lang):
    L = T[lang]
    meta = res["meta"]
    bits = []
    view = meta.get("view")
    ent = res["entities"]
    if view == "asin":
        bits.append("%s %s" % (L["asin"], ", ".join(ent[:4]) + (" …" if len(ent) > 4 else "") if ent else "?"))
    elif view == "brand":
        bits.append("%s %s" % (L["brand"], ", ".join(ent) if ent else "?"))
    else:
        bits.append(L["mine"])
    if len(res["periods"]) == 1:
        bits.append("%s %s" % (L["period"], res["periods"][0]))
    else:
        bits.append(L["periods_n"] % len(res["periods"]) + " (%s … %s)" % (res["periods"][0], res["periods"][-1]))
    if meta.get("market"):
        bits.append("%s %s" % (L["market"], meta["market"]))
    bits.append("`%s`" % meta["file"])
    return " · ".join(bits)


def render_audit(res, lang, files=(), top=10, extra_sections=(), handoff=(), notes=()):
    L = T[lang]
    t = res["totals"]
    out = ["## %s" % L["title"], scope_line(res, lang), "",
           L["headline"] % (fnum(t["queries"], lang), fnum(t["pur_t"], lang), fnum(t["pur_m"], lang), fpct(t["s_pur"], lang)),
           "", L["funnel_h"], L["funnel_sep"]]
    stages = [("imp", "st_imp"), ("clk", "st_clk")] + ([("cart", "st_cart")] if t["s_cart"] is not None else []) + [("pur", "st_pur")]
    for s, key in stages:
        out.append("| %s | %s | %s | %s |" % (L[key], fnum(t["%s_t" % s], lang), fnum(t["%s_m" % s], lang), fpct(t["s_" + s], lang)))
    out.append("")
    ci, vi = t["ctr_idx"], t["cvr_idx"]
    out.append("- " + (L["read_ctr_hi"] if ci >= 1.1 else L["read_ctr_lo"] if ci <= 0.9 else L["read_ctr_eq"]) % fidx(ci, lang))
    out.append("- " + (L["read_cvr_hi"] if vi >= 1.1 else L["read_cvr_lo"] if vi <= 0.9 else L["read_cvr_eq"]) % fidx(vi, lang))
    if t["s_pur"] > t["s_imp"] * 1.15:
        out.append("- " + L["read_vis"] % (fpct(t["s_pur"], lang), fpct(t["s_imp"], lang)))
    out.append("")

    opp = opportunities(res)
    out.append(L["opp_h"] % fnum(sum(q["lost"] for q in opp), lang))
    if opp:
        out += [L["opp_cols"], L["opp_sep"]]
        for i, q in enumerate(opp[:top], 1):
            out.append("| %d | %s | %s | %s → %s | %s | +%s | %s |" % (
                i, md_cell(q["query_raw"]), fnum(q["pur_t"], lang), fpct(q["s_imp"], lang), fpct(q["s_pur"], lang),
                L["lev_" + q["lever"]] if q["lever"] else "–", fnum(q["lost"], lang, 1 if q["lost"] < 10 else 0),
                action_text(q, L, lang, q.get("in_ads"))))
        if len(opp) > top:
            out.append(L["more"] % (len(opp) - top))
    else:
        out.append(L["none"])
    out.append("")

    short = max(3, top // 2)
    for status, head, cols, fn in (
            ("click", "click_h", "click_cols",
             lambda q: (fpct(q["s_imp"], lang), fpct(q["s_clk"], lang), fidx(q["ctr_idx"], lang), fnum(q["lost_click"], lang, 1))),
            ("conv", "conv_h", "conv_cols",
             lambda q: (fpct(q["s_clk"], lang), fpct(q["s_pur"], lang), fidx(q["cvr_idx"], lang), fnum(q["lost_conv"], lang, 1)))):
        rows = [q for q in by_status(res, status) if q["lost_click" if status == "click" else "lost_conv"] >= 1]
        if not rows:
            continue
        out += [L[head], L[cols], "|---|---:|---:|---:|---:|"]
        for q in rows[:short]:
            out.append("| %s | %s |" % (md_cell(q["query_raw"]), " | ".join(fn(q))))
        out.append("")
    strong = by_status(res, "strong")
    out += [L["strong_h"]]
    if strong:
        out += [L["strong_cols"], "|---|---:|---:|---:|"]
        for q in strong[:top]:
            out.append("| %s | %s | %s | %s |" % (md_cell(q["query_raw"]), fnum(q["pur_t"], lang), fnum(q["pur_m"], lang), fpct(q["s_pur"], lang)))
    else:
        out.append(L["none"])
    out.append("")
    irr = by_status(res, "irrelevant")
    if irr:
        out += [L["irr_h"], L["irr_cols"], "|---|---:|---:|---:|"]
        for q in irr[:short]:
            out.append("| %s | %s | %s | %s |" % (md_cell(q["query_raw"]), fnum(q["clk_m"], lang), fnum(q["exp_pur"], lang, 1), fnum(q["pur_m"], lang)))
        out += [L["irr_note"], ""]
    for sec in extra_sections:
        out += [sec, ""]
    if handoff:
        out += [L["handoff_h"]] + ["- " + h for h in handoff] + [""]
    if files:
        out += [L["files_h"]] + ["- `%s` — %s" % (os.path.basename(p), d) for p, d in files] + [""]
    th = res["thresholds"]
    out += [L["notes_h"], "- " + (L["n_paid_ads"] if res.get("ads_used") else L["n_paid"]),
            "- " + L["n_target"] % (fpct(th["target_imp"], lang), L["n_target_auto"] if th["target_auto"] else L["n_target_set"],
                                    fpct(th["strong_share"], lang), th["min_market_purchases"]),
            "- " + L["n_estimate"]]
    for n in list(res["meta"].get("notes", [])) + list(notes):
        out.append("- " + note_text(n, lang))
    return "\n".join(out).rstrip() + "\n"


def note_text(n, lang):
    """Notes are plain strings or (key, args) tuples translated here."""
    if isinstance(n, (tuple, list)):
        return T[lang][n[0]] % tuple(n[1])
    return n


def apply_focus(rows, focus=None, exclude=None):
    """Keep queries containing any focus word, drop those containing an exclude word (product line scoping)."""
    fw = [norm_text(w) for w in (focus or "").split(",") if w.strip()]
    xw = [norm_text(w) for w in (exclude or "").split(",") if w.strip()]
    if not fw and not xw:
        return rows, []
    out = [r for r in rows if (not fw or any(w in r["query"] for w in fw)) and not any(w in r["query"] for w in xw)]
    notes = []
    if fw:
        notes.append(("n_focus", (", ".join(fw),)))
    if xw:
        notes.append(("n_exclude", (", ".join(xw),)))
    return out, notes


# ---------------------------------------------------------------- workbook

SHEET = {
    "en": {"summary": "Summary", "opp": "Opportunities", "funnel": "Funnel", "strong": "Strong",
           "k": "Key", "v": "Value",
           "cols": ["Search query", "Score", "Search volume", "Market impressions", "Your impressions", "Impression share",
                    "Market clicks", "Your clicks", "Click share", "Market cart adds", "Your cart adds", "Cart add share",
                    "Market purchases", "Your purchases", "Purchase share", "Market CTR", "Your CTR", "Market CVR", "Your CVR",
                    "Click index", "Conversion index", "Status", "Main lever", "+ Purchases (visibility)",
                    "+ Purchases (click)", "+ Purchases (conversion)", "+ Purchases total", "Next step"],
           "status": {"strong": "strong", "vis": "visibility gap", "click": "click leak", "conv": "conversion leak",
                      "irrelevant": "probably not a fit", "ok": "ok", "thin": "too little data"}},
    "de": {"summary": "Übersicht", "opp": "Chancen", "funnel": "Trichter", "strong": "Stark",
           "k": "Kennzahl", "v": "Wert",
           "cols": ["Suchanfrage", "Score", "Suchvolumen", "Markt-Impressionen", "deine Impressionen", "Impressionsanteil",
                    "Markt-Klicks", "deine Klicks", "Klickanteil", "Markt-Warenkorb", "dein Warenkorb", "Warenkorbanteil",
                    "Marktkäufe", "deine Käufe", "Kaufanteil", "Markt-CTR", "deine CTR", "Markt-Conversion", "deine Conversion",
                    "Klick-Index", "Conversion-Index", "Status", "Haupthebel", "+ Käufe (Sichtbarkeit)",
                    "+ Käufe (Klick)", "+ Käufe (Conversion)", "+ Käufe gesamt", "Nächster Schritt"],
           "status": {"strong": "stark", "vis": "Sichtbarkeitslücke", "click": "Klick-Leck", "conv": "Conversion-Leck",
                      "irrelevant": "passt vermutlich nicht", "ok": "ok", "thin": "zu wenig Daten"}},
}
PCT_COLS = [5, 8, 11, 14, 15, 16, 17, 18]


def query_row(q, lang):
    L, S = T[lang], SHEET[lang]

    def r(x, d=2):
        return round(x, d) if isinstance(x, float) else x
    return [q["query_raw"], q["score"], r(q["volume"], 0), r(q["imp_t"], 0), r(q["imp_m"], 0), q["s_imp"],
            r(q["clk_t"], 0), r(q["clk_m"], 0), q["s_clk"], r(q["cart_t"], 0), r(q["cart_m"], 0), q["s_cart"],
            r(q["pur_t"], 0), r(q["pur_m"], 0), q["s_pur"], q["ctr_mkt"], q["ctr_me"], q["cvr_mkt"], q["cvr_me"],
            r(q["ctr_idx"]) if q["ctr_judged"] else None, r(q["cvr_idx"]) if q["cvr_judged"] else None,
            S["status"][q["status"]], L["lev_" + q["lever"]] if q["lever"] else "",
            r(q["lost_vis"], 1), r(q["lost_click"], 1), r(q["lost_conv"], 1), r(q["lost"], 1),
            action_text(q, L, lang, q.get("in_ads"))]


def review_sheets(res, lang):
    S, L = SHEET[lang], T[lang]
    t, th = res["totals"], res["thresholds"]
    widths = [34, 7, 11, 13, 12, 10, 11, 10, 9, 11, 10, 10, 11, 10, 9, 9, 9, 10, 10, 9, 10, 18, 14, 12, 12, 12, 12, 44]
    summary = [[S["k"], S["v"]],
               [L["period"], " · ".join(res["periods"])],
               ["File", res["meta"]["file"]],
               [L["st_imp"] + " %", fpct(t["s_imp"], lang, 2)], [L["st_clk"] + " %", fpct(t["s_clk"], lang, 2)]]
    if t["s_cart"] is not None:
        summary.append([L["st_cart"] + " %", fpct(t["s_cart"], lang, 2)])
    summary += [[L["st_pur"] + " %", fpct(t["s_pur"], lang, 2)],
                ["Click index" if lang == "en" else "Klick-Index", round(t["ctr_idx"], 3)],
                ["Conversion index" if lang == "en" else "Conversion-Index", round(t["cvr_idx"], 3)],
                ["+ Purchases (visibility)" if lang == "en" else "+ Käufe (Sichtbarkeit)", round(t["lost_vis"], 1)],
                ["+ Purchases (click)" if lang == "en" else "+ Käufe (Klick)", round(t["lost_click"], 1)],
                ["+ Purchases (conversion)" if lang == "en" else "+ Käufe (Conversion)", round(t["lost_conv"], 1)],
                ["Target impression share" if lang == "en" else "Ziel-Impressionsanteil", fpct(th["target_imp"], lang)],
                ["Strong purchase share" if lang == "en" else "Stark ab Kaufanteil", fpct(th["strong_share"], lang)],
                ["Search queries" if lang == "en" else "Suchanfragen", t["queries"]]]
    hdr = S["cols"]
    allq = sorted(res["queries"], key=lambda q: (-(q["pur_t"] or 0)))
    opp = opportunities(res)
    strong = by_status(res, "strong")
    return [(S["summary"], summary, {"widths": [30, 40], "pct": []}),
            (S["opp"], [hdr] + [query_row(q, lang) for q in opp], {"widths": widths, "pct": PCT_COLS}),
            (S["funnel"], [hdr] + [query_row(q, lang) for q in allq], {"widths": widths, "pct": PCT_COLS}),
            (S["strong"], [hdr] + [query_row(q, lang) for q in strong], {"widths": widths, "pct": PCT_COLS})]
