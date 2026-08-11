"""AskDarwin — Streamlit UI.

Upload -> review what was understood -> ask -> get an answer you can check.

The "review what was understood" step exists because the product's real risk is not
failing to answer; it is answering confidently from a relationship it guessed wrong.
"""

import os
import sys

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import charts, ingest, joins, llm, query  # noqa: E402

DEMO_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DEMO_FILES = ["employees.csv", "recruitment.csv", "performance.csv",
              "attendance.csv", "compensation.csv"]

SUGGESTED = [
    "How many employees are currently active, by department?",
    "What is the average tenure in years for employees who exited, by exit reason?",
    "Compare the average performance rating of employees hired through Employee Referral versus Recruitment Agency",
    "Show the monthly trend of total days absent across the company",
    "What is the total monthly payroll cost by department for the latest effective month?",
    "Which 5 departments have the highest attrition rate?",
    "What is the offer-to-join conversion rate by recruitment source?",
    "Compare average base salary of employees rated 5 versus rated 2",
]

st.set_page_config(page_title="AskDarwin", page_icon="📊", layout="wide")


def _init_state():
    for key, default in [("tables", {}), ("schemas", []), ("joins", []),
                         ("history", []), ("warnings", []), ("loaded_from", None)]:
        if key not in st.session_state:
            st.session_state[key] = default


def _ingest(files, source_label):
    tables, warnings = ingest.load_files(files)
    if not tables:
        st.session_state.warnings = warnings or ["No readable tables found."]
        return
    schemas = ingest.profile_all(tables)
    st.session_state.tables = tables
    st.session_state.schemas = schemas
    st.session_state.joins = joins.infer_joins(tables, schemas)
    st.session_state.warnings = warnings
    st.session_state.loaded_from = source_label
    st.session_state.history = []


def _provider_badge():
    try:
        provider, model = llm.active_provider()
        label = "Groq (free tier)" if provider == "groq" else "Ollama (local)"
        st.sidebar.success("Model: %s\n\n`%s`" % (label, model))
    except llm.LLMError as exc:
        st.sidebar.error(str(exc))


def sidebar():
    st.sidebar.markdown("### AskDarwin")
    st.sidebar.caption("Ask your HR spreadsheets anything.")
    _provider_badge()
    st.sidebar.markdown("---")

    uploaded = st.sidebar.file_uploader(
        "Upload CSV or Excel files", type=["csv", "xlsx", "xls", "xlsm", "tsv"],
        accept_multiple_files=True)
    if uploaded and st.sidebar.button("Load uploaded files", width="stretch"):
        _ingest(uploaded, "upload")

    if st.sidebar.button("Load demo HR dataset", width="stretch"):
        paths = [os.path.join(DEMO_DIR, f) for f in DEMO_FILES
                 if os.path.exists(os.path.join(DEMO_DIR, f))]
        _ingest(paths, "demo")

    st.sidebar.markdown("---")
    st.sidebar.caption(
        "Your data stays on the machine running this app. Only the **schema** — "
        "table and column names, types, and sample values from low-cardinality "
        "categorical columns — is sent to the model. Never the rows.")


def render_schema():
    schemas = st.session_state.schemas
    if not schemas:
        return
    total_rows = sum(s["rows"] for s in schemas)
    c1, c2, c3 = st.columns(3)
    c1.metric("Tables", len(schemas))
    c2.metric("Total rows", "{:,}".format(total_rows))
    c3.metric("Relationships found", len(st.session_state.joins))

    with st.expander("What AskDarwin understood from your files", expanded=False):
        for s in schemas:
            st.markdown("**%s** — %s rows" % (s["name"], "{:,}".format(s["rows"])))
            rows = []
            for c in s["columns"]:
                detail = ", ".join(c["samples"][:4]) if c["samples"] else (
                    "— withheld —" if c["redacted"] else "")
                rows.append({"column": c["name"], "type": c["type"],
                             "null %": c["null_pct"], "distinct": c["distinct"],
                             "sample values sent to model": detail})
            st.dataframe(rows, width="stretch", hide_index=True)

        st.markdown("#### Detected relationships")
        if st.session_state.joins:
            st.caption("Inferred from column names and how much the values actually "
                       "overlap. Check these — a wrong join produces a confident wrong answer.")
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
    """Show the literal payload sent to the model.

    The privacy claim is the product's main argument for existing, so it should be
    something the user can inspect rather than something they have to believe.
    """
    schemas = st.session_state.schemas
    schema_text = ingest.schema_to_prompt(schemas)
    joins_text = joins.joins_to_prompt(st.session_state.joins)

    redacted = [(t["name"], c["name"]) for t in schemas for c in t["columns"]
                if c["redacted"] or (c["type"] == "VARCHAR" and not c["samples"])]
    total_rows = sum(t["rows"] for t in schemas)

    with st.expander("Exactly what gets sent to the model", expanded=False):
        c1, c2, c3 = st.columns(3)
        c1.metric("Rows of your data sent", "0")
        c2.metric("Rows kept on this machine", "{:,}".format(total_rows))
        c3.metric("Columns with values withheld", len(redacted))

        st.caption("This is the complete payload — nothing else leaves the machine. "
                   "The model reads structure and writes SQL; your rows are only ever "
                   "touched by DuckDB, locally.")
        st.code(schema_text + "\n\n" + joins_text, language="text")

        if redacted:
            st.caption("Values withheld from: " +
                       ", ".join("%s.%s" % r for r in redacted[:12]) +
                       ("…" if len(redacted) > 12 else ""))


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

    bits =["%d rows returned" % len(df),
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


def main():
    _init_state()
    sidebar()

    st.title("AskDarwin")
    st.caption("Ask your HR spreadsheets anything. Every answer comes with the "
               "query that produced it.")

    if not st.session_state.tables:
        st.info("Upload CSV or Excel files in the sidebar, or load the demo HR "
                "dataset to try it out.")
        st.markdown(
            "**How it works** — your files are read locally and profiled. Only the "
            "*schema* is sent to an open-weights model, which writes a SQL query. "
            "DuckDB executes that query over your data, so every number is computed, "
            "not generated.")
        return

    render_schema()
    st.markdown("---")

    with st.form("ask", clear_on_submit=False):
        question = st.text_input(
            "Ask a question", placeholder="e.g. Which department has the highest attrition rate?")
        submitted = st.form_submit_button("Ask", type="primary")

    st.caption("Try one of these:")
    cols = st.columns(2)
    for i, suggestion in enumerate(SUGGESTED):
        if cols[i % 2].button(suggestion, key="sugg_%d" % i, width="stretch"):
            question, submitted = suggestion, True

    if submitted and question and question.strip():
        schema_text = ingest.schema_to_prompt(st.session_state.schemas)
        joins_text = joins.joins_to_prompt(st.session_state.joins)
        with st.spinner("Writing SQL and running it over your data…"):
            result = query.answer_question(
                question.strip(), st.session_state.tables, schema_text, joins_text)
        st.session_state.history.insert(0, {"question": question.strip(), "result": result})

    for i, entry in enumerate(st.session_state.history):
        st.markdown("---")
        render_answer(entry)
        if i == 0 and len(st.session_state.history) > 1:
            st.caption("Earlier questions below. Each question is answered independently — "
                       "follow-ups like “and for Sales?” are not supported in this version.")


if __name__ == "__main__":
    main()
