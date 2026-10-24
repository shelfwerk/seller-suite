---
name: setup
description: "Speichert MargenCheck-Einstellungen in margencheck.json: Marktplatz (amazon.de/CEP, FR, IT, ES), Kanal, Einkaufswährung, eigene Frachtpreise, EUSt-Abzug, Prep, Werbe- und Retourenanteil. Bei „MargenCheck einrichten“ oder eigenen Kosten."
argument-hint: "[Marktplatz] [Kanal]"
allowed-tools: 'Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/margencheck.py" *), Bash(python "${CLAUDE_PLUGIN_ROOT}/scripts/margencheck.py" *), Bash(py -3 "${CLAUDE_PLUGIN_ROOT}/scripts/margencheck.py" *), Read'
---

# MargenCheck einrichten

Fragen in **einer** Nachricht stellen, was `$ARGUMENTS`, die Unterhaltung oder eine vorhandene
`margencheck.json` nicht schon beantworten. Alles ist optional – ohne Angabe gelten die
Standardwerte aus `data/standardwerte.json` (im Ergebnis als Annahmen gekennzeichnet).

1. **Marktplatz**: amazon.de (`DE`), amazon.de mit Zentraleuropa-Programm (`DE-CEP`, 0,26 € je Einheit
   günstiger), `FR`, `IT`, `ES`. **Kanal**: `amazon`, `shopify` oder `beide`.
2. **Einkauf**: Standardwährung der Lieferanten (USD/EUR/CNY), Import auf eigene EORI (dann ist die
   EUSt abziehbar), Importland (`DE`/`AT`).
3. **Fracht** (wenn ein Spediteur-Angebot vorliegt): See €/m³, Bahn $/m³ und Mindestbetrag, Luft $/kg,
   Nebenkosten je Sendung, Laufzeiten.
4. **Vorbereitung**: Etikett je Teil, Inbound zu Amazon je Einheit/kg, Produktionszeit.
5. **Planung**: geplanter Werbeanteil (TACOS), typische Retourenquote, maximale Reichweite einer
   Erstbestellung (Standard 4 Monate).
6. **Shopify** (bei Kanal shopify/beide): Tarif (basic/grow/advanced/plus), Zahlartenmix, eigene
   Versandkosten je Gewichtsstufe, Verpackung je Bestellung, Versandgebühr für Kunden.
7. **Schwellen** nur auf Wunsch ändern (GO ab Break-even-TACOS 40 %, TEST ab 25 %).

Speichern (bestehende Werte bleiben erhalten; im Arbeitsordner ausführen oder `--out <ordner>`):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/margencheck.py" init --markt <DE|DE-CEP|FR|IT|ES> --kanal <amazon|shopify|beide> --waehrung <USD> --tacos <15> [--set fracht.bahn.usd_je_m3=420] [--set zoll.eust_abziehbar=ja] [--set shopify.tarif=grow] [--set "shopify.versand_eigen.bis_kg=[[2,4.95],[5,6.20],[31.5,12.90]]"]
```

Alle Schlüssel: `references/einstellungen.md`. Genau diesen einen Befehl ausführen (ohne `cd`, `;`,
`&&`, `|`). Auf Windows `python` oder `py -3`. Danach die
gespeicherte Datei kurz zeigen und anbieten, ein Angebot zu prüfen.
