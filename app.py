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
  .pill-blue   { background: #E2E8F0; color: #2B6CB0; }

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

# ---------------------------------------------------------------------------
# Signa API config
# ---------------------------------------------------------------------------
SIGNA_URL = "https://api.signa.so/v1/trademarks"

# Verfügbare Ämter bei Signa (Stand der Doku): USPTO, EUIPO, WIPO (Madrid).
# WICHTIG: Nationale DE-Marken (DPMA) sind NICHT enthalten — diese Lücke
# bleibt bewusst der anwaltlichen Recherche vorbehalten.
# EUIPO deckt EU-Unionsmarken inkl. EU-Designationen aus dem Madrid-System ab.
# WIPO ergänzt internationale Registrierungen (IR) aus dem Madrid-Protokoll.
OFFICE_CHOICES = {
    "EUIPO – EU-Unionsmarken (inkl. EU-Madrid-Designationen)": "euipo",
    "WIPO – Internationale Registrierungen (Madrid, IR)": "wipo",
}
DEFAULT_OFFICES = ["euipo"]

# --- Suchmodus -------------------------------------------------------------
# Die /v1/trademarks-Suche liefert bereits per Default auch klanglich/
# schriftbildlich ähnliche Treffer (fuzzy/phonetic) samt relevance_score.
# Ein expliziter Strategie-Parameter ist daher nicht nötig und wird nicht
# gesendet (das vermeidet 400-Fehler).
EXACT_SCORE_THRESHOLD = 90                # relevance_score >= X  => Kollision
SIMILAR_SCORE_FLOOR   = 60                # darunter: als Rauschen ignorieren

ACTIVE_STATUSES = {"active", "registered", "published", "filed", "pending"}

STATUS_LABELS = {
    # Aktive/eingetragene Marken sind KOLLISIONSRISIKO -> rotes Icon.
    "active":     ("🔴 Aktiv/Eingetragen", "pill-red"),
    "registered": ("🔴 Eingetragen",       "pill-red"),
    "published":  ("🟡 Veröffentlicht",    "pill-yellow"),
    "filed":      ("🟡 Angemeldet",        "pill-yellow"),
    "pending":    ("🟡 Ausstehend",        "pill-yellow"),
    "expired":    ("⚫ Abgelaufen",        "pill-gray"),
    "cancelled":  ("⚫ Gelöscht",          "pill-gray"),
    "withdrawn":  ("⚫ Zurückgezogen",     "pill-gray"),
    "abandoned":  ("⚫ Aufgegeben",        "pill-gray"),
}


def _get_relevance(tm: dict):
    """Relevance-Score (0-100) falls die API ihn liefert, sonst None."""
    rel = tm.get("relevance_score")
    if isinstance(rel, (int, float)):
        return rel
    return None


def _get_strategies(tm: dict) -> list[str]:
    """Welche Match-Strategien haben getroffen (exact/fuzzy/phonetic/...)."""
    me = tm.get("match_explanation") or {}
    strat = me.get("strategies_matched")
    return [s.lower() for s in strat] if isinstance(strat, list) else []


def _is_exact_like(tm: dict) -> bool:
    """True wenn Treffer identisch/sehr nah ist (=> echte Kollision).

    Fällt zurück auf 'True', wenn die API keine Score-/Strategie-Infos
    liefert — dann verhält sich das Tool wie zuvor (jeder aktive Treffer =
    Kollision), statt eine Ähnlichkeit fälschlich zu verharmlosen.
    """
    strat = _get_strategies(tm)
    rel = _get_relevance(tm)
    if strat:
        if "exact" in strat and rel is None:
            return True
        if rel is not None:
            return rel >= EXACT_SCORE_THRESHOLD and "exact" in strat
        # nur fuzzy/phonetic getroffen -> ähnlich, nicht identisch
        return False
    if rel is not None:
        return rel >= EXACT_SCORE_THRESHOLD
    return True  # keine Infos -> konservativ als Kollision behandeln


def query_signa(name: str, nice_classes: list[int], offices: list[str]) -> list[dict] | None:
    """Query Signa API. Returns list of hits, empty list if none, None on error."""
    api_key = st.secrets.get("SIGNA_API_KEY", "")
    if not api_key:
        st.error("API-Key fehlt. Bitte in den App-Settings unter Secrets eintragen: SIGNA_API_KEY = \"sig_...\"")
        return None

    base_params = {
        "q": name,
        "offices": ",".join(offices) if offices else "euipo",
        "limit": 30,
    }
    if nice_classes:
        base_params["nice_classes"] = ",".join(str(c) for c in nice_classes)

    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        r = requests.get(SIGNA_URL, params=base_params, headers=headers, timeout=12)

        if r.status_code == 401:
            st.error("API-Key ungültig. Bitte in den App-Settings unter Secrets prüfen.")
            return None
        if r.status_code != 200:
            return None
        data = r.json()
        hits = data.get("data", [])
        # Nach Relevanz sortieren (falls vorhanden), sonst Reihenfolge lassen
        hits.sort(key=lambda h: (_get_relevance(h) or 0), reverse=True)
        return hits
    except Exception:
        return None


def classify_result(hits: list[dict] | None) -> tuple[str, str, str]:
    if hits is None:
        return "Fehler", "warn", "API nicht erreichbar"

    active = [h for h in hits if (h.get("status", {}).get("primary", "") or "").lower() in ACTIVE_STATUSES]
    # sehr schwache Treffer (nur Rauschen aus fuzzy/phonetic) ausblenden
    active = [
        h for h in active
        if (_get_relevance(h) is None or _get_relevance(h) >= SIMILAR_SCORE_FLOOR)
    ]

    if not active:
        if hits:
            return "Nur inaktive", "warn", f"{len(hits)} abgelaufene/zurückgezogene Einträge"
        return "Frei ✓", "clear", "Kein Treffer im Register"

    exact_like = [h for h in active if _is_exact_like(h)]
    similar    = [h for h in active if not _is_exact_like(h)]

    if exact_like:
        extra = f" + {len(similar)} ähnliche" if similar else ""
        return "Kollision", "hit", f"{len(exact_like)} identische/aktive Marke(n){extra}"
    # nur ähnliche aktive Treffer -> juristisch prüfen
    return "Ähnlich – prüfen", "warn", f"{len(similar)} klanglich/schriftbildlich ähnliche aktive Marke(n)"


def render_hit(tm: dict) -> str:
    status_raw = (tm.get("status", {}).get("primary", "") or "").lower()
    status_label, pill_class = STATUS_LABELS.get(status_raw, (status_raw.capitalize(), "pill-gray"))
    name_val  = tm.get("mark_text", "-")
    owner     = tm.get("owner_name", "-") or "-"
    app_date  = (tm.get("filing_date", "") or "")[:10]
    office    = (tm.get("office", "") or "").upper()
    classes   = ", ".join(
        str(c.get("nice_class", "")) for c in (tm.get("classifications") or [])
    )

    # Match-Info (Relevanz + Strategie), falls von der API geliefert
    rel = _get_relevance(tm)
    strat = _get_strategies(tm)
    match_bits = []
    if rel is not None:
        match_bits.append(f"Relevanz {int(rel)}%")
    if strat:
        pretty = {"exact": "identisch", "fuzzy": "ähnlich", "phonetic": "klanglich", "prefix": "Präfix"}
        match_bits.append("/".join(pretty.get(s, s) for s in strat))
    match_pill = ""
    if match_bits:
        match_pill = f"<span class='status-pill pill-blue'>{' · '.join(match_bits)}</span>"

    tm_id = tm.get("id", "")
    euipo_link = ""
    if tm_id and office == "EUIPO":
        euipo_link = f"&nbsp;|&nbsp; <a href='https://euipo.europa.eu/eSearch/#details/trademarks/{tm_id}' target='_blank'>EUIPO ↗</a>"

    office_tag = f" &nbsp;|&nbsp; {office}" if office else ""

    return f"""
<div style="background:#F7FAFC;border-radius:8px;padding:0.6rem 0.9rem;margin:0.4rem 0;
            font-size:0.83rem;border:1px solid #E2E8F0;">
  <span class="status-pill {pill_class}">{status_label}</span>{match_pill}
  <strong>{name_val}</strong><br>
  <span class="meta">👤 {owner} &nbsp;|&nbsp; 📅 {app_date or '-'}
  &nbsp;|&nbsp; Nizza: {classes or '-'}{office_tag}{euipo_link}</span>
</div>
"""


# UI
st.markdown("""
<div class="hero">
  <div class="badge">EUIPO · EU-Markenregister</div>
  <h1>🔍 Markenprüfung EU</h1>
  <p>Schnellcheck gegen das Unionsmarkenregister — inkl. klanglich/ähnlicher Treffer.
     Für eine erste Einschätzung vor der Agentur-Beauftragung.</p>
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

office_labels = st.multiselect(
    "Register / Ämter",
    options=list(OFFICE_CHOICES.keys()),
    default=[k for k, v in OFFICE_CHOICES.items() if v in DEFAULT_OFFICES],
    help="Nationale DE-Marken (DPMA) sind bei dieser Datenquelle NICHT enthalten.",
)
offices = [OFFICE_CHOICES[l] for l in office_labels] or DEFAULT_OFFICES

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
        hits = query_signa(name, nice_filter, offices)
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
        {', '.join(o.upper() for o in offices)} · {len(results)} Namen
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
                st.success("Kein Treffer im Register.")

            esearch_url = f"https://euipo.europa.eu/eSearch/#basic/trademarks/name,Boolean/{quote(r['name'])}"
            st.markdown(f"[Direkt in EUIPO eSearch öffnen ↗]({esearch_url})")

    # Excel Export
    st.markdown("---")
    export_rows = []
    for r in results:
        if r["hits"]:
            for tm in r["hits"]:
                status_raw = (tm.get("status", {}).get("primary", "") or "")
                classes = ", ".join(
                    str(c.get("nice_class", "")) for c in (tm.get("classifications") or [])
                )
                rel = _get_relevance(tm)
                export_rows.append({
                    "Geprüfter Name": r["name"],
                    "Bewertung":      r["label"],
                    "Treffer-Marke":  tm.get("mark_text", ""),
                    "Status":         status_raw,
                    "Match":          "/".join(_get_strategies(tm)) or "",
                    "Relevanz":       int(rel) if rel is not None else "",
                    "Amt":            (tm.get("office", "") or "").upper(),
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
                "Match":          "",
                "Relevanz":       "",
                "Amt":            "",
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
  Datenquelle: EUIPO Unionsmarkenregister (+ optional WIPO/Madrid) via Signa API.<br>
  <strong>Nationale DE-Marken (DPMA) sind nicht enthalten.</strong>
  Dieser Schnellcheck ersetzt <strong>keine</strong> rechtliche Markenrecherche.
  Für eine rechtsverbindliche Prüfung: spezialisierte Agentur (Nomen, Namestorm) oder Markenanwalt.
</div>
""", unsafe_allow_html=True)
