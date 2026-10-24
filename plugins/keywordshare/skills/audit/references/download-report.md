# Downloading the reports

Brand Analytics needs **Amazon Brand Registry** and the **Brand Representative** role on the account.

## Search Query Performance (needed)

**English console:** Seller Central → *Brands* → *Brand Analytics* → *Search Query Performance*
1. Choose **Brand view** (whole brand) or **ASIN view** (one product), range **Weekly** (or Monthly).
2. Pick the week, then **Generate download** → *Download* as **CSV**. Keep the file as it is
   (the first line with `Brand=[…]` / `Reporting Range=[…]` tells KeywordShare the period).
3. For a trend: download several weeks, one file per week.

**German console:** Seller Central → *Marken* → *Markenanalyse* → *Suchanalyse* →
*Suchanfragenleistung* (labels may differ slightly) — view *Markenansicht* or *ASIN-Ansicht*,
range *wöchentlich*. If the downloaded columns are not recognised, switch Seller Central to English
before downloading (KeywordShare knows the English headers for sure).

Tool exports (e.g. AMALYTIX "Search Query Performance" export with *My …/Total …* columns) and the
SP-API JSON report also work.

## Top Search Terms (Pro, competition view)

Brand Analytics → *Top Search Terms* (German: *Top-Suchbegriffe*). Filter to your search terms or your
brand before downloading — the full marketplace file is very large. Download as CSV.

## Sponsored Products search term report (Pro, organic estimate)

Amazon Ads console → *Reports* → *Create report* → Sponsored Products → **Search term**, same period as
the Search Query Performance file, time unit *Summary*. (The same file TermSweep reads.)
