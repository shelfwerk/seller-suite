# Einstellungen (`margencheck.json`)

Nur Abweichungen von `data/standardwerte.json` eintragen. Speichern per
`margencheck.py init [--markt DE] [--kanal amazon|shopify|beide] [--waehrung USD] [--tacos 15] --set abschnitt.schluessel=wert …`

| Schlüssel | Standard | Bedeutung |
|---|---|---|
| `marktplatz` | `DE` | `DE` (Lager nur DE), `DE-CEP` (Zentraleuropa-Programm, 0,26 € günstiger), `FR`, `IT`, `ES` |
| `kanal` | `amazon` | `amazon`, `shopify`, `beide` |
| `waehrung_ek` | `USD` | Standardwährung der Lieferantenpreise |
| `import_land` | `DE` | bestimmt den EUSt-Satz (`DE` 19 %, `AT` 20 % …) |
| `kurse.USD` / `kurse.CNY` | EZB 21.10.2026 | Umrechnung in EUR |
| `fracht.see.eur_je_m3`, `fracht.see.min_m3`, `fracht.see.tage_transit` | 170 / 1 / 45 | Seefracht LCL inkl. CFS beidseitig (Richtwert Marktübersicht 10/2026) |
| `fracht.bahn.usd_je_m3`, `fracht.bahn.min_usd`, `fracht.bahn.tage_transit` | 450 / 525 / 30 | Bahn China–EU |
| `fracht.luft.usd_je_kg`, `fracht.luft.volumen_teiler`, `fracht.luft.tage_transit` | 6,50 / 6000 / 10 | Luftfracht |
| `fracht.<see|bahn|luft>.nebenkosten_je_sendung_eur` | 450 / 150 / 100 | Abholung, Dokumente, Verzollung, Zustellung je Sendung |
| `sendung.nebenkosten_je_sendung_eur` | 75 | nur Rückfallwert, wenn bei der Frachtart nichts steht |
| `sendung.packfaktor_volumen` | 1,15 | Zuschlag aufs Packmaß ohne Packliste |
| `zoll.standard_satz` | 12 % | Zollsatz ohne HS-Code (konservativ) |
| `zoll.eust_abziehbar` | `true` | EUSt als Vorsteuer abziehbar (eigene EORI) |
| `zoll.eust_erstattung_tage` | 40 | bis die EUSt zurückkommt |
| `vorbereitung.etikett_je_teil` / `set_verpackung_je_set` / `inbound_je_einheit` / `inbound_je_kg` | 0,12 / 0,06 / 0,10 / 0,10 | Prep und Anlieferung zu Amazon |
| `zeiten.produktion_tage` / `inbound_tage` / `auszahlung_tage` / `anzahlung_anteil` | 30 / 10 / 21 / 30 % | Zeitachse der Kapitalbindung |
| `planung.tacos_plan` | 15 % | geplanter Werbeanteil am Umsatz |
| `planung.retourenquote` / `unverkaeuflich_anteil` | 5 % / 15 % | wenn je Position nichts angegeben |
| `planung.reichweite_monate_max` | 4 | Obergrenze für Mengenempfehlungen |
| `entscheidung.go_be_tacos` / `test_be_tacos` / `min_db_eur` / `min_marge` | 40 % / 25 % / 1,00 € / 10 % | Schwellen GO/TEST/NEIN |
| `shopify.tarif` | `basic` | `basic`, `grow`, `advanced`, `plus` |
| `shopify.zahlarten_mix` | Karte 60 / PayPal 30 / Klarna 10 | Anteil der Zahlarten |
| `shopify.versand_eigen.bis_kg` | Beispielwerte | `[[1, 4.50], [2, 5.20], …]` netto je Paket |
| `shopify.versand_eigen.verpackung_je_bestellung` / `pick_pack_je_bestellung` | 0,40 / 0 | je Bestellung |
| `shopify.kunde_zahlt_versand_brutto` | 0 | Versandgebühr, die der Kunde zahlt |
| `shopify.marketing_anteil` | = `tacos_plan` | Marketing-Anteil am Shop-Umsatz |

Beispiel:

```bash
python3 margencheck.py init --markt DE-CEP --kanal beide --tacos 12 \
  --set fracht.bahn.usd_je_m3=420 --set shopify.tarif=grow \
  --set "shopify.versand_eigen.bis_kg=[[2,4.95],[5,6.20],[31.5,12.90]]"
```
