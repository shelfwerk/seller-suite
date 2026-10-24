"""TermSweep analysis: classify search terms into bleeders, watch list, high-ACOS and harvest.

All thresholds are derived from the account's own numbers (conversion rate, order value,
target ACOS) so the rules work for a 5-euro sock and a 300-dollar grill alike. Everything is
a suggestion: nothing here talks to Amazon.
"""
import json
import math
import os
import re

from ts_report import ASIN_TARGET_RE, norm_text

DEFAULTS = {
    "target_acos": 0.30,          # used when the seller has not set one
    "min_clicks": 10,             # never call a term a bleeder below this many clicks ...
    "max_clicks": 60,             # ... and never wait for more than this many
    "harvest_min_orders": 2,
    "high_acos_factor": 1.5,      # ACOS this many times the target counts as "too expensive"
    "max_bid_cut": 0.3,           # never suggest cutting a bid by more than 30 % per run
    "max_bid_raise": 0.25,
    "protected_terms": [],
    "currency": None,
}
CONFIG_NAMES = ("termsweep.json", ".termsweep.json")


class ConfigError(Exception):
    pass


def load_config(path=None, cwd=".", near=()):
    """--config wins; otherwise termsweep.json in the working folder, then next to the report / in the
    output folder (`near`), so settings saved in the reports folder apply wherever TermSweep is run from."""
    cfg = dict(DEFAULTS)
    cfg["_source"] = "defaults"
    if path:
        candidates = [path]
    else:
        candidates, seen = [], set()
        for d in [cwd] + [d for d in near if d]:
            for n in CONFIG_NAMES:
                p = os.path.abspath(os.path.join(d, n))
                if p not in seen:
                    seen.add(p)
                    candidates.append(p)
    for p in candidates:
        if p and os.path.exists(p):
            try:
                with open(p, encoding="utf-8") as f:
                    user = json.load(f)
            except ValueError as e:
                raise ConfigError("Config %s is not valid JSON: %s" % (p, e))
            for k, v in user.items():
                if k in DEFAULTS:
                    cfg[k] = v
            cfg["_source"] = p
            break
        elif path:
            raise ConfigError("Config file not found: %s" % path)
    cfg["target_acos"] = _as_fraction(cfg["target_acos"])
    cfg["target_acos_set"] = cfg["_source"] != "defaults" and "target_acos" in (user if cfg["_source"] != "defaults" else {})
    cfg["protected_terms"] = [norm_protected(t) for t in (cfg.get("protected_terms") or []) if str(t).strip("= ")]
    return cfg


def _as_fraction(x):
    x = float(str(x).replace("%", "").replace(",", "."))
    return x / 100.0 if x > 1 else x


def norm_protected(entry):
    """'Brand' protects every search term containing the word(s); '=core query' protects exactly that search term."""
    s = str(entry).strip()
    if s.startswith("="):
        return "=" + norm_text(s[1:])
    return norm_text(s)


def read_protect_file(path):
    """One protected entry per line ('=' prefix = exact search term); blank lines and '#' comments ignored."""
    with open(path, encoding="utf-8-sig") as f:
        return [l.strip() for l in f if l.strip() and not l.strip().startswith("#")]


def is_protected(term, protected):
    t = " %s " % term
    for p in protected:
        if p.startswith("="):
            if term == p[1:]:
                return True
        elif re.search(r"(^|\W)%s($|\W)" % re.escape(p), t):
            return True
    return False


def account_totals(rows):
    t = {k: sum(r[k] for r in rows) for k in ("impressions", "clicks", "spend", "sales", "orders", "units")}
    t["acos"] = t["spend"] / t["sales"] if t["sales"] else None
    t["cvr"] = t["orders"] / t["clicks"] if t["clicks"] else None
    t["cpc"] = t["spend"] / t["clicks"] if t["clicks"] else None
    t["aov"] = t["sales"] / t["orders"] if t["orders"] else None
    t["terms"] = len(set(r["term"] for r in rows))
    return t


def thresholds(totals, cfg):
    """Clicks after which a term converting like the account average would have sold with 90 %
    probability: (1 - cvr)^n <= 0.1  ->  n ≈ 2.3 / cvr. Fewer zero-order clicks are often just luck."""
    cvr = totals["cvr"]
    if cvr and cvr > 0:
        clicks = int(math.ceil(2.3 / cvr))
    else:
        clicks = 20
    clicks = max(cfg["min_clicks"], min(cfg["max_clicks"], clicks))
    cpa = cfg["target_acos"] * totals["aov"] if totals["aov"] else None
    return {"clicks": clicks, "cpa": cpa, "watch_clicks": max(3, int(math.ceil(clicks / 2.0)))}


def _exact_keywords(rows):
    return set(norm_text(r["targeting"]) for r in rows if r["kind"] == "keyword" and r["match"] == "exact")


def _is_own_exact(r):
    """The search term is exactly what this row targets (own exact keyword or own ASIN target)."""
    if r["kind"] == "keyword" and r["match"] == "exact":
        return norm_text(r["targeting"]) == r["term"]
    if r["kind"] == "product" and r["is_asin"]:
        m = ASIN_TARGET_RE.search(norm_text(r["targeting"]))
        return bool(m) and m.group(1).lower() == r["term"]
    return False


def analyze(report, cfg):
    rows = report["rows"]
    totals = account_totals(rows)
    th = thresholds(totals, cfg)
    target = cfg["target_acos"]
    prot = cfg["protected_terms"]
    exact_kw = _exact_keywords(rows)
    targeted_asins = set(m.group(1).lower() for m in (ASIN_TARGET_RE.search(norm_text(r["targeting"])) for r in rows) if m)
    term_orders = {}
    for r in rows:
        term_orders[r["term"]] = term_orders.get(r["term"], 0) + r["orders"]

    bleeders, watch, high_acos, protected_hits, funnel = [], [], [], [], []
    for r in rows:
        r["acos"] = r["spend"] / r["sales"] if r["sales"] else None
        r["protected"] = is_protected(r["term"], prot)
        if r["orders"] <= 0:
            bleeding = r["clicks"] >= th["clicks"] or (th["cpa"] is not None and r["spend"] >= 2 * th["cpa"]
                                                       and r["clicks"] >= max(3, th["clicks"] / 3.0))
            if bleeding:
                if _is_own_exact(r):
                    r["action"] = "pause_or_lower_bid"
                elif r["protected"]:
                    r["action"] = "review_protected"
                    protected_hits.append(r)
                    continue
                elif term_orders.get(r["term"], 0) > 0:
                    # sells in another ad group: negating here only makes sense to funnel the traffic
                    # to the ad group that converts (same product) — a decision for the seller
                    r["action"] = "funnel"
                    funnel.append(r)
                    continue
                elif r["is_asin"]:
                    r["action"] = "negative_product"
                else:
                    r["action"] = "negative_exact"
                bleeders.append(r)
            elif r["clicks"] >= th["watch_clicks"] or (th["cpa"] is not None and r["spend"] >= th["cpa"]):
                r["action"] = "watch"
                watch.append(r)
        else:
            if r["acos"] is not None and r["acos"] >= target * cfg["high_acos_factor"] and \
                    (th["cpa"] is None or r["spend"] >= th["cpa"]):
                factor = max(1 - cfg["max_bid_cut"], target / r["acos"])
                r["bid_factor"] = factor
                cpc = r["spend"] / r["clicks"] if r["clicks"] else None
                r["iso_bid"] = round(cpc * factor, 2) if cpc else None
                # a bid belongs to a target, not to a search term: lower the bid of our own exact
                # keyword/target, otherwise isolate the term as exact keyword with a lower bid
                r["action"] = "lower_bid" if _is_own_exact(r) else "isolate"
                high_acos.append(r)

    # harvest is decided per search term over all ad groups it showed up in
    by_term = {}
    for r in rows:
        if r["orders"] <= 0 and r["clicks"] <= 0:
            continue
        g = by_term.setdefault(r["term"], {"term": r["term"], "term_raw": r["term_raw"], "is_asin": r["is_asin"],
                                           "clicks": 0.0, "spend": 0.0, "sales": 0.0, "orders": 0.0, "sources": []})
        for k in ("clicks", "spend", "sales", "orders"):
            g[k] += r[k]
        g["sources"].append(r)
    harvest = []
    for g in by_term.values():
        if g["orders"] < cfg["harvest_min_orders"] or not g["sales"]:
            continue
        g["acos"] = g["spend"] / g["sales"]
        if g["acos"] > target:
            continue
        if g["term"] in exact_kw or (g["is_asin"] and g["term"] in targeted_asins):
            continue
        g["cpc"] = g["spend"] / g["clicks"] if g["clicks"] else None
        raise_ok = 1 + cfg["max_bid_raise"]
        g["bid"] = round(g["cpc"] * min(raise_ok, max(0.8, target / g["acos"])), 2) if g["cpc"] else None
        g["source_groups"] = sorted(set((s["campaign"], s["ad_group"]) for s in g["sources"]
                                        if not _is_own_exact(s)))
        harvest.append(g)

    bleeders.sort(key=lambda r: -r["spend"])
    funnel.sort(key=lambda r: -r["spend"])
    watch.sort(key=lambda r: -r["spend"])
    high_acos.sort(key=lambda r: -(r["spend"] - target * r["sales"]))
    harvest.sort(key=lambda g: -g["sales"])
    zero_order_spend = sum(r["spend"] for r in rows if r["orders"] <= 0)
    # zero-order spend on terms with too few clicks to judge = the normal cost of testing search terms
    longtail_spend = sum(r["spend"] for r in rows if r["orders"] <= 0 and r["clicks"] < th["watch_clicks"])
    bleed_spend = sum(r["spend"] for r in bleeders)
    excess_spend = sum(max(0.0, r["spend"] - target * r["sales"]) for r in high_acos)
    days = _days(report["meta"])
    return {"totals": totals, "thresholds": th, "bleeders": bleeders, "watch": watch,
            "high_acos": high_acos, "harvest": harvest, "protected_hits": protected_hits, "funnel": funnel,
            "funnel_spend": sum(r["spend"] for r in funnel), "longtail_spend": longtail_spend,
            "zero_order_spend": zero_order_spend, "bleed_spend": bleed_spend, "excess_spend": excess_spend,
            "days": days, "target_acos": target, "cfg": cfg, "meta": report["meta"], "all_rows": rows}


def _days(meta):
    import datetime
    try:
        a = datetime.date.fromisoformat(meta["date_from"][:10])
        b = datetime.date.fromisoformat(meta["date_to"][:10])
        return (b - a).days + 1
    except (TypeError, ValueError, KeyError):
        return None


# ---------------------------------------------------------------- output

T = {
    "en": {
        "title": "TermSweep audit", "period": "Period", "unknown": "unknown (no date column)",
        "days": "days", "spend": "Ad spend", "sales": "Ad sales", "acos": "ACOS", "orders": "Orders",
        "clicks": "Clicks", "cvr": "Conversion rate", "cpc": "Avg. CPC", "terms": "Search terms",
        "zero": "Spend on terms without a single order", "bleed": "Clear bleeders (rule below)",
        "longtail": "of which terms with fewer than %d clicks each (testing cost — too few clicks to judge one by one)",
        "excess": "Overspend above target ACOS on converting terms",
        "monthly": "≈ per 30 days", "target": "Target ACOS", "target_default": "(default — set yours with TermSweep setup)",
        "rule": "Rule: no order after %d clicks (a term converting like your account average would have sold by then with 90 %% probability) or after spending two target CPAs (= %s)",
        "rule_nocpa": "Rule: no order after %d clicks (a term converting like your account average would have sold by then with 90 %% probability)",
        "funnel": "Bleeding here, but selling in other ad groups", "h_funnel": "Sells elsewhere — negate here only to funnel traffic",
        "a_funnel": "Negate here only if the converting ad group sells the same product",
        "h_bleed": "Bleeders — negate these", "h_high": "Converting, but too expensive",
        "h_harvest": "Winners — add as exact keywords", "h_watch": "Watch list — not enough data yet",
        "h_prot": "Protected terms that are bleeding — review manually",
        "c_term": "Search term", "c_camp": "Campaign / ad group", "c_target": "Targeting",
        "c_action": "Suggested action", "c_bid": "Suggested bid", "c_sources": "Found in",
        "a_negative_exact": "Negative exact (ad group)", "a_negative_product": "Negative product target",
        "a_pause_or_lower_bid": "It is your own keyword/target: pause or lower bid",
        "a_lower_bid": "Lower bid by %d%%", "a_isolate": "Move to exact at ≈ %s and negate in source",
        "a_isolate_protected": "Move to exact at ≈ %s and negate in source (protected: moved, not blocked)",
        "a_watch": "Watch", "a_review_protected": "Protected — review",
        "more": "… and %d more in the Excel file", "none": "none",
        "files": "Files written", "f_review": "review workbook (all lists + every term)",
        "f_neg": "negatives to copy into Campaign Manager (or turn into a bulk file with TermSweep Pro)",
        "notice": "Suggestions only — TermSweep never changes your campaigns. Check the lists before uploading anything.",
        "columns": "Columns recognised", "rows": "rows",
        "no_campaign": "This file has no campaign/ad group columns, so negatives cannot be placed automatically. For placement (and TermSweep Pro bulk files) use Amazon's Sponsored Products search term report.",
        "no_ad_group": "This file has campaigns but no ad groups: add the negatives at campaign level (campaign negative keywords).",
    },
    "de": {
        "title": "TermSweep-Audit", "period": "Zeitraum", "unknown": "unbekannt (keine Datumsspalte)",
        "days": "Tage", "spend": "Werbekosten", "sales": "Werbeumsatz", "acos": "ACOS", "orders": "Bestellungen",
        "clicks": "Klicks", "cvr": "Konversionsrate", "cpc": "Ø CPC", "terms": "Suchbegriffe",
        "zero": "Kosten für Suchbegriffe ohne eine einzige Bestellung", "bleed": "Klare Geldverbrenner (Regel unten)",
        "longtail": "davon Begriffe mit je weniger als %d Klicks (Testkosten — einzeln noch nicht bewertbar)",
        "excess": "Mehrkosten über Ziel-ACOS bei konvertierenden Begriffen",
        "monthly": "≈ pro 30 Tage", "target": "Ziel-ACOS", "target_default": "(Standardwert — eigenen im TermSweep-Setup festlegen)",
        "rule": "Regel: keine Bestellung nach %d Klicks (ein Begriff mit deiner durchschnittlichen Konversionsrate hätte bis dahin mit 90 %% Wahrscheinlichkeit verkauft) oder nach Ausgaben von zwei Ziel-CPA (= %s)",
        "rule_nocpa": "Regel: keine Bestellung nach %d Klicks (ein Begriff mit deiner durchschnittlichen Konversionsrate hätte bis dahin mit 90 %% Wahrscheinlichkeit verkauft)",
        "funnel": "Verbrennt hier Geld, verkauft aber in anderen Anzeigengruppen", "h_funnel": "Verkauft anderswo — hier nur negativ setzen, um Traffic umzulenken",
        "a_funnel": "Nur negativ setzen, wenn die konvertierende Anzeigengruppe dasselbe Produkt bewirbt",
        "h_bleed": "Geldverbrenner — negativ setzen", "h_high": "Konvertiert, aber zu teuer",
        "h_harvest": "Gewinner — als exakte Keywords anlegen", "h_watch": "Beobachten — noch zu wenig Daten",
        "h_prot": "Geschützte Begriffe, die Geld verbrennen — manuell prüfen",
        "c_term": "Suchbegriff", "c_camp": "Kampagne / Anzeigengruppe", "c_target": "Ausrichtung",
        "c_action": "Vorschlag", "c_bid": "Gebotsvorschlag", "c_sources": "Gefunden in",
        "a_negative_exact": "Negativ exakt (Anzeigengruppe)", "a_negative_product": "Negatives Produkt-Targeting",
        "a_pause_or_lower_bid": "Ist dein eigenes Keyword/Target: pausieren oder Gebot senken",
        "a_lower_bid": "Gebot um %d %% senken", "a_isolate": "Als exaktes Keyword mit ≈ %s anlegen, in der Quelle negativ setzen",
        "a_isolate_protected": "Als exaktes Keyword mit ≈ %s anlegen, in der Quelle negativ setzen (geschützt: verschoben, nicht gesperrt)",
        "a_watch": "Beobachten", "a_review_protected": "Geschützt — prüfen",
        "more": "… und %d weitere in der Excel-Datei", "none": "keine",
        "files": "Erzeugte Dateien", "f_review": "Prüf-Arbeitsmappe (alle Listen + jeder Begriff)",
        "f_neg": "Negativ-Keywords zum Einfügen im Kampagnenmanager (oder mit TermSweep Pro als Bulk-Datei)",
        "notice": "Nur Vorschläge — TermSweep ändert nie etwas an deinen Kampagnen. Listen prüfen, bevor du etwas hochlädst.",
        "columns": "Erkannte Spalten", "rows": "Zeilen",
        "no_campaign": "Diese Datei hat keine Kampagnen-/Anzeigengruppen-Spalten — wo die Negativ-Keywords hingehören, lässt sich daraus nicht ablesen. Für die Zuordnung (und TermSweep-Pro-Bulk-Dateien) den Sponsored-Products-Suchbegriffbericht von Amazon verwenden.",
        "no_ad_group": "Diese Datei hat Kampagnen, aber keine Anzeigengruppen: Negativ-Keywords auf Kampagnenebene anlegen.",
    },
}


def money(x, lang, cur=None):
    if x is None:
        return "–"
    s = "{:,.2f}".format(x)
    if lang == "de":
        s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    sym = {"EUR": "€", "USD": "$", "GBP": "£"}.get((cur or "").upper(), cur or "")
    if not sym:
        return s
    return ("%s %s" % (s, sym)) if lang == "de" or sym == "€" else ("%s%s" % (sym, s))


def pct(x, lang):
    if x is None:
        return "–"
    s = "%.1f %%" % (x * 100) if lang == "de" else "%.1f%%" % (x * 100)
    return s.replace(".", ",") if lang == "de" else s


def num(x, lang):
    s = "{:,.0f}".format(x)
    return s.replace(",", ".") if lang == "de" else s


def md_escape(s):
    return str(s).replace("|", "\\|").replace("\n", " ")


def action_text(r, L, fmt_money=None):
    a = r.get("action")
    if a == "lower_bid":
        return L["a_" + a] % int(round((1 - r.get("bid_factor", 1)) * 100))
    if a == "isolate":
        bid = r.get("iso_bid")
        key = "a_isolate_protected" if r.get("protected") else "a_isolate"
        return L[key] % (fmt_money(bid) if fmt_money else ("%.2f" % bid if bid else "–"))
    if not a:
        return ""
    return L.get("a_" + a, a)


def render_audit(res, lang="en", files=None, top=15, extra_sections=None):
    L = T[lang]
    tot, th, meta = res["totals"], res["thresholds"], res["meta"]
    cur = res["cfg"].get("currency") or meta.get("currency")
    m = lambda x: money(x, lang, cur)
    out = []
    period = ("%s – %s (%d %s)" % (meta["date_from"], meta["date_to"], res["days"], L["days"])
              if res["days"] else L["unknown"])
    out.append("## %s — %s" % (L["title"], meta["file"]))
    out.append("")
    out.append("%s: %s · %s: %s %s" % (L["period"], period, L["target"], pct(res["target_acos"], lang),
                                         "" if res["cfg"].get("target_acos_set") else L["target_default"]))
    out.append("")
    out.append("| | |")
    out.append("|---|---|")
    out.append("| %s | %s |" % (L["spend"], m(tot["spend"])))
    out.append("| %s | %s |" % (L["sales"], m(tot["sales"])))
    out.append("| %s | %s |" % (L["acos"], pct(tot["acos"], lang)))
    out.append("| %s / %s | %s / %s |" % (L["clicks"], L["orders"], num(tot["clicks"], lang), num(tot["orders"], lang)))
    out.append("| %s / %s | %s / %s |" % (L["cvr"], L["cpc"], pct(tot["cvr"], lang), m(tot["cpc"])))
    out.append("| %s | %s |" % (L["terms"], num(tot["terms"], lang)))
    share = lambda x: (" (%s)" % pct(x / tot["spend"], lang)) if tot["spend"] else ""
    per30 = lambda x: (" · %s %s" % (m(x * 30.0 / res["days"]), L["monthly"])) if res["days"] else ""
    out.append("| **%s** | **%s**%s%s |" % (L["bleed"], m(res["bleed_spend"]), share(res["bleed_spend"]), per30(res["bleed_spend"])))
    if res.get("funnel"):
        out.append("| %s | %s%s |" % (L["funnel"], m(res["funnel_spend"]), share(res["funnel_spend"])))
    out.append("| %s | %s%s |" % (L["zero"], m(res["zero_order_spend"]), share(res["zero_order_spend"])))
    out.append("| ↳ %s | %s%s |" % (L["longtail"] % th["watch_clicks"], m(res["longtail_spend"]), share(res["longtail_spend"])))
    out.append("| %s | %s%s |" % (L["excess"], m(res["excess_spend"]), per30(res["excess_spend"])))
    out.append("")
    out.append((L["rule"] % (th["clicks"], m(2 * th["cpa"]))) if th["cpa"] else (L["rule_nocpa"] % th["clicks"]))
    for note in meta.get("notes") or []:
        out.append("")
        out.append("_%s_" % note)
    if not meta.get("has_campaign"):
        out.append("")
        out.append("> %s" % L["no_campaign"])
    elif not meta.get("has_ad_group"):
        out.append("")
        out.append("> %s" % L["no_ad_group"])

    def table(title, items, cols):
        out.append("")
        out.append("### %s (%d)" % (title, len(items)))
        if not items:
            out.append(L["none"])
            return
        out.append("| " + " | ".join(c[0] for c in cols) + " |")
        out.append("|" + "|".join("---" for _ in cols) + "|")
        for it in items[:top]:
            out.append("| " + " | ".join(md_escape(c[1](it)) for c in cols) + " |")
        if len(items) > top:
            out.append(L["more"] % (len(items) - top))

    camp = lambda r: ("%s / %s" % (r["campaign"], r["ad_group"])) if (r["campaign"] or r["ad_group"]) else "–"
    table(L["h_bleed"], res["bleeders"], [
        (L["c_term"], lambda r: r["term_raw"]), (L["c_camp"], camp),
        (L["clicks"], lambda r: num(r["clicks"], lang)), (L["spend"], lambda r: m(r["spend"])),
        (L["c_action"], lambda r: action_text(r, L))])
    table(L["h_high"], res["high_acos"], [
        (L["c_term"], lambda r: r["term_raw"]), (L["c_target"], lambda r: "%s %s" % (r["targeting"], r["match"] if r["match"] != "-" else "")),
        (L["orders"], lambda r: num(r["orders"], lang)), (L["spend"], lambda r: m(r["spend"])),
        (L["acos"], lambda r: pct(r["acos"], lang)), (L["c_action"], lambda r: action_text(r, L, m))])
    table(L["h_harvest"], res["harvest"], [
        (L["c_term"], lambda g: g["term_raw"]), (L["orders"], lambda g: num(g["orders"], lang)),
        (L["sales"], lambda g: m(g["sales"])), (L["acos"], lambda g: pct(g["acos"], lang)),
        (L["c_bid"], lambda g: m(g["bid"])),
        (L["c_sources"], lambda g: "; ".join("%s / %s" % s for s in g["source_groups"][:2]) + (" …" if len(g["source_groups"]) > 2 else ""))])
    if res.get("funnel"):
        table(L["h_funnel"], res["funnel"], [
            (L["c_term"], lambda r: r["term_raw"]), (L["c_camp"], camp),
            (L["clicks"], lambda r: num(r["clicks"], lang)), (L["spend"], lambda r: m(r["spend"])),
            (L["c_action"], lambda r: action_text(r, L))])
    if res["protected_hits"]:
        table(L["h_prot"], res["protected_hits"], [
            (L["c_term"], lambda r: r["term_raw"]), (L["c_camp"], camp),
            (L["clicks"], lambda r: num(r["clicks"], lang)), (L["spend"], lambda r: m(r["spend"]))])
    table(L["h_watch"], res["watch"], [
        (L["c_term"], lambda r: r["term_raw"]), (L["c_camp"], camp),
        (L["clicks"], lambda r: num(r["clicks"], lang)), (L["spend"], lambda r: m(r["spend"]))])
    for sec in extra_sections or []:
        out.append("")
        out.extend(sec)
    if files:
        out.append("")
        out.append("**%s:**" % L["files"])
        for path, what in files:
            out.append("- `%s` — %s" % (path, what))
    out.append("")
    out.append("_%s_" % L["notice"])
    return "\n".join(out)


def review_sheets(res, lang="en"):
    """Rows for the review workbook (same lists as the Markdown, but complete)."""
    L = T[lang]
    head_r = [L["c_term"], "Campaign", "Ad group", L["c_target"], "Match", L["clicks"], L["spend"],
              L["orders"], L["sales"], L["acos"], L["c_action"]]

    def r_row(r):
        return [r["term_raw"], r["campaign"], r["ad_group"], r["targeting"], r["match"], r["clicks"],
                round(r["spend"], 2), r["orders"], round(r["sales"], 2),
                round(r["acos"], 4) if r.get("acos") is not None else None, action_text(r, L)]

    w = [34, 30, 26, 22, 8, 8, 10, 8, 10, 8, 34]
    sheets = [
        ("Bleeders" if lang == "en" else "Geldverbrenner", [head_r] + [r_row(r) for r in res["bleeders"]], {"widths": w}),
        ("High ACOS" if lang == "en" else "Zu teuer", [head_r] + [r_row(r) for r in res["high_acos"]], {"widths": w}),
    ]
    head_h = [L["c_term"], L["orders"], L["clicks"], L["spend"], L["sales"], L["acos"], L["c_bid"], L["c_sources"]]
    sheets.append(("Harvest" if lang == "en" else "Gewinner", [head_h] + [
        [g["term_raw"], g["orders"], g["clicks"], round(g["spend"], 2), round(g["sales"], 2), round(g["acos"], 4),
         g["bid"], "; ".join("%s / %s" % s for s in g["source_groups"])] for g in res["harvest"]],
        {"widths": [34, 8, 8, 10, 10, 8, 10, 60]}))
    sheets.append(("Watch" if lang == "en" else "Beobachten", [head_r] + [r_row(r) for r in res["watch"]], {"widths": w}))
    if res.get("funnel"):
        sheets.append(("Sells elsewhere" if lang == "en" else "Verkauft anderswo", [head_r] + [r_row(r) for r in res["funnel"]], {"widths": w}))
    if res["protected_hits"]:
        sheets.append(("Protected" if lang == "en" else "Geschuetzt", [head_r] + [r_row(r) for r in res["protected_hits"]], {"widths": w}))
    all_rows = sorted(res["all_rows"] if "all_rows" in res else [], key=lambda r: -r["spend"])
    sheets.append(("All terms" if lang == "en" else "Alle Begriffe", [head_r] + [r_row(r) for r in all_rows], {"widths": w}))
    return sheets


def negatives_csv_rows(res):
    rows = [["Campaign", "Ad Group", "Negative", "Match Type", "Spend", "Clicks", "Reason"]]
    for r in res["bleeders"]:
        if r["action"] == "negative_exact":
            rows.append([r["campaign"], r["ad_group"], r["term_raw"], "negative exact", round(r["spend"], 2), int(r["clicks"]),
                         "0 orders"])
        elif r["action"] == "negative_product":
            rows.append([r["campaign"], r["ad_group"], 'asin="%s"' % r["term_raw"].upper(), "negative product target",
                         round(r["spend"], 2), int(r["clicks"]), "0 orders"])
    return rows
