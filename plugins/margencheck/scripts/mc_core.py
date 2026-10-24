"""Unit economics: Amazon FBA and Shopify contribution margin, break-even ACOS/TACOS, storage over
the real sell-through (incl. Q4 rates), capital tied up, decision (GO / TEST / NEIN) and fee levers.

Deterministic: the same input and fee tables always give the same numbers. Claude never does
this arithmetic itself.
"""
import calendar
import datetime as dt
import math

import mc_fees as F
import mc_landed as L
from mc_report import eur as _eur, num as _num, pct as _pct

ORDER = {"NEIN": 0, "TEST": 1, "PREIS PRÜFEN": 1, "GO": 2}


# ------------------------------------------------------------------ sell-through simulation
def lead_days(tables, mode):
    z = tables.cfg["zeiten"]
    return int(z["produktion_tage"]) + int(tables.cfg["fracht"][mode]["tage_transit"]) + int(z["inbound_tage"])


def simulate_sales(qty, per_month, start, vol_m3, store_key, amz, window, apparel, horizon=1095):
    """Day-by-day sell-through from the day the goods are available at Amazon.

    Returns storage cost (EUR, whole quantity, incl. aged-inventory surcharge), units sold in the
    peak window, days until sold out and the daily sales list (for the cash flow).
    """
    daily = max(per_month, 1e-9) * 12.0 / 365.0
    stock = float(qty)
    storage = aged = 0.0
    peak_units = 0.0
    q4_units = 0.0
    sold_days = []
    aged_bands = amz["lager"].get("veraltet_eur_m3_monat", [])
    aged_from = 271 if apparel else int(amz["lager"].get("veraltet_ab_tagen", 241))
    day = start
    i = 0
    while stock > 1e-9 and i < horizon:
        sold = min(stock, daily)
        avg = stock - sold / 2.0
        dim = calendar.monthrange(day.year, day.month)[1]
        storage += avg * vol_m3 * F.storage_rate(amz, store_key, day.month) / dim
        if i >= aged_from:
            rate = aged_bands[-1][1] if aged_bands else 0.0
            for upto, r in aged_bands:
                if i <= upto:
                    rate = r
                    break
            aged += avg * vol_m3 * rate / 30.0
        if F.in_peak(day, window):
            peak_units += sold
        if day.month >= 10:
            q4_units += sold
        sold_days.append(sold)
        stock -= sold
        day += dt.timedelta(days=1)
        i += 1
    return {"lager_gesamt": storage + aged, "lager_veraltet": aged, "spitzen_einheiten": peak_units,
            "q4_einheiten": q4_units, "tage_abverkauf": i, "rest": max(0.0, stock), "verkauf_tage": sold_days,
            "monatsabsatz": per_month, "start": start}


# ------------------------------------------------------------------ Amazon
def fuel_rate(amz, market_code, day):
    """Fuel and logistics surcharge on FBA fees valid on a given day (0 if not applicable)."""
    tz = amz.get("treibstoffzuschlag") or {}
    if market_code not in tz.get("maerkte", []) or day is None:
        return 0.0
    rate = 0.0
    for st in sorted(tz.get("stufen", []), key=lambda x: x["ab"]):
        try:
            start = dt.date(*[int(x) for x in st["ab"].split("-")])
        except (KeyError, ValueError):
            continue
        if day >= start:
            rate = float(st["satz"])
    return rate


def fee_factors(amz, market_code, m, day):
    """(DST on referral, DST on FBA, fuel surcharge on FBA) for a marketplace and day."""
    dst_ref = float(m.get("dst_referral", m.get("dst", 0.0)))
    dst_fba = float(m.get("dst_fba", m.get("dst", 0.0)))
    return dst_ref, dst_fba, fuel_rate(amz, market_code, day)


def amazon_unit(p, lc, tables, market_code, sim, price=None, tacos=None):
    """Contribution margin per kept (not returned) unit on Amazon FBA."""
    amz = tables.amazon
    code, m = tables.market(market_code)
    col = m["spalte"]
    plan = tables.cfg["planung"]
    brutto = float(price if price is not None else p["vk_brutto"])
    netto = brutto / (1.0 + m["ust"])
    dst_ref, dst_fba, fuel = fee_factors(amz, code, m, sim.get("start"))
    cat = p.get("kategorie") or "sonstige"
    info = F.fba_fee(amz, col, p["masse_cm"], p["gewicht_g"], cat, brutto, allow_lp=p.get("niedrigpreis", True) is not False)
    fba = float(p["fba_gebuehr"]) if p.get("fba_gebuehr") is not None else info["gebuehr"]
    if p.get("fba_gebuehr") is not None:
        info = dict(info, tarif="manuell (Seller Central)")
    fba_factor = (1 + fuel) * (1 + dst_fba)
    fba_d = fba * fba_factor
    ref, ref_desc, cat_name = F.referral_fee(amz, brutto, cat)
    ref_d = ref * (1 + dst_ref)
    window = F.peak_window(amz, code) if m.get("spitzenzeit") else None
    peak_fee = 0.0
    peak_arts = (amz.get("spitzenzeit") or {}).get("gilt_fuer", ["paket", "umschlag"])
    if window and not info.get("niedrigpreis") and info["art"] in peak_arts:
        peak_fee = window[2] * fba_factor * (sim["spitzen_einheiten"] / float(p["menge"]))
    r = float(p.get("retourenquote") if p.get("retourenquote") is not None else plan["retourenquote"])
    r = min(max(r, 0.0), 0.9)
    u = float(plan["unverkaeuflich_anteil"])
    k = r / (1.0 - r)
    ret = amz["retouren"]
    refund_admin = min(ref * ret["erstattungsgebuehr_anteil_referral"], ret["erstattungsgebuehr_max"])
    rpf = ret["bearbeitung_kleidung_anteil_fba"] * fba_d if cat in ret["bearbeitung_kleidung_kategorien"] else 0.0
    if p.get("retourengebuehr_je_retoure") is not None:
        rpf = float(p["retourengebuehr_je_retoure"])
    landed = lc["landed"]
    fba_eff = (fba_d + peak_fee) * (1.0 + k)
    ref_eff = ref_d + k * refund_admin
    ret_bearb = k * rpf
    ret_verlust = k * u * landed
    lager = sim["lager_gesamt"] / float(p["menge"])
    t = float(tacos if tacos is not None else (p.get("tacos_plan") if p.get("tacos_plan") is not None else plan["tacos_plan"]))
    ads = t * brutto
    db_vor = netto - landed - ref_eff - fba_eff - ret_bearb - ret_verlust - lager
    db = db_vor - ads
    be = db_vor / brutto if brutto else 0.0
    return {
        "kanal": "amazon", "markt": code, "markt_name": m["name"], "vk_brutto": brutto, "vk_netto": netto, "ust": m["ust"],
        "landed": landed, "referral": ref_d, "referral_regel": ref_desc, "kategorie_name": cat_name,
        "fba": fba_d, "fba_info": info, "spitzenzeit": peak_fee * (1.0 + k), "fba_eff": fba_eff,
        "treibstoff_satz": fuel, "dst_referral": dst_ref, "dst_fba": dst_fba, "fba_faktor": fba_factor,
        "erstattungsgebuehr": k * refund_admin, "retouren_bearbeitung": ret_bearb, "retouren_verlust": ret_verlust,
        "retouren_gesamt": k * refund_admin + ret_bearb + ret_verlust + fba_d * k,
        "retourenquote": r, "lager": lager, "werbung": ads, "tacos_plan": t,
        "db_vor_werbung": db_vor, "db": db, "be_tacos": be, "be_acos": be,
        "marge": db / netto if netto else 0.0, "roi": db / landed if landed else 0.0,
        "amazon_gebuehren": ref_eff + fba_eff + ret_bearb,
    }


# ------------------------------------------------------------------ Shopify
def shopify_unit(p, lc_shop, tables, sim=None, price=None, share=None):
    shop = tables.shopify
    plan = tables.cfg["planung"]
    ust = tables.amazon["maerkte"]["DE"]["ust"]
    brutto = float(price if price is not None else (p.get("vk_shopify") or p["vk_brutto"]))
    netto = brutto / (1.0 + ust)
    n = max(1, int(shop.get("einheiten_je_bestellung", 1)))
    vers_kunde = float(shop.get("kunde_zahlt_versand_brutto", 0.0))
    pay, plan_name = F.shopify_payment(shop, brutto * n + vers_kunde)
    pay /= n
    ship = F.shopify_shipping(shop, p["gewicht_g"] * n) / n
    ve = shop["versand_eigen"]
    pack = (float(ve.get("verpackung_je_bestellung", 0.0)) + float(ve.get("pick_pack_je_bestellung", 0.0))) / n
    back = float(ve["ruecksendung_je_retoure"]) if ve.get("ruecksendung_je_retoure") is not None else ship * n
    r = float(p.get("retourenquote_shop") if p.get("retourenquote_shop") is not None else
              (p.get("retourenquote") if p.get("retourenquote") is not None else plan["retourenquote"]))
    r = min(max(r, 0.0), 0.9)
    k = r / (1.0 - r)
    u = float(plan["unverkaeuflich_anteil"])
    landed = lc_shop["landed"]
    vers_erl = vers_kunde / (1.0 + ust) / n
    order_cost = (ship + pack + pay) * (1.0 + k)
    ret_cost = k * (back / n + u * landed)
    lager = float(shop.get("lagerkosten_je_einheit", 0.0))
    s = float(share if share is not None else (shop.get("marketing_anteil") if shop.get("marketing_anteil") is not None
                                               else plan["tacos_plan"]))
    mkt = s * brutto
    db_vor = netto + vers_erl - landed - order_cost - ret_cost - lager
    db = db_vor - mkt
    be = db_vor / brutto if brutto else 0.0
    return {
        "kanal": "shopify", "markt": "Shopify DE", "tarif": plan_name, "vk_brutto": brutto, "vk_netto": netto,
        "landed": landed, "zahlung": pay * (1.0 + k), "versand": ship * (1.0 + k), "verpackung": pack * (1.0 + k),
        "versand_erloes": vers_erl, "retouren_gesamt": ret_cost, "retourenquote": r, "lager": lager,
        "werbung": mkt, "marketing_anteil": s, "db_vor_werbung": db_vor, "db": db, "be_tacos": be,
        "be_roas": (1.0 / be) if be > 0 else None, "marge": db / netto if netto else 0.0,
        "roi": db / landed if landed else 0.0,
    }


# ------------------------------------------------------------------ decision
def verdict(unit, tables):
    e = tables.cfg["entscheidung"]
    be, db, marge = unit["be_tacos"], unit["db"], unit["marge"]
    if db <= 0 or be < e["test_be_tacos"]:
        if be < e["test_be_tacos"]:
            why = "BE-TACOS %.0f %% < %.0f %% – die Marge ist der Engpass" % (be * 100, e["test_be_tacos"] * 100)
        else:
            why = "DB bei Plan-Werbung %s ≤ 0" % _eur(db)
        return "NEIN", "Marge", why
    if be >= e["go_be_tacos"] and db >= e["min_db_eur"] and marge >= e["min_marge"]:
        return "GO", "Rechnung trägt", "BE-TACOS %.0f %% ≥ %.0f %% – Marge ist nicht der Engpass" % (be * 100, e["go_be_tacos"] * 100)
    if be < e["go_be_tacos"]:
        why = "BE-TACOS %.0f %% zwischen %.0f und %.0f %% – tragfähig, kalter Launch wird eng" % (
            be * 100, e["test_be_tacos"] * 100, e["go_be_tacos"] * 100)
    elif db < e["min_db_eur"]:
        why = "DB %s unter Mindest-DB %s" % (_eur(db), _eur(e["min_db_eur"]))
    else:
        why = "Marge %.0f %% unter Mindestmarge %.0f %%" % (marge * 100, e["min_marge"] * 100)
    return "TEST", "Rechnung knapp", why


def combine(calc, manual):
    """Final decision = the stricter of calculation and qualitative assessment (Claude/user)."""
    if not manual:
        return calc
    raw = str(manual.get("urteil") or "").strip()
    base = raw.split("·")[0].split(" - ")[0].strip().upper()
    if base.startswith("PREIS"):
        base = "PREIS PRÜFEN"
    if base not in ORDER:
        return calc
    if ORDER[base] < ORDER[calc[0]] or (base == "PREIS PRÜFEN" and calc[0] != "NEIN"):
        sub = raw.split("·", 1)[1].strip() if "·" in raw else (manual.get("grund") or "Bewertung")
        return base, sub, manual.get("begruendung") or manual.get("grund") or ""
    return calc


# ------------------------------------------------------------------ negotiation targets and levers
def max_ek_for(target_be, p, lc, unit, tables):
    """Highest purchase price (supplier currency, per sellable unit) that still reaches target BE-TACOS."""
    plan = tables.cfg["planung"]
    r = unit["retourenquote"]
    k = r / (1.0 - r)
    u = plan["unverkaeuflich_anteil"] if unit["kanal"] == "amazon" else plan["unverkaeuflich_anteil"]
    brutto = unit["vk_brutto"]
    a = unit["db_vor_werbung"] + unit["landed"] * (1.0 + k * u)
    landed_target = (a - target_be * brutto) / (1.0 + k * u)
    eust_cost_factor = (lc["eust"] / lc["zollwert"] / (1.0 + lc["zollsatz"])) if lc["eust_kosten"] > 0 and lc["zollwert"] else 0.0
    per_ek_eur = (1.0 + lc["zollsatz"]) * (1.0 + eust_cost_factor)
    ek_eur = lc["ek_eur"] + (landed_target - unit["landed"]) / per_ek_eur
    return ek_eur / lc["kurs"] if ek_eur > 0 else None


def min_price_for(target_be, p, lc, tables, market_code, sim, start_price):
    """Lowest gross price (10-cent steps) at which BE-TACOS reaches the target."""
    cents = max(100, int(round(start_price * 50)) // 10 * 10)
    top = int(start_price * 400)
    while cents <= top:
        u = amazon_unit(p, lc, tables, market_code, sim, price=cents / 100.0)
        if u["be_tacos"] >= target_be and u["db"] > 0:
            return cents / 100.0
        cents += 10
    return None


def fee_levers(p, lc, unit, tables, market_code, sim):
    """Concrete fee levers: smaller packing, Low-Price threshold, referral price steps."""
    out = []
    amz = tables.amazon
    _, m = tables.market(market_code)
    col = m["spalte"]
    cat = p.get("kategorie") or "sonstige"
    info = unit["fba_info"]
    base_fba = unit["fba"]
    if p.get("fba_gebuehr") is None:
        dims = sorted(p["masse_cm"], reverse=True)
        g = p["gewicht_g"]
        lp_ok = p.get("niedrigpreis", True) is not False
        dst = unit.get("fba_faktor", 1.0)
        cands = []
        gk = amz["groessenklassen"]
        tiers = [gk["def"][t]["max_cm"] for t in gk["reihenfolge"][:-1]]
        if cat in amz.get("auswahl_kategorien", []):
            sel = gk["auswahl_kategorien_paket"]
            tiers += [sel["def"][t]["max_cm"] for t in sel["reihenfolge"]]
        for mx in tiers:
            mxs = sorted(mx, reverse=True)
            new = [min(d, x) for d, x in zip(dims, mxs)]
            if new == dims or any((d - n) / d > 0.15 for d, n in zip(dims, new)):
                continue
            f2 = F.fba_fee(amz, col, new, g, cat, unit["vk_brutto"], allow_lp=lp_ok)
            cands.append((base_fba - f2["gebuehr"] * dst, "Packmaß %s cm statt %s cm" % (
                "×".join(_n(x) for x in new), "×".join(_n(x) for x in dims)), f2))
        def label(fi):
            name = fi["klasse_name"] + (" (Niedrigpreis)" if fi.get("niedrigpreis") else "")
            return name + (" ≤ %s g" % _num(fi["band_g"], 0) if fi.get("band_g") else "")
        block = None
        if info.get("band_g") and not info.get("niedrigpreis"):
            for limit in [50, 60, 80, 100, 150, 210, 400, 460, 900, 1400, 1900, 2900, 3900, 5900, 8900]:
                if limit < g <= limit * 1.10:
                    f2 = F.fba_fee(amz, col, dims, limit, cat, unit["vk_brutto"], allow_lp=lp_ok)
                    cands.append((base_fba - f2["gebuehr"] * dst, "Stückgewicht ≤ %s g statt %s g" % (_num(limit, 0), _num(g, 0)), f2))
        cands = [c for c in cands if c[0] >= 0.10]
        if cands:
            best = max(cands, key=lambda c: c[0])
            out.append(("packmass", "%s → %s statt %s: FBA-Gebühr −%s/Stk." % (
                best[1], label(best[2]), label(info), _eur(best[0]))))
    # Low-Price FBA threshold
    if not info.get("niedrigpreis") and info.get("lp_gebuehr_moeglich") is not None and p.get("fba_gebuehr") is None:
        limit = info.get("lp_grenze", 20.0)
        if unit["vk_brutto"] > limit and unit["vk_brutto"] - limit <= 3.0:
            alt = amazon_unit(p, lc, tables, market_code, sim, price=limit - 0.01)
            if alt["db"] > unit["db"] + 0.05:
                out.append(("niedrigpreis", "VK %s → %s aktiviert den Niedrigpreisversand (FBA %s statt %s); DB %s statt %s je Stück." % (
                _eur(unit["vk_brutto"]), _eur(limit - 0.01), _eur(alt["fba"]), _eur(unit["fba"]), _eur(alt["db"]), _eur(unit["db"]))))
    # referral price steps (whole-price bands, e.g. apparel 15/20 €)
    rule = amz["referral"]["kategorien"].get(cat) or {}
    if rule.get("typ") == "stufe":
        for upto, rate in rule["stufen"]:
            if upto is not None and upto < unit["vk_brutto"] <= upto + 2.0:
                alt = amazon_unit(p, lc, tables, market_code, sim, price=upto)
                if alt["db"] > unit["db"] - 0.05:
                    out.append(("preisstufe", "VK %s → %s senkt die Verkaufsgebühr auf %s: DB %s statt %s je Stück." % (
                        _eur(unit["vk_brutto"]), _eur(upto), _pct(rate, 0), _eur(alt["db"]), _eur(unit["db"]))))
                break
    return out


def _n(x):
    return ("%.1f" % x).rstrip("0").rstrip(".").replace(".", ",")


def hints(p, lc, unit, sim, shipment, tables, market_code):
    out = [("zahlformat", h + ".") for h in p.get("zahl_hinweise") or []]
    if p.get("annahmen"):
        out.append(("schaetzung", "Schätzwerte: %s – vor der Bestellung beim Lieferanten bestätigen lassen." % ", ".join(p["annahmen"])))
    if p.get("zoll_quelle") == "standard":
        out.append(("zoll", "Zollsatz %s angenommen (kein HS-Code). HS-Code klären; eine verbindliche Zolltarifauskunft (ZTA) ist kostenlos und 3 Jahre EU-weit bindend." % _pct(lc["zollsatz"])))
    elif p.get("zoll_quelle") and "prüfen" in str(p.get("zoll_hinweis", "")):
        out.append(("zoll", "Zollsatz %s ist ein Richtwert (HS %s) – TARIC prüfen." % (_pct(lc["zollsatz"]), p.get("hs_code"))))
    if lc.get("geliefert"):
        out.append(("dap", "%s-Angebot: Transport bis zum Bestimmungsort ist im Preis (keine Fracht gerechnet). Einfuhrabfertigung, "
                           "Zoll und EUSt trägt der Käufer; der Zollsatz hängt vom Ursprungsland ab (z. B. Türkei mit A.TR, "
                           "EU-Ware: 0 %%) – sonst Satz laut HS-Code." % lc["geliefert"]))
    if lc["ddp"]:
        out.append(("ddp", "DDP-Angebot: EUSt ist nur abziehbar, wenn die Einfuhr auf die eigene EORI läuft – beim Lieferanten klären."))
    if lc["eust_kosten"] > 0:
        out.append(("eust", "EUSt %s/Stk als Kosten gerechnet (nicht abziehbar)." % _eur(lc["eust_kosten"])))
    if unit["kanal"] == "amazon":
        if sim["q4_einheiten"] / float(p["menge"]) > 0.3:
            out.append(("q4", "%s des Abverkaufs fällt in Okt–Dez (Q4-Lagertarif, Spitzenzeit-Zuschlag)." % _pct(sim["q4_einheiten"] / float(p["menge"]), 0)))
        weeks = sim["tage_abverkauf"] / 7.0
        cat = p.get("kategorie") or "sonstige"
        if weeks > 22 and cat not in tables.amazon["lager"].get("kleidung_kategorien", []):
            out.append(("nutzung", "Reichweite %.0f Wochen > 22: kontoweiter Lagernutzungszuschlag möglich (ab 14,85 €/m³/Monat) – kleinere Menge oder Teilanlieferung prüfen." % weeks))
        if sim["lager_veraltet"] > 0:
            out.append(("veraltet", "Abverkauf %d Tage: Zuschlag für veralteten Bestand (> 241 Tage) eingerechnet (%s/Stk)." % (sim["tage_abverkauf"], _eur(sim["lager_veraltet"] / float(p["menge"])))))
        if sim["rest"] > 0:
            out.append(("rest", "Bei %s Stk/Monat ist die Menge nach 3 Jahren nicht abverkauft." % _num(sim["monatsabsatz"], 0)))
    if p.get("absatz_angenommen"):
        out.append(("absatz", "Monatsabsatz nicht angegeben – angenommen: Menge in %d Monaten verkauft (%s Stk/Monat)." % (
            p["absatz_angenommen"], _num(sim["monatsabsatz"], 0))))
    if lc["ddp"] or lc.get("geliefert") or p.get("fracht_je_einheit") is not None:
        return out  # not part of our own shipment: minimum freight and packing list do not apply
    mode = shipment["modus"]
    f = tables.cfg["fracht"]
    if mode == "bahn" and shipment["m3"] * f["bahn"]["usd_je_m3"] < f["bahn"]["min_usd"]:
        out.append(("mindestfracht", "Bahn-Mindestabrechnung greift (%s m³ liegen unter %s $ Mindestbetrag) – bei kleinen Sendungen ist Luft oft billiger." % (_num(shipment["m3"], 2), _num(f["bahn"]["min_usd"], 0))))
    if mode == "see" and shipment["m3"] < f["see"]["min_m3"]:
        out.append(("mindestfracht", "See-Mindestabrechnung %s m³ greift (Sendung %s m³)." % (_num(f["see"]["min_m3"], 0), _num(shipment["m3"], 2))))
    if lc["volumen_geschaetzt"]:
        out.append(("packliste", "Sendungsvolumen aus dem Packmaß geschätzt – Packliste mit Kartonmaßen/CBM anfordern."))
    return out


# ------------------------------------------------------------------ capital
def cashflow(items, tables, mode, horizon_pad=60, channel="amazon"):
    """Cash flow of one order (all positions, one freight mode), in days from ordering.

    items: list of dicts with p, lc (landed row), unit (amazon or shopify unit), sim.
    """
    z = tables.cfg["zeiten"]
    zoll = tables.cfg["zoll"]
    prod = int(z["produktion_tage"])
    transit = int(tables.cfg["fracht"][mode]["tage_transit"])
    inbound = int(z["inbound_tage"])
    payout = int(z["auszahlung_tage_shopify"] if channel == "shopify" and "auszahlung_tage_shopify" in z else z["auszahlung_tage"])
    dep = float(z["anzahlung_anteil"])
    avail = prod + transit + inbound
    last = avail + max([len(it["sim"]["verkauf_tage"]) for it in items] or [0]) + payout + 1
    days = max(last, prod + transit + int(zoll["eust_erstattung_tage"]) + 1) + 1
    flow = [0.0] * (days + horizon_pad)
    for it in items:
        p, lc, unit, sim = it["p"], it["lc"], it["unit"], it["sim"]
        q = float(p["menge"])
        goods = lc["ek_eur"] * q
        flow[0] -= goods * dep
        flow[prod] -= goods * (1 - dep) + lc["fracht"] * q
        flow[prod + transit] -= (lc["nebenkosten"] + lc["zoll"] + lc["eust"]) * q
        flow[prod + transit] -= lc["vorbereitung"] * q
        if lc["eust_kosten"] <= 0:
            flow[prod + transit + int(zoll["eust_erstattung_tage"])] += lc["eust"] * q
        cash_per_unit = unit["db"] + unit["landed"]
        for d, sold in enumerate(sim["verkauf_tage"]):
            flow[avail + d + payout] += sold * cash_per_unit
    cum, peak, peak_day, payback = 0.0, 0.0, 0, None
    series = []
    for d, v in enumerate(flow):
        cum += v
        series.append(cum)
        if cum < peak:
            peak, peak_day = cum, d
        if payback is None and d > prod and cum >= 0:
            payback = d
    end = len(series) - 1
    while end > 0 and abs(flow[end]) < 1e-9:
        end -= 1
    db_total = sum(it["unit"]["db"] * it["p"]["menge"] for it in items)
    cap = -peak
    cycle = max(end, 1)
    return {"kapital_max": cap, "tag_kapital_max": peak_day, "payback_tag": payback, "zyklus_tage": cycle,
            "db_gesamt": db_total, "rendite_jahr": (db_total / cap * 365.0 / cycle) if cap > 0 else None,
            "verfuegbar_tag": avail, "verlauf": series[:end + 1], "kapital_euro_tage": -sum(min(0.0, c) for c in series[:end + 1])}


# ------------------------------------------------------------------ one order end to end
def best_mode(evs):
    """Freight mode with the highest total contribution margin (ties: cheaper freight)."""
    return max(evs, key=lambda md: (round(evs[md]["kapital"]["db_gesamt"], 2), -evs[md]["sendung"][md]))


def plan_sales(p, tables):
    plan = tables.cfg["planung"]
    if p.get("monatsabsatz"):
        return float(p["monatsabsatz"]), None
    months = 3
    return float(p["menge"]) / months, months


def evaluate(positions, tables, mode="auto", market=None, channels=("amazon",), today=None, start=None, focus=None):
    """Compute everything for one order. Returns dict with shipment, per-position results and cash flow."""
    today = today or tables.today
    market = market or tables.markt
    if mode == "auto":
        evs = {md: evaluate(positions, tables, md, market, channels, today, start) for md in L.MODES}
        return evs[best_mode(evs)]
    rows_a, ship = L.landed_costs(positions, tables, mode, "amazon")
    rows_s, _ = L.landed_costs(positions, tables, mode, "shopify")
    avail = start or (today + dt.timedelta(days=lead_days(tables, mode)))
    code, m = tables.market(market)
    window = F.peak_window(tables.amazon, code) if m.get("spitzenzeit") else None
    results = []
    for i, (p, la, ls) in enumerate(zip(positions, rows_a, rows_s)):
        if focus is not None and i != focus:
            results.append({"p": p, "lc": la, "lc_shop": ls, "skip": True})
            continue
        per_month, assumed = plan_sales(p, tables)
        if assumed:
            p["absatz_angenommen"] = assumed
        res = {"p": p, "lc": la, "lc_shop": ls}
        cat = p.get("kategorie") or "sonstige"
        if "amazon" in channels:
            info = F.fba_fee(tables.amazon, m["spalte"], p["masse_cm"], p["gewicht_g"], cat, p["vk_brutto"])
            key = F.storage_key(tables.amazon, info["art"], cat, p.get("gefahrgut"))
            sim = simulate_sales(p["menge"], per_month, avail, L.unit_volume_m3(p), key, tables.amazon, window,
                                 cat in tables.amazon["lager"].get("kleidung_kategorien", []))
            unit = amazon_unit(p, la, tables, code, sim)
            res.update(sim=sim, amazon=unit)
            calc = verdict(unit, tables)
            res["urteil_rechnung"] = calc
            res["urteil"] = combine(calc, p.get("bewertung"))
            e = tables.cfg["entscheidung"]
            res["max_ek_go"] = max_ek_for(e["go_be_tacos"], p, la, unit, tables)
            res["max_ek_test"] = max_ek_for(e["test_be_tacos"], p, la, unit, tables)
            res["min_vk_go"] = min_price_for(e["go_be_tacos"], p, la, tables, code, sim, p["vk_brutto"])
            res["hebel"] = fee_levers(p, la, unit, tables, code, sim)
            res["hinweise"] = hints(p, la, unit, sim, ship, tables, code)
        if "shopify" in channels:
            simple_sim = simulate_sales(p["menge"], per_month, avail, L.unit_volume_m3(p), "standard", tables.amazon, None, False)
            su = shopify_unit(p, ls, tables, simple_sim)
            res["shopify"] = su
            res.setdefault("sim", simple_sim)
            calc_s = verdict(su, tables)
            res["urteil_shopify"] = combine(calc_s, p.get("bewertung"))
            if "amazon" not in channels:
                res["urteil_rechnung"] = calc_s
                res["urteil"] = res["urteil_shopify"]
                res.setdefault("hinweise", hints(p, ls, su, simple_sim, ship, tables, code))
                res.setdefault("hebel", [])
                e = tables.cfg["entscheidung"]
                res["max_ek_go"] = max_ek_for(e["go_be_tacos"], p, ls, su, tables)
                res["max_ek_test"] = max_ek_for(e["test_be_tacos"], p, ls, su, tables)
                res["min_vk_go"] = None
        results.append(res)
    main = "amazon" if "amazon" in channels else "shopify"
    items = [{"p": r["p"], "lc": r["lc"] if main == "amazon" else r["lc_shop"], "unit": r[main], "sim": r["sim"]}
             for r in results if not r.get("skip")]
    cf = cashflow(items, tables, mode, channel=main)
    return {"modus": mode, "sendung": ship, "positionen": results, "kapital": cf, "markt": code,
            "markt_name": m["name"], "kanaele": list(channels), "verfuegbar_ab": avail, "heute": today}
