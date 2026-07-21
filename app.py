import streamlit as st
import requests
import pandas as pd
import time
import io
import json
import re
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
    margin-bottom: 1.5rem;
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
  .name-card {
    background: white;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: 0.9rem 1.1rem;
    margin: 0.5rem 0;
    box-shadow: 0 1px 2px rgba(0,0,0,0.04);
  }
  .name-card h3 { margin: 0; font-size: 1.15rem; font-weight: 700; color: #1A1F36; }
  .dom { font-size: 0.74rem; font-weight: 600; border-radius: 6px; padding: 2px 7px; margin-right: 4px; }
  .dom-free { background: #C6F6D5; color: #276749; }
  .dom-taken { background: #FED7D7; color: #C53030; }
  .dom-unk  { background: #EDF2F7; color: #4A5568; }
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
# Signa API config (Marken-Knockout, EUIPO)
# ---------------------------------------------------------------------------
SIGNA_URL = "https://api.signa.so/v1/trademarks"
# Verfügbare Ämter bei Signa: USPTO, EUIPO, WIPO (Madrid).
# Nationale DE-Marken (DPMA) sind NICHT enthalten -> Stufe 2 (TMview).
OFFICE_CHOICES = {
    "EUIPO – EU-Unionsmarken (inkl. EU-Madrid-Designationen)": "euipo",
    "WIPO – Internationale Registrierungen (Madrid, IR)": "wipo",
}
DEFAULT_OFFICES = ["euipo"]
EXACT_SCORE_THRESHOLD = 90   # relevance_score >= X  => Kollision
SIMILAR_SCORE_FLOOR   = 60   # darunter: als Rauschen ignorieren
# LLM-Modell für die Namensgenerierung (per Secret überschreibbar).
LLM_MODEL = st.secrets.get("LLM_MODEL", "claude-sonnet-5")
# Leitmotiv: der nächste Evolutionsschritt = Emergenz (auf Wunsch der Gesellschafter).
EVOLUTION_THEME = (
    "Leitmotiv (sinngemäß spürbar, NICHT wörtlich): der nächste Schritt nach der Evolution — "
    "Emergenz. Aus dem Zusammenspiel von Daten und Prozessen entsteht eine neue, höhere Ordnung "
    "und Intelligenz (Emergenz, Sprung, neue Art, das Ganze ist mehr als seine Teile). "
    "Das Motiv darf anklingen, aber verwende NICHT die wörtlichen Begriffe 'Evolution', 'Emergence', "
    "'Emergent', 'Evolve', 'Nexus' o. Ä. im Namen."
)
# Ausgelutschte Tech-Namen-Klischees, die die KI meiden soll (fast alle längst vergeben).
NAME_CLICHES = (
    "Artemis, Apollo, Helios, Atlas, Aurora, Nova, Terra, Luna, Lumina, Luminae, Aura, Solaris, "
    "Nexus, Vertex, Zenith, Apex, Prism, Pulse, Pulsar, Quantum, Synergy, Catalyst, Momentum, "
    "Veridian, Acuity, Cognita, Cognition, Insightia, Qualia, Aether, Sapient, Lucid, Lucida, Clarity, "
    "Vibe, Flow, Core, Cloud, Logic, Sense, Mind, Cerebra, Synapse, Cortex"
)
# Echte Fehlschläge aus früheren Läufen — als Negativ-Anker in den Prompt.
NEGATIVE_EXAMPLES = (
    "Contourly, Foldwise, Groundmesh, Jointframe, Wharfline, Converj, Vantege, Fielderis. "
    "Das sind ECHTE Fehlschläge aus früheren Läufen: Sie wirken wie ein Nischen-Feature oder eine "
    "Dev-Library statt wie das System, das ein ganzes Unternehmen trägt — oder sie sind am Telefon "
    "heikel bzw. sehen nach Tippfehler aus. Erzeuge NICHTS in dieser Machart."
)
# Ziel-Anmutung für den Plattform-Modus (Anmutung treffen, nicht kopieren).
ERP_BENCHMARK = "SAP, Oracle, Odoo, Sage, Xero, Weclapp"
# Bekannte ERP-/Business-Software-Marken: Namen, die diesen zu ähnlich sind, fliegen raus.
COMPETITOR_NAMES = [
    "sap", "sage", "xero", "odoo", "oracle", "weclapp", "datev", "lexware",
    "addison", "abas", "proalpha", "infor", "navision", "sevdesk", "scopevisio",
]
# Produktvision (Gesellschafter-Abstimmung) — fließt in jeden Namens-Brief ein.
PRODUCT_VISION = (
    "Nachfolger des ERP-Systems eEvolution – kein reines Update, sondern ein neues Produkt: "
    "cloudfähig, moderne Architektur, integrierte KI, die Prozesse, Daten und Zusammenhänge "
    "versteht und daraus Empfehlungen ableitet. Der Name soll den Anspruch tragen, dass das "
    "System das Unternehmen versteht und intelligente Entscheidungen unterstützt – und sich klar "
    "von klassischem ERP-Sprech und Microsoft Business Central abgrenzen."
)
ACTIVE_STATUSES = {"active", "registered", "published", "filed", "pending"}
STATUS_LABELS = {
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
# ---------------------------------------------------------------------------
# Marken-Helfer (von beiden Tabs genutzt)
# ---------------------------------------------------------------------------
def _get_relevance(tm: dict):
    rel = tm.get("relevance_score")
    return rel if isinstance(rel, (int, float)) else None
def _get_strategies(tm: dict) -> list[str]:
    me = tm.get("match_explanation") or {}
    strat = me.get("strategies_matched")
    return [s.lower() for s in strat] if isinstance(strat, list) else []
def _is_exact_like(tm: dict) -> bool:
    strat = _get_strategies(tm)
    rel = _get_relevance(tm)
    if strat:
        if "exact" in strat and rel is None:
            return True
        if rel is not None:
            return rel >= EXACT_SCORE_THRESHOLD and "exact" in strat
        return False
    if rel is not None:
        return rel >= EXACT_SCORE_THRESHOLD
    return True
def query_signa(name: str, nice_classes: list[int], offices: list[str], silent: bool = False) -> list[dict] | None:
    """Query Signa API. Returns list of hits, [] if none, None on error.
    silent=True unterdrückt st.error/st.stop (für den Batch-Generator).
    """
    api_key = st.secrets.get("SIGNA_API_KEY", "")
    if not api_key:
        if not silent:
            st.error("API-Key fehlt. Bitte in den App-Settings unter Secrets eintragen: SIGNA_API_KEY = \"sig_...\"")
        return None
    params = {
        "q": name,
        "offices": ",".join(offices) if offices else "euipo",
        "limit": 30,
    }
    if nice_classes:
        params["nice_classes"] = ",".join(str(c) for c in nice_classes)
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        r = requests.get(SIGNA_URL, params=params, headers=headers, timeout=12)
        if r.status_code == 401:
            if not silent:
                st.error("API-Key ungültig. Bitte in den App-Settings unter Secrets prüfen.")
            return None
        if r.status_code != 200:
            return None
        hits = r.json().get("data", [])
        hits.sort(key=lambda h: (_get_relevance(h) or 0), reverse=True)
        return hits
    except Exception:
        return None
def classify_result(hits: list[dict] | None) -> tuple[str, str, str]:
    if hits is None:
        return "Ungeprüft", "unknown", "Marken-API nicht erreichbar"
    active = [h for h in hits if (h.get("status", {}).get("primary", "") or "").lower() in ACTIVE_STATUSES]
    active = [h for h in active if (_get_relevance(h) is None or _get_relevance(h) >= SIMILAR_SCORE_FLOOR)]
    if not active:
        if hits:
            return "Nur inaktive", "warn", f"{len(hits)} abgelaufene/zurückgezogene Einträge"
        return "Frei ✓", "clear", "Kein Treffer im Register"
    exact_like = [h for h in active if _is_exact_like(h)]
    similar    = [h for h in active if not _is_exact_like(h)]
    if exact_like:
        extra = f" + {len(similar)} ähnliche" if similar else ""
        return "Kollision", "hit", f"{len(exact_like)} identische/aktive Marke(n){extra}"
    return "Ähnlich – prüfen", "warn", f"{len(similar)} klanglich/schriftbildlich ähnliche aktive Marke(n)"
def render_hit(tm: dict) -> str:
    status_raw = (tm.get("status", {}).get("primary", "") or "").lower()
    status_label, pill_class = STATUS_LABELS.get(status_raw, (status_raw.capitalize(), "pill-gray"))
    name_val  = tm.get("mark_text", "-")
    owner     = tm.get("owner_name", "-") or "-"
    app_date  = (tm.get("filing_date", "") or "")[:10]
    office    = (tm.get("office", "") or "").upper()
    classes   = ", ".join(str(c.get("nice_class", "")) for c in (tm.get("classifications") or []))
    rel = _get_relevance(tm)
    strat = _get_strategies(tm)
    match_bits = []
    if rel is not None:
        match_bits.append(f"Relevanz {int(rel)}%")
    if strat:
        pretty = {"exact": "identisch", "fuzzy": "ähnlich", "phonetic": "klanglich", "prefix": "Präfix"}
        match_bits.append("/".join(pretty.get(s, s) for s in strat))
    match_pill = f"<span class='status-pill pill-blue'>{' · '.join(match_bits)}</span>" if match_bits else ""
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
# ---------------------------------------------------------------------------
# Generator-Helfer (Tab "Namen finden")
# ---------------------------------------------------------------------------
_UMLAUT = str.maketrans({
    "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
    "Ä": "ae", "Ö": "oe", "Ü": "ue",
})
_DOMAIN_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789")
def slugify(name: str) -> str:
    """Namen -> reiner ASCII-Domain-Slug (Umlaute konvertiert, Akzente entfernt)."""
    s = name.lower().translate(_UMLAUT)
    return "".join(ch for ch in s if ch in _DOMAIN_CHARS)
_VOWELS = set("aeiouy")
_VOWEL_MAP = str.maketrans({"ä": "a", "ö": "o", "ü": "u", "ß": "s"})
def count_syllables(name: str) -> int:
    """Grobe Silbenzählung über Vokalgruppen im Slug."""
    return len(re.findall(r"[aeiouy]+", slugify(name)))
def _lev(a: str, b: str) -> int:
    """Levenshtein-Distanz (klein, ohne Abhängigkeit)."""
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]
def competitor_clash(name: str) -> tuple[str | None, str | None]:
    """Zu nah an bekannter ERP-/Business-Marke? -> (Marke, 'hard'|'soft')."""
    s = slugify(name)
    for comp in COMPETITOR_NAMES:
        d = _lev(s, comp)
        if d <= 1:
            return comp, "hard"
        if d == 2 and len(s) <= 6:
            return comp, "soft"
    return None, None
def phone_test_issues(name: str) -> tuple[list[str], list[str]]:
    """Telefontest für DE-Kunden: eindeutig schreibbar nach einmal Hören?"""
    hard, soft = [], []
    s = slugify(name)
    if s.endswith("j"):
        hard.append("endet auf 'j' (Telefontest: sieht nach Tippfehler aus, z. B. 'Converj')")
    if "ph" in s:
        soft.append("'ph' (Telefontest: f oder ph?)")
    if re.search(r"c(?![hk])", s):
        soft.append("'c' ohne h/k (Telefontest: k oder z?)")
    if "y" in s[1:-1]:
        soft.append("'y' im Wortinneren (Telefontest: i oder y?)")
    if re.search(r"[aeiou]{3}", s):
        soft.append("Vokalhäufung (Telefontest: unklare Schreibweise)")
    return hard, soft
def naming_issues(name: str, open_vowels: bool = True, no_erp: bool = True,
                  mode: str = "descriptive") -> tuple[list[str], list[str]]:
    """Deterministische Namensregeln aus dem Gesellschafter-Feedback.
    Rückgabe: (hard_reasons, soft_tags). hard_reasons != [] => verwerfen.
    mode='abstract' aktiviert zusätzlich die Plattform-Formregeln (1 Wort, kurz, 2 Silben).
    """
    hard, soft = [], []
    low = name.lower().translate(_VOWEL_MAP)
    compact = low.replace(" ", "").replace("-", "")
    slug = slugify(name)
    # Frank: 'ERP' darf nicht Namensbestandteil sein.
    if no_erp and (re.search(r"\berp\b", low) or "ERP" in name):
        hard.append("enthält 'ERP'")
    # Frank: offene Vokale – 'o' als EINZIGER Vokal ist ein hartes K.o.
    vowels_present = {ch for ch in compact if ch in _VOWELS}
    if open_vowels and vowels_present and vowels_present <= {"o"}:
        hard.append("nur 'o' als Vokal (klanglich geschlossen/unfreundlich)")
    # Stephan Müller: 'No-' am Anfang klingt nach Verneinung (nur Hinweis)
    if compact.startswith("no"):
        soft.append("beginnt mit 'No-' (mögliche Verneinungs-Assoziation)")
    # Trend-Suffix '-ai' (wirkt schnell abgestanden)
    if compact.endswith("ai"):
        hard.append("Trend-Suffix '-ai'")
    # Telefontest (beide Modi)
    ph_hard, ph_soft = phone_test_issues(name)
    hard += ph_hard
    soft += ph_soft
    # Abstand zu bekannten ERP-/Business-Marken (beide Modi)
    comp, sev = competitor_clash(name)
    if comp:
        if sev == "hard":
            hard.append(f"zu nah an bestehender Marke '{comp}'")
        else:
            soft.append(f"klanglich nah an '{comp}'")
    # Plattform-Formregeln (nur Modus 'kurz & abstrakt')
    if mode == "abstract":
        syl = count_syllables(name)
        if len(name.split()) > 1:
            hard.append("mehr als ein Wort (Plattform-Modus: genau ein Wort)")
        if len(slug) > 9:
            hard.append(f"{len(slug)} Buchstaben (Plattform-Modus: max. 8-9)")
        elif len(slug) == 9:
            soft.append("9 Buchstaben (Ziel: max. 8)")
        if syl > 3:
            hard.append(f"{syl} Silben (Plattform-Modus: max. 2-3)")
        elif syl == 3:
            soft.append("3 Silben (Ziel: 2)")
    return hard, soft
def _limit_clusters(cands: list[dict], keylen: int = 4) -> tuple[list[dict], list[dict]]:
    """Begrenzt Namen mit gleichem Präfix/Suffix auf je einen (gegen True-/-frame-Häufung)."""
    seen_pre, seen_suf = set(), set()
    kept, dropped = [], []
    for c in cands:
        s = slugify(c["name"])
        if len(s) >= keylen:
            pre, suf = s[:keylen], s[-keylen:]
            if pre in seen_pre or suf in seen_suf:
                c["naming_reasons"] = c.get("naming_reasons", []) + ["Cluster (gleiches Präfix/Suffix)"]
                dropped.append(c)
                continue
            seen_pre.add(pre)
            seen_suf.add(suf)
        kept.append(c)
    return kept, dropped
def check_domain(fqdn: str) -> str:
    """RDAP-Abfrage: 'frei' / 'vergeben' / 'unbekannt' (kein Key nötig)."""
    try:
        r = requests.get(
            f"https://rdap.org/domain/{fqdn}",
            timeout=8,
            headers={"Accept": "application/rdap+json"},
        )
        if r.status_code == 404:
            return "frei"
        if r.status_code == 200:
            return "vergeben"
        return "unbekannt"
    except Exception:
        return "unbekannt"
def check_domains(name: str, tlds=("com", "de", "io")) -> dict:
    s = slugify(name)
    if not s:
        return {}
    return {tld: check_domain(f"{s}.{tld}") for tld in tlds}
# ---------------------------------------------------------------------------
# Prompt-Bau: zwei Register — "kurz & abstrakt" (Plattform) vs. "bildhaft"
# ---------------------------------------------------------------------------
def _prompt_common_header(brief: dict, n: int) -> list[str]:
    lines = [
        f"Erzeuge {n} originelle Namensvorschläge für ein Software-Produkt.",
        f"Produkt / Kategorie: {brief['category']}",
    ]
    if brief.get("attributes"):
        lines.append("Gewünschte Assoziationen / Werte: " + ", ".join(brief["attributes"]))
    if brief.get("seed"):
        lines.append("Inspirations-/Seed-Wörter (dürfen anklingen, müssen nicht wörtlich vorkommen): " + brief["seed"])
    if brief.get("nogo"):
        lines.append("Vermeide diese Wörter/Bedeutungen: " + brief["nogo"])
    lines.append("Produktvision: " + PRODUCT_VISION)
    lines.append(
        "WICHTIG: Übersetze diese Vision NICHT wörtlich in Namen. Genau das führt zu "
        "ausgelutschten Latein-/Griechisch-Wörtern für Wissen, Licht, Geist oder Wahrheit "
        "(Cognita, Lumina, Acuity, Qualia, Insightia …). Solche Namen sind verboten."
    )
    lines.append(EVOLUTION_THEME)
    lines.append("Sprache: " + brief.get("language", "international"))
    return lines
def _prompt_common_footer(brief: dict, n: int) -> list[str]:
    lines = []
    lines.append("NEGATIV-BEISPIELE (hart verboten, auch nichts Ähnliches): " + NEGATIVE_EXAMPLES)
    lines.append(
        "Verboten sind diese Klischees und alles, was ihnen stark ähnelt: " + NAME_CLICHES + ". "
        "Ebenso verboten: griechische/römische Götternamen und generische Endungen wie -ia, -ify, -ly, -ex, -ion, wenn sie beliebig wirken."
    )
    lines.append(
        "SERIOSITÄT (hart): Der Name muss im B2B-/Mittelstandskontext seriös und glaubwürdig sein. "
        "KEIN Fantasy-, Rollenspiel-, Games- oder Sci-Fi-Klang (nicht wie ein Videospiel-Titel wie "
        "'Veylan', 'Kironda', 'Brenmark'). Ein Geschäftsführer muss den Namen im Anzug einem Kunden "
        "nennen können, ohne dass es albern oder nach Gaming wirkt."
    )
    lines.append(
        "TELEFONTEST (hart): Ein deutscher Kunde muss den Namen am Telefon einmal hören und ihn "
        "sofort eindeutig richtig schreiben können. Genau EINE plausible Schreibweise — keine "
        "Buchstaben, die man erklären muss (kein 'Converj', kein 'Vantege')."
    )
    rules = [
        "gut aussprechbar (deutsch UND englisch), international tragfähig",
        "keine offensichtlich bestehenden bekannten Marken",
        "keine rein generischen Begriffe (nicht bloß 'Cloud', 'Soft', 'System')",
        "möglichst keine Umlaute/Sonderzeichen im Kernnamen",
    ]
    if brief.get("no_erp", True):
        rules.append("die Abkürzung 'ERP' darf NICHT im Namen vorkommen")
    if brief.get("open_vowels", True):
        rules.append(
            "bevorzuge offen klingende Namen; vermeide Namen, deren EINZIGER Vokal 'o' ist "
            "(im Deutschen klingt reines 'o' geschlossen/unfreundlich) – nutze offene Vokale wie a, e, i"
        )
    rules.append("kein Name darf auf '-ai' enden")
    lines.append("Regeln: " + "; ".join(rules) + ".")
    crea = brief.get("creativity", 0.9)
    if crea >= 0.9:
        lines.append("Kreativitätsgrad: SEHR MUTIG. Lieber überraschend und ungewöhnlich als brav — aber immer innerhalb der Form- und Seriositätsregeln.")
    elif crea >= 0.75:
        lines.append("Kreativitätsgrad: kreativ, aber ausgewogen und solide.")
    else:
        lines.append("Kreativitätsgrad: eher konservativ, klar und sofort zugänglich.")
    lines.append(
        f"Gib genau {n} Vorschläge über das Werkzeug 'namen_abgeben' zurück "
        "(je Eintrag: name, family, rationale)."
    )
    return lines
def build_prompt_abstract(brief: dict, n: int, angle: str = "") -> str:
    """Register 'kurz & abstrakt': Plattform-Namen im SAP/Odoo/Xero-Stil."""
    lines = _prompt_common_header(brief, n)
    lines.append(
        f"ZIEL-ANMUTUNG (wichtigste Vorgabe): Der Name trägt ein komplettes Unternehmenssystem — "
        f"die Anmutung von {ERP_BENCHMARK}: kurz, abstrakt, selbstbewusst. Eine PLATTFORM, kein Feature. "
        "Echte ERP-Flaggschiffe erklären nichts — sie behaupten. KEINE bildhaft-beschreibenden "
        "Zusammensetzungen (nicht Mesh/Frame/Weave/Gear/Strata/Contour und nichts dieser Machart)."
    )
    lines.append(
        "FORM (hart): genau EIN Wort, maximal 8 Buchstaben, ideal 2 Silben (max. 3). "
        "Klare Konsonant-Vokal-Struktur, offene Vokale (a, e, i), ruhiger, souveräner Klang."
    )
    lines.append(
        "GRAVITAS (hart): 'Groß genug für 10-15 Jahre.' Test: Ein Geschäftsführer nennt den Namen "
        "im selben Satz wie SAP und Oracle, ohne dass er klein oder verspielt wirkt. Wenn der Name "
        "wie ein Tool, ein Plugin oder eine Dev-Library klingt, verwirf ihn selbst."
    )
    lines.append(
        "KONSTRUKTION: Bedeutung darf nur noch als Echo mitschwingen — geclippte oder verschmolzene "
        "Wortwurzeln (Latein/Deutsch/Englisch/Romanisch), verdichtet bis zur Eigenständigkeit; oder ein "
        "freies, rundes Kunstwort ohne direkte Bedeutung; oder ein reales kurzes Wort, minimal (1 Buchstabe) "
        "verfremdet. Der Name muss als Marke besitzbar sein, nicht als Wörterbucheintrag lesbar."
    )
    if angle:
        lines.append("FOKUS DIESES DURCHGANGS: " + angle)
    lines += _prompt_common_footer(brief, n)
    return "\n".join(lines)
def build_prompt_descriptive(brief: dict, n: int) -> str:
    """Register 'bildhaft-beschreibend': ursprünglicher Trueforge/deepMerge-Stil."""
    lines = _prompt_common_header(brief, n)
    if brief.get("styles"):
        lines.append("Bevorzugter Stil: " + ", ".join(brief["styles"]))
    if brief.get("liked"):
        lines.append(
            "Der Kunde mag den Stil von: " + brief["liked"] + ". "
            "Triff diese Anmutung — konkret, bildhaft, besitzbar, meist aus echten Wörtern "
            "zusammengesetzt (z. B. 'Trueforge' = wahr+schmieden, 'deepMerge' = tief+zusammenführen) — "
            "ohne die Vorbilder zu kopieren."
        )
    lines.append(
        "Erzeuge bewusst VIELFALT über diese Konstruktionsprinzipien und verteile die Vorschläge "
        "darüber (nicht alle nach einem Schema):"
    )
    lines.append("1) Konkrete Zusammensetzungen zweier echter Wörter, bildhaft & besitzbar (im Geist von 'Trueforge', aber BREITER: Struktur, Fundament, Übersicht, Verbindung, Steuerung, Zusammenhang — nicht nur Schmiede/Handwerk).")
    lines.append("2) Leicht abgewandelte echte Wörter (ein Buchstabe/eine Silbe verschoben), sodass sie eigenständig und markenfähig werden.")
    lines.append("3) Metaphern aus unerwarteten, aber SERIÖSEN Domänen — Architektur, Geologie/Schichten, Kartografie/Navigation, Mechanik/Getriebe, Statik — NICHT die üblichen Licht-/Gehirn-/Sternen-Bilder.")
    lines.append("4) Ruhige, klare Neuschöpfungen aus einer echten Wortwurzel (Latein/Deutsch/Englisch), professionell und leicht lesbar.")
    lines.append("5) Kurze, klare Kunstwörter mit ruhigem, seriösem Klang — NICHT rau/kantig, NICHT wie erfundene Fantasy-Namen.")
    lines.append("6) Tech-literate Zusammenführungs-Begriffe (im Geist von 'deepMerge'): das Verschmelzen/Verweben vieler Teile zu einem verstehenden Ganzen (merge, weave, mesh, converge, join) — seriös, nicht verspielt.")
    lines.append(
        "Gewichte das Emergenz-/Zusammenführungs-Motiv (aus vielen Teilen entsteht ein verstehendes Ganzes) "
        "STÄRKER als reine Stabilitäts-/Fundament-Bilder. Höchstens ein Drittel darf primär "
        "'solide/verlässlich/Fundament' transportieren."
    )
    lines.append(
        "Keine gehäuften gleichen Präfixe ODER Suffixe (nicht mehrfach True-, Deep-, -forge, -frame, -wise, "
        "-line, -merge); höchstens EIN Name mit 'True'."
    )
    lines.append("1–2 Wörter sind erlaubt.")
    lines += _prompt_common_footer(brief, n)
    return "\n".join(lines)
# Unterschiedliche Blickwinkel pro Batch — gegen die Konvergenz innerhalb EINES Calls.
ABSTRACT_ANGLES = [
    "Verdichtete Wortwurzel: Nimm eine passende Wurzel (Latein/Deutsch/Englisch/Romanisch für "
    "Ordnung, Verstehen, Zusammenspiel, Ganzheit) und clippe/verschmelze sie so stark, dass nur "
    "ein Klang-Echo der Bedeutung bleibt.",
    "Freies Kunstwort: Baue aus offenen Vokalen (a, e, i) und weichen, klaren Konsonanten ein "
    "rundes, souveränes Zwei-Silben-Wort OHNE direkte Bedeutung — reiner Klang mit Gravitas.",
    "Minimal verfremdetes reales Wort: Nimm ein kurzes, kraftvolles echtes Wort und verändere "
    "genau einen Buchstaben, sodass es markenfähig wird und trotzdem eindeutig schreibbar bleibt.",
]
def parse_candidates(text: str) -> list[dict]:
    if not text:
        return []
    a, b = text.find("["), text.rfind("]")
    snippet = text[a:b + 1] if (a != -1 and b != -1 and b > a) else text
    data = None
    for attempt in (snippet, re.sub(r",\s*([\]}])", r"\1", snippet)):  # 2. Versuch: Trailing-Commas entfernen
        try:
            data = json.loads(attempt)
            break
        except Exception:
            continue
    if data is None:
        # Fallback: einzelne Objekte per Regex herausziehen
        data = []
        for m in re.finditer(r"\{[^{}]*\}", snippet):
            try:
                data.append(json.loads(m.group(0)))
            except Exception:
                pass
    if not isinstance(data, list):
        return []
    return _normalize_items(data)
def _normalize_items(data: list) -> list[dict]:
    out, seen = [], set()
    for it in data:
        if not isinstance(it, dict):
            continue
        nm = str(it.get("name", "")).strip()
        if not nm or nm.lower() in seen:
            continue
        seen.add(nm.lower())
        out.append({
            "name": nm,
            "family": str(it.get("family", "")).strip(),
            "rationale": str(it.get("rationale", "")).strip(),
        })
    return out
def _get_anthropic_client():
    api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        st.error("ANTHROPIC_API_KEY fehlt. Bitte in den Streamlit-Secrets eintragen.")
        return None
    try:
        import anthropic
    except ImportError:
        st.error("Paket 'anthropic' nicht installiert. In requirements.txt aufnehmen und neu deployen.")
        return None
    return anthropic.Anthropic(api_key=api_key)
def generate_names(brief: dict, n: int, angle: str = "") -> list[dict] | None:
    client = _get_anthropic_client()
    if client is None:
        return None
    system = (
        "Du bist ein preisgekrönter Namensentwickler für Marken und B2B-Software. "
        "Du hasst generische, austauschbare KI-Namen und lieferst eigenständige, besitzbare, "
        "überraschende Produktnamen. Nutze das Werkzeug 'namen_abgeben', um sie strukturiert zurückzugeben."
    )
    tools = [{
        "name": "namen_abgeben",
        "description": "Gib die generierten Namensvorschläge strukturiert zurück.",
        "input_schema": {
            "type": "object",
            "properties": {
                "namen": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Der Produktname"},
                            "family": {"type": "string", "description": "Konstruktionsprinzip/Familie"},
                            "rationale": {"type": "string", "description": "1 kurzer Satz, warum er passt"},
                        },
                        "required": ["name"],
                    },
                }
            },
            "required": ["namen"],
        },
    }]
    if brief.get("mode") == "abstract":
        prompt = build_prompt_abstract(brief, n, angle)
    else:
        prompt = build_prompt_descriptive(brief, n)
    try:
        msg = client.messages.create(
            model=LLM_MODEL,
            max_tokens=3000,
            system=system,
            tools=tools,
            tool_choice={"type": "tool", "name": "namen_abgeben"},
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        st.error(f"LLM-Aufruf fehlgeschlagen: {e}")
        return None
    # Bevorzugt: strukturierte Tool-Ausgabe
    items = None
    for block in msg.content:
        if getattr(block, "type", "") == "tool_use" and getattr(block, "name", "") == "namen_abgeben":
            inp = getattr(block, "input", None) or {}
            items = inp.get("namen")
            break
    if isinstance(items, list):
        cands = _normalize_items(items)
    else:
        # Fallback: eventuellen Freitext parsen
        text = "".join(getattr(b, "text", "") for b in msg.content if getattr(b, "type", "") == "text")
        cands = parse_candidates(text)
        if not cands:
            with st.expander("Debug: Rohantwort der KI"):
                st.code((text or str(msg.content))[:2500])
    return cands
def generate_names_diverse(brief: dict, n: int) -> list[dict] | None:
    """Mehrere kleinere Batches mit unterschiedlichem Fokus statt EINEM großen Call.
    Innerhalb eines einzelnen Calls konvergiert das Modell auf ein Schema — getrennte
    Batches liefern messbar mehr Vielfalt.
    """
    if brief.get("mode") != "abstract":
        return generate_names(brief, n)
    per = max(4, round(n / len(ABSTRACT_ANGLES)))
    all_c, seen = [], set()
    for i, angle in enumerate(ABSTRACT_ANGLES):
        cands = generate_names(brief, per, angle=angle)
        if cands is None and i == 0:
            return None  # harter Fehler (Key/Paket) direkt beim ersten Call
        for c in (cands or []):
            key = slugify(c["name"])
            if key and key not in seen:
                seen.add(key)
                all_c.append(c)
    return all_c
# ---------------------------------------------------------------------------
# Juror-Stufe: Gravitas-Vorauswahl per zweitem LLM-Call
# ---------------------------------------------------------------------------
JUROR_GRAVITAS_MIN = 7
JUROR_PHONE_MIN = 7
def judge_names(cands: list[dict], brief: dict) -> tuple[list[dict], list[dict], str | None]:
    """Bewertet Kandidaten auf Flaggschiff-Gravitas + Telefontauglichkeit.
    Rückgabe: (kept, dropped, warn_msg). Bei API-Fehler: alle behalten (fail open).
    """
    client = _get_anthropic_client()
    if client is None or not cands:
        return cands, [], "Juror übersprungen (kein API-Zugang)" if cands else None
    names_list = "\n".join(f"- {c['name']}" for c in cands)
    system = (
        "Du bist ein extrem kritischer Markenstratege für B2B-Unternehmenssoftware im deutschen "
        "Mittelstand. Du bewertest Produktnamen hart und ehrlich — Schmeichelei ist nutzlos."
    )
    prompt = (
        f"Produkt: {brief['category']}\n\n"
        "Bewerte jeden der folgenden Namensvorschläge auf zwei Skalen von 1-10:\n\n"
        f"1) gravitas: Trägt der Name ein KOMPLETTES Unternehmenssystem über 10-15 Jahre — auf "
        f"Augenhöhe mit {ERP_BENCHMARK}? 10 = klingt wie ein Flaggschiff/eine Plattform. "
        "1 = klingt wie ein Nischen-Tool, Feature, Plugin oder eine Dev-Library.\n"
        "2) telefon: Kann ein deutscher Kunde den Namen am Telefon einmal hören und sofort eindeutig "
        "richtig schreiben? 10 = genau eine plausible Schreibweise. 1 = mehrdeutig oder sieht nach "
        "Tippfehler aus.\n\n"
        f"Kalibrierung: Namen wie 'Contourly', 'Foldwise', 'Groundmesh' wären gravitas 2-3; "
        f"'Converj', 'Vantege' wären telefon 2-3.\n\n"
        f"Namen:\n{names_list}\n\n"
        "Gib die Bewertungen über das Werkzeug 'namen_bewerten' zurück."
    )
    tools = [{
        "name": "namen_bewerten",
        "description": "Gib die Bewertungen strukturiert zurück.",
        "input_schema": {
            "type": "object",
            "properties": {
                "bewertungen": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "gravitas": {"type": "integer", "description": "1-10"},
                            "telefon": {"type": "integer", "description": "1-10"},
                            "kommentar": {"type": "string", "description": "max. 1 kurzer Satz"},
                        },
                        "required": ["name", "gravitas", "telefon"],
                    },
                }
            },
            "required": ["bewertungen"],
        },
    }]
    try:
        msg = client.messages.create(
            model=LLM_MODEL,
            max_tokens=2500,
            system=system,
            tools=tools,
            tool_choice={"type": "tool", "name": "namen_bewerten"},
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        return cands, [], f"Juror-Aufruf fehlgeschlagen ({e}) — alle Kandidaten behalten"
    ratings = {}
    for block in msg.content:
        if getattr(block, "type", "") == "tool_use" and getattr(block, "name", "") == "namen_bewerten":
            for b in (getattr(block, "input", None) or {}).get("bewertungen", []) or []:
                if isinstance(b, dict) and b.get("name"):
                    ratings[str(b["name"]).strip().lower()] = b
            break
    if not ratings:
        return cands, [], "Juror lieferte keine verwertbare Bewertung — alle Kandidaten behalten"
    kept, dropped = [], []
    for c in cands:
        r = ratings.get(c["name"].strip().lower())
        if r is None:
            kept.append(c)  # unbewertet -> behalten
            continue
        try:
            grav = int(r.get("gravitas", 0))
            tel = int(r.get("telefon", 0))
        except (TypeError, ValueError):
            kept.append(c)
            continue
        c["juror"] = {"gravitas": grav, "telefon": tel, "kommentar": str(r.get("kommentar", "")).strip()}
        if grav >= JUROR_GRAVITAS_MIN and tel >= JUROR_PHONE_MIN:
            kept.append(c)
        else:
            dropped.append(c)
    return kept, dropped, None
def domains_html(domains: dict) -> str:
    if not domains:
        return ""
    cls = {"frei": "dom-free", "vergeben": "dom-taken", "unbekannt": "dom-unk"}
    parts = []
    for tld, state in domains.items():
        parts.append(f"<span class='dom {cls.get(state, 'dom-unk')}'>.{tld}: {state}</span>")
    return " ".join(parts)
# --- Tiefenprüfung: geführte Links zu autoritativen Registern -------------
# DE=DPMA (national), EM=EU-Unionsmarke, WO=Madrid/international
def tmview_url(name: str, offices: str = "DE,EM,WO") -> str:
    return ("https://www.tmdn.org/tmview/#/tmview/results?page=1&pageSize=30&criteria=C"
            f"&offices={offices}&basicSearch={quote(name)}&tmStatus=Filed,Registered")
DPMAREGISTER_URL = "https://register.dpma.de/DPMAregister/marke/einsteiger"
# Handelsregister: Deep-Links auf Suchseiten (z. B. erweitertesuche.xhtml) liefern 404,
# weil das Portal sessiongebunden ist — nur die Startseite ist stabil verlinkbar.
HANDELSREGISTER_URL = "https://www.handelsregister.de/"
def northdata_url(name: str) -> str:
    """North Data: frei verlinkbare Firmennamen-Schnellsuche (HRB-Daten)."""
    return "https://www.northdata.de/" + quote(name)
def google_exact_url(name: str) -> str:
    return "https://www.google.com/search?q=" + quote(f'"{name}" software')
# ===========================================================================
# UI
# ===========================================================================
st.markdown("""
<div class="hero">
  <div class="badge">EUIPO · Namensfindung & Markencheck</div>
  <h1>🔍 Markenprüfung EU</h1>
  <p>Namen finden lassen — inkl. automatischem Marken-Knockout — oder eigene Namen gegen das EU-Register prüfen.</p>
</div>
""", unsafe_allow_html=True)
tab_find, tab_check, tab_deep = st.tabs(["✨ Namen finden", "🔍 Namen prüfen", "🎯 Tiefenprüfung"])
# ---------------------------------------------------------------------------
# TAB: Namen finden
# ---------------------------------------------------------------------------
with tab_find:
    st.markdown("#### Brief")
    st.caption("Beschreibe die Richtung — die KI generiert Namen, sortiert Marken-Kollisionen automatisch aus und prüft Domains.")
    naming_mode_label = st.radio(
        "Namens-Register",
        [
            "Kurz & abstrakt – Plattform-Stil (SAP / Odoo / Xero)",
            "Bildhaft-beschreibend (Trueforge / deepMerge)",
        ],
        index=0,
        key="gen_mode",
        help="Plattform-Stil: 1 Wort, max. 8 Buchstaben, 2 Silben, abstrakt — die Anmutung echter ERP-Flaggschiffe. "
             "Bildhaft: der bisherige Kompositum-Stil.",
    )
    naming_mode = "abstract" if naming_mode_label.startswith("Kurz") else "descriptive"
    category = st.text_input(
        "Produkt / Kategorie",
        value="Cloudfähiges, KI-gestütztes Unternehmenssystem (ERP-Nachfolger), das das Unternehmen versteht",
        key="gen_category",
    )
    ATTR_PRESETS = [
        "versteht das Unternehmen", "Erkenntnis/Einsicht", "Intelligenz", "Echtzeit",
        "Zukunft", "Sicherheit", "coole/moderne Technik", "inhabergeführt",
        "solide/verlässlich", "erstklassiger Service", "Klarheit", "Vertrauen",
        "Abgrenzung von klassischem ERP",
    ]
    attributes = st.multiselect(
        "Werte / Assoziationen",
        options=ATTR_PRESETS,
        default=["versteht das Unternehmen", "Erkenntnis/Einsicht", "Zukunft", "coole/moderne Technik", "solide/verlässlich"],
        key="gen_attrs",
    )
    attr_extra = st.text_input("Weitere Assoziationen (optional, kommagetrennt)", value="", key="gen_attr_extra")
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        seed = st.text_input("Seed-/Inspirationswörter (optional)", value="", placeholder="z. B. evolution, hive", key="gen_seed")
    with col_s2:
        nogo = st.text_input("No-Go-Wörter (optional)", value="", placeholder="z. B. strawberry", key="gen_nogo")
    col_s3, col_s4 = st.columns(2)
    with col_s3:
        language = st.selectbox("Sprache", ["international (EN)", "Deutsch", "Latein/erfunden"], index=0, key="gen_lang")
    with col_s4:
        styles = st.multiselect(
            "Stil (nur bildhafter Modus)",
            ["Kunstwort", "echtes Wort", "Zusammensetzung", "kurz & prägnant"],
            default=["Kunstwort", "kurz & prägnant"],
            key="gen_styles",
        )
    liked = st.text_input(
        "Vorbild – Namen, deren Stil dir gefällt (nur bildhafter Modus)",
        value="Trueforge, deepMerge",
        help="Nur im bildhaften Modus aktiv. Im Plattform-Modus ist die Benchmark fest: SAP, Oracle, Odoo, Sage, Xero, Weclapp.",
        key="gen_liked",
    )
    creativity = st.slider(
        "Kreativität", min_value=0.6, max_value=1.0, value=0.95, step=0.05, key="gen_creativity",
        help="Höher = mutigere, ungewöhnlichere Namen. Modell via Secret LLM_MODEL (Standard: claude-sonnet-5).",
    )
    st.markdown("**Namensregeln (Gesellschafter-Feedback)**")
    colr1, colr2 = st.columns(2)
    with colr1:
        open_vowels = st.checkbox('Offene Vokale – kein „o“ als einziger Vokal (Frank)', value=True, key="gen_open")
        no_erp = st.checkbox('„ERP“ nicht im Namen (Frank)', value=True, key="gen_noerp")
        use_juror = st.checkbox(
            "KI-Juror: Gravitas-Vorauswahl", value=True, key="gen_juror",
            help="Zweiter LLM-Call bewertet jeden Namen auf Flaggschiff-Gravitas (≥7/10) und "
                 "Telefontauglichkeit (≥7/10), BEVOR Signa-Kontingent verbraucht wird.",
        )
    with colr2:
        show_house = st.checkbox("Marktform mit Hausmarke zeigen (Stefan/Peter)", value=True, key="gen_house")
        house_mark = st.text_input("Hausmarke", value="eEvolution", key="gen_housemark")
    pool = st.slider("Wie viele Ideen generieren?", min_value=8, max_value=60, value=30, key="gen_pool",
                     help="Breit erzeugen, hart filtern: Der Juror sortiert VOR dem Marken-Check aus — "
                          "nur Juror-Überlebende kosten Signa-Abfragen.")
    gen_btn = st.button("✨ Namen generieren & prüfen", key="gen_run")
    if gen_btn:
        brief = {
            "mode": naming_mode,
            "category": category.strip() or "Software",
            "attributes": attributes + ([a.strip() for a in attr_extra.split(",") if a.strip()] if attr_extra else []),
            "seed": seed.strip(),
            "nogo": nogo.strip(),
            "language": language,
            "styles": styles,
            "liked": liked.strip(),
            "creativity": creativity,
            "open_vowels": open_vowels,
            "no_erp": no_erp,
        }
        with st.spinner("Generiere Namen mit der KI…" + (" (3 Batches mit unterschiedlichem Fokus)" if naming_mode == "abstract" else "")):
            cands = generate_names_diverse(brief, pool)
        if cands is None:
            st.stop()
        if not cands:
            st.warning("Keine verwertbaren Vorschläge erhalten. Bitte Brief anpassen und erneut versuchen.")
            st.stop()
        n_generated = len(cands)
        # 0) Namensregeln (deterministische Guardrails) VOR Juror und Marken-Check
        kept, dropped_naming = [], []
        for c in cands:
            hard, soft = naming_issues(c["name"], open_vowels=brief["open_vowels"],
                                       no_erp=brief["no_erp"], mode=naming_mode)
            c["tags"] = soft
            if hard:
                c["naming_reasons"] = hard
                dropped_naming.append(c)
            else:
                kept.append(c)
        cands = kept
        # Cluster-Sperre: gleiche Präfixe/Suffixe (True-, -frame …) auf je einen begrenzen
        cands, cluster_dropped = _limit_clusters(cands)
        dropped_naming += cluster_dropped
        if not cands:
            st.warning("Alle Vorschläge wurden von den Namensregeln aussortiert. Bitte Regeln lockern oder erneut generieren.")
            st.stop()
        # 0b) Juror-Stufe (spart Signa-Kontingent: nur Überlebende werden geprüft)
        dropped_juror = []
        if use_juror:
            with st.spinner("KI-Juror bewertet Gravitas & Telefontauglichkeit…"):
                cands, dropped_juror, juror_warn = judge_names(cands, brief)
            if juror_warn:
                st.warning(juror_warn)
            if not cands:
                st.warning("Der Juror hat alle Kandidaten aussortiert. Pool erhöhen oder erneut generieren.")
                st.stop()
        # 1) Marken-Knockout
        prog = st.progress(0, text="Marken-Knockout…")
        for i, c in enumerate(cands):
            prog.progress((i + 1) / len(cands), text=f"Marken-Check: {c['name']}")
            hits = query_signa(c["name"], [9, 42], ["euipo"], silent=True)
            label, css, summary = classify_result(hits)
            c["tm_label"], c["tm_css"], c["tm_summary"] = label, css, summary
            c["hits"] = hits or []
            time.sleep(0.12)
        prog.empty()
        # Überlebende = frei (clear) oder ähnlich (warn) oder ungeprüft (unknown); Kollision (hit) raus
        survivors = [c for c in cands if c["tm_css"] in ("clear", "warn", "unknown")]
        dropped = [c for c in cands if c["tm_css"] == "hit"]
        # 2) Domain-Check nur für Überlebende
        if survivors:
            prog2 = st.progress(0, text="Domain-Check…")
            for i, c in enumerate(survivors):
                prog2.progress((i + 1) / len(survivors), text=f"Domain: {c['name']}")
                c["domains"] = check_domains(c["name"])
            prog2.empty()
        # Ranking: frei vor ähnlich vor ungeprüft; dann Juror-Gravitas; dann freie Domains
        order = {"clear": 0, "warn": 1, "unknown": 2}
        survivors.sort(key=lambda c: (
            order.get(c["tm_css"], 3),
            -(c.get("juror", {}).get("gravitas", 0)),
            -sum(1 for v in c.get("domains", {}).values() if v == "frei"),
        ))
        st.markdown(f"""
        <div class="summary-box">
          <div><span style="font-size:1.5rem;font-weight:700;color:#2D3561;">{n_generated}</span><br>
               <span style="font-size:0.8rem;color:#718096;">generiert</span></div>
          <div><span style="font-size:1.5rem;font-weight:700;color:#38A169;">{len(survivors)}</span><br>
               <span style="font-size:0.8rem;color:#718096;">überlebt</span></div>
          <div><span style="font-size:1.5rem;font-weight:700;color:#E53E3E;">{len(dropped)}</span><br>
               <span style="font-size:0.8rem;color:#718096;">Marken-K.o.</span></div>
          <div><span style="font-size:1.5rem;font-weight:700;color:#975A16;">{len(dropped_naming)}</span><br>
               <span style="font-size:0.8rem;color:#718096;">Regel-K.o.</span></div>
          <div><span style="font-size:1.5rem;font-weight:700;color:#2B6CB0;">{len(dropped_juror)}</span><br>
               <span style="font-size:0.8rem;color:#718096;">Juror-K.o.</span></div>
          <div style="margin-left:auto;font-size:0.78rem;color:#A0AEC0;align-self:center;">
            EUIPO · Nizza 9, 42<br>{'Plattform-Modus' if naming_mode == 'abstract' else 'Bildhafter Modus'}
          </div>
        </div>
        """, unsafe_allow_html=True)
        if dropped_naming:
            with st.expander(f"{len(dropped_naming)} per Namensregel aussortiert"):
                for c in dropped_naming:
                    st.markdown("- **" + c["name"] + "** — " + ", ".join(c.get("naming_reasons", [])))
        if dropped_juror:
            with st.expander(f"{len(dropped_juror)} vom KI-Juror aussortiert (Gravitas/Telefon < {JUROR_GRAVITAS_MIN})"):
                for c in dropped_juror:
                    j = c.get("juror", {})
                    st.markdown(
                        f"- **{c['name']}** — Gravitas {j.get('gravitas', '?')}/10, "
                        f"Telefon {j.get('telefon', '?')}/10"
                        + (f" — {j['kommentar']}" if j.get("kommentar") else "")
                    )
        if dropped:
            with st.expander(f"{len(dropped)} wegen Marken-Kollision verworfen"):
                for c in dropped:
                    st.markdown("- **" + c["name"] + "** — " + c["tm_summary"])
        if not survivors:
            st.info("Keine sauberen Kandidaten übrig. Bitte Brief/Regeln anpassen und erneut generieren.")
        else:
            for c in survivors:
                tm_pill_class = {"clear": "pill-green", "warn": "pill-yellow", "unknown": "pill-gray"}.get(c["tm_css"], "pill-gray")
                juror_pill = ""
                j = c.get("juror")
                if j:
                    juror_pill = (f"<span class='status-pill pill-blue' style='vertical-align:middle;'>"
                                  f"Gravitas {j['gravitas']}/10 · Telefon {j['telefon']}/10</span>")
                marktform = ""
                if show_house and house_mark.strip():
                    marktform = f"<div class='meta'>Marktform: <strong>{house_mark.strip()} {c['name']}</strong></div>"
                tagline = ""
                if c.get("tags"):
                    tagline = "<div class='meta' style='color:#975A16;'>⚠ " + "; ".join(c["tags"]) + "</div>"
                st.markdown(f"""
                <div class="name-card">
                  <h3>{c['name']}
                    <span class="status-pill {tm_pill_class}" style="vertical-align:middle;">{c['tm_label']}</span>
                    {juror_pill}
                  </h3>
                  <div class="meta">{('· ' + c['family'] + ' ') if c['family'] else ''}{c['rationale']}</div>
                  {marktform}{tagline}
                  <div style="margin-top:0.5rem;">{domains_html(c.get('domains', {}))}</div>
                </div>
                """, unsafe_allow_html=True)
                if c["hits"]:
                    with st.expander("Marken-Treffer zu " + c["name"] + " (" + c["tm_summary"] + ")"):
                        for tm in c["hits"][:6]:
                            st.markdown(render_hit(tm), unsafe_allow_html=True)
            # Export
            st.markdown("---")
            rows = []
            for c in survivors:
                doms = c.get("domains", {})
                j = c.get("juror", {})
                marktform_txt = f"{house_mark.strip()} {c['name']}" if (show_house and house_mark.strip()) else ""
                rows.append({
                    "Name": c["name"],
                    "Marktform": marktform_txt,
                    "Familie": c["family"],
                    "Begründung": c["rationale"],
                    "Juror Gravitas": j.get("gravitas", ""),
                    "Juror Telefon": j.get("telefon", ""),
                    "Juror Kommentar": j.get("kommentar", ""),
                    "Marken-Bewertung": c["tm_label"],
                    "Marken-Detail": c["tm_summary"],
                    "Hinweis": "; ".join(c.get("tags", [])),
                    ".com": doms.get("com", ""),
                    ".de": doms.get("de", ""),
                    ".io": doms.get("io", ""),
                })
            df_gen = pd.DataFrame(rows)
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                df_gen.to_excel(writer, index=False, sheet_name="Namensvorschlaege")
            st.download_button(
                "⬇ Vorschläge als Excel",
                data=buf.getvalue(),
                file_name="namensvorschlaege.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="gen_dl",
            )
    st.markdown("""
    <div class="disclaimer">
      Vor-Filter = Namensregeln + KI-Juror + EU-Markt-Knockout (EUIPO, Klasse 9/42) + Domain-Verfügbarkeit.
      <strong>Keine DPMA, keine Firmennamen</strong> — das ist die Tiefenprüfung (Stufe 2) bzw. die Kanzlei.
      „Überlebt" heißt: kein K.o., nicht „garantiert frei".
    </div>
    """, unsafe_allow_html=True)
# ---------------------------------------------------------------------------
# TAB: Namen prüfen (ursprünglicher Checker)
# ---------------------------------------------------------------------------
with tab_check:
    st.markdown("#### Namen eingeben")
    st.caption("Einen Namen pro Zeile — bis zu 20 Namen auf einmal.")
    raw_input = st.text_area(
        "Namen",
        placeholder="Vorano\nVereno\nOperanto\nComodi",
        height=160,
        label_visibility="collapsed",
        key="chk_input",
    )
    nice_filter = st.multiselect(
        "Nizza-Klassen filtern (optional — leer = alle)",
        options=list(range(1, 46)),
        default=[9, 42],
        help="Klasse 9 = Software, Klasse 42 = IT-Dienstleistungen.",
        key="chk_nice",
    )
    office_labels = st.multiselect(
        "Register / Ämter",
        options=list(OFFICE_CHOICES.keys()),
        default=[k for k, v in OFFICE_CHOICES.items() if v in DEFAULT_OFFICES],
        help="Nationale DE-Marken (DPMA) sind bei dieser Datenquelle NICHT enthalten.",
        key="chk_offices",
    )
    offices = [OFFICE_CHOICES[l] for l in office_labels] or DEFAULT_OFFICES
    col1, col2 = st.columns([2, 1])
    with col1:
        run = st.button("Prüfen →", use_container_width=True, key="chk_run")
    with col2:
        st.caption("Kostenlos, kein Login")
    if run:
        raw_names = [n.strip() for n in raw_input.splitlines() if n.strip()]
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
            if hits is None and not st.secrets.get("SIGNA_API_KEY", ""):
                st.stop()
            label, css_class, summary = classify_result(hits)
            results.append({
                "name": name, "label": label, "css_class": css_class,
                "summary": summary, "hits": hits or [],
            })
            time.sleep(0.2)
        progress.empty()
        n_hit   = sum(1 for r in results if r["css_class"] == "hit")
        n_warn  = sum(1 for r in results if r["css_class"] in ("warn", "unknown"))
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
        for r in results:
            icon = "🔴" if r["css_class"] == "hit" else "🟢" if r["css_class"] == "clear" else "🟡"
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
        st.markdown("---")
        export_rows = []
        for r in results:
            if r["hits"]:
                for tm in r["hits"]:
                    classes = ", ".join(str(c.get("nice_class", "")) for c in (tm.get("classifications") or []))
                    rel = _get_relevance(tm)
                    export_rows.append({
                        "Geprüfter Name": r["name"], "Bewertung": r["label"],
                        "Treffer-Marke": tm.get("mark_text", ""),
                        "Status": (tm.get("status", {}).get("primary", "") or ""),
                        "Match": "/".join(_get_strategies(tm)) or "",
                        "Relevanz": int(rel) if rel is not None else "",
                        "Amt": (tm.get("office", "") or "").upper(),
                        "Inhaber": tm.get("owner_name", ""),
                        "Anmeldedatum": (tm.get("filing_date", "") or "")[:10],
                        "Nizza-Klassen": classes, "Signa-ID": tm.get("id", ""),
                    })
            else:
                export_rows.append({
                    "Geprüfter Name": r["name"], "Bewertung": r["label"],
                    "Treffer-Marke": "", "Status": "", "Match": "", "Relevanz": "",
                    "Amt": "", "Inhaber": "", "Anmeldedatum": "", "Nizza-Klassen": "", "Signa-ID": "",
                })
        df = pd.DataFrame(export_rows)
        buf2 = io.BytesIO()
        with pd.ExcelWriter(buf2, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Markenpruefung")
        st.download_button(
            "⬇ Ergebnisse als Excel",
            data=buf2.getvalue(),
            file_name="markenpruefung_euipo.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="chk_dl",
        )
    st.markdown("""
    <div class="disclaimer">
      Datenquelle: EUIPO Unionsmarkenregister (+ optional WIPO/Madrid) via Signa API.<br>
      <strong>Nationale DE-Marken (DPMA) sind nicht enthalten.</strong>
      Dieser Schnellcheck ersetzt <strong>keine</strong> rechtliche Markenrecherche.
    </div>
    """, unsafe_allow_html=True)
# ---------------------------------------------------------------------------
# TAB: Tiefenprüfung (Finalisten-Cockpit)
# ---------------------------------------------------------------------------
with tab_deep:
    st.markdown("#### Finalisten-Tiefenprüfung")
    st.caption(
        "Für die 1–5 Favoriten: automatischer EU-Marken- und Domain-Check plus "
        "geführte Ein-Klick-Links zu DPMA, TMview, Handelsregister und North Data."
    )
    deep_raw = st.text_area(
        "Finalisten (ein Name pro Zeile, max. 5)",
        height=120,
        placeholder="z. B.\nVorano\nVereno\nOperanto",
        key="deep_input",
    )
    deep_house = st.text_input("Hausmarke (für die Marktform)", value="eEvolution", key="deep_house")
    deep_btn = st.button("🎯 Tiefenprüfung starten", key="deep_run")
    if deep_btn:
        names = [n.strip() for n in deep_raw.splitlines() if n.strip()][:5]
        if not names:
            st.warning("Bitte mindestens einen Namen eingeben.")
            st.stop()
        prog = st.progress(0, text="Prüfe Finalisten…")
        for i, name in enumerate(names):
            prog.progress((i + 1) / len(names), text=f"Prüfe {name}…")
            hits = query_signa(name, [9, 42], ["euipo", "wipo"], silent=True)
            label, css, summary = classify_result(hits)
            doms = check_domains(name, tlds=("com", "de", "eu", "io"))
            pill = {"clear": "pill-green", "warn": "pill-yellow", "hit": "pill-red", "unknown": "pill-gray"}.get(css, "pill-gray")
            marktform = f"{deep_house.strip()} {name}" if deep_house.strip() else name
            st.markdown(f"""
            <div class="name-card">
              <h3>{name} <span class="status-pill {pill}" style="vertical-align:middle;">{label}</span></h3>
              <div class="meta">Marktform: <strong>{marktform}</strong> &nbsp;·&nbsp; EU-Marke (EUIPO + Madrid): {summary}</div>
              <div style="margin-top:0.4rem;">{domains_html(doms)}</div>
            </div>
            """, unsafe_allow_html=True)
            if hits:
                with st.expander("EU-Marken-Treffer zu " + name):
                    for tm in hits[:8]:
                        st.markdown(render_hit(tm), unsafe_allow_html=True)
            st.markdown(
                "**Manuell prüfen (kostenlos, 1 Klick):** "
                + f"[TMview – DE + EU + IR ↗]({tmview_url(name)}) &nbsp;·&nbsp; "
                + f"[DPMAregister (DE-national) ↗]({DPMAREGISTER_URL}) &nbsp;·&nbsp; "
                + f"[North Data – Firmennamen-Schnellsuche ↗]({northdata_url(name)}) &nbsp;·&nbsp; "
                + f"[Handelsregister (Startseite) ↗]({HANDELSREGISTER_URL}) &nbsp;·&nbsp; "
                + f"[Google-Suche ↗]({google_exact_url(name)})"
            )
            st.markdown("---")
        prog.empty()
        st.info(
            "**Automatisiert:** EU-Marken (EUIPO + Madrid) und Domains. "
            "**DPMA (DE-national) und Firmennamen bitte über die Links oben manuell prüfen** – "
            "eine kostenlose, zuverlässige Vollautomatik gibt es dafür nicht (TMview benötigt einen "
            "Datenvertrag, das Handelsregister-Portal ist sessiongebunden und blockt automatisierte "
            "Zugriffe; der North-Data-Link ist eine frei verlinkbare Alternative für die Firmennamen-"
            "Schnellsuche). Der TMview-Link ist bereits auf DE + EU + international vorgefiltert."
        )
    st.markdown("""
    <div class="disclaimer">
      Tiefenprüfung für Finalisten: automatischer EU-Check + geführte Register-Links.<br>
      Für die rechtsverbindliche Freigabe bleibt die anwaltliche Recherche (DPMA-Ähnlichkeit,
      Firmenname, Titelschutz) maßgeblich.
    </div>
    """, unsafe_allow_html=True)
