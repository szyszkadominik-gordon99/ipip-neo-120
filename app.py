"""
IPIP-NEO-120 — Aplikacja webowa
Streamlit UI: ankieta → scoring → normalizacja → raport dla LLM
"""

import streamlit as st
import plotly.graph_objects as go
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from scoring_engine import load_questions, compute_raw_scores
from normalization_engine import load_norms, compute_percentiles
from output_formatter import format_for_llm, detect_dissociations

# ── Stałe ─────────────────────────────────────────────────────────────────────

ITEMS_PER_PAGE = 10
TOTAL_PAGES    = 12

SCALE_LABELS = {
    1: "Zdecydowanie\nnieprawdziwe",
    2: "Raczej\nnieprawdziwe",
    3: "Ani tak,\nani nie",
    4: "Raczej\nprawdziwe",
    5: "Zdecydowanie\nprawdziwe",
}

DOMAIN_COLORS = {
    "N": "#e74c3c",
    "E": "#f39c12",
    "O": "#2ecc71",
    "A": "#3498db",
    "C": "#9b59b6",
}

# ── Ładowanie danych (cached) ─────────────────────────────────────────────────

@st.cache_resource
def get_questions():
    path = Path(__file__).parent / "questions.json"
    return load_questions(str(path))

@st.cache_resource
def get_norms():
    path = Path(__file__).parent / "norms.json"
    return load_norms(str(path))

# ── Session state ─────────────────────────────────────────────────────────────

def init_state():
    for key, default in [("page", 0), ("results", None)]:
        if key not in st.session_state:
            st.session_state[key] = default

def go_to(page: int):
    st.session_state.page = page

# ── Strona: Powitanie ─────────────────────────────────────────────────────────

def page_welcome():
    st.title("Test osobowości IPIP-NEO-120")

    st.markdown("""
Kwestionariusz składa się z **120 pytań** (12 stron po 10 pytań).  
Każde zdanie oceniasz w skali 1–5:

| 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|
| Zdecydowanie nieprawdziwe | Raczej nieprawdziwe | Ani tak, ani nie | Raczej prawdziwe | Zdecydowanie prawdziwe |

Wypełnienie zajmuje około **15–20 minut**. Nie ma odpowiedzi dobrych ani złych — odpowiadaj szczerze.

**Co otrzymasz po wypełnieniu:**
- Profil percentylowy dla 5 domen i 30 faset osobowości
- Wykresy (radar + słupki faset)
- Sformatowany raport gotowy do wklejenia do dowolnego LLM (Claude, ChatGPT itp.)

---
*Podstawa naukowa: IPIP-NEO-120 (Johnson, 2014). Normy: próba internetowa N=619,150.*
    """)

    st.info(
        "Wyniki nie są przechowywane na żadnym serwerze. "
        "Obliczenia wykonywane są lokalnie w Twojej sesji przeglądarki."
    )

    if st.button("Rozpocznij test →", type="primary", use_container_width=True):
        go_to(1)
        st.rerun()

# ── Strona: Pytania ───────────────────────────────────────────────────────────

def page_questions(questions: list):
    page_num  = st.session_state.page
    start_idx = (page_num - 1) * ITEMS_PER_PAGE
    end_idx   = start_idx + ITEMS_PER_PAGE
    page_qs   = questions[start_idx:end_idx]

    # Pasek postępu
    progress_pct = (page_num - 1) / TOTAL_PAGES
    st.progress(
        progress_pct,
        text=f"Strona {page_num} z {TOTAL_PAGES}  ·  pytania {start_idx + 1}–{min(end_idx, 120)} z 120"
    )

    st.markdown(f"#### Oceń, na ile każde zdanie opisuje Ciebie:")
    st.divider()

    for q in page_qs:
        item_id = q["id"]
        key     = f"q_{item_id}"

        st.markdown(f"**{item_id}.** {q['text']}")

        # index=None → brak domyślnej odpowiedzi (user musi aktywnie wybrać)
        # Jeśli klucz jest już w session_state (powrót na stronę), Streamlit
        # automatycznie używa zapisanej wartości.
        current = st.session_state.get(key)
        st.radio(
            label=key,
            options=[1, 2, 3, 4, 5],
            format_func=lambda x: SCALE_LABELS[x],
            horizontal=True,
            key=key,
            index=None if current is None else (current - 1),
            label_visibility="collapsed",
        )
        st.markdown("")

    st.divider()

    # Sprawdź kompletność bieżącej strony
    answered = all(
        st.session_state.get(f"q_{q['id']}") is not None
        for q in page_qs
    )

    if not answered:
        st.warning("Odpowiedz na wszystkie pytania na tej stronie, aby przejść dalej.")

    col_back, col_space, col_next = st.columns([1, 2, 1])

    with col_back:
        if page_num > 1:
            if st.button("← Wstecz", use_container_width=True):
                go_to(page_num - 1)
                st.rerun()

    with col_next:
        if page_num < TOTAL_PAGES:
            if st.button(
                "Dalej →",
                type="primary",
                use_container_width=True,
                disabled=not answered,
            ):
                go_to(page_num + 1)
                st.rerun()
        else:
            if st.button(
                "Oblicz wyniki →",
                type="primary",
                use_container_width=True,
                disabled=not answered,
            ):
                _compute_and_store(questions)
                go_to(TOTAL_PAGES + 1)
                st.rerun()

# ── Obliczenia ────────────────────────────────────────────────────────────────

def _compute_and_store(questions: list):
    responses = {}
    for q in questions:
        val = st.session_state.get(f"q_{q['id']}")
        if val is not None:
            responses[q["id"]] = int(val)

    norms   = get_norms()
    raw     = compute_raw_scores(responses, questions)
    results = compute_percentiles(raw, norms)
    st.session_state.results = results

# ── Strona: Wyniki ────────────────────────────────────────────────────────────

def page_results():
    results = st.session_state.results
    if results is None:
        st.error("Brak wyników. Wróć do początku.")
        if st.button("← Restart"):
            go_to(0)
            st.rerun()
        return

    st.title("Twój profil osobowości")
    st.success("Test ukończony.")

    tab_overview, tab_facets, tab_llm = st.tabs([
        "Przegląd domenowy",
        "Szczegóły faset",
        "Raport dla LLM",
    ])

    # ── Tab 1: Domeny ──────────────────────────────────────────────────────────
    with tab_overview:
        st.subheader("Radar — 5 domen")
        st.caption(
            "Wartości to proxy domenowe (mediana percentyli 6 faset). "
            "Przy dużej dysocjacji wewnątrz domeny wynik domenowy jest mniej informatywny — "
            "sprawdź zakładkę 'Szczegóły faset'."
        )
        st.plotly_chart(
            _chart_radar(results["domains"]),
            use_container_width=True,
        )

        st.subheader("Wyniki domenowe")
        cols = st.columns(5)
        for i, d in enumerate(["N", "E", "O", "A", "C"]):
            dom = results["domains"][d]
            with cols[i]:
                st.metric(
                    label=f"{d}",
                    value=f"{dom['percentile_proxy']}",
                    help=f"{dom['name']}\n\n{dom['note']}",
                )
        st.caption("Wartości w centylach (1–99). Mediana populacji = 50.")

    # ── Tab 2: Fasety ──────────────────────────────────────────────────────────
    with tab_facets:
        diss = detect_dissociations(results["facets"], threshold=40)
        if diss:
            items = []
            for d in diss:
                f_max = results["facets"][d["max_facet"]]
                f_min = results["facets"][d["min_facet"]]
                items.append(
                    f"**{d['domain']}**: "
                    f"{d['max_facet']} {f_max['name']} = {d['max_pct']}. centyl  "
                    f"vs  {d['min_facet']} {f_min['name']} = {d['min_pct']}. centyl  "
                    f"(rozstęp: {d['spread']} pp)"
                )
            st.warning(
                "**Dysocjacje wewnątrzdomenowe** (rozstęp ≥ 40 pp) — "
                "wynik domenowy maskuje te różnice:\n\n" + "\n\n".join(items)
            )

        st.subheader("Wszystkie 30 faset")
        st.caption(
            "Linia przerywana szara = 50. centyl (mediana). "
            "Linie kropkowane czerwone = 15. i 85. centyl."
        )
        st.plotly_chart(
            _chart_facets(results["facets"]),
            use_container_width=True,
        )

    # ── Tab 3: Raport LLM ──────────────────────────────────────────────────────
    with tab_llm:
        st.subheader("Raport gotowy do wklejenia do LLM")
        st.markdown(
            "Skopiuj poniższy tekst i wklej go do **Claude, ChatGPT, Gemini** lub innego LLM. "
            "Raport zawiera pełny profil percentylowy oraz sugerowany prompt z instrukcją analizy."
        )

        formatted = format_for_llm(results, include_prompt_template=True)

        st.text_area(
            label="raport",
            value=formatted,
            height=550,
            label_visibility="collapsed",
        )

        st.download_button(
            label="Pobierz jako .txt",
            data=formatted,
            file_name="profil_ipip_neo_120.txt",
            mime="text/plain",
            use_container_width=True,
        )

    st.divider()
    if st.button("Zacznij od nowa", use_container_width=False):
        for k in list(st.session_state.keys()):
            if k.startswith("q_"):
                del st.session_state[k]
        st.session_state.results = None
        go_to(0)
        st.rerun()

# ── Wykresy ───────────────────────────────────────────────────────────────────

def _chart_radar(domains: dict) -> go.Figure:
    order  = ["N", "E", "O", "A", "C"]
    labels = [domains[d]["name"] for d in order]
    values = [domains[d]["percentile_proxy"] for d in order]

    # Zamknięcie wielokąta
    values_c = values + values[:1]
    labels_c = labels + labels[:1]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=values_c,
        theta=labels_c,
        fill="toself",
        fillcolor="rgba(52, 152, 219, 0.15)",
        line=dict(color="rgba(52, 152, 219, 0.85)", width=2),
        marker=dict(size=6),
    ))

    # Linia referencji na 50. centyl
    ref = [50] * (len(order) + 1)
    fig.add_trace(go.Scatterpolar(
        r=ref,
        theta=labels_c,
        mode="lines",
        line=dict(color="gray", width=1, dash="dot"),
        showlegend=False,
    ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 99],
                tickvals=[25, 50, 75],
                ticktext=["25", "50", "75"],
            )
        ),
        showlegend=False,
        height=400,
        margin=dict(t=30, b=30, l=70, r=70),
    )
    return fig


def _chart_facets(facets: dict) -> go.Figure:
    order = ["N", "E", "O", "A", "C"]
    labels, pcts, colors = [], [], []

    for d in order:
        for code, fdata in facets.items():
            if fdata["domain"] == d:
                labels.append(f"{code}  {fdata['name']}")
                pcts.append(fdata["percentile"])
                colors.append(DOMAIN_COLORS[d])

    fig = go.Figure(go.Bar(
        x=pcts,
        y=labels,
        orientation="h",
        marker_color=colors,
        text=pcts,
        textposition="outside",
        cliponaxis=False,
    ))

    fig.add_vline(x=50, line_dash="dash",  line_color="gray", opacity=0.5)
    fig.add_vline(x=85, line_dash="dot",   line_color="red",  opacity=0.35)
    fig.add_vline(x=15, line_dash="dot",   line_color="red",  opacity=0.35)

    fig.update_layout(
        xaxis=dict(range=[0, 112], title="Centyl"),
        yaxis=dict(autorange="reversed"),
        height=920,
        margin=dict(l=200, r=60, t=20, b=40),
        showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    st.set_page_config(
        page_title="IPIP-NEO-120 — Test osobowości",
        page_icon="🧠",
        layout="centered",
        initial_sidebar_state="collapsed",
    )

    init_state()
    questions = get_questions()

    page = st.session_state.page

    if page == 0:
        page_welcome()
    elif 1 <= page <= TOTAL_PAGES:
        page_questions(questions)
    else:
        page_results()


if __name__ == "__main__":
    main()
