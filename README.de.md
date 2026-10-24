
# Shelfwerk Seller Suite: kostenlose Claude-Plugins für Amazon-Seller

[English](README.md) · [Website](https://shelfwerk.com) · MIT-Lizenz

Vier kostenlose Plugins für Claude. Du lädst einen Bericht aus Seller Central herunter, ziehst ihn in Claude und stellst eine Frage.
Die Rechnung macht ein kleines Python-Skript auf deinem Rechner, Claude erklärt das Ergebnis. Es gibt keine API-Schlüssel und keinen Konto-Zugriff,
und an deinem Konto ändert sich nichts.

| Plugin | Bericht | Ergebnis |
|---|---|---|
| **TermSweep** | Suchbegriffbericht Sponsored Products | Suchbegriffe, die Geld ohne Bestellung kosten, zu teure Begriffe, Gewinner für exakte Keywords |
| **KeywordShare** | Brand Analytics → Suchanfragenleistung | Dein Anteil an Impressionen, Klicks, Warenkorb und Käufen je Suchanfrage. Dazu: wo du Käufe verlierst, welche Suchanfragen du verteidigen solltest, eine Keyword-Liste |
| **ListingDoctor** | Kategorie-Angebotsbericht, Vorlage oder ASINs | Regel-Check (Titel ≤ 75 Zeichen, Artikel-Highlights, Backend ≤ 249 Byte, EU-Faserbezeichnung, Umweltaussagen): Score und Top-5-Fixes |
| **MargenCheck** | Lieferantenangebot (Preis, Maße, Gewicht) | Landed Cost, Amazon-EU-Gebühren 2026, Marge, Break-even-ACOS, Max-EK |

Liest deutsche und englische Berichte, andere Konsolensprachen werden erkannt. Antworten auf Deutsch oder Englisch.

## Installation

**Claude Code**

```
/plugin marketplace add shelfwerk/seller-suite
/plugin install termsweep@shelfwerk
```

`keywordshare`, `listingdoctor` und `margencheck` installierst du genauso. Ein Plugin nur für eine Sitzung ausprobieren:
`claude --plugin-dir ./plugins/termsweep`.

**Claude-Desktop-App / Cowork:** Plugin-ZIP unter [Releases](https://github.com/shelfwerk/seller-suite/releases) herunterladen, dann **Customize → Plugins → Add → Upload plugin**.

Du brauchst einen bezahlten Claude-Plan. Die Skripte brauchen Python 3. In Cowork und auf dem Mac ist es normalerweise schon da; nur bei Claude Code
unter Windows musst du es einmal von python.org installieren.

## Erste Schritte

- „Wo verbrenne ich Werbegeld? Ziel-ACOS 30 %." (Suchbegriffbericht) → `/termsweep:audit`
- „Wo verliere ich Käufe?" (Suchanfragenleistung) → `/keywordshare:audit`
- „Prüf meine Listings" (Kategorie-Angebotsbericht) oder „Prüf B0…, B0…" → `/listingdoctor:check`
- „Lohnt sich das? 2000 Stk zu 3,20 USD FOB, VK 24,99 €" → `/margencheck:rechner`

## Pro

Die Pro-Versionen haben zusätzlich:
- Upload-Dateien (Bulk-Datei, Teilaktualisierung für Listings);
- Wortgruppen-Analyse;
- ASIN-Matrix und Trend;
- regelgeprüfte Neufassungen;
- Vergleich ganzer Lieferantenangebote.

Details und Preise: **https://shelfwerk.com**.

## Datenschutz

- Die Skripte lesen lokale Dateien und machen **keine Netzwerkanfragen**. Einzige Ausnahme: ListingDoctor ruft die öffentliche Amazon-Produktseite ab, wenn
  du ASINs nennst.
- Es gibt keine Telemetrie und keinen Login.
- Was du Claude zeigst, verarbeitet Claude wie jede Datei im Chat, nach den Bedingungen deines Claude-Plans.
- Mehr in [PRIVACY.md](PRIVACY.md).

## Support

support@shelfwerk.com. Unabhängiges Werkzeug, nicht mit Amazon oder Anthropic verbunden.
