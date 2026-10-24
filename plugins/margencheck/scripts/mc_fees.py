"""Amazon EU fee logic (size tier, FBA fee, Low-Price FBA, referral, storage, peak) and Shopify costs.

Every number comes from the loaded fee table (data/amazon_eu_*.json, data/shopify_de_*.json);
this module only contains the rules for applying them.
"""
import datetime as dt
import math


def sorted_dims(dims):
    return sorted([float(x) for x in dims], reverse=True)


def fits(dims, max_cm):
    return all(a <= b + 1e-9 for a, b in zip(sorted_dims(dims), sorted_dims(max_cm)))


def volume_weight_g(dims, divisor=5000):
    l, b, h = dims
    return l * b * h / float(divisor) * 1000.0


def size_tier(amz, dims, unit_g):
    """Return (tier_id, definition, dimensional weight in g) for a packed unit."""
    gk = amz["groessenklassen"]
    vol_g = volume_weight_g(dims, gk.get("volumen_teiler", 5000))
    d = sorted_dims(dims)
    girth = d[0] + 2 * (d[1] + d[2])
    for tid in gk["reihenfolge"]:
        t = gk["def"][tid]
        if tid == "uebergroesse_besonders":
            return tid, t, vol_g
        if tid in ("uebergroesse_sperrig", "uebergroesse_schwer"):
            if d[0] > 175 or girth > 360:
                continue
        elif not fits(dims, t["max_cm"]):
            continue
        if unit_g > t["max_g"] + 1e-9:
            continue
        if t.get("max_vol_g") and vol_g > t["max_vol_g"] + 1e-9:
            continue
        return tid, t, vol_g
    return "uebergroesse_besonders", gk["def"]["uebergroesse_besonders"], vol_g


def _band(fee_block, col, weight_g):
    for limit, fee in zip(fee_block["bis_g"], fee_block["gebuehr"][col]):
        if weight_g <= limit + 1e-9:
            return fee, limit
    return None, None


def lp_eligible(amz, price_gross, category):
    lp = amz["fba_niedrigpreis"]
    limit = lp["preisgrenze_brutto"]["reduziert" if category in lp.get("kategorien_reduziert", []) else "standard"]
    return price_gross <= limit + 1e-9, limit


def fba_fee(amz, market_col, dims, unit_g, category, price_gross, allow_lp=True):
    """FBA fulfilment fee per unit (without peak surcharge or DST). Returns a dict."""
    tid, tdef, vol_g = size_tier(amz, dims, unit_g)
    art = tdef["art"]
    res = {"klasse": tid, "klasse_name": tdef["name"], "art": art, "volumengewicht_g": round(vol_g, 1),
           "niedrigpreis": False, "tarif": "Standard"}
    # 1) Low-Price FBA (unit weight only, envelopes and small parcels up to 400 g)
    if allow_lp:
        ok, limit = lp_eligible(amz, price_gross, category)
        res["lp_grenze"] = limit
        block = amz["fba_niedrigpreis"].get(tid)
        if block:
            fee, band = _band(block, market_col, unit_g)
            res["lp_gebuehr_moeglich"] = fee
            if ok and fee is not None:
                res.update(gebuehr=fee, niedrigpreis=True, tarif="Niedrigpreis", gewicht_basis_g=unit_g, band_g=band)
                return res
    # 2) Packages in selected categories (apparel etc.): base up to 100 g + per further 100 g, unit weight
    if art == "paket" and category in amz.get("auswahl_kategorien", []):
        sel = amz["groessenklassen"]["auswahl_kategorien_paket"]
        for sid in sel["reihenfolge"]:
            sdef = sel["def"][sid]
            if fits(dims, sdef["max_cm"]) and unit_g <= sdef["max_g"]:
                block = amz["fba_auswahl_kategorien"][sid]
                extra = max(0, int(math.ceil((unit_g - 100) / 100.0 - 1e-9)))
                fee = block["bis_100g"][market_col] + extra * block["je_weitere_100g"][market_col]
                res.update(gebuehr=round(fee, 2), tarif="Ausgewählte Kategorie", klasse_name=sdef["name"],
                           klasse_auswahl=sid, gewicht_basis_g=unit_g)
                return res
    # 3) Standard rates
    block = amz["fba_standard"][tid]
    if art == "umschlag":
        weight = unit_g
    else:
        weight = max(unit_g, vol_g)
    res["gewicht_basis_g"] = round(weight, 1)
    if "bis_g" in block and tid != "uebergroesse_besonders":
        fee, band = _band(block, market_col, weight)
        if fee is None:  # heavier than the last band within the tier -> use last band (should not happen)
            fee = block["gebuehr"][market_col][-1]
        res.update(gebuehr=fee, band_g=band)
        return res
    if tid == "uebergroesse_besonders":
        weight = unit_g
        fee, band = _band(block, market_col, weight)
        if fee is None:
            extra_kg = int(math.ceil((weight - 60000) / 1000.0))
            fee = block["gebuehr"][market_col][-1] + extra_kg * block["je_kg_ueber_60kg"][market_col]
        res.update(gebuehr=round(fee, 2), gewicht_basis_g=weight)
        return res
    base_g = block["basis_bis_g"]
    extra_kg = max(0, int(math.ceil((weight - base_g) / 1000.0 - 1e-9)))
    fee = block["basis"][market_col] + extra_kg * block["je_kg_darueber"][market_col]
    res.update(gebuehr=round(fee, 2))
    return res


def referral_fee(amz, price_gross, category):
    """Referral fee on the gross price incl. VAT; returns (fee, rule description)."""
    ref = amz["referral"]
    cats = ref["kategorien"]
    rule = cats.get(category) or cats["sonstige"]
    p = float(price_gross)
    typ = rule["typ"]
    if typ == "flat":
        fee = p * rule["satz"]
        desc = "%.0f %%" % (rule["satz"] * 100)
    elif typ == "stufe":
        fee = None
        for upto, rate in rule["stufen"]:
            if upto is None or p <= upto + 1e-9:
                fee = p * rate
                desc = ("%.0f %%, Preisstufe bis %.0f €" % (rate * 100, upto)) if upto else ("%.0f %%" % (rate * 100))
                break
        if fee is None and rule.get("ueber_anteil"):
            fee = _portion(p, rule["ueber_anteil"])
            desc = "15 % bis 45 €, 7 % darüber"
        if fee is None:
            fee = p * rule["stufen"][-1][1]
            desc = "%.0f %%" % (rule["stufen"][-1][1] * 100)
    elif typ == "anteil":
        fee = _portion(p, rule["anteile"])
        desc = " / ".join("%.0f %%%s" % (r * 100, "" if u is None else " bis %.0f €" % u) for u, r in rule["anteile"])
    else:
        raise ValueError("unknown referral rule type %s" % typ)
    fee = max(fee, ref.get("mindestgebuehr", 0.30))
    return round(fee, 4), desc, rule.get("name", category)


def _portion(p, parts):
    fee, lower = 0.0, 0.0
    for upto, rate in parts:
        top = p if upto is None else min(p, upto)
        if top > lower:
            fee += (top - lower) * rate
        if upto is None or p <= upto:
            break
        lower = upto
    return fee


def storage_key(amz, art, category, dangerous=False):
    lager = amz["lager"]
    if dangerous:
        return "gefahrgut_uebergroesse" if art == "uebergroesse" else "gefahrgut_standard"
    if art == "uebergroesse":
        return "uebergroesse"
    if category in lager.get("kleidung_kategorien", []):
        return "kleidung_standard"
    return "standard"


def storage_rate(amz, key, month):
    r = amz["lager"][key]
    return r["okt_dez"] if month >= 10 else r["jan_sep"]


def peak_window(amz, market_code):
    sp = amz.get("spitzenzeit") or {}
    if market_code not in sp.get("maerkte", []):
        return None
    try:
        a = dt.date(*[int(x) for x in sp["von"].split("-")])
        b = dt.date(*[int(x) for x in sp["bis"].split("-")])
    except (KeyError, ValueError):
        return None
    return a, b, float(sp.get("zuschlag_eur", 0.0))


def in_peak(day, window):
    """Peak season repeats every year with the same calendar window."""
    if not window:
        return False
    a, b, _ = window
    md = (day.month, day.day)
    start, end = (a.month, a.day), (b.month, b.day)
    if start <= end:
        return start <= md <= end
    return md >= start or md <= end


# ------------------------------------------------------------------ Shopify
def shopify_shipping(shop, weight_g):
    bands = shop["versand_eigen"]["bis_kg"]
    kg = weight_g / 1000.0
    for upto, cost in bands:
        if kg <= upto + 1e-9:
            return float(cost)
    return float(bands[-1][1])


def shopify_payment(shop, amount_gross):
    """Average payment cost for one order of amount_gross, over the configured payment mix."""
    plan = shop["tarife"].get(str(shop.get("tarif", "basic")).lower()) or shop["tarife"]["basic"]
    mix = shop.get("zahlarten_mix") or shop.get("zahlarten_mix_standard") or {"karte": 1.0}
    total_w = sum(mix.values()) or 1.0
    cost = 0.0
    for method, w in mix.items():
        info = shop["zahlarten"].get(method)
        if not info:
            continue
        if info.get("quelle") == "tarif":
            c = amount_gross * plan["karte_prozent"] + plan["karte_fix"]
        else:
            c = amount_gross * info["prozent"] + info["fix"]
            if info.get("fremdanbieter"):
                c += amount_gross * plan["fremdanbieter_aufschlag"]
        cost += c * (w / total_w)
    return cost, plan["name"]
