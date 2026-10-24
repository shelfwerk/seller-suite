---
name: gebuehren
description: Zeigt Stand, Quelle und Prüfdatum der MargenCheck-Gebührentabellen (Amazon EU, Shopify, Fracht, Zoll) und alle ungeprüften Werte. Bei „wie aktuell sind die Gebühren“, „woher kommen die Zahlen“ oder nach Amazon-Preisänderungen.
argument-hint: "[neue Tarifübersicht als PDF]"
allowed-tools: 'Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/margencheck.py" *), Bash(python "${CLAUDE_PLUGIN_ROOT}/scripts/margencheck.py" *), Bash(py -3 "${CLAUDE_PLUGIN_ROOT}/scripts/margencheck.py" *), Bash(pdftotext -layout *), Read, Glob, Edit(./**)'
---

# MargenCheck – Gebührentabellen

1. Stand anzeigen:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/margencheck.py" gebuehren
```

Genau diesen einen Befehl ausführen (ohne `cd`, `;`, `&&`, `|`). Ausgabe unverändert zeigen und in einem Satz einordnen: was offiziell ist, was Annahme/Drittquelle,
ob ein Prüfdatum überschritten ist – und in einem Satz, wo eigene Werte hingehören: Einstellungen und
Spediteur-Raten in `margencheck.json` (`/…:setup`), eine eigene Gebührentabelle als
`margencheck-gebuehren.json` im Arbeitsordner; die Dateien im Plugin bleiben unverändert.
Gebührenkategorien: `margencheck.py kategorien`.

2. Aktualisieren (nur auf Wunsch und mit neuer Quelle – nie aus dem Gedächtnis):
   Ablauf in `references/gebuehren-pflegen.md`. Kurz: Plugin-Tabelle in den Arbeitsordner kopieren
   (`margencheck-gebuehren.json`), Werte aus der neuen Amazon-Tarifübersicht Spalte für Spalte
   übertragen, `_meta` (Version, gültig ab, Stand, Quelle, nächste Prüfung) setzen, mit drei bekannten
   Produkten gegen den Revenue Calculator gegenprüfen. **Die Dateien im Plugin-Ordner nicht ändern**
   (sie werden bei Updates ersetzt); eigene Fracht- und Kostenwerte gehören in `margencheck.json`
   (`/…:setup`).
3. Nach dem Aktualisieren `margencheck.py gebuehren` erneut ausführen und die neue Version zeigen.
