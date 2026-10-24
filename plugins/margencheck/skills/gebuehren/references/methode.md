# MargenCheck – Rechenmethode

Alle Zahlen rechnet `scripts/margencheck.py` deterministisch aus den Tabellen in `data/`. Claude
rechnet nichts selbst nach und schätzt keine Ergebnisse.

## 1. Landed Cost je Verkaufseinheit

```
EK €        = EK (Lieferantenwährung) × Kurs                      Kurs: data/standardwerte.json → kurse
Fracht      = Frachtrechnung der Sendung × Anteil der Position ÷ Menge
Nebenkosten = Pauschale je Sendung und Frachtart (See 450 €, Bahn 150 €, Luft 100 €: Verzollung,
              CFS, Avis, Zustellung) × Volumenanteil ÷ Menge
Zollwert    = EK € + Fracht + Nebenkosten                          (CIF, konservativ: ganze Fracht)
Zoll        = Zollwert × Zollsatz                                  (HS-Code → data/zoll_richtwerte.csv, sonst 12 %)
EUSt        = (Zollwert + Zoll) × EUSt-Satz                        (nur Kosten, wenn nicht abziehbar)
Vorbereitung= Etikett je Teil + Set-Verpackung (Sets) + Inbound je Einheit + Inbound je kg
Landed      = EK € + Fracht + Nebenkosten + Zoll + Vorbereitung (+ EUSt, falls nicht abziehbar)
```

- **Fracht nach Volumen verteilen, nicht nach Wert** (See, Bahn); Luftfracht nach frachtpflichtigem
  Gewicht = max(Bruttogewicht, m³ × 1.000.000 ÷ 6000).
- Sendungsvolumen: aus der Packliste (Karton-Maße × Kartons oder CBM gesamt), sonst geschätzt aus
  Packmaß × Menge × 1,15 + 0,05 m³ (im Ergebnis als Schätzung markiert).
- Mindestabrechnungen: Bahn 525 $, See 1 m³ – kleine Sendungen werden je Stück teurer.
- **Frachtart `auto`** = die Frachtart mit dem höchsten DB gesamt (Lager- und Q4-Effekt der späteren
  Ankunft eingerechnet); der Liefertermin selbst wird nicht bewertet – bei Saisonware vorgeben.
- **Kontrolle:** Summe Stückkosten × Menge = Blockrechnung (Ware + Frachtrechnung + Nebenkosten + Zoll
  + Vorbereitung). Die Abweichung muss 0,00 € sein; sie steht in jedem Bericht.
- DDP-Positionen und Positionen mit fester Fracht je Stück sind nicht Teil der eigenen Sendung.

## 2. Amazon-Gebühren je verkaufter Einheit

- **Größenklasse** aus Packmaß und Stückgewicht (Tarifübersicht S. 6). Umschläge nach Stückgewicht,
  Pakete/Übergrößen nach max(Stückgewicht, Volumengewicht = L × B × H ÷ 5000).
- **Niedrigpreisversand** automatisch, wenn VK brutto ≤ 20 € (≤ 12 € in Schönheit, Gesundheit,
  Bürobedarf, Lebensmittel, Bücher, Küche …) und Umschlag oder Kleines Paket ≤ 400 g.
- **Ausgewählte Kategorien** (u. a. Kleidung & Accessoires, Schuhe, Heimtextilien, Taschen): Pakete
  mit Grundgebühr bis 100 g + Zusatz je weitere angefangene 100 g (S. 7).
- **Verkaufsgebühr** auf den Bruttopreis nach Kategorie (Satz, Preisstufe oder Preisanteile),
  mindestens 0,30 €.
- **Digital-Services-Gebühr** (Amazon-Ankündigung, gültig ab 20.03.2026) für Verkäufer mit Sitz
  außerhalb UK/FR/IT/ES: + 3 % auf die Verkaufsgebühr in FR, IT, ES und zusätzlich + 3 % auf die
  FBA-Gebühr in FR.
- **Treibstoff- und Logistikaufschlag** auf die FBA-Versandgebühr (DE, FR, IT, ES): 1,5 % ab
  17.04.2026 (sell.amazon.de), 2 % ab 02.11.2026 (Fachpresse); es gilt der Satz am Tag der
  Verfügbarkeit bei Amazon.
- **Spitzenzeit** (nur DE, 15.10.–14.01., nur kleine und Standardpakete, nicht Umschlag/Übergröße/
  Niedrigpreis): Zuschlag × Anteil des Abverkaufs, der in das Fenster fällt.
- **Lager**: Tag-für-Tag-Abverkauf ab Verfügbarkeit bei Amazon (Bestelltag + Produktion + Transit +
  Inbound), Ø-Bestand × Volumen × Monatstarif (Jan–Sep / Okt–Dez, Kleidung günstiger), plus Zuschlag
  für veralteten Bestand ab Tag 241 (Kleidung ab 271). Lagernutzungszuschlag (kontoweit) nur als Hinweis.
- **Retouren** mit Quote r, k = r ÷ (1 − r) je behaltener Einheit:
  - FBA-Versand auch für zurückgesendete Einheiten: FBA × (1 + k)
  - Rückerstattungsgebühr: k × min(20 % der Verkaufsgebühr, 5 €) (sell.amazon.de/preisgestaltung)
  - Bearbeitung Kleidung/Schuhe: k × 50 % der FBA-Gebühr (andere Kategorien nur bei hoher Quote – Eingabe `retourengebuehr_je_retoure`)
  - Unverkäuflicher Anteil (Standard 15 %): k × 15 % × Landed

## 3. Deckungsbeitrag und Break-even

```
DB vor Werbung = VK netto − Landed − Verkaufsgebühr − FBA − Spitzenzeit − Lager − Retouren
Werbung        = TACOS-Plan × VK brutto
DB             = DB vor Werbung − Werbung
Break-even-ACOS = Break-even-TACOS = DB vor Werbung ÷ VK brutto
```

Amazon weist Werbeumsätze in der EU brutto aus; deshalb beziehen sich ACOS/TACOS auf den Bruttopreis.
Bei Break-even-ACOS trägt ein Werbeverkauf gerade noch seine Kosten, bei Break-even-TACOS trägt das
ganze Produkt seine Werbung.

**Shopify:** DB vor Marketing = VK netto + Versanderlös netto − Landed (ohne FBA-Inbound) −
(Versand + Verpackung + Zahlungsgebühren) × (1 + k) − k × (Rücksendung + unverkäuflich × Landed).
Zahlungsgebühren nach Tarif und Zahlartenmix (Shopify Payments, PayPal inkl. Fremdanbieter-Aufschlag,
Klarna). Break-even-ROAS = 1 ÷ Break-even-Marketinganteil.

## 4. Kapitalbindung

Tag 0 Anzahlung (Standard 30 %), Tag Produktionsende Rest + Fracht, Ankunft Zoll + EUSt +
Nebenkosten + Vorbereitung, EUSt-Erstattung 40 Tage nach Einfuhr (wenn abziehbar), Auszahlungen
21 Tage nach Verkauf (14-Tage-Zyklus + 7 Tage Reserve) mit DB + Landed je Einheit. Ergebnis:
Kapitalbedarf in der Spitze, Tag des Kapitalrückflusses, DB gesamt und Kapitalrendite p. a.
= DB gesamt ÷ Kapitalbedarf × 365 ÷ Zykluslänge.

## 5. Urteil

| Rechnung | Bedingung (Standard, in margencheck.json änderbar) |
|---|---|
| **GO** | BE-TACOS ≥ 40 %, DB ≥ 1,00 €, Marge ≥ 10 % |
| **TEST** | BE-TACOS 25–40 % oder DB/Marge knapp – kleine Menge |
| **NEIN · Marge** | BE-TACOS < 25 % oder DB bei Plan-Werbung ≤ 0 |

Die qualitative Bewertung (Datei `--bewertung`: Compliance, Duplikat, Markenpassung, unbelegt) wird
mit der Rechnung kombiniert – es gilt das **strengere** Urteil. `PREIS PRÜFEN` (Duplikat, aber
günstiger als der laufende Einkauf) wird durchgereicht, solange die Rechnung nicht NEIN ist.

## 6. Grenzwerte, Hebel, Szenarien (Pro)

- **Max-EK** für GO/TEST: höchster Einkaufspreis, bei dem der BE-TACOS die Schwelle erreicht
  (lineare Rechnung über Zoll und Retourenverlust).
- **Mindest-VK** für GO: niedrigster Bruttopreis in 10-Cent-Schritten.
- **Gebührenhebel**: nächstkleinere Größenklasse mit ≤ 15 % weniger Packmaß oder ≤ 10 % weniger
  Gewicht, Niedrigpreisgrenze (bis 3 € darüber), Preisstufen der Verkaufsgebühr.
- **Mengenszenarien je Position** (Rest der Bestellung unverändert): MOQ, ½×, 1×, 2×, 2/3/4/6
  Monatsabsätze, Staffelpreise. Empfehlung = höchster DB gesamt bei Reichweite ≤ 4 Monate und
  BE-TACOS ≥ 25 %. Ohne bekannten Absatz nie mehr als die angebotene Menge.
- **Bestellvorschlag**: nur GO/TEST, GO in empfohlener Menge, TEST in kleinster Menge mit DB > 0
  (Reichweite ≤ 2,5 Monate), neu gerechnet als eigene Sendung; fällt eine Position dabei auf NEIN,
  wird sie entfernt und neu gerechnet.
- **Bestellung × Faktor**, **Frachtvergleich** See/Bahn/Luft, **Sensitivität** (Werbung 0–30 %,
  VK ±, EK +10 %).
