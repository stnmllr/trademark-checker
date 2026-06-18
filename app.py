import streamlit as st
import requests
import pandas as pd
import time
from urllib.parse import quote

# Page config
st.set_page_config(
    page_title="Markenprüfung EU",
    page_icon="🔍",
    layout="centered",
)

# Custom CSS
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
  html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
  .stApp { background: #F8F9FB; }

  .hero {
    background: linear-gradient(135deg, #1A1F36 0%, #2D3561 100%);
    border-radius: 16px;
    padding: 2rem 2.5rem 1.75rem;
    margin-bottom: 2rem;
    color: white;
  }
  .hero h1 { font-size: 1.75rem; font-weight: 700; margin: 0 0 0.25rem; letter-spacing: -0.5px; }
  .hero p  { font-size: 0.95rem; opacity: 0.75; margin: 0; }
  .hero .badge {
    display: inline-block;
    background: rgba(255,255,255,0.15);
    border: 1px solid rgba(255,255,255,0.25);
    border-radius: 20px;
    font-size: 0.75rem;
    padding: 2px 10px;
    margin-bottom: 0.75rem;
    letter-spacing: 0.5px;
    text-transform: uppercase;
  }

  .summary-box {
    background: white;
    border-radius: 12px;
    padding: 1.25rem 1.5rem;
    margin-bottom: 1.5rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    display: flex;
    gap: 2rem;
  }

  .status-pill {
    display: inline-block;
    border-radius: 20px;
    font-size: 0.72rem;
    font-weight: 600;
    padding: 2px 10px;
    margin-right: 4px;
  }
  .pill-red    { background: #FED7D7; color: #C53030; }
  .pill-green  { background: #C6F6D5; color: #276749; }
  .pill-yellow { background: #FEFCBF; color: #975A16; }
  .pill-gray   { background: #EDF2F7; color: #4A5568; }

  .meta { font-size: 0.8rem; color: #718096; margin-top: 0.2rem; }

  div[data-testid="stButton"] > button {
    background: #2D3561;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 0.5rem 1.5rem;
    font-weight: 600;
    font-size: 0.95rem;
    width: 100%;
  }
  div[data-testid="stButton"] > button:hover { background: #1A1F36; }

  .disclaimer {
    font-size: 0.78rem;
    color: #A0AEC0;
    text-align: center;
    margin-top: 1.5rem;
    padding-top: 1rem;
    border-top: 1px solid #E2E8F0;
  }
</style>
""", unsafe_allow_html=True)

# Signa API
SIGNA_URL = "https://api.signa.so/v1/trademarks"

ACTIVE_STATUSES = {"active", "registered", "published", "filed", "pending"}

STATUS_LABELS = {
    "active":     ("🟢 Aktiv/Eingetragen", "pill-red"),
    "registered": ("🟢 Eingetragen",       "pill-red"),
    "published":  ("🟡 Veröffentlicht",    "pill-yellow"),
    "filed":      ("🟡 Angemeldet",        "pill-yellow"),
    "pending":    ("🟡 Ausstehend",        "pill-yellow"),
    "expired":    ("⚫ Abgelaufen",        "pill-gray"),
    "cancelled":  ("⚫ Gelöscht",          "pill-gray"),
    "withdrawn":  ("⚫ Zurückgezogen",     "pill-gray"),
    "abandoned":  ("⚫ Aufgegeben",        "pill-gray"),
}


def query_signa(name: str, nice_classes: list[int]) -> list[dict] | None:
    """Query Signa API. Returns list of hits, empty list if none, None on error."""
    api_key = st.secrets.get("SIGNA_API_KEY", "")
    if not api_key:
        st.error("API-Key fehlt. Bitte in den App-Settings unter Secrets eintragen: SIGNA_API_KEY = \"sig_...\"")
        return None

    params = {
        "q": name,
        "offices": "euipo",
        "limit": 20,
    }
    if nice_classes:
        params["nice_classes"] = ",".join(str(c) for c in nice_classes)

    try:
        r = requests.get(
            SIGNA_URL,
            params=params,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        if r.status_code == 401:
            st.error("API-Key ungültig. Bitte in den App-Settings unter Secrets prüfen.")
            return None
        if r.status_code != 200:
            return None
        data = r.json()
        return data.get("data", [])
    except Exception:
        return None


def classify_result(hits: list[dict] | None) -> tuple[str, str, str]:
    if hits is None:
        return "Fehler", "warn", "API nicht erreichbar"
    active = [h for h in hits if (h.get("status", {}).get("primary", "") or "").lower() in ACTIVE_STATUSES]
    if not active:
        if hits:
            return "Nur inaktive", "warn", f"{len(hits)} abgelaufene/zurückgezogene Einträge"
        return "Frei ✓", "clear", "Kein Treffer in EUIPO"
    return "Kollision", "hit", f"{len(active)} aktive(r) Eintrag/Einträge"


def render_hit(tm: dict) -> str:
    status_raw = (tm.get("status", {}).get("primary", "") or "").lower()
    status_label, pill_class = STATUS_LABELS.get(status_raw, (status_raw.capitalize(), "pill-gray"))
    name_val  = tm.get("mark_text", "-")
    owner     = tm.get("owner_name", "-") or "-"
    app_date  = (tm.get("filing_date", "") or "")[:10]
    classes   = ", ".join(
        str(c.get("nice_class", "")) for c in (tm.get("classifications") or [])
    )
    tm_id = tm.get("id", "")
    euipo_link = ""
    if tm_id:
        euipo_link = f"&nbsp;|&nbsp; <a href='https://euipo.europa.eu/eSearch/#details/trademarks/{tm_id}' target='_blank'>EUIPO ↗</a>"

    return f"""
<div style="background:#F7FAFC;border-radius:8px;padding:0.6rem 0.9rem;margin:0.4rem 0;
            font-size:0.83rem;border:1px solid #E2E8F0;">
  <span class="status-pill {pill_class}">{status_label}</span>
  <strong>{name_val}</strong><br>
  <span class="meta">👤 {owner} &nbsp;|&nbsp; 📅 {app_date or '-'}
  &nbsp;|&nbsp; Nizza: {classes or '-'}{euipo_link}</span>
</div>
"""


# UI
st.markdown("""
<div class="hero">
  <div class="badge">EUIPO · EU-Markenregister</div>
  <h1>🔍 Markenprüfung EU</h1>
  <p>Schnellcheck gegen das Unionsmarkenregister — für eine erste Einschätzung vor der Agentur-Beauftragung.</p>
</div>
""", unsafe_allow_html=True)

st.markdown("#### Namen eingeben")
st.caption("Einen Namen pro Zeile — bis zu 20 Namen auf einmal.")

raw_input = st.text_area(
    "Namen",
    placeholder="Vorano\nVereno\nOperanto\nComodi",
    height=160,
    label_visibility="collapsed",
)

nice_filter = st.multiselect(
    "Nizza-Klassen filtern (optional — leer = alle)",
    options=list(range(1, 46)),
    default=[9, 42],
    help="Klasse 9 = Software, Klasse 42 = IT-Dienstleistungen.",
)

col1, col2 = st.columns([2, 1])
with col1:
    run = st.button("Prüfen →", use_container_width=True)
with col2:
    st.caption("Kostenlos, kein Login")

# Run search
if run:
    raw_names = [n.strip() for n in raw_input.splitlines() if n.strip()]
    # Deduplicate case-insensitively, keep first occurrence
    seen = set()
    names = []
    for n in raw_names:
        if n.lower() not in seen:
            seen.add(n.lower())
            names.append(n)
    dupes = len(raw_names) - len(names)

    if not names:
        st.warning("Bitte mindestens einen Namen eingeben.")
        st.stop()
    if len(names) > 20:
        st.warning("Maximal 20 Namen auf einmal. Bitte Liste kuerzen.")
        st.stop()
    if dupes > 0:
        st.info(f"{dupes} doppelte(r) Name(n) uebersprungen (Gross-/Kleinschreibung wird ignoriert).")

    results = []
    progress = st.progress(0, text="Prüfe Namen...")

    for i, name in enumerate(names):
        progress.progress((i + 1) / len(names), text=f"Pruefe {name}...")
        hits = query_signa(name, nice_filter)
        if hits is None:
            # Error already shown by query_signa
            st.stop()

        label, css_class, summary = classify_result(hits)
        results.append({
            "name":      name,
            "label":     label,
            "css_class": css_class,
            "summary":   summary,
            "hits":      hits,
        })
        time.sleep(0.2)

    progress.empty()

    # Summary bar
    n_hit   = sum(1 for r in results if r["css_class"] == "hit")
    n_warn  = sum(1 for r in results if r["css_class"] == "warn")
    n_clear = sum(1 for r in results if r["css_class"] == "clear")

    st.markdown(f"""
    <div class="summary-box">
      <div><span style="font-size:1.5rem;font-weight:700;color:#E53E3E;">{n_hit}</span><br>
           <span style="font-size:0.8rem;color:#718096;">Kollision</span></div>
      <div><span style="font-size:1.5rem;font-weight:700;color:#D69E2E;">{n_warn}</span><br>
           <span style="font-size:0.8rem;color:#718096;">Prüfen</span></div>
      <div><span style="font-size:1.5rem;font-weight:700;color:#38A169;">{n_clear}</span><br>
           <span style="font-size:0.8rem;color:#718096;">Frei</span></div>
      <div style="margin-left:auto;font-size:0.78rem;color:#A0AEC0;align-self:center;">
        Nizza {', '.join(str(c) for c in nice_filter) if nice_filter else 'alle'}<br>
        EUIPO · {len(results)} Namen
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Per-name results
    for r in results:
        icon = "🔴" if r["css_class"] == "hit" else "🟡" if r["css_class"] == "warn" else "🟢"
        with st.expander(
            f"{icon}  **{r['name']}** — {r['label']}   ·   {r['summary']}",
            expanded=(r["css_class"] == "hit"),
        ):
            if r["hits"]:
                for tm in r["hits"][:8]:
                    st.markdown(render_hit(tm), unsafe_allow_html=True)
                if len(r["hits"]) > 8:
                    st.caption(f"... und {len(r['hits'])-8} weitere Treffer.")
            else:
                st.success("Kein Treffer im EUIPO-Register.")

            esearch_url = f"https://euipo.europa.eu/eSearch/#basic/trademarks/name,Boolean/{quote(r['name'])}"
            st.markdown(f"[Direkt in EUIPO eSearch öffnen ↗]({esearch_url})")

    # CSV Export
    st.markdown("---")
    export_rows = []
    for r in results:
        if r["hits"]:
            for tm in r["hits"]:
                status_raw = (tm.get("status", {}).get("primary", "") or "")
                classes = ", ".join(
                    str(c.get("nice_class", "")) for c in (tm.get("classifications") or [])
                )
                export_rows.append({
                    "Geprüfter Name": r["name"],
                    "Bewertung":      r["label"],
                    "Treffer-Marke":  tm.get("mark_text", ""),
                    "Status":         status_raw,
                    "Inhaber":        tm.get("owner_name", ""),
                    "Anmeldedatum":   (tm.get("filing_date", "") or "")[:10],
                    "Nizza-Klassen":  classes,
                    "Signa-ID":       tm.get("id", ""),
                })
        else:
            export_rows.append({
                "Geprüfter Name": r["name"],
                "Bewertung":      r["label"],
                "Treffer-Marke":  "",
                "Status":         "",
                "Inhaber":        "",
                "Anmeldedatum":   "",
                "Nizza-Klassen":  "",
                "Signa-ID":       "",
            })

    df = pd.DataFrame(export_rows)
    import io
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Markenpruefung")
    st.download_button(
        "⬇ Ergebnisse als Excel",
        data=buf.getvalue(),
        file_name="markenpruefung_euipo.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

# Footer
st.markdown("""
<div class="disclaimer">
  Datenquelle: EUIPO Unionsmarkenregister via Signa API (EU-weit gültige Marken).<br>
  Dieser Schnellcheck ersetzt <strong>keine</strong> rechtliche Markenrecherche.
  Für eine rechtsverbindliche Prüfung: spezialisierte Agentur (Nomen, Namestorm) oder Markenanwalt.
</div>
""", unsafe_allow_html=True)
