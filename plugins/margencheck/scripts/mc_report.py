"""Markdown output (German). All figures are formatted, never recomputed, here."""
import datetime as dt

MODE_NAME = {"see": "Seefracht", "bahn": "Bahn", "luft": "Luftfracht"}


def num(x, dec=2):
    if x is None:
        return "–"
    x = float(x)
    if abs(x) < 0.5 * 10 ** (-dec):
        x = 0.0
    s = "{:,.{d}f}".format(x, d=dec)
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def eur(x, dec=2):
    return "–" if x is None else num(x, dec) + " €"


def pct(x, dec=1):
    return "–" if x is None else num(float(x) * 100.0, dec) + " %"


def date_de(d):
    return d.strftime("%d.%m.%Y") if isinstance(d, (dt.date, dt.datetime)) else str(d)


def verdict_badge(v):
    return {"GO": "🟢 GO", "TEST": "🟡 TEST", "NEIN": "🔴 NEIN", "PREIS PRÜFEN": "🔵 PREIS PRÜFEN"}.get(v, v)


def unit_lines_amazon(u):
    fi = u["fba_info"]
    k = u["retourenquote"] / (1 - u["retourenquote"])
    extra = []
    if u.get("treibstoff_satz"):
        extra.append("+ %s Treibstoffaufschlag" % pct(u["treibstoff_satz"], 1))
    if u.get("dst_fba"):
        extra.append("+ %s Digitalsteuer" % pct(u["dst_fba"], 0))
    fba_label = "FBA-Versand (%s%s%s)" % (fi["klasse_name"], ", Niedrigpreis" if fi.get("niedrigpreis") else "",
                                         (", " + ", ".join(extra)) if extra else "")
    if fi.get("tarif", "").startswith("manuell"):
        fba_label = "FBA-Versand (manuell aus Seller Central%s)" % ((", " + ", ".join(extra)) if extra else "")
    ref_label = "Verkaufsgebühr (%s%s)" % (u["referral_regel"], (" + %s Digitalsteuer" % pct(u["dst_referral"], 0)) if u.get("dst_referral") else "")
    rows = [
        ("VK brutto", u["vk_brutto"], None),
        ("− USt %s" % pct(u["ust"], 0), u["vk_brutto"] - u["vk_netto"], None),
        ("= VK netto", u["vk_netto"], 1.0),
        ("Landed Cost", u["landed"], u["landed"] / u["vk_netto"]),
        (ref_label, u["referral"], u["referral"] / u["vk_netto"]),
        (fba_label + (" inkl. Retourensendungen" if k > 0 else ""), u["fba"] * (1 + k), u["fba"] * (1 + k) / u["vk_netto"]),
    ]
    if u["spitzenzeit"] > 0.0049:
        rows.append(("Spitzenzeit-Zuschlag (anteilig)", u["spitzenzeit"], u["spitzenzeit"] / u["vk_netto"]))
    rows.append(("Lager (Abverkauf inkl. Q4-Tarif)", u["lager"], u["lager"] / u["vk_netto"]))
    ret = u["erstattungsgebuehr"] + u["retouren_bearbeitung"] + u["retouren_verlust"]
    rows.append(("Retouren %s (Erstattungsgebühr, Bearbeitung, unverkäuflich)" % pct(u["retourenquote"], 0), ret, ret / u["vk_netto"]))
    rows.append(("**= DB vor Werbung**", u["db_vor_werbung"], u["db_vor_werbung"] / u["vk_netto"]))
    rows.append(("− Werbung (TACOS %s)" % pct(u["tacos_plan"], 0), u["werbung"], u["werbung"] / u["vk_netto"]))
    rows.append(("**= Deckungsbeitrag**", u["db"], u["db"] / u["vk_netto"]))
    return rows


def unit_lines_shopify(u):
    rows = [
        ("VK brutto", u["vk_brutto"], None),
        ("= VK netto", u["vk_netto"], 1.0),
    ]
    if u["versand_erloes"]:
        rows.append(("+ Versanderlös netto", u["versand_erloes"], u["versand_erloes"] / u["vk_netto"]))
    rows += [
        ("Landed Cost", u["landed"], u["landed"] / u["vk_netto"]),
        ("Zahlungsgebühren (%s)" % u["tarif"], u["zahlung"], u["zahlung"] / u["vk_netto"]),
        ("Versand + Verpackung", u["versand"] + u["verpackung"], (u["versand"] + u["verpackung"]) / u["vk_netto"]),
        ("Retouren %s (Rücksendung, unverkäuflich)" % pct(u["retourenquote"], 0), u["retouren_gesamt"], u["retouren_gesamt"] / u["vk_netto"]),
    ]
    if u["lager"]:
        rows.append(("Lager", u["lager"], u["lager"] / u["vk_netto"]))
    rows += [
        ("**= DB vor Marketing**", u["db_vor_werbung"], u["db_vor_werbung"] / u["vk_netto"]),
        ("− Marketing (%s vom Umsatz)" % pct(u["marketing_anteil"], 0), u["werbung"], u["werbung"] / u["vk_netto"]),
        ("**= Deckungsbeitrag**", u["db"], u["db"] / u["vk_netto"]),
    ]
    return rows


def ek_num(x):
    """Purchase price for display: 3 decimals only below 1 ('0,345'); from 1 on 2 decimals, because '21,820' reads
    as twenty-one thousand when copied into SupplierPilot or a supplier mail."""
    if x is None:
        return "–"
    return num(x, 3 if abs(x) < 1 else 2)


def ek_txt(x, cur):
    return "unerreichbar (auch EK 0 reicht nicht)" if x is None else "%s %s" % (ek_num(x), cur)


def table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] + ["---:"] * (len(header) - 1)) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(out)


def landed_lines(p, lc, ship):
    mode = ship["modus"]
    rows = [("EK %s %s × Kurs %s" % (num(p["ek"], 3), lc["waehrung"], num(lc["kurs"], 4)), lc["ek_eur"])]
    if lc["ddp"]:
        rows.append(("Fracht, Zoll (DDP – im EK enthalten)", 0.0))
    else:
        rows.append(("Fracht %s (Anteil nach %s)" % (MODE_NAME[mode], "frachtpfl. Gewicht" if mode == "luft" else "Volumen"), lc["fracht"]))
        rows.append(("Nebenkosten der Sendung (Verzollung, Zustellung)", lc["nebenkosten"]))
        rows.append(("Zoll %s auf CIF (%s)" % (pct(lc["zollsatz"]), {"eingabe": "Eingabe", "tabelle": "HS %s" % (p.get("hs_code") or ""),
                                                                    "standard": "Annahme ohne HS-Code"}.get(p.get("zoll_quelle"), "")), lc["zoll"]))
    if lc["eust_kosten"] > 0:
        rows.append(("EUSt %s (nicht abziehbar)" % pct(ship["eust_satz"], 0), lc["eust_kosten"]))
    rows.append(("Etikett, Set-Verpackung, Inbound", lc["vorbereitung"]))
    rows.append(("**= Landed Cost**", lc["landed"]))
    return rows


def render_single(res, ev, modes, tables, channels):
    """res: one position result, ev: evaluation dict, modes: {mode: evaluation} for comparison."""
    p, lc = res["p"], res["lc"]
    out = []
    v, sub, why = res["urteil"]
    out.append("# MargenCheck – %s" % p["name"])
    out.append("")
    head = res["amazon"] if "amazon" in res else res["shopify"]
    out.append("**Urteil: %s** · %s – %s" % (verdict_badge(v), sub, why))
    if res.get("urteil_rechnung") and res["urteil_rechnung"][0] != v:
        out.append("Rechnung allein: %s (%s)" % (res["urteil_rechnung"][0], res["urteil_rechnung"][2]))
    out.append("")
    cap = ev["kapital"]
    out.append("Landed Cost **%s** · DB **%s/Stk** bei %s Werbung · Break-even-ACOS/TACOS **%s** · Kapitalbedarf **%s** · %s, %s, %s Stk" % (
        eur(head["landed"]), eur(head["db"]), pct(head.get("tacos_plan", head.get("marketing_anteil")), 0), pct(head["be_tacos"]),
        eur(cap["kapital_max"], 0), ev["markt_name"] if "amazon" in res else "Shopify", MODE_NAME[ev["modus"]], num(p["menge"], 0)))
    out.append("")
    if "amazon" in res:
        u = res["amazon"]
        out.append("## Stückrechnung %s (je verkaufter Einheit)" % u["markt_name"])
        out.append("")
        out.append(table(["Posten", "€ je Stück", "% vom Netto"], [(a, num(b), pct(c) if c is not None else "") for a, b, c in unit_lines_amazon(u)]))
        out.append("")
        out.append("Break-even-ACOS = Break-even-TACOS = **%s** (DB vor Werbung ÷ VK brutto) · Marge %s · ROI auf Landed Cost %s" % (
            pct(u["be_tacos"]), pct(u["marge"]), pct(u["roi"], 0)))
        out.append("")
    if "shopify" in res:
        su = res["shopify"]
        out.append("## Stückrechnung Shopify (je Bestellung mit 1 Stück)")
        out.append("")
        out.append(table(["Posten", "€ je Stück", "% vom Netto"], [(a, num(b), pct(c) if c is not None else "") for a, b, c in unit_lines_shopify(su)]))
        out.append("")
        out.append("Break-even-Marketinganteil **%s** · Break-even-ROAS **%s** · Marge %s" % (
            pct(su["be_tacos"]), num(su["be_roas"], 2) if su["be_roas"] else "–", pct(su["marge"])))
        out.append("")
    out.append("## Landed Cost je Stück (%s, %s Stk)" % (MODE_NAME[ev["modus"]], num(p["menge"], 0)))
    out.append("")
    out.append(table(["Posten", "€ je Stück"], [(a, num(b)) for a, b in landed_lines(p, lc, ev["sendung"])]))
    if lc["eust_kosten"] <= 0 and lc["eust"] > 0:
        out.append("")
        out.append("EUSt %s = %s/Stk wird vorgestreckt und als Vorsteuer zurückgeholt (nur Kapitalbindung, eigene EORI vorausgesetzt)." % (
            pct(ev["sendung"]["eust_satz"], 0), eur(lc["eust"])))
    sh = ev["sendung"]
    out.append("")
    out.append("Sendung: %s m³, %s kg brutto, frachtpflichtig Luft %s kg · Kontrolle Stückkosten × Menge gegen Blockrechnung: Abweichung %s" % (
        num(sh["m3"], 3), num(sh["kg"], 1), num(sh["frachtpflichtig_kg"], 0), eur(sh["abweichung"])))
    out.append("")
    if modes:
        out.append("## Fracht im Vergleich (gleiche Menge)")
        out.append("")
        rows = []
        key = "amazon" if "amazon" in res else "shopify"
        for md in ("see", "bahn", "luft"):
            e2 = modes.get(md)
            if not e2:
                continue
            r2 = e2["positionen"][0]
            u2 = r2[key]
            rows.append((MODE_NAME[md] + (" ✓" if md == ev["modus"] else ""), eur(e2["sendung"][md], 0), eur(r2["lc"]["landed"]), eur(u2["db"]),
                         pct(u2["be_tacos"]), date_de(e2["verfuegbar_ab"]), eur(e2["kapital"]["kapital_max"], 0)))
        out.append(table(["Modus", "Fracht gesamt", "Landed/Stk", "DB/Stk", "BE-TACOS", "verfügbar ab", "Kapitalbedarf"], rows))
        out.append("")
    e = tables.cfg["entscheidung"]
    out.append("## Grenzwerte für die Verhandlung")
    out.append("")
    out.append("- Max. EK für GO (BE-TACOS %s): **%s** · für TEST (%s): **%s** (angeboten: %s %s)" % (
        pct(e["go_be_tacos"], 0), ek_txt(res["max_ek_go"], lc["waehrung"]), pct(e["test_be_tacos"], 0),
        ek_txt(res["max_ek_test"], lc["waehrung"]), ek_num(p["ek"]), lc["waehrung"]))
    if res.get("min_vk_go"):
        out.append("- Mindest-VK für GO bei diesem EK: **%s**" % eur(res["min_vk_go"]))
    out.append("")
    out.append("## Kapital")
    out.append("")
    out.append("Kapitalbedarf in der Spitze **%s** (Tag %d nach Bestellung) · verfügbar bei Amazon ab Tag %d (%s) · Kapital zurück nach **%s Tagen** · Abverkauf %d Tage bei %s Stk/Monat · DB gesamt **%s** · Kapitalrendite p. a. %s" % (
        eur(cap["kapital_max"], 0), cap["tag_kapital_max"], cap["verfuegbar_tag"], date_de(ev["verfuegbar_ab"]),
        cap["payback_tag"] if cap["payback_tag"] is not None else "–", res["sim"]["tage_abverkauf"], num(res["sim"]["monatsabsatz"], 0),
        eur(cap["db_gesamt"], 0), pct(cap["rendite_jahr"], 0) if cap["rendite_jahr"] is not None else "–"))
    out.append("")
    items = res.get("hebel", []) + res.get("hinweise", [])
    if items:
        out.append("## Hebel und Hinweise")
        out.append("")
        for _, text in items:
            out.append("- " + text)
        out.append("")
    out.append("## Grundlagen")
    out.append("")
    out.extend("- " + x for x in basis_lines(tables, ev))
    return "\n".join(out)


def _d(iso):
    try:
        return date_de(dt.date(*[int(x) for x in str(iso).split("-")]))
    except (TypeError, ValueError):
        return str(iso)


def basis_lines(tables, ev):
    d = tables.describe()
    a = tables.amazon["_meta"]
    tz = tables.amazon.get("treibstoffzuschlag") or {}
    tz_txt = ", ".join("%s ab %s%s" % (pct(s["satz"], 1), _d(s["ab"]), "" if s.get("status") == "offiziell" else " (Drittquelle)")
                       for s in tz.get("stufen", []))
    lines = ["Amazon-Gebühren: Tarifübersicht EU gültig ab %s (Stand %s, offiziell); Treibstoff-/Logistikaufschlag auf FBA %s; Spitzenzeit-Zuschlag 2026 Ø %s € je Paket (15.10.–14.01., Drittquelle)." % (
        _d(a["gueltig_ab"]), _d(a["stand"]), tz_txt or "–", num(tables.amazon["spitzenzeit"]["zuschlag_eur"])),
        "Fracht, Nebenkosten, Vorbereitung, Zahlungsziele: Standardwerte Stand %s (Annahmen, mit margencheck.json änderbar) – Einstellungen: %s." % (
            _d(d["standardwerte_stand"]), d["einstellungen"]),
        "Wechselkurs: %s." % tables.cfg["kurse"].get("_quelle", "")]
    if "shopify" in (ev or {}).get("kanaele", []):
        own = bool((tables.user.get("shopify") or {}).get("versand_eigen"))
        lines.append("Shopify: Tarif %s, Zahlungsgebühren laut shopify.com/de/preise; Versand- und Verpackungskosten %s." % (
            tables.shopify.get("tarif", "basic"),
            "aus deinen Einstellungen" if own else "sind BEISPIELWERTE – eigene Konditionen per setup eintragen"))
    lines.append("Nicht im Deckungsbeitrag: Fixkosten (Verkäufertarif 39 €/Monat, Shopify-Abo, Content, Muster, Vine).")
    for w in tables.staleness():
        lines.append("⚠️ " + w)
    return lines
