# Markenprüfung EU — EUIPO Trademark Checker

Streamlit-App für eine schnelle Vorprüfung von Produktnamen gegen das EU-Unionsmarkenregister (EUIPO) — jetzt inklusive **klanglich/schriftbildlich ähnlicher** Treffer.

## Features

- Batch-Prüfung: bis zu 20 Namen auf einmal
- **Ähnlichkeitssuche** (fuzzy + phonetic), nicht nur identische Schreibweisen
- Filterbar nach Nizza-Klassen (Standard: 9 + 42 = Software / IT-Services)
- Register wählbar: EUIPO (Unionsmarken) und optional WIPO (internationale Registrierungen, Madrid)
- Ampel-Bewertung: **Kollision** (identisch/aktiv) / **Ähnlich – prüfen** / **Frei**
- Detailansicht je Treffer: Markenname, Inhaber, Datum, Klassen, Amt, Match-Relevanz, EUIPO-Link
- Excel-Export der Ergebnisse (inkl. Match-Strategie und Relevanz)
- Direktlink zu EUIPO eSearch pro Name

## Lokaler Start

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy auf Streamlit Community Cloud (kostenlos)

1. GitHub-Repo anlegen (public oder private)
2. `app.py` + `requirements.txt` pushen
3. https://share.streamlit.io → "New app" → Repo auswählen
4. Unter **Settings → Secrets** eintragen: `SIGNA_API_KEY = "sig_..."`
5. Deploy → Link an Marketing-Team schicken

## Datenquelle & Abdeckung

- Quelle: **Signa API** (`api.signa.so`) — normalisierter Zugriff auf EUIPO, WIPO (Madrid) u. a.
- **Enthalten:** EU-Unionsmarken (EUTM) inkl. EU-Designationen aus dem Madrid-System; optional internationale Registrierungen (IR) über WIPO
- **NICHT enthalten:** Rein nationale DE-Marken (DPMA), Firmennamen (Handelsregister), Werktitel (Titelschutz)

> **Wichtig:** Dieser Schnellcheck ersetzt keine rechtliche Markenrecherche.
> Insbesondere nationale DE-Marken, Firmennamen und Titelschutz prüft er **nicht** —
> das bleibt Sache einer spezialisierten Agentur (Nomen, Namestorm) oder eines Markenanwalts.

## Hinweis zum Suchmodus (wichtig beim ersten Live-Test)

Der genaue Request-Parametername für die Ähnlichkeitssuche (`STRATEGY_PARAM` in `app.py`,
aktuell `"search_type"`) ist nicht gegen die Live-API verifiziert. Die App sendet ihn
bevorzugt; lehnt die API ihn mit HTTP 400 ab, wird automatisch ohne ihn erneut gesucht
(Kompatibilitätsmodus) und ein Hinweis angezeigt. Erscheint dieser Hinweis, den echten
Parameternamen aus der Signa-Doku (https://docs.signa.so) in `app.py` eintragen.

## Nizza-Klassen für ERP/SaaS

| Klasse | Beschreibung |
|--------|--------------|
| 9      | Software, Apps, digitale Inhalte |
| 42     | IT-Dienstleistungen, SaaS, Cloud |
| 35     | Unternehmensberatung, Bürodienstleistungen |
| 38     | Telekommunikation / Datenübertragung |
