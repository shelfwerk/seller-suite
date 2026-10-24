# Eingabe: Angebotsvorlage und Extraktionsregeln

MargenCheck liest **CSV, XLSX oder JSON**. Lieferantenlisten mit erkennbaren Spalten (auch englische
PI-Köpfe wie „Item No.“, „Unit Price (USD)“, „MOQ“, „N.W. (kg)“, „Carton Size“, „PCS/CTN“, „CBM“)
gehen direkt; `margencheck.py inspect <datei>` zeigt, welche Spalte wie erkannt wurde, `--map
feld="Spaltenname"` ordnet den Rest zu.

PDFs, Bilder, E-Mail-Text und unübersichtliche Excel-Dateien überträgt Claude zuerst in die
Vorlage (`margencheck.py vorlage` legt `margencheck-angebot-vorlage.csv` an).

## Spalten der Vorlage (`;`-getrennt, Dezimalkomma oder -punkt)

| Spalte | Pflicht | Bedeutung |
|---|---|---|
| `pos` | ja | Positions-/Artikelnummer des Lieferanten |
| `name` | ja | kurze deutsche Produktbezeichnung |
| `ek` | ja | Einkaufspreis **je Verkaufseinheit** in Lieferantenwährung (Set = Summe der Teile) |
| `waehrung` | – | USD (Standard), EUR, CNY |
| `menge` | ja* | Bestellmenge in Verkaufseinheiten (*sonst wird `moq` genommen) |
| `moq` | – | Mindestmenge |
| `staffel` | – | Staffelpreise `500:0,40|1000:0,36` (Menge:EK je Verkaufseinheit) |
| `vk_brutto` | ja | geplanter Verkaufspreis inkl. USt auf dem Zielmarktplatz |
| `kategorie` | – | Schlüssel aus `margencheck.py kategorien` (Standard `sonstige` = 15 %) |
| `masse_cm` | ja | Packmaß der verkaufsfertigen Einheit (Polybag/Schachtel) `L x B x H` in cm |
| `gewicht_g` | ja | Stückgewicht inkl. Verpackung in Gramm |
| `stueck_je_karton`, `karton_masse_cm`, `karton_kg` | – | aus der Packliste – macht Volumen und Fracht genau |
| `hs_code` | – | KN/HS-Code (mind. 4 Stellen), daraus der Zollsatz |
| `zollsatz` | – | direkt, z. B. `12%` – hat Vorrang vor `hs_code` |
| `retourenquote` | – | erwartete Quote, z. B. `6%` |
| `monatsabsatz` | – | erwartete Stück/Monat (eigene Zahlen vergleichbarer Produkte!) |
| `teile_je_einheit` | – | Teile je Set (2er-Set = 2) |
| `incoterm` | – | FOB (Standard), EXW, DDP (DDP: Fracht/Zoll im Preis) |
| `fba_gebuehr` | – | bekannte FBA-Gebühr aus Seller Central (überschreibt die Tabelle) |
| `vk_shopify` | – | abweichender Shop-Preis |
| `annahmen` | – | Felder, die geschätzt wurden, z. B. `gewicht_g,vk_brutto` |
| `notiz` | – | freier Text |

## Regeln für die Extraktion durch Claude

1. **Nichts erfinden, was im Angebot steht oder stehen müsste.** Fehlt der Einkaufspreis, bleibt `ek`
   leer – die Position erscheint als „unvollständig“. Preise nie runden oder umrechnen.
2. **Eine Zeile je Verkaufseinheit.** Farbvarianten mit gleichem Preis und Maß dürfen zusammengefasst
   werden (Menge addieren, in `notiz` nennen).
3. **Schätzen ist erlaubt, aber sichtbar:** fehlen Gewicht, Packmaß, VK, HS-Code oder Retourenquote,
   mit Vergleichswerten schätzen und das Feld in `annahmen` eintragen. Gewicht immer inklusive
   Polybag/Schachtel; Packmaß gefaltet/verpackt.
4. **VK brutto**: Preis, zu dem der Seller realistisch verkaufen kann (eigene Preise vergleichbarer
   Produkte oder Marktpreise), nicht Wunschpreis. Unbekannt → einmal nachfragen oder schätzen und
   als Annahme markieren.
5. **Kategorie** bestimmt Verkaufsgebühr, Niedrigpreisgrenze, Lager- und Retourentarif – mit
   `margencheck.py kategorien` den passenden Schlüssel wählen (Stirnband/Socke = `kleidung_accessoires`,
   Pfanne = `kueche`, Hantel = `sport_outdoor`).
6. **Mengen** aus dem Angebot; bei Musterpreislisten ohne Menge die MOQ.
7. **Sendungsdaten**: Packliste (Kartonmaße, Stück je Karton, Bruttogewicht) übernehmen, sonst leer
   lassen – MargenCheck schätzt dann und sagt es.

## JSON-Format (für Claude oder Automationen)

```json
{
  "einstellungen": {"marktplatz": "DE", "kanal": "amazon", "fracht_modus": "auto", "waehrung": "USD", "tacos_plan": 0.15},
  "positionen": [
    {"pos": "12", "name": "Sport-Stirnband", "ek": 0.40, "menge": 300, "vk_brutto": 12.90,
     "kategorie": "kleidung_accessoires", "masse_cm": [22, 10, 1], "gewicht_g": 24,
     "hs_code": "6117 80", "retourenquote": 0.08, "monatsabsatz": 100, "annahmen": ["gewicht_g"]}
  ]
}
```

## Qualitative Bewertung (`--bewertung bewertung.json`)

```json
{"12": {"urteil": "NEIN · Compliance", "begruendung": "Fremdlogo auf dem eingenähten Etikett"},
 "30": {"urteil": "TEST", "begruendung": "unbelegt: Produktgruppe noch nicht im Sortiment"},
 "7":  {"urteil": "PREIS PRÜFEN", "begruendung": "gleiches Produkt läuft schon – 0,08 $ günstiger"}}
```

Es gilt das strengere Urteil aus Rechnung und Bewertung.
