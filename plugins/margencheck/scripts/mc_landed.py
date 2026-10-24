"""Shipment volume/weight, freight per mode, customs, import VAT and landed cost per unit.

Rules (from the sourcing practice this tool is built on):
  * Freight is allocated by VOLUME (sea, rail) or by chargeable weight (air) -- never by value.
  * The freight total is fixed per shipment, unit costs are not: minimum charges (rail 1 m³,
    sea 1 m³) make small orders relatively expensive.
  * Customs value = CIF (goods + freight); import VAT = (customs value + duty) × rate. Import VAT
    is only a cost when it cannot be reclaimed (no own EORI / DDP via the supplier's forwarder).
  * Control: the sum of unit landed costs × quantity must equal the block calculation.
"""
import math

MODES = ("see", "bahn", "luft")
GELIEFERT = ("DAP", "DPU")  # supplier delivers to the named place; import clearance, duty and EUSt are ours


def incoterm(p):
    """'DAP Rosenheim' -> 'DAP'."""
    parts = str(p.get("incoterm") or "").strip().upper().split()
    return parts[0] if parts else ""


def unit_volume_m3(p):
    l, b, h = p["masse_cm"]
    return l * b * h / 1e6


def position_load(p, cfg):
    """Volume (m³), gross kg and whether it is estimated, for one position's whole quantity."""
    s = cfg["sendung"]
    qty = p["menge"]
    if p.get("karton_masse_cm") and p.get("stueck_je_karton"):
        cartons = int(math.ceil(qty / float(p["stueck_je_karton"])))
        l, b, h = p["karton_masse_cm"]
        vol = cartons * l * b * h / 1e6
        kg = cartons * float(p["karton_kg"]) if p.get("karton_kg") else qty * p["gewicht_g"] / 1000.0 * s["packfaktor_gewicht"] + vol * s["karton_kg_je_m3"]
        return {"m3": vol, "kg": kg, "kartons": cartons, "geschaetzt": False}
    if p.get("cbm_gesamt"):
        vol = float(p["cbm_gesamt"])
        kg = float(p.get("kg_gesamt") or qty * p["gewicht_g"] / 1000.0 * s["packfaktor_gewicht"] + vol * s["karton_kg_je_m3"])
        return {"m3": vol, "kg": kg, "kartons": None, "geschaetzt": False}
    vol = unit_volume_m3(p) * qty * s["packfaktor_volumen"]
    kg = qty * p["gewicht_g"] / 1000.0 * s["packfaktor_gewicht"] + vol * s["karton_kg_je_m3"]
    return {"m3": vol, "kg": kg, "kartons": None, "geschaetzt": True}


def freight_totals(loads, tables):
    """Freight cost in EUR per mode for the whole shipment (without the per-shipment extras)."""
    cfg = tables.cfg
    s = cfg["sendung"]
    m3 = sum(x["m3"] for x in loads)
    if any(x["geschaetzt"] for x in loads):
        m3 += s["zuschlag_m3"]
    kg = sum(x["kg"] for x in loads)
    _, usd = tables.fx("USD")
    f = cfg["fracht"]
    vol_kg = m3 * 1e6 / f["luft"]["volumen_teiler"]
    pflicht = max(vol_kg, kg)
    out = {
        "m3": m3, "kg": kg, "volumengewicht_kg": vol_kg, "frachtpflichtig_kg": pflicht,
        "see": max(f["see"]["min_m3"], m3) * f["see"]["eur_je_m3"],
        "bahn": max(f["bahn"]["min_usd"], m3 * f["bahn"]["usd_je_m3"]) * usd,
        "luft": pflicht * f["luft"]["usd_je_kg"] * usd,
        "nebenkosten": s["nebenkosten_je_sendung_eur"],
    }
    for md in MODES:  # per-shipment extras (customs broker, CFS, delivery) differ by freight mode
        out["nebenkosten_" + md] = float(f[md].get("nebenkosten_je_sendung_eur", s["nebenkosten_je_sendung_eur"]))
    out["guenstigste"] = min(MODES, key=lambda k: out[k])
    return out


def allocation_shares(loads, mode, tables):
    """Share of the freight bill per position: by volume (sea/rail) or chargeable weight (air)."""
    if mode == "luft":
        div = tables.cfg["fracht"]["luft"]["volumen_teiler"]
        w = [max(x["m3"] * 1e6 / div, x["kg"]) for x in loads]
    else:
        w = [x["m3"] for x in loads]
    total = sum(w) or 1.0
    return [v / total for v in w]


def landed_costs(positions, tables, mode, channel="amazon"):
    """Per-unit landed cost breakdown for every position for one freight mode.

    Returns (rows, shipment) where rows[i] is a dict of EUR per unit and shipment has the totals
    and the control calculation.
    """
    cfg = tables.cfg
    zoll = cfg["zoll"]
    prep = cfg["vorbereitung"]
    imp = str(tables.user.get("import_land") or "DE").upper()
    eust_rate = zoll["eust"].get(imp, zoll["eust"]["DE"])
    loads = [position_load(p, cfg) for p in positions]
    # only goods we ship ourselves form the shipment (DDP/DAP/DPU or fixed freight per unit are outside it)
    own = [not (incoterm(p) in ("DDP",) + GELIEFERT or p.get("fracht_je_einheit") is not None)
           for p in positions]
    own_loads = [ld for ld, o in zip(loads, own) if o] or [{"m3": 0.0, "kg": 0.0, "geschaetzt": False}]
    ft = freight_totals(own_loads, tables)
    ft["nebenkosten"] = ft["nebenkosten_" + mode]
    if not any(own):
        for k in MODES + ("nebenkosten",):
            ft[k] = 0.0
    sh_own = iter(allocation_shares(own_loads, mode, tables))
    vsh_own = iter(allocation_shares(own_loads, "see", tables))
    shares, vol_shares = [], []
    for o in own:
        shares.append(next(sh_own) if o else 0.0)
        vol_shares.append(next(vsh_own) if o else 0.0)
    rows = []
    block = {"ware": 0.0, "fracht": 0.0, "nebenkosten": 0.0, "zoll": 0.0, "eust": 0.0,
             "vorbereitung": 0.0, "eust_kosten": 0.0}
    for p, ld, sh, vsh in zip(positions, loads, shares, vol_shares):
        qty = float(p["menge"])
        cur, rate = tables.fx(p.get("waehrung"))
        ek_eur = p["ek"] * rate
        term = incoterm(p)
        ddp = term == "DDP"
        if p.get("fracht_je_einheit") is not None:
            fr, nk = float(p["fracht_je_einheit"]), 0.0
            block["fracht"] += fr * qty
        elif ddp or term in GELIEFERT:
            fr, nk = 0.0, 0.0  # main carriage to the named place is in the price; DAP/DPU: duty and EUSt stay with us
        else:
            fr = ft[mode] * sh / qty
            nk = ft["nebenkosten"] * vsh / qty
            block["fracht"] += ft[mode] * sh          # invoice side: the shipment's freight bill share
            block["nebenkosten"] += ft["nebenkosten"] * vsh
        cif = ek_eur + (fr + nk) * zoll["fracht_anteil_im_zollwert"] + ek_eur * zoll.get("versicherung_anteil", 0.0)
        satz = 0.0 if ddp else p["zollsatz"]
        duty = cif * satz
        eust = (cif + duty) * eust_rate
        eust_cost = 0.0 if (zoll["eust_abziehbar"] and not p.get("eust_nicht_abziehbar")) else eust
        teile = int(p.get("teile_je_einheit") or 1)
        if channel == "amazon":
            vb = prep["etikett_je_teil"] + (prep["set_verpackung_je_set"] if teile > 1 else 0.0) \
                + prep["inbound_je_einheit"] + prep["inbound_je_kg"] * p["gewicht_g"] / 1000.0
        else:
            vb = (prep["set_verpackung_je_set"] if teile > 1 else 0.0)
        vb += float(p.get("zusatzkosten_je_einheit") or 0.0)
        landed = ek_eur + fr + nk + duty + vb + eust_cost
        rows.append({"ek_eur": ek_eur, "waehrung": cur, "kurs": rate, "fracht": fr, "nebenkosten": nk,
                     "zollwert": cif, "zollsatz": satz, "zoll": duty, "eust": eust, "eust_kosten": eust_cost,
                     "vorbereitung": vb, "landed": landed, "ddp": ddp, "geliefert": term if term in GELIEFERT else None,
                     "m3_position": ld["m3"], "kg_position": ld["kg"],
                     "volumen_geschaetzt": ld["geschaetzt"], "frachtanteil": sh})
        block["ware"] += ek_eur * qty
        block["zoll"] += duty * qty
        block["eust"] += eust * qty
        block["eust_kosten"] += eust_cost * qty
        block["vorbereitung"] += vb * qty
    # control: unit costs x quantity must add up to the block (invoice-side) calculation
    unit_sum = sum(r["landed"] * p["menge"] for r, p in zip(rows, positions))
    block_total = (block["ware"] + block["fracht"] + block["nebenkosten"] + block["zoll"]
                   + block["vorbereitung"] + block["eust_kosten"])
    shipment = dict(ft)
    own_freight = sum(r["fracht"] * p["menge"] for r, p, o in zip(rows, positions, own) if o)
    shipment.update({"modus": mode, "block": block, "summe_stueckkosten": unit_sum, "summe_block": block_total,
                     "abweichung": unit_sum - block_total, "abweichung_fracht": own_freight - ft[mode],
                     "eust_satz": eust_rate, "import_land": imp, "eigene_positionen": sum(own)})
    return rows, shipment
