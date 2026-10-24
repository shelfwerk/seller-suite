# Changelog

## 1.1.4 – 2026-10-24 (Skill-Frontmatter)

- **Fehler behoben:** Die Beschreibungen von `setup` (Gratis und Pro) sowie `rechner`, `angebot` und `szenarien` (Pro)
  enthielten „: " ohne Anführungszeichen. Das ist ungültiges YAML. Neuere Claude-CLI-Versionen melden „frontmatter failed to parse",
  und der Skill lädt dann ohne Beschreibung und springt nicht mehr an. Die Werte stehen jetzt in Anführungszeichen, der Text ist unverändert.
- Neuer Test prüft alle SKILL.md auf YAML-sichere Werte.
- Keine Änderung an Rechnung, Gebühren oder Skripten.

## 1.1.3 – 2026-10-22 (Versionsangabe)

- **Fehler behoben:** `margencheck.py --version` meldete noch 1.1.0. Die Versionsangabe im Skript stimmt jetzt mit
  plugin.json überein; ein Test und der Build prüfen das künftig (44 Tests).
- Changelog-Einträge zu 1.1.1 und 1.1.2 neutral formuliert.
- Keine Änderung an Rechnung, Gebühren oder Skills.

## 1.1.2 – 2026-10-22 (Auslöser)

- **Skill-Beschreibungen gekürzt und geschärft** (rechner, angebot, szenarien, setup, gebuehren; −45 %): Der Auslöser steht
  jetzt vorn, z. B. „immer nutzen, auch wenn EK, Menge und VK schon im Chat stehen … oder Maße fehlen (fragt nach); nie
  selbst schätzen“. Grund aus einem Auslöse-Test mit vielen gleichzeitig geladenen Plugins: Bei „Lohnt sich das? 2000 Stk
  zu 3,20 USD FOB, VK 24,99 €“ rechnete Claude selbst, ohne Skill. Ursache: Claude Code kürzt die Skill-Liste nach
  Zeichenbudget; bei vielen installierten Skills kommen lange Beschreibungen nur noch teilweise oder gar nicht an.
- Keine Änderung an Rechnung oder Skripten.

## 1.1.1 – 2026-10-22 (Zahlenformat bei Preisen)

- **Fehler behoben:** In Preisspalten (EK, VK, Staffelpreise, FBA-Gebühr, Fracht, Zusatzkosten) wurde „1,780“ als
  Tausendertrennzeichen gelesen (1.780 statt 1,78). SupplierPilot-Übergaben bis 1.0.0 schreiben genau so, und alle
  Positionen wurden ohne Warnung „NEIN“. Jetzt gilt:
  - Das Dezimalformat wird je Datei aus den Preisspalten bestimmt („0,40“, „1.234,56“ → Komma; „0.40“, „1,234.56“ → Punkt);
    Übergaben aus SupplierPilot gelten als Dezimalkomma.
  - Ohne Anhaltspunkt wird ein mehrdeutiger Preis wie „1,780“ als 1,78 gelesen, und der Bericht zeigt einen Hinweis
    „EK „1,780“ als 1,78 gelesen … bitte prüfen“.
  - Mengen bleiben wie bisher („1.000“ / „1,000“ = tausend); Staffel-Mengen werden jetzt ebenfalls so gelesen.
- **Max-EK und EK in der Anzeige:** Ab 1 mit zwei Nachkommastellen („21,82 CNY“ statt „21,820“), denn „21,820“ wurde beim
  Übernehmen in SupplierPilot oder eine Lieferanten-Mail als 21.820 gelesen. Unter 1 bleiben drei Stellen („0,345“).
  Pro-Tabelle „Max-EK GO“ jetzt mit Währung.
- **Alternativ-Angebote:** Eine SupplierPilot-Übergabe enthält Angebote verschiedener Lieferanten für *ein* Produkt.
  Bisher wurden sie als eine Sammelbestellung gerechnet (z. B. 4.500 Stk von 3 Lieferanten, verzerrte Fracht je Stück).
  `angebot` erkennt das jetzt an der Spalte `notiz` und rechnet jedes Angebot als eigene Bestellung mit eigener Sendung:
  Rangliste, Empfehlung, Max-EK mit Währung, kein Bestellvorschlag. `--gemeinsam` erzwingt die Sammelbestellung,
  `--alternativen` schaltet den Modus für eigene Listen ein.
- **DAP/DPU** (auch „DAP Rosenheim“): Der Hauptlauf ist im Preis, deshalb wird keine Fracht mehr aufgeschlagen. Zoll und EUSt
  bleiben beim Käufer, mit Hinweis auf das Ursprungsland. Bisher wurde bei DAP Seefracht ab China gerechnet.
  Hinweise zu Mindestfracht und Packliste entfallen bei DDP/DAP/DPU und bei fester Fracht je Stück.
- `angebot --out <neuer Ordner>` legt den Ordner an, statt mit FileNotFoundError abzubrechen.
- Regressionstests für 0,890 / 1,780 / 12,345 / 1.234,56 / 1234.56, SupplierPilot-Übergabe alt/neu, DAP und Alternativen (43 Tests).
  Gefunden im Integrationstest der Übergabedateien.

## 1.1.0 – 2026-10-22 (Härtung)

- Gebühren gegen offizielle Amazon-Quellen geprüft (docs/03): Rückerstattungsgebühr bestätigt (offiziell),
  Digital-Services-Gebühr korrigiert (DE-Sitz: 3 % auf Verkaufsgebühr in FR/IT/ES, auf FBA nur in FR),
  neuer Treibstoff- und Logistikaufschlag auf FBA (1,5 % ab 17.04.2026, 2 % ab 02.11.2026, je Ankunftstag),
  Spitzenzeit-Zuschlag nur noch auf Pakete (nicht Umschläge).
- Seefracht-Richtwert 170 €/m³ mit Herleitung; Nebenkosten je Sendung jetzt je Frachtart (See 450 €,
  Bahn 150 €, Luft 100 €).
- Skills: genau ein Befehl ohne `;`/`&&`/`echo $?` (vermeidet abgelehnte Bash-Freigaben), Shopify-Hinweis
  auf Beispiel-Versandkosten, Szenarien aus xlsx über eine CSV mit Monatsabsatz.
- Bericht: Treibstoffaufschlag und Digitalsteuer in der Stückrechnung ausgewiesen, Shopify-Grundlagenzeile.
- Niedrigpreis-Hebel nur noch, wenn er den DB verbessert.
- Neu: `--absatz <Stk/Monat>` für angebot/szenarien/rechner mit Datei (gilt für `--pos` bzw. alle
  Positionen) – Szenarien direkt auf einer Lieferanten-PI ohne CSV-Umweg; Szenario-Kopf zeigt Marktplatz
  und Absatz.
- Eval-Suite für `claude plugin eval` (Gratis 4 Fälle, Pro 8 Fälle: PI-xlsx DE, PDF FR, CSV IT,
  Szenarien ES, Shopify, Compliance-Mail, Guard, Gebührenstand); 37 Unit-Tests.

## 1.0.0 – 2026-10-22

- Erste Version (Gratis + Pro).
- Gebührentabelle Amazon EU gültig ab 01.02.2026 (DE, DE-CEP, FR, IT, ES): Größenklassen, FBA Standard,
  Niedrigpreisversand, ausgewählte Kategorien (je 100 g), Verkaufsgebühren, Lager (Jan–Sep/Okt–Dez,
  veralteter Bestand), Retouren, Spitzenzeit 2026 (Drittquelle).
- Shopify-Tarife DE 2026 (Shopify Payments, PayPal, Klarna), Beispiel-Versandkosten.
- Landed Cost mit Frachtverteilung nach Volumen/frachtpflichtigem Gewicht, Mindestfracht, CIF-Zoll,
  EUSt (abziehbar/Kosten), DDP, Kontrollrechnung.
- Deckungsbeitrag, Break-even-ACOS/TACOS, Max-EK, Mindest-VK, Gebührenhebel, Kapitalbindung.
- Pro: Angebotslisten (CSV/XLSX/JSON, PI-Spalten DE/EN), qualitative Bewertung, Bestellvorschlag,
  Mengen-/Fracht-/Preisszenarien, Sensitivität, Excel-Bericht (ohne Zusatzpakete).
