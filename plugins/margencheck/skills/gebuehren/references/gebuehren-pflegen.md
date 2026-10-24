# Gebührentabellen prüfen und aktualisieren

Gebühren sind **nicht** im Code, sondern in Tabellen mit Quelle und Stand-Datum:

| Datei | Inhalt | Quelle / Status |
|---|---|---|
| `data/amazon_eu_2026-02-01.json` | Größenklassen, FBA (Standard, Niedrigpreis, ausgewählte Kategorien), Verkaufsgebühren, Lager, Retouren, Spitzenzeit, Treibstoffaufschlag, Digital-Services-Gebühr, USt je Markt | Amazon-Tarifübersicht „Gebühren für Europa“, gültig ab 01.02.2026, sell.amazon.de/preisgestaltung (Erstattungsgebühr, Treibstoffaufschlag 1,5 %) und Amazon-Ankündigung zur Digital-Services-Gebühr (20.03.2026) – offiziell; Spitzenzeit-Höhe 2026 (Ø 0,27 €) und Erhöhung des Treibstoffaufschlags auf 2 % ab 02.11.2026 als Drittquelle markiert |
| `data/shopify_de_2026.json` | Shopify-Tarife, Zahlungsgebühren, Beispiel-Versandkosten | shopify.com/de/preise (offiziell), PayPal/Klarna Drittquelle, Versand = Beispielwerte |
| `data/standardwerte.json` | Wechselkurse, Fracht See/Bahn/Luft, Nebenkosten, Vorbereitung, Zeiten, Planung, Entscheidungsschwellen | EZB-Kurs; sonst Praxiswerte/Annahmen |
| `data/zoll_richtwerte.csv` | Zollsätze je HS-Code | Richtwerte – vor der Bestellung TARIC/ZTA |

`margencheck.py gebuehren` zeigt Stand, nächstes Prüfdatum und alle Werte, die nicht aus einer
offiziellen Quelle stammen. Ist das Prüfdatum überschritten, steht eine Warnung in jedem Bericht.

## Eigene Werte (ohne die Plugin-Dateien zu ändern)

Die Dateien im Plugin werden bei jedem Update ersetzt. Eigene Werte gehören in den Arbeitsordner:

- `margencheck.json` – Einstellungen und Abweichungen (Fracht-Angebot des Spediteurs, Kurs, Zeiten,
  Schwellen, Shopify-Versandkosten). Anlegen mit `/margencheck:setup` bzw. `margencheck.py init --set …`.
- `margencheck-gebuehren.json` – vollständige eigene Amazon-Tabelle (gleiches Format).
- `margencheck-zoll.csv` – eigene Zollsätze (gleiche Spalten wie `zoll_richtwerte.csv`; hat Vorrang).

## Wenn Amazon neue Gebühren veröffentlicht (meist zum 1. Februar)

1. Neue Tarifübersicht als PDF laden (Seller Central → Gebühren → „Tarifübersicht“), lokal ablegen.
2. `data/amazon_eu_*.json` in den Arbeitsordner kopieren als `margencheck-gebuehren.json`.
3. Claude liest das PDF (Seiten Niedrigpreis, Standardversand, ausgewählte Kategorien, Lager,
   Empfehlungsgebühren) und trägt die Werte **Spalte für Spalte** in die Kopie ein:
   `fba_niedrigpreis`, `fba_standard`, `fba_auswahl_kategorien` (Spalten `CEP`, `DE` = „Nur DE“, `FR`,
   `IT`, `ES`), `lager`, `referral.kategorien`, `spitzenzeit`.
4. `_meta` aktualisieren: `version`, `gueltig_ab`, `stand` (heute), `quelle` (Dateiname + Abrufdatum),
   `naechste_pruefung` (ca. 15.01. des Folgejahres).
5. Gegenprobe: drei bekannte Produkte mit `margencheck.py rechner … --kanal amazon` rechnen und die
   FBA-Gebühr mit dem Revenue Calculator bzw. der „Vorschau auf FBA-Gebühren“ in Seller Central
   vergleichen. Abweichung → Größenklasse/Packmaß prüfen, nicht die Tabelle verbiegen.

Spitzenzeit-Gebühren kündigt Amazon jeweils um den 15. September an – dann `spitzenzeit.von/bis/
zuschlag_eur` anpassen. Änderungen am Treibstoff- und Logistikaufschlag als neue Stufe unter
`treibstoffzuschlag.stufen` (`ab`, `satz`, `status`, `quelle`) eintragen – alte Stufen stehen lassen,
dann rechnet MargenCheck je Ankunftstag mit dem richtigen Satz. Verkäufer mit Sitz in UK, IT oder ES
passen `maerkte.<FR|IT|ES>.dst_referral/dst_fba` an (Regeln siehe `dst_hinweis`).
