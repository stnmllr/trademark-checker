import streamlit as st
import requests
import pandas as pd
import time
from urllib.parse import quote

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Markenprüfung EU",
    page_icon="🔍",
    layout="centered",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────
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

  .result-card {
    background: white;
    border-radius: 12px;
    padding: 1rem 1.25rem;
    margin-bottom: 0.75rem;
    border-left: 4px solid #ccc;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
  }
  .result-card.hit    { border-left-color: #E53E3E; }
  .result-card.clear  { border-left-color: #38A169; }
  .result-card.warn   { border-left-color: #D69E2E; }

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

  .name-tag {
    font-size: 1.1rem;
    font-weight: 700;
    color: #1A1F36;
    margin-bottom: 0.25rem;
  }
  .meta { font-size: 0.8rem; color: #718096; margin-top: 0.2rem; }

  .summary-box {
    background: white;
    border-radius: 12px;
    padding: 1.25rem 1.5rem;
    margin-bottom: 1.5rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    display: flex;
    gap: 2rem;
  }

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


# ── EUIPO API ──────────────────────────────────────────────────────────────────
EUIPO_URL = "https://euipo.europa.eu/copla/trademark/data/api/v1/trademarks"

STATUS_MAP = {
    "Registered":        ("🟢 Eingetragen",   "pill-red"),
    "Filed":             ("🟡 Angemeldet",    "pill-yellow"),
    "Refused":           ("⚫ Abgelehnt",     "pill-gray"),
    "Withdrawn":         ("⚫ Zurückgezogen", "pill-gray"),
    "Expired":           ("⚫ Abgelaufen",    "pill-gray"),
    "Cancelled":         ("⚫ Gelöscht",      "pill-gray"),
    "Surrendered":       ("⚫ Verzichtet",    "pill-gray"),
    "Opposition period": ("🟡 Widerspruch",   "pill-yellow"),
}

ACTIVE_STATUSES = {"Registered", "Filed", "Opposition period"}


def query_euipo(name: str, max_results: int = 10) -> list[dict]:
    """Search EUIPO for trademark name. Returns list of hits."""
    params = {
        "trademarkName": name,
        "trademarkNameType": "WORD",
        "start": 0,
        "rows": max_results,
        "sortBy": "applicationDate",
        "sortOrder": "DESC",
    }
    try:
        r = requests.get(EUIPO_URL, params=params, timeout=10,
                         headers={"Accept": "application/json"})
        if r.status_code != 200:
            return []
        data = r.json()
        trademarks = data.get("trademarks", []) or data.get("content", [])
        return trademarks
    except Exception:
        return None  # distinguish error from empty


def classify_result(hits: list[dict]) -> tuple[str, str, str]:
    """Returns (label, css_class, summary_text)."""
    if hits is None:
        return "Fehler", "warn", "API nicht erreichbar"
    active = [h for h in hits if h.get("trademarkStatus", "") in ACTIVE_STATUSES]
    if not active:
        if hits:
            return "Nur inaktive", "warn", f"{len(hits)} abgelaufene/zurückgezogene Einträge"
        return "Frei ✓", "clear", "Kein Treffer in EUIPO"
    return "Kollision", "hit", f"{len(active)} aktive(r) Eintrag/Einträge"


def render_hit(tm: dict):
    status_raw = tm.get("trademarkStatus", "Unknown")
    status_label, pill_class = STATUS_MAP.get(status_raw, (status_raw, "pill-gray"))
    name_val = tm.get("trademarkName", "–")
    owner = tm.get("trademarkOwner", [{}])
    owner_name = owner[0].get("trademarkOwnerName", "–") if owner else "–"
    app_date = tm.get("applicationDate", "")[:10] if tm.get("applicationDate") else "–"
    nice_classes = ", ".join(str(c) for c in (tm.get("niceClasses") or []))
    app_num = tm.get("applicationNumber", "")
    euipo_link = f"https://euipo.europa.eu/eSearch/#details/trademarks/{app_num}" if app_num else ""

    return f"""
<div style="background:#F7FAFC;border-radius:8px;padding:0.6rem 0.9rem;margin:0.4rem 0;font-size:0.83rem;border:1px solid #E2E8F0;">
  <span class="status-pill {pill_class}">{status_label}</span>
  <strong>{name_val}</strong><br>
  <span class="meta">👤 {owner_name} &nbsp;|&nbsp; 📅 {app_date} &nbsp;|&nbsp; Nizza: {nice_classes or '–'}
  {"&nbsp;|&nbsp; <a href='" + euipo_link + "' target='_blank'>EUIPO ↗</a>" if euipo_link else ""}
  </span>
</div>
"""


# ── UI ─────────────────────────────────────────────────────────────────────────
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
    help="Klasse 9 = Software, Klasse 42 = IT-Dienstleistungen. Relevant für ERP/SaaS.",
)

col1, col2 = st.columns([2, 1])
with col1:
    run = st.button("Prüfen →", use_container_width=True)
with col2:
    st.caption("Kostenlos, kein Login")

# ── Run search ─────────────────────────────────────────────────────────────────
if run:
    names = [n.strip() for n in raw_input.splitlines() if n.strip()]
    if not names:
        st.warning("Bitte mindestens einen Namen eingeben.")
        st.stop()
    if len(names) > 20:
        st.warning("Maximal 20 Namen auf einmal. Bitte Liste kürzen.")
        st.stop()

    results = []
    progress = st.progress(0, text="Prüfe Namen…")

    for i, name in enumerate(names):
        progress.progress((i + 1) / len(names), text=f"Pruefe {name}...")
        hits = query_euipo(name, max_results=20)

        # Filter by nice class if selected
        if hits and nice_filter:
            hits_filtered = [
                h for h in hits
                if any(c in (h.get("niceClasses") or []) for c in nice_filter)
            ]
            # Keep original for "any class" count too
            hits_any = hits
            hits = hits_filtered
        else:
            hits_any = hits

        label, css_class, summary = classify_result(hits)
        results.append({
            "name": name,
            "label": label,
            "css_class": css_class,
            "summary": summary,
            "hits": hits or [],
            "hits_any": hits_any or [],
        })
        time.sleep(0.3)  # be polite to EUIPO API

    progress.empty()

    # ── Summary bar ──────────────────────────────────────────────────────────
    n_hit = sum(1 for r in results if r["css_class"] == "hit")
    n_warn = sum(1 for r in results if r["css_class"] == "warn")
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

    # ── Per-name results ──────────────────────────────────────────────────────
    for r in results:
        with st.expander(
            f"{'🔴' if r['css_class']=='hit' else '🟡' if r['css_class']=='warn' else '🟢'}  "
            f"**{r['name']}** — {r['label']}   ·   {r['summary']}",
            expanded=(r["css_class"] == "hit"),
        ):
            if r["hits"]:
                for tm in r["hits"][:8]:
                    st.markdown(render_hit(tm), unsafe_allow_html=True)
                if len(r["hits"]) > 8:
                    st.caption(f"... und {len(r['hits'])-8} weitere. Direkt in EUIPO eSearch prüfen.")
            elif r["hits_any"] and nice_filter:
                st.info(
                    f"In den gewählten Nizza-Klassen ({', '.join(str(c) for c in nice_filter)}) "
                    f"kein Treffer. In anderen Klassen: {len(r['hits_any'])} Einträge."
                )
                for tm in r["hits_any"][:3]:
                    st.markdown(render_hit(tm), unsafe_allow_html=True)
            else:
                st.success("Kein Treffer im EUIPO-Register.")

            esearch_url = f"https://euipo.europa.eu/eSearch/#basic/trademarks/name,Boolean/{quote(r['name'])}"
            st.markdown(f"[Direkt in EUIPO eSearch öffnen ↗]({esearch_url})")

    # ── CSV Export ────────────────────────────────────────────────────────────
    st.markdown("---")
    export_rows = []
    for r in results:
        if r["hits"]:
            for tm in r["hits"]:
                status_raw = tm.get("trademarkStatus", "")
                owner = tm.get("trademarkOwner", [{}])
                owner_name = owner[0].get("trademarkOwnerName", "–") if owner else "–"
                export_rows.append({
                    "Geprüfter Name": r["name"],
                    "Bewertung": r["label"],
                    "Treffer-Marke": tm.get("trademarkName", ""),
                    "Status": status_raw,
                    "Inhaber": owner_name,
                    "Anmeldedatum": (tm.get("applicationDate", "") or "")[:10],
                    "Nizza-Klassen": ", ".join(str(c) for c in (tm.get("niceClasses") or [])),
                    "EUIPO-Nummer": tm.get("applicationNumber", ""),
                })
        else:
            export_rows.append({
                "Geprüfter Name": r["name"],
                "Bewertung": r["label"],
                "Treffer-Marke": "",
                "Status": "",
                "Inhaber": "",
                "Anmeldedatum": "",
                "Nizza-Klassen": "",
                "EUIPO-Nummer": "",
            })

    df = pd.DataFrame(export_rows)
    csv = df.to_csv(index=False, sep=";", encoding="utf-8-sig")
    st.download_button(
        "⬇ Ergebnisse als CSV",
        data=csv,
        file_name="markenprüfung_euipo.csv",
        mime="text/csv",
    )

# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="disclaimer">
  Datenquelle: EUIPO Unionsmarkenregister (EU-weit gültige Marken).<br>
  Dieser Schnellcheck ersetzt <strong>keine</strong> rechtliche Markenrecherche.
  Für eine rechtsverbindliche Prüfung ist eine spezialisierte Agentur (z.B. Nomen, Namestorm)
  oder ein Markenanwalt einzuschalten.
</div>
""", unsafe_allow_html=True)
