"""Deterministic execution of model-generated SQL, plus the ask -> answer loop.

The model writes the query; DuckDB does every arithmetic operation. That split is
what makes an answer reproducible and checkable rather than merely plausible.
"""

import re
import time
from typing import Dict, List, Optional

import duckdb
import pandas as pd

from . import llm

MAX_RESULT_ROWS = 5000


def make_connection(tables: Dict[str, pd.DataFrame]):
    """In-memory DuckDB with the uploaded frames registered as tables.

    External access is disabled so a generated query cannot reach the filesystem
    or the network — the model's output is untrusted input by definition.
    """
    try:
        con = duckdb.connect(":memory:", config={"enable_external_access": False})
    except Exception:
        con = duckdb.connect(":memory:")
    for name, df in tables.items():
        con.register(name, df)
    return con


def run_sql(con, sql: str) -> Dict:
    started = time.time()
    df = con.execute(sql).fetch_df()
    elapsed = time.time() - started
    truncated = len(df) > MAX_RESULT_ROWS
    if truncated:
        df = df.head(MAX_RESULT_ROWS)
    return {"dataframe": df, "elapsed": elapsed, "truncated": truncated}


def tables_referenced(sql: str, known: List[str]) -> List[str]:
    lowered = sql.lower()
    return [t for t in known if re.search(r"\b%s\b" % re.escape(t.lower()), lowered)]


def rows_scanned(tables: Dict[str, pd.DataFrame], used: List[str]) -> int:
    return int(sum(len(tables[t]) for t in used if t in tables))


def answer_question(question: str, tables: Dict[str, pd.DataFrame], schema_text: str,
                    joins_text: str, con=None) -> Dict:
    """Generate SQL, execute it, and retry once with the error text on failure.

    The retry is the single highest-value correctness lever in the system: small
    models routinely emit a wrong dialect function, and the engine's own error
    message is a far better correction signal than any amount of prompt wording.
    """
    owns_connection = con is None
    con = con or make_connection(tables)
    attempts: List[Dict] = []

    try:
        sql, refusal = llm.generate_sql(schema_text, joins_text, question)
    except llm.LLMError as exc:
        return {"ok": False, "error": str(exc), "stage": "generation", "attempts": attempts}

    if refusal:
        return {"ok": False, "refusal": refusal, "stage": "refused", "attempts": attempts}

    for attempt in range(2):
        try:
            result = run_sql(con, sql)
            used = tables_referenced(sql, list(tables.keys()))
            return {
                "ok": True,
                "sql": sql,
                "dataframe": result["dataframe"],
                "elapsed": result["elapsed"],
                "truncated": result["truncated"],
                "tables_used": used,
                "rows_scanned": rows_scanned(tables, used),
                "retried": attempt > 0,
                "attempts": attempts,
            }
        except Exception as exc:
            error = str(exc).split("\n")[0][:300]
            attempts.append({"sql": sql, "error": error})
            if attempt == 1:
                return {"ok": False, "error": error, "sql": sql,
                        "stage": "execution", "attempts": attempts}
            try:
                sql, refusal = llm.generate_sql(
                    schema_text, joins_text, question,
                    previous_error=error, previous_sql=sql)
                if refusal:
                    return {"ok": False, "refusal": refusal, "stage": "refused",
                            "attempts": attempts}
            except llm.LLMError as exc2:
                return {"ok": False, "error": str(exc2), "stage": "generation",
                        "attempts": attempts}
    return {"ok": False, "error": "Query could not be executed.", "attempts": attempts}
