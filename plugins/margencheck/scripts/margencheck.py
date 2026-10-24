#!/usr/bin/env python3
"""MargenCheck – Sourcing-/Angebotsprüfer für Amazon-FBA- und Shopify-Seller.

  margencheck.py rechner  [--ek 2.10 --waehrung USD --menge 500 --vk 24.95 --masse 25x18x4 --gewicht 380 ...]
  margencheck.py rechner  --datei angebot.csv --pos 3          eine Position aus einer Liste
  margencheck.py angebot  angebot.xlsx [--out ordner]          ganze Angebotsliste + Excel (Pro)
  margencheck.py szenarien angebot.xlsx [--mengen 300,500,1000] Mengen-/Fracht-/Preisszenarien (Pro)
  margencheck.py gebuehren [--pruefen]                         Stand der Gebührentabellen
  margencheck.py vorlage  [--out ordner]                       leere Angebotsvorlage (CSV)
  margencheck.py inspect  datei.xlsx                           erkannte Spalten anzeigen
  margencheck.py kategorien                                    Gebührenkategorien (Verkaufsgebühr)
  margencheck.py init --markt DE --kanal beide --set fracht.bahn.usd_je_m3=420   Einstellungen speichern

Exit codes: 0 ok, 2 Eingabeproblem (Grund auf stderr), 3 Funktion nur in MargenCheck Pro.
"""
import argparse
import datetime as dt
import io
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import mc_core  # noqa: E402
import mc_input  # noqa: E402
import mc_report  # noqa: E402
from mc_tables import InputError, Tables, data_dir, deep_merge  # noqa: E402

try:
    import mc_pro  # noqa: E402
except ImportError:  # free edition
    mc_pro = None

VERSION = "1.1.5"
PRO_HINT = ("Diese Funktion gehört zu MargenCheck Pro (ganze Angebotslisten, Mengenszenarien, Excel-Bericht). "
            "Die Gratis-Edition rechnet ein Produkt: margencheck.py rechner … oder --datei <liste> --pos <nr>.")


def apply_settings(tables, settings, args=None):
    """Offer-file settings and command-line options override margencheck.json for this run."""
    settings = dict(settings or {})
    for k in list(settings):
        if k in tables.cfg and isinstance(settings[k], dict):
            tables.cfg = deep_merge(tables.cfg, {k: settings.pop(k)})
    if "shopify" in settings:
        tables.shopify = deep_merge(tables.shopify, settings.pop("shopify"))
    if settings.get("marktplatz"):
        tables.markt = str(settings["marktplatz"]).upper()
    if settings.get("kanal"):
        tables.kanal = str(settings["kanal"]).lower()
    for k in ("import_land", "waehrung_ek"):
        if settings.get(k):
            tables.user[k] = settings[k]
    if settings.get("tacos_plan") is not None:
        tables.cfg["planung"]["tacos_plan"] = mc_input.parse_rate(settings["tacos_plan"])
    if settings.get("kurs") and isinstance(settings["kurs"], dict):
        tables.cfg["kurse"].update(settings["kurs"])
    if args is not None:
        if getattr(args, "markt", None):
            tables.markt = args.markt.upper()
        if getattr(args, "kanal", None):
            tables.kanal = args.kanal.lower()
        if getattr(args, "tacos", None) is not None:
            tables.cfg["planung"]["tacos_plan"] = mc_input.parse_rate(args.tacos)
        if getattr(args, "kurs", None):
            tables.cfg["kurse"]["USD"] = float(str(args.kurs).replace(",", "."))
    tables.market()  # validates
    return settings


def channels_of(tables):
    k = tables.kanal
    if k in ("beide", "both", "amazon+shopify"):
        return ("amazon", "shopify")
    if k == "shopify":
        return ("shopify",)
    return ("amazon",)


def positions_from(args, tables):
    """Build normalized positions from --datei/--json or from the single-product options."""
    raw_headers = {}
    settings = {}
    if getattr(args, "datei", None) or getattr(args, "json", None):
        path = args.datei or args.json
        if not os.path.exists(path):
            raise InputError("file not found: %s" % path)
        settings, recs, raw_headers = mc_input.load_offer(path, tables, mapping_of(args), getattr(args, "blatt", None))
    else:
        rec = {}
        for opt, field in (("ek", "ek"), ("waehrung", "waehrung"), ("menge", "menge"), ("vk", "vk_brutto"),
                           ("vk_shopify", "vk_shopify"), ("masse", "masse"), ("gewicht", "gewicht_g"),
                           ("kategorie", "kategorie"), ("hs", "hs_code"), ("zoll", "zollsatz"), ("retouren", "retourenquote"),
                           ("absatz", "monatsabsatz"), ("name", "name"), ("teile", "teile_je_einheit"), ("fba", "fba_gebuehr"),
                           ("incoterm", "incoterm"), ("fracht_stk", "fracht_je_einheit"), ("staffel", "staffel"),
                           ("annahmen", "annahmen"), ("cbm", "cbm_gesamt")):
            v = getattr(args, opt, None)
            if v is not None:
                rec[field] = v
        if "gewicht_g" in rec:
            rec["gewicht"] = rec.pop("gewicht_g")
        recs = [rec]
    settings = apply_settings(tables, settings, args)
    defaults = {k: settings.get(k) for k in ("waehrung", "menge", "kategorie", "incoterm", "hs_code", "retourenquote",
                                             "monatsabsatz", "vk_brutto") if settings.get(k) is not None}
    positions, incomplete = [], []
    for i, rec in enumerate(recs):
        p, missing = mc_input.normalize(rec, tables, defaults, raw_headers, i)
        if missing:
            incomplete.append((p, missing))
        else:
            positions.append(p)
    # --absatz with a file: monthly sales for the selected positions (--pos) or for all positions
    ab = getattr(args, "absatz", None)
    if ab is not None and (getattr(args, "datei", None) or getattr(args, "json", None)):
        value = mc_input.parse_num(ab, int_like=True)
        if not value or value <= 0:
            raise InputError("--absatz needs a positive number of units per month")
        want = set(x.strip() for x in str(args.pos).split(",")) if getattr(args, "pos", None) else None
        for p in positions:
            if want is None or p["pos"] in want:
                p["monatsabsatz"] = value
    return positions, incomplete, settings


def mapping_of(args):
    m = {}
    for item in getattr(args, "map", None) or []:
        if "=" in item:
            k, v = item.split("=", 1)
            m[k.strip()] = v.strip().strip('"')
    return m


def mode_of(args, settings):
    mode = (getattr(args, "fracht", None) or settings.get("fracht_modus") or "auto").lower()
    mode = {"sea": "see", "rail": "bahn", "air": "luft", "zug": "bahn", "schiff": "see"}.get(mode, mode)
    if mode not in ("auto", "see", "bahn", "luft"):
        raise InputError("--fracht must be auto, see, bahn or luft")
    return mode


# ---------------------------------------------------------------- commands
def cmd_rechner(args):
    tables = Tables(args.workdir, args.einstellungen, args.gebuehren)
    positions, incomplete, settings = positions_from(args, tables)
    if args.pos:
        wanted = str(args.pos).strip()
        sel = [p for p in positions if p["pos"] == wanted]
        inc = [x for x in incomplete if x[0]["pos"] == wanted]
        if not sel and inc:
            raise InputError("position %s is incomplete – missing: %s" % (wanted, ", ".join(inc[0][1])))
        if not sel:
            raise InputError("position %s not found (available: %s)" % (wanted, ", ".join(p["pos"] for p in positions)))
        positions = sel
    elif len(positions) + len(incomplete) > 1:
        if mc_pro is None:
            sys.stderr.write(PRO_HINT + "\n")
            return 3
        raise InputError("rechner takes one product – use --pos <nr> or the 'angebot' command for the whole list")
    if not positions:
        p, missing = incomplete[0]
        raise InputError("missing input: %s (e.g. --ek 2.10 --vk 24.95 --menge 500 --masse 25x18x4 --gewicht 380)" % ", ".join(missing))
    mode = mode_of(args, settings)
    ch = channels_of(tables)
    modes = {}
    for md in ("see", "bahn", "luft"):
        modes[md] = mc_core.evaluate([dict(positions[0])], tables, md, tables.markt, ch)
    if mode == "auto":
        key = "amazon" if "amazon" in ch else "shopify"
        mode = max(modes, key=lambda m: modes[m]["positionen"][0][key]["db"])
    ev = modes[mode]
    md = mc_report.render_single(ev["positionen"][0], ev, modes, tables, ch)
    print(md)
    if args.json_out:
        with io.open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(to_jsonable(ev), f, ensure_ascii=False, indent=1)
    return 0


def to_jsonable(ev):
    def clean(x):
        if isinstance(x, dict):
            return {k: clean(v) for k, v in x.items() if k not in ("verkauf_tage", "verlauf")}
        if isinstance(x, (list, tuple)):
            return [clean(v) for v in x]
        if isinstance(x, (dt.date, dt.datetime)):
            return x.isoformat()
        if isinstance(x, float):
            return round(x, 4)
        return x
    return clean(ev)


def cmd_angebot(args):
    if mc_pro is None:
        sys.stderr.write(PRO_HINT + "\n")
        return 3
    tables = Tables(args.workdir, args.einstellungen, args.gebuehren)
    positions, incomplete, settings = positions_from(args, tables)
    if args.bewertung:
        mc_pro.attach_assessment(positions, args.bewertung)
    return mc_pro.run_offer(args, tables, positions, incomplete, settings, mode_of(args, settings), channels_of(tables))


def cmd_szenarien(args):
    if mc_pro is None:
        sys.stderr.write(PRO_HINT + "\n")
        return 3
    tables = Tables(args.workdir, args.einstellungen, args.gebuehren)
    positions, incomplete, settings = positions_from(args, tables)
    return mc_pro.run_scenarios(args, tables, positions, incomplete, settings, mode_of(args, settings), channels_of(tables))


def cmd_gebuehren(args):
    tables = Tables(args.workdir, args.einstellungen, args.gebuehren)
    a = tables.amazon["_meta"]
    print("# MargenCheck – Gebührentabellen")
    print("")
    print("| Tabelle | Version | Stand | nächste Prüfung | Quelle |")
    print("|---|---|---|---|---|")
    print("| Amazon EU | %s | %s | %s | %s |" % (a.get("version"), a.get("stand"), a.get("naechste_pruefung"), a.get("quelle")))
    s = tables.shopify["_meta"]
    print("| Shopify DE | %s | %s | %s | %s |" % (s.get("version"), s.get("stand"), s.get("naechste_pruefung"), s.get("quelle")))
    c = tables.cfg["_meta"]
    print("| Standardwerte | %s | %s | %s | Annahmen/Praxiswerte, siehe Datei |" % (c.get("version"), c.get("stand"), c.get("naechste_pruefung")))
    print("")
    print("Ordner: %s · eigene Einstellungen: %s" % (data_dir(), tables.settings_file or "keine margencheck.json"))
    print("")
    print("Marktplätze: " + ", ".join("%s (%s, USt %s)" % (k, v["name"], mc_report.pct(v["ust"], 0)) for k, v in tables.amazon["maerkte"].items()))
    print("")
    flagged = []
    for sec in ("spitzenzeit", "dst_hinweis"):
        x = tables.amazon.get(sec, {})
        if x.get("_status", x.get("status")) in ("drittquelle", "annahme"):
            flagged.append("%s: %s – %s" % (sec, x.get("_status", x.get("status")), x.get("_quelle", x.get("quelle"))))
    for st in (tables.amazon.get("treibstoffzuschlag") or {}).get("stufen", []):
        if st.get("status") in ("drittquelle", "annahme"):
            flagged.append("treibstoffzuschlag ab %s (%s): %s – %s" % (st["ab"], mc_report.pct(st["satz"], 1), st["status"], st.get("quelle", "")))
    r = tables.amazon["retouren"]
    if r.get("erstattungsgebuehr_status") in ("annahme", "drittquelle"):
        flagged.append("Rückerstattungsgebühr: %s – %s" % (r.get("erstattungsgebuehr_status"), r.get("erstattungsgebuehr_quelle")))
    for k, v in tables.cfg.items():
        if not isinstance(v, dict):
            continue
        if v.get("_status") in ("annahme", "praxiswert", "richtwert"):
            flagged.append("%s: %s – %s" % (k, v["_status"], v.get("_quelle") or v.get("_hinweis") or ""))
        for k2, v2 in v.items():
            if isinstance(v2, dict) and v2.get("_status") in ("annahme", "praxiswert", "richtwert"):
                flagged.append("%s.%s: %s – %s" % (k, k2, v2["_status"], v2.get("_quelle") or v2.get("_hinweis") or ""))
    v = tables.shopify.get("versand_eigen", {})
    if v.get("_status") == "annahme":
        flagged.append("shopify.versand_eigen: annahme – %s" % v.get("_hinweis", ""))
    if flagged:
        print("## Zu prüfen (nicht aus offizieller Quelle)")
        print("")
        for f in flagged:
            print("- " + f)
        print("")
    warn = tables.staleness()
    if warn:
        print("## ⚠️ Fällig")
        print("")
        for w in warn:
            print("- " + w)
        return 0
    print("Alle Tabellen innerhalb ihres Prüfdatums.")
    return 0


def cmd_vorlage(args):
    src = os.path.join(data_dir(), "..", "templates", "angebot_vorlage.csv")
    if not os.path.exists(src):
        src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "templates", "angebot_vorlage.csv")
    out_dir = args.out or os.getcwd()
    dst = os.path.join(out_dir, "margencheck-angebot-vorlage.csv")
    shutil.copyfile(src, dst)
    print(dst)
    return 0


def cmd_inspect(args):
    info = mc_input.inspect(args.datei, mapping_of(args), args.blatt)
    print("Datei: %s · Kopfzeile: %s" % (info["datei"], info["kopfzeile"]))
    for c in info["spalten"]:
        print("  %-30s -> %s" % (str(c["spalte"])[:30], c["feld"] or "(nicht erkannt)"))
    return 0


def cmd_kategorien(args):
    tables = Tables(args.workdir, args.einstellungen, args.gebuehren)
    print("| Schlüssel | Kategorie | Regel |")
    print("|---|---|---|")
    for k, r in sorted(tables.amazon["referral"]["kategorien"].items()):
        if r["typ"] == "flat":
            rule = mc_report.pct(r["satz"], 0)
        elif r["typ"] == "stufe":
            rule = ", ".join("%s bis %s €" % (mc_report.pct(x, 0), u) if u else "%s darüber" % mc_report.pct(x, 0) for u, x in r["stufen"])
        else:
            rule = ", ".join("%s bis %s €" % (mc_report.pct(x, 0), u) if u else "%s darüber" % mc_report.pct(x, 0) for u, x in r["anteile"])
        print("| %s | %s | %s |" % (k, r["name"], rule))
    return 0


TOP_KEYS = ("marktplatz", "kanal", "waehrung_ek", "import_land")


def _value(text):
    t = str(text).strip()
    low = t.lower()
    if low in ("true", "ja", "yes", "wahr"):
        return True
    if low in ("false", "nein", "no", "falsch"):
        return False
    if low in ("null", "none", "leer"):
        return None
    if t[:1] in "[{":
        try:
            return json.loads(t)
        except ValueError:
            raise InputError("value is not valid JSON: %s" % t)
    x = mc_input.parse_num(t) if any(ch.isdigit() for ch in t) and not any(ch.isalpha() for ch in t.replace("e", "")) else None
    return x if x is not None else t


def cmd_init(args):
    out_dir = args.out or args.workdir or os.getcwd()
    path = os.path.join(out_dir, "margencheck.json")
    doc = {}
    if os.path.exists(path):
        with io.open(path, encoding="utf-8") as f:
            try:
                doc = json.load(f)
            except ValueError as e:
                raise InputError("%s is not valid JSON: %s" % (path, e))
    base = Tables(out_dir if os.path.isdir(out_dir) else None)
    allowed = set(k for k in base.cfg if not k.startswith("_")) | {"shopify"} | set(TOP_KEYS)
    sets = list(args.set or [])
    for opt, key in (("markt", "marktplatz"), ("kanal", "kanal"), ("waehrung", "waehrung_ek"), ("import_land", "import_land")):
        v = getattr(args, opt, None)
        if v:
            sets.append("%s=%s" % (key, v.upper() if key != "kanal" else v.lower()))
    if args.tacos is not None:
        sets.append("planung.tacos_plan=%s" % mc_input.parse_rate(args.tacos))
    for item in sets:
        if "=" not in item:
            raise InputError("--set needs key=value, e.g. fracht.bahn.usd_je_m3=420")
        key, val = item.split("=", 1)
        parts = [x.strip() for x in key.strip().split(".") if x.strip()]
        if not parts or parts[0] not in allowed:
            raise InputError("unknown setting %s (allowed: %s)" % (key, ", ".join(sorted(allowed))))
        node = doc
        for k in parts[:-1]:
            node = node.setdefault(k, {})
            if not isinstance(node, dict):
                raise InputError("%s is not a section" % key)
        v = _value(val)
        if parts[-1] in ("tacos_plan", "retourenquote", "unverkaeuflich_anteil", "standard_satz", "go_be_tacos", "test_be_tacos", "min_marge") and isinstance(v, float):
            v = v / 100.0 if v > 1 else v
        node[parts[-1]] = v
    doc.setdefault("_hinweis", "MargenCheck-Einstellungen. Nur Abweichungen von data/standardwerte.json eintragen; Schlüssel siehe references/einstellungen.md.")
    with io.open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    Tables(out_dir).market()  # validates the result loads
    print(path)
    print(json.dumps(doc, ensure_ascii=False, indent=1))
    return 0


def build_parser():
    ap = argparse.ArgumentParser(prog="margencheck", description="MargenCheck %s" % VERSION)
    ap.add_argument("--version", action="version", version="MargenCheck %s (%s)" % (VERSION, "Pro" if mc_pro else "Gratis"))
    sub = ap.add_subparsers(dest="cmd")

    def common(sp):
        sp.add_argument("--workdir", default=None, help="Arbeitsordner (margencheck.json usw.)")
        sp.add_argument("--einstellungen", default=None, help="Pfad zu margencheck.json")
        sp.add_argument("--gebuehren", default=None, help="eigene Gebührentabelle (JSON)")
        sp.add_argument("--markt", default=None, help="DE, DE-CEP, FR, IT, ES")
        sp.add_argument("--kanal", default=None, help="amazon, shopify oder beide")
        sp.add_argument("--fracht", default=None, help="auto, see, bahn, luft")
        sp.add_argument("--tacos", default=None, help="Plan-Werbeanteil, z. B. 15 oder 0.15")
        sp.add_argument("--kurs", default=None, help="USD→EUR, z. B. 0.89")
        sp.add_argument("--map", action="append", help='Spaltenzuordnung feld="Spalte"')
        sp.add_argument("--blatt", default=None, help="Tabellenblatt (xlsx)")

    r = sub.add_parser("rechner", help="ein Produkt rechnen")
    common(r)
    for opt in ("ek", "menge", "vk", "gewicht", "zoll", "retouren", "absatz", "teile", "fba", "fracht_stk", "vk_shopify", "cbm"):
        r.add_argument("--" + opt.replace("_", "-"), dest=opt, default=None)
    for opt in ("waehrung", "masse", "kategorie", "hs", "name", "incoterm", "staffel", "annahmen"):
        r.add_argument("--" + opt, dest=opt, default=None)
    r.add_argument("--datei", default=None, help="CSV/XLSX/JSON mit Positionen")
    r.add_argument("--json", default=None, help="JSON mit Position(en)")
    r.add_argument("--pos", default=None, help="Position aus der Datei")
    r.add_argument("--json-out", dest="json_out", default=None)
    r.set_defaults(func=cmd_rechner)

    for name, fn, helptext in (("angebot", cmd_angebot, "ganze Angebotsliste (Pro)"),
                               ("szenarien", cmd_szenarien, "Mengen-/Fracht-/Preisszenarien (Pro)")):
        a = sub.add_parser(name, help=helptext)
        common(a)
        a.add_argument("datei")
        a.add_argument("--out", default=None, help="Ausgabeordner")
        a.add_argument("--bewertung", default=None, help="JSON mit qualitativer Bewertung je Position")
        a.add_argument("--titel", default=None)
        a.add_argument("--lieferant", default=None)
        a.add_argument("--mengen", default=None, help="z. B. 300,500,1000 oder x0.5,x1,x2")
        a.add_argument("--absatz", default=None, help="Monatsabsatz (Stk) für die mit --pos gewählten bzw. alle Positionen")
        a.add_argument("--pos", default=None, help="nur diese Positionen (z. B. 3,5)")
        a.add_argument("--json-out", dest="json_out", default=None)
        a.add_argument("--kein-excel", dest="kein_excel", action="store_true")
        a.add_argument("--alternativen", dest="alternativen", action="store_true", default=None,
                       help="Zeilen sind Angebote verschiedener Lieferanten für dasselbe Produkt: einzeln rechnen "
                            "(automatisch bei SupplierPilot-Übergaben)")
        a.add_argument("--gemeinsam", dest="alternativen", action="store_false",
                       help="Zeilen als eine gemeinsame Bestellung rechnen, auch bei SupplierPilot-Übergaben")
        a.set_defaults(func=fn, json=None)

    g = sub.add_parser("gebuehren", help="Stand der Gebührentabellen")
    common(g)
    g.add_argument("--pruefen", action="store_true")
    g.set_defaults(func=cmd_gebuehren)
    v = sub.add_parser("vorlage", help="Angebotsvorlage (CSV)")
    v.add_argument("--out", default=None)
    v.set_defaults(func=cmd_vorlage)
    i = sub.add_parser("inspect", help="erkannte Spalten anzeigen")
    i.add_argument("datei")
    i.add_argument("--map", action="append")
    i.add_argument("--blatt", default=None)
    i.set_defaults(func=cmd_inspect)
    n = sub.add_parser("init", help="Einstellungen in margencheck.json speichern")
    n.add_argument("--out", default=None, help="Ordner für margencheck.json (Standard: aktueller Ordner)")
    n.add_argument("--workdir", default=None)
    n.add_argument("--markt", default=None)
    n.add_argument("--kanal", default=None)
    n.add_argument("--waehrung", default=None)
    n.add_argument("--import-land", dest="import_land", default=None)
    n.add_argument("--tacos", default=None)
    n.add_argument("--set", action="append", help="abschnitt.schluessel=wert, mehrfach möglich")
    n.set_defaults(func=cmd_init)
    k = sub.add_parser("kategorien", help="Gebührenkategorien")
    common(k)
    k.set_defaults(func=cmd_kategorien)
    return ap


def main(argv=None):
    ap = build_parser()
    args = ap.parse_args(argv)
    if not getattr(args, "cmd", None):
        ap.print_help()
        return 2
    try:
        return args.func(args)
    except InputError as e:
        sys.stderr.write("MargenCheck: %s\n" % e)
        return 2


if __name__ == "__main__":
    sys.exit(main())
