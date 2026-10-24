"""Load MargenCheck's fee tables and settings.

Everything that changes over time (Amazon/Shopify fees, freight rates, exchange rates, customs
rates, decision thresholds) lives in data/*.json|csv next to the scripts -- never in the code.
Users override any value without touching the shipped files:

  margencheck.json            settings (same keys as data/standardwerte.json, plus "shopify")
  margencheck-gebuehren.json  a complete replacement for data/amazon_eu_*.json
  margencheck-zoll.csv        extra/override customs rates (same columns as data/zoll_richtwerte.csv)

All three are looked up in the working folder (or passed explicitly on the command line).
"""
import copy
import csv
import datetime as dt
import glob
import io
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_CANDIDATES = [os.path.join(HERE, "..", "data"), os.path.join(HERE, "data")]


class InputError(Exception):
    """A problem with the user's input or settings (exit code 2)."""


def data_dir():
    for d in DATA_CANDIDATES:
        if os.path.isdir(d):
            return os.path.normpath(d)
    raise InputError("data folder with fee tables not found next to the scripts")


def _load_json(path):
    try:
        with io.open(path, encoding="utf-8") as f:
            return json.load(f)
    except ValueError as e:
        raise InputError("%s is not valid JSON: %s" % (path, e))


def deep_merge(base, extra):
    """Return a copy of base with extra merged in (dicts recursively, everything else replaced)."""
    out = copy.deepcopy(base)
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def newest(pattern):
    files = sorted(glob.glob(os.path.join(data_dir(), pattern)))
    if not files:
        raise InputError("no fee table matching %s in %s" % (pattern, data_dir()))
    return files[-1]


def load_zoll(paths):
    rates = []
    for p in paths:
        if not p or not os.path.exists(p):
            continue
        with io.open(p, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f, delimiter=";"):
                code = (row.get("hs_code") or "").replace(" ", "").replace(".", "")
                if not code:
                    continue
                try:
                    satz = float(str(row.get("zollsatz", "")).replace(",", "."))
                except ValueError:
                    continue
                rates.append({"hs": code, "satz": satz, "name": row.get("warengruppe", ""),
                              "status": row.get("status", ""), "hinweis": row.get("hinweis", ""),
                              "datei": os.path.basename(p)})
    return rates


def zoll_lookup(rates, hs_code):
    """Longest-prefix match of an HS/KN code (digits only). User files win over shipped ones."""
    code = "".join(ch for ch in str(hs_code or "") if ch.isdigit())
    if not code:
        return None
    best = None
    for r in rates:
        if code.startswith(r["hs"]) or r["hs"].startswith(code):
            score = min(len(r["hs"]), len(code))
            if best is None or score > best[0] or (score == best[0] and r["datei"] != "zoll_richtwerte.csv"):
                best = (score, r)
    return best[1] if best else None


class Tables(object):
    """All tables plus the merged settings for one run."""

    def __init__(self, workdir=None, settings_path=None, fees_path=None, today=None):
        self.today = today or dt.date.today()
        workdir = workdir or os.getcwd()
        self.sources = []
        fees_path = fees_path or _first_existing([os.path.join(workdir, "margencheck-gebuehren.json")])
        self.amazon = _load_json(fees_path or newest("amazon_eu_*.json"))
        self.sources.append(fees_path or newest("amazon_eu_*.json"))
        defaults = _load_json(os.path.join(data_dir(), "standardwerte.json"))
        shopify = _load_json(os.path.join(data_dir(), "shopify_de_2026.json"))
        settings_path = settings_path or _first_existing([os.path.join(workdir, "margencheck.json")])
        self.settings_file = settings_path
        user = _load_json(settings_path) if settings_path else {}
        if not isinstance(user, dict):
            raise InputError("margencheck.json must contain a JSON object")
        self.user = user
        self.cfg = deep_merge(defaults, {k: v for k, v in user.items() if k in defaults})
        self.shopify = deep_merge(shopify, user.get("shopify") or {})
        self.markt = str(user.get("marktplatz") or "DE").upper()
        self.kanal = str(user.get("kanal") or "amazon").lower()
        self.zoll = load_zoll([os.path.join(workdir, "margencheck-zoll.csv"),
                               os.path.join(data_dir(), "zoll_richtwerte.csv")])

    def market(self, code=None):
        code = (code or self.markt).upper()
        m = self.amazon["maerkte"].get(code)
        if not m:
            raise InputError("unknown marketplace %s (available: %s)" % (code, ", ".join(sorted(self.amazon["maerkte"]))))
        return code, m

    def fx(self, currency):
        cur = (currency or "USD").upper().replace("$", "USD").replace("€", "EUR").replace("RMB", "CNY")
        rate = self.cfg["kurse"].get(cur)
        if rate is None:
            raise InputError("no exchange rate for %s – add it under \"kurse\" in margencheck.json" % cur)
        return cur, float(rate)

    def staleness(self):
        """List of warnings for tables whose review date has passed."""
        out = []
        for label, meta in (("Amazon", self.amazon.get("_meta", {})), ("Shopify", self.shopify.get("_meta", {})),
                            ("Standardwerte", self.cfg.get("_meta", {}))):
            due = meta.get("naechste_pruefung")
            if due:
                try:
                    if self.today > dt.date(*[int(x) for x in due.split("-")]):
                        out.append("%s-Tabelle (Stand %s) ist seit %s fällig zur Prüfung." % (label, meta.get("stand"), due))
                except ValueError:
                    pass
        return out

    def describe(self):
        a = self.amazon.get("_meta", {})
        return {"amazon_version": a.get("version"), "amazon_stand": a.get("stand"), "amazon_quelle": a.get("quelle"),
                "shopify_stand": self.shopify.get("_meta", {}).get("stand"),
                "standardwerte_stand": self.cfg.get("_meta", {}).get("stand"),
                "einstellungen": self.settings_file or "(keine margencheck.json – Standardwerte)"}


def _first_existing(paths):
    for p in paths:
        if p and os.path.exists(p):
            return p
    return None
