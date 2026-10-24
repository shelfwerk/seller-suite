# MargenCheck (Gratis) – Produkt-Rechner für Amazon FBA & Shopify

Rechnet **ein Produkt** aus einem Lieferantenangebot durch, bevor du bestellst:

- **Landed Cost je Stück**: EK × Kurs, Fracht See/Bahn/Luft (nach Volumen bzw. frachtpflichtigem
  Gewicht, mit Mindestfracht), Nebenkosten, Zoll auf CIF nach HS-Code, EUSt (abziehbar = nur
  Kapitalbindung), Etikett/Set/Inbound – mit Kontrollrechnung.
- **Amazon-Gebühren** nach der EU-Tarifübersicht gültig ab 01.02.2026: Verkaufsgebühr je Kategorie,
  FBA-Größenklasse, Niedrigpreisversand, ausgewählte Kategorien (Kleidung je 100 g), Lager über den
  echten Abverkauf inkl. Q4-Tarif, Spitzenzeit-Zuschlag, Retouren (Erstattungsgebühr, Bearbeitung,
  unverkäufliche Ware). Märkte: DE (mit/ohne Zentraleuropa-Programm), FR, IT, ES.
- **Shopify**: Zahlungsgebühren nach Tarif und Zahlartenmix, Versand, Verpackung, Retouren.
- **Deckungsbeitrag, Break-even-ACOS/TACOS** (bzw. Break-even-ROAS), Max-EK für GO/TEST als
  Verhandlungsziel, Mindest-VK, Frachtvergleich, Kapitalbedarf, **GO / TEST / NEIN** und konkrete
  Gebührenhebel (Packmaß, Niedrigpreisgrenze, Preisstufen).

Gebühren stehen als **datierte Tabellen mit Quelle** in `data/` (nicht im Code); eigene Werte in
`margencheck.json`. Alles läuft lokal mit Python 3 (keine Zusatzpakete, kein API-Zugang).

## Ausprobieren (ohne Installation)

```bash
claude --plugin-dir /pfad/zu/margencheck
```

Dann z. B.: „Lohnt sich das? EK 2,10 $, VK 24,95 €, 25×18×4 cm, 380 g, 500 Stück, Küche“ oder
`/margencheck:rechner`. Einrichten: `/margencheck:setup`, Gebührenstand: `/margencheck:gebuehren`.

Direkt in der Kommandozeile:

```bash
python3 scripts/margencheck.py rechner --ek 2.10 --waehrung USD --menge 500 --vk 24.95 \
  --masse 25x18x4 --gewicht 380 --kategorie kueche --hs "7323 93" --absatz 150
```

In Claude Desktop/Cowork: die ZIP-Datei unter *Plugins → Hochladen* hinzufügen.

## Gratis vs. Pro

| | Gratis | Pro |
|---|---|---|
| Ein Produkt komplett rechnen | ✓ | ✓ |
| Ganze Angebotslisten (PI, Excel, PDF, Text) auf einmal | – | ✓ |
| Bestellvorschlag mit Mengen je Position | – | ✓ |
| Mengen-, Fracht-, Preis-Szenarien, Sensitivität | – | ✓ |
| Excel-Bericht (11 Blätter) | – | ✓ |

## Grenzen

- Werte mit Status *Annahme/Drittquelle* (Spitzenzeit-Zuschlag 2026, Rückerstattungsgebühr,
  Frachtpreise, Nebenkosten, Zollrichtwerte) vor einer Bestellung prüfen – `/margencheck:gebuehren`
  listet sie.
- Kontoweite Zuschläge (Lagernutzung, niedriger Lagerbestand) werden nur als Hinweis ausgegeben.
- Ausgabe auf Deutsch. Keine Rechts- oder Steuerberatung.

Lizenz: MIT.
