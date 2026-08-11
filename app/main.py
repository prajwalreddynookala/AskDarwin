"""AskDarwin — Streamlit UI.

Upload -> understand what you uploaded -> ask -> get an answer you can check.

The "understand what you uploaded" step exists because the product's real risk is not
failing to answer; it is answering confidently from a relationship it guessed wrong.
"""

import os
import sys

import streamlit as st
import streamlit.components.v1 as components

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import charts, ingest, joins, llm, query  # noqa: E402

DEMO_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DEMO_FILES = ["employees.csv", "recruitment.csv", "performance.csv",
              "attendance.csv", "compensation.csv"]

st.set_page_config(page_title="AskDarwin", page_icon="📊", layout="wide")

# The keyed container itself cannot be the sticky element: Streamlit wraps it in a flex
# layout wrapper that is exactly as tall as its child, leaving sticky no travel. Pinning
# the wrapper instead gives it the full height of the page to stick within.
STICKY_CSS = """
<style>
div[data-testid="stLayoutWrapper"]:has(> .st-key-askbox) {
    position: sticky;
    top: 0;
    z-index: 999;
    background: var(--background-color, #ffffff);
}
.st-key-askbox {
    background: var(--background-color, #ffffff);
    padding-top: 0.5rem;
    padding-bottom: 0.25rem;
    border-bottom: 1px solid rgba(128, 128, 128, 0.18);
}
</style>
"""


def _init_state():
    for key, default in [("tables", {}), ("schemas", []), ("joins", []),
                         ("history", []), ("warnings", []), ("overview", None),
                         ("scroll", False)]:
        if key not in st.session_state:
            st.session_state[key] = default


# ------------------------------------------------------------- suggestions

def _fallback_questions(schemas):
    """Deterministic suggestions from the schema, used when the model call fails.

    Never hard-coded to a domain — they are built from whatever columns arrived.
    """
    out = []
    for s in schemas:
        cats = [c["name"] for c in s["columns"]
                if c["type"] == "VARCHAR" and 1 < c["distinct"] <= 20]
        nums = [c["name"] for c in s["columns"]
                if c["type"] in ("INTEGER", "DOUBLE") and not c["redacted"]]
        dates = [c["name"] for c in s["columns"] if c["type"] == "DATE"]
        if cats:
            out.append("How many rows are there in %s for each %s?" % (s["name"], cats[0]))
        if cats and nums:
            out.append("What is the average %s by %s?" % (nums[0], cats[0]))
            out.append("Which %s has the highest total %s?" % (cats[0], nums[0]))
        if dates and nums:
            out.append("Show the trend of total %s over time" % nums[0])
    if not out:
        out = ["How many rows are in each table?"]
    return out[:6]


def _suggestions(schemas):
    ov = st.session_state.overview
    if ov and ov.get("questions"):
        return ov["questions"]
    return _fallback_questions(schemas)


# ----------------------------------------------------------------- ingest

def _ingest(files):
    tables, warnings = ingest.load_files(files)
    if not tables:
        st.session_state.warnings = warnings or ["No readable tables found."]
        return
    schemas = ingest.profile_all(tables)
    st.session_state.tables = tables
    st.session_state.schemas = schemas
    st.session_state.joins = joins.infer_joins(tables, schemas)
    st.session_state.warnings = warnings
    st.session_state.history = []
    st.session_state.overview = None

    with st.spinner("Reading the schema and working out what this data is…"):
        try:
            st.session_state.overview = llm.describe_dataset(
                ingest.schema_to_prompt(schemas),
                joins.joins_to_prompt(st.session_state.joins))
        except Exception:
            st.session_state.overview = None


def _provider_badge():
    try:
        provider, model = llm.active_provider()
        label = "Groq (free tier)" if provider == "groq" else "Ollama (local)"
        st.sidebar.success("Model: %s\n\n`%s`" % (label, model))
    except llm.LLMError as exc:
        st.sidebar.error(str(exc))


def sidebar():
    st.sidebar.markdown("### AskDarwin")
    st.sidebar.caption("Ask your spreadsheets anything.")
    _provider_badge()
    st.sidebar.markdown("---")

    uploaded = st.sidebar.file_uploader(
        "Upload CSV or Excel files", type=["csv", "xlsx", "xls", "xlsm", "tsv"],
        accept_multiple_files=True)
    if uploaded and st.sidebar.button("Load uploaded files", width="stretch"):
        _ingest(uploaded)

    if st.sidebar.button("Load demo HR dataset", width="stretch"):
        paths = [os.path.join(DEMO_DIR, f) for f in DEMO_FILES
                 if os.path.exists(os.path.join(DEMO_DIR, f))]
        _ingest(paths)

    st.sidebar.markdown("---")
    st.sidebar.caption(
        "Your rows never go to the model. Only the **schema** — table and column names, "
        "types, and sample values from low-cardinality categorical columns — is sent. "
        "The data itself is only ever read by DuckDB.")


# ----------------------------------------------------------------- panels

def render_overview():
    schemas = st.session_state.schemas
    overview = st.session_state.overview
    total_rows = sum(s["rows"] for s in schemas)

    c1, c2, c3 = st.columns(3)
    c1.metric("Tables", len(schemas))
    c2.metric("Total rows", "{:,}".format(total_rows))
    c3.metric("Relationships found", len(st.session_state.joins))

    if overview and overview.get("summary"):
        st.info("**What this data looks like** — " + overview["summary"])

    with st.expander("What AskDarwin understood from your files", expanded=False):
        described = {t["name"]: t["describes"] for t in (overview or {}).get("tables", [])}
        for s in schemas:
            heading = "**%s** — %s rows" % (s["name"], "{:,}".format(s["rows"]))
            if described.get(s["name"]):
                heading += "  ·  _%s_" % described[s["name"]]
            st.markdown(heading)
            st.dataframe(
                [{"column": c["name"], "type": c["type"], "null %": c["null_pct"],
                  "distinct": c["distinct"],
                  "sample values sent to model": (
                      ", ".join(c["samples"][:4]) if c["samples"]
                      else ("— withheld —" if c["redacted"] else ""))}
                 for c in s["columns"]],
                width="stretch", hide_index=True)

        st.markdown("#### Detected relationships")
        if st.session_state.joins:
            st.caption("Inferred from column names and how much the values actually "
                       "overlap. Check these — a wrong join gives a confident wrong answer.")
            st.dataframe(
                [{"left": "%s.%s" % (j["left_table"], j["left_column"]),
                  "right": "%s.%s" % (j["right_table"], j["right_column"]),
                  "cardinality": j["cardinality"],
                  "confidence": "%.0f%%" % (100 * j["confidence"]),
                  "why": j["explanation"]} for j in st.session_state.joins],
                width="stretch", hide_index=True)
        else:
            st.info("No relationships detected — cross-file questions may not work.")

        flags = ingest.data_quality_flags(schemas)
        if flags:
            st.markdown("#### Data quality notes")
            for f in flags[:8]:
                st.warning(f)

    render_payload_panel()

    for w in st.session_state.warnings:
        st.warning(w)


def render_payload_panel():
    """The literal payload sent to the model — the privacy claim, made inspectable."""
    schemas = st.session_state.schemas
    schema_text = ingest.schema_to_prompt(schemas)
    joins_text = joins.joins_to_prompt(st.session_state.joins)
    redacted = [(t["name"], c["name"]) for t in schemas for c in t["columns"]
                if c["redacted"] or (c["type"] == "VARCHAR" and not c["samples"])]

    with st.expander("Exactly what gets sent to the model", expanded=False):
        c1, c2, c3 = st.columns(3)
        c1.metric("Rows of your data sent", "0")
        c2.metric("Rows kept out of the model", "{:,}".format(
            sum(t["rows"] for t in schemas)))
        c3.metric("Columns with values withheld", len(redacted))
        st.caption("This is the complete payload. The model reads structure and writes "
                   "SQL; your rows are only ever touched by DuckDB.")
        st.code(schema_text + "\n\n" + joins_text, language="text")
        if redacted:
            st.caption("Values withheld from: " + ", ".join("%s.%s" % r for r in redacted[:12])
                       + ("…" if len(redacted) > 12 else ""))


def render_answer(entry):
    result = entry["result"]
    st.markdown("#### " + entry["question"])

    if not result.get("ok"):
        if result.get("refusal"):
            st.info("**I can't answer that from these files.** " + result["refusal"])
        else:
            st.error("**That didn't work.** " + result.get("error", "Unknown error"))
            if result.get("sql"):
                with st.expander("Query that failed"):
                    st.code(result["sql"], language="sql")
        return

    df = result["dataframe"]
    spec = charts.choose_chart(df)

    if spec["kind"] == "metric":
        st.metric(str(spec["column"]).replace("_", " ").title(),
                  charts.format_value(spec["value"]))
    elif spec["kind"] == "metric_row":
        cols = st.columns(len(spec["columns"]))
        for col, name in zip(cols, spec["columns"]):
            col.metric(str(name).replace("_", " ").title(),
                       charts.format_value(df.iloc[0][name]))
    elif spec["kind"] == "empty":
        st.info("The query ran successfully but matched no rows.")
    else:
        fig = charts.build_figure(df, spec)
        if fig is not None:
            st.plotly_chart(fig)
        st.dataframe(df, width="stretch", hide_index=True)

    bits = ["%d rows returned" % len(df),
            "%s rows scanned" % "{:,}".format(result["rows_scanned"]),
            "%.1fs" % result["elapsed"]]
    if result.get("retried"):
        bits.append("recovered after one retry")
    st.caption(" · ".join(bits) + " · tables: " + ", ".join(result["tables_used"]))
    if result.get("truncated"):
        st.caption("Showing the first %s rows." % "{:,}".format(query.MAX_RESULT_ROWS))

    with st.expander("Show the SQL that produced this"):
        st.code(result["sql"], language="sql")
        if result.get("attempts"):
            st.caption("First attempt failed and was corrected automatically:")
            st.code(result["attempts"][0]["sql"], language="sql")
            st.caption("Error: " + result["attempts"][0]["error"])


# ------------------------------------------------------------------- main

def _ask(question):
    schema_text = ingest.schema_to_prompt(st.session_state.schemas)
    joins_text = joins.joins_to_prompt(st.session_state.joins)
    with st.spinner("Writing SQL and running it over your data…"):
        result = query.answer_question(
            question.strip(), st.session_state.tables, schema_text, joins_text)
    st.session_state.history.insert(0, {"question": question.strip(), "result": result})
    st.session_state.scroll = True


def main():
    _init_state()
    st.markdown(STICKY_CSS, unsafe_allow_html=True)
    sidebar()

    st.title("AskDarwin")
    st.caption("Ask your spreadsheets anything. Every answer comes with the query "
               "that produced it.")

    if not st.session_state.tables:
        st.info("Upload CSV or Excel files in the sidebar — any domain, not just HR — "
                "or load the demo HR dataset to try it out.")
        st.markdown(
            "**How it works** — your files are read and profiled. Only the *schema* is "
            "sent to an open-weights model, which writes a SQL query. DuckDB executes "
            "that query over your data, so every number is computed, not generated.")
        return

    render_overview()
    st.markdown("---")

    asked = None
    with st.container(key="askbox"):
        with st.form("ask", clear_on_submit=False):
            question = st.text_input(
                "Ask a question",
                placeholder="e.g. Which category has the highest total value?")
            if st.form_submit_button("Ask", type="primary") and question.strip():
                asked = question

    suggestions = _suggestions(st.session_state.schemas)
    has_history = bool(st.session_state.history)

    if suggestions:
        if has_history:
            with st.expander("Suggested questions for this data", expanded=False):
                for i, s in enumerate(suggestions):
                    if st.button(s, key="sugg_%d" % i, width="stretch"):
                        asked = s
        else:
            st.caption("Questions this data can answer:")
            cols = st.columns(2)
            for i, s in enumerate(suggestions):
                if cols[i % 2].button(s, key="sugg_%d" % i, width="stretch"):
                    asked = s

    if asked:
        _ask(asked)
        st.rerun()

    if st.session_state.history:
        st.markdown('<div id="latest-answer"></div>', unsafe_allow_html=True)
        for i, entry in enumerate(st.session_state.history):
            st.markdown("---")
            render_answer(entry)
            if i == 0 and len(st.session_state.history) > 1:
                st.caption("Earlier questions below. Each is answered independently — "
                           "follow-ups like “and for Sales?” are not supported here.")

    if st.session_state.scroll:
        st.session_state.scroll = False
        # Streamlit scrolls an inner <section data-testid="stMain">, not the window, so
        # scrollIntoView on the document does nothing. Offset the sticky ask box.
        # Retried, because Streamlit finishes laying out after the component script
        # fires and a single early attempt gets overwritten.
        components.html(
            """<script>
            (function () {
                var tries = 0;
                function jump() {
                    tries += 1;
                    var d = window.parent.document;
                    var target = d.getElementById('latest-answer');
                    var main = d.querySelector('section[data-testid="stMain"]');
                    if (target && main) {
                        var t = target.getBoundingClientRect();
                        var m = main.getBoundingClientRect();
                        main.scrollTo({top: main.scrollTop + (t.top - m.top) - 90,
                                       behavior: tries === 1 ? 'smooth' : 'auto'});
                    } else if (target) {
                        target.scrollIntoView({block: 'start'});
                    }
                    if (tries < 4) { setTimeout(jump, 400); }
                }
                setTimeout(jump, 250);
            })();
            </script>""",
            height=0)


if __name__ == "__main__":
    main()
