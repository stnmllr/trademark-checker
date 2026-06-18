# Markenprüfung EU — EUIPO Trademark Checker

Streamlit-App für eine schnelle Vorprüfung von Produktnamen gegen das EU-Unionsmarkenregister (EUIPO).

## Features

- Batch-Prüfung: bis zu 20 Namen auf einmal
- Filterbar nach Nizza-Klassen (Standard: 9 + 42 = Software / IT-Services)
- Ampel-Bewertung: Kollision / Prüfen / Frei
- Detailansicht je Treffer: Markenname, Inhaber, Datum, Klassen, EUIPO-Link
- CSV-Export der Ergebnisse
- Direktlink zu EUIPO eSearch pro Name

## Lokaler Start

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy auf Streamlit Community Cloud (kostenlos, 1 Tag)

1. GitHub-Repo anlegen (public oder private)
2. `app.py` + `requirements.txt` pushen
3. https://share.streamlit.io → "New app" → Repo auswählen
4. Deploy → Link an Marketing-Team schicken

Kein API-Key notwendig. Die App nutzt die öffentliche EUIPO-Backend-API.

## Datenquelle & Hinweise

- Quelle: EUIPO Unionsmarkenregister (~3 Mio. Einträge, EU-weit gültig)
- Abdeckung: Unionsmarken (EUTM) — deckt ~80% der relevanten Software-Marken ab
- Nicht enthalten: Rein nationale DE-Marken (nur DPMA), die bewusst nur DE schützen

> **Wichtig:** Dieser Schnellcheck ersetzt keine rechtliche Markenrecherche.
> Für eine rechtsverbindliche Prüfung: spezialisierte Agentur (Nomen, Namestorm) oder Markenanwalt.

## Nizza-Klassen für ERP/SaaS

| Klasse | Beschreibung |
|--------|--------------|
| 9      | Software, Apps, digitale Inhalte |
| 42     | IT-Dienstleistungen, SaaS, Cloud |
| 35     | Unternehmensberatung, Bürodienstleistungen |
| 38     | Telekommunikation / Datenübertragung |
