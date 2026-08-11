"""File ingestion and schema profiling.

Turns uploaded CSV/Excel files into named pandas DataFrames plus a *schema* —
the structural description that is the only thing ever sent to the language model.

The privacy rule lives here: sample values are included only for low-cardinality
categorical columns, and never for anything that looks like PII or money.
"""

import io
import os
import re
from typing import Dict, List, Optional, Tuple

import pandas as pd

MAX_SAMPLE_VALUES = 8
MAX_CARDINALITY_FOR_SAMPLES = 25

# Columns whose *values* never leave the machine, regardless of cardinality.
PII_PATTERNS = re.compile(
    r"(name|email|mail|phone|mobile|contact|address|dob|birth|aadhaar|aadhar|pan|"
    r"passport|account|ifsc|salary|ctc|compensation|bonus|wage|pay|income|"
    r"remark|comment|note|feedback|reason_text|description)",
    re.I,
)


def normalise_name(name: str) -> str:
    """employee ID -> employee_id, so the model sees predictable identifiers."""
    s = str(name).strip().lower()
    s = re.sub(r"[^\w]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "column"


def _table_name_from_filename(filename: str, sheet: Optional[str] = None) -> str:
    stem = os.path.splitext(os.path.basename(filename))[0]
    base = normalise_name(stem)
    return "%s_%s" % (base, normalise_name(sheet)) if sheet else base


def _coerce_types(df: pd.DataFrame) -> pd.DataFrame:
    """Best-effort date detection. Numbers are already handled by the readers."""
    for col in df.columns:
        if df[col].dtype != "object":
            continue
        non_null = df[col].dropna()
        if non_null.empty:
            continue
        sample = non_null.head(200)
        # only attempt dates on strings that actually look date-ish
        looks_datey = sample.astype(str).str.match(r"^\s*\d{4}[-/]\d{1,2}([-/]\d{1,2})?\s*$").mean()
        if looks_datey < 0.9:
            continue
        try:
            parsed = pd.to_datetime(df[col], errors="coerce")
        except Exception:
            continue
        if parsed.notna().sum() >= non_null.shape[0] * 0.9:
            df[col] = parsed
    return df


def load_files(files) -> Tuple[Dict[str, pd.DataFrame], List[str]]:
    """Read uploaded CSV/Excel files. Each Excel sheet becomes its own table.

    `files` are Streamlit UploadedFile objects (or any object with .name and .read()).
    Returns (tables, warnings).
    """
    tables: Dict[str, pd.DataFrame] = {}
    warnings: List[str] = []

    for f in files:
        name = getattr(f, "name", str(f))
        ext = os.path.splitext(name)[1].lower()
        try:
            raw = f.read() if hasattr(f, "read") else open(f, "rb").read()
        except Exception as exc:
            warnings.append("Could not read %s: %s" % (name, exc))
            continue

        try:
            if ext in (".csv", ".txt", ".tsv"):
                sep = "\t" if ext == ".tsv" else None
                df = pd.read_csv(io.BytesIO(raw), sep=sep, engine="python")
                frames = {_table_name_from_filename(name): df}
            elif ext in (".xlsx", ".xls", ".xlsm"):
                book = pd.read_excel(io.BytesIO(raw), sheet_name=None)
                frames = {}
                for sheet, df in book.items():
                    key = _table_name_from_filename(name, sheet) if len(book) > 1 \
                        else _table_name_from_filename(name)
                    frames[key] = df
            else:
                warnings.append("Skipped %s — unsupported file type." % name)
                continue
        except Exception as exc:
            warnings.append("Could not parse %s: %s" % (name, exc))
            continue

        for key, df in frames.items():
            if df.empty or df.shape[1] == 0:
                warnings.append("Skipped %s — no rows or columns found." % key)
                continue
            df.columns = [normalise_name(c) for c in df.columns]
            # de-duplicate column names after normalisation
            seen: Dict[str, int] = {}
            cols = []
            for c in df.columns:
                if c in seen:
                    seen[c] += 1
                    cols.append("%s_%d" % (c, seen[c]))
                else:
                    seen[c] = 0
                    cols.append(c)
            df.columns = cols
            df = _coerce_types(df)

            unnamed = sum(1 for c in df.columns if c.startswith("unnamed"))
            if unnamed > df.shape[1] / 2:
                warnings.append(
                    "%s: most columns are unnamed — the header row may not be the first row." % key)

            final_key, n = key, 2
            while final_key in tables:
                final_key = "%s_%d" % (key, n)
                n += 1
            tables[final_key] = df

    return tables, warnings


def _simple_type(series: pd.Series) -> str:
    if pd.api.types.is_datetime64_any_dtype(series):
        return "DATE"
    if pd.api.types.is_bool_dtype(series):
        return "BOOLEAN"
    if pd.api.types.is_integer_dtype(series):
        return "INTEGER"
    if pd.api.types.is_float_dtype(series):
        return "DOUBLE"
    return "VARCHAR"


def profile_table(name: str, df: pd.DataFrame) -> Dict:
    """Structural description of one table. No row-level data escapes except
    sample values for low-cardinality, non-sensitive categorical columns."""
    columns = []
    for col in df.columns:
        s = df[col]
        n = len(s)
        nulls = int(s.isna().sum())
        dtype = _simple_type(s)
        try:
            distinct = int(s.nunique(dropna=True))
        except TypeError:
            distinct = -1

        samples: List[str] = []
        redacted = bool(PII_PATTERNS.search(col))
        if (not redacted and dtype == "VARCHAR"
                and 0 < distinct <= MAX_CARDINALITY_FOR_SAMPLES):
            vals = s.dropna().astype(str).unique()[:MAX_SAMPLE_VALUES]
            samples = [str(v) for v in vals]

        col_info = {
            "name": col,
            "type": dtype,
            "null_pct": round(100.0 * nulls / n, 1) if n else 0.0,
            "distinct": distinct,
            "samples": samples,
            "redacted": redacted,
        }
        if dtype in ("INTEGER", "DOUBLE") and not redacted and s.notna().any():
            col_info["min"] = float(s.min())
            col_info["max"] = float(s.max())
        columns.append(col_info)

    return {"name": name, "rows": int(len(df)), "columns": columns}


def profile_all(tables: Dict[str, pd.DataFrame]) -> List[Dict]:
    return [profile_table(name, df) for name, df in tables.items()]


def schema_to_prompt(schemas: List[Dict]) -> str:
    """Render schemas as compact DDL-ish text for the model. This string, plus the
    question, is the entire payload sent to the LLM."""
    blocks = []
    for t in schemas:
        lines = ['TABLE %s  -- %d rows' % (t["name"], t["rows"])]
        for c in t["columns"]:
            bits = ["  %s %s" % (c["name"], c["type"])]
            if c["samples"]:
                bits.append("values: %s" % ", ".join('"%s"' % v for v in c["samples"]))
            if "min" in c:
                lo, hi = c["min"], c["max"]
                fmt = "%d" if float(lo).is_integer() and float(hi).is_integer() else "%.2f"
                bits.append(("range: " + fmt + " to " + fmt) % (lo, hi))
            if c["null_pct"] >= 5:
                bits.append("%.0f%% null" % c["null_pct"])
            lines.append("  ".join(bits))
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def data_quality_flags(schemas: List[Dict]) -> List[str]:
    """Surfaced to the user, not to the model — dirty data should fail loudly."""
    flags = []
    for t in schemas:
        for c in t["columns"]:
            if c["null_pct"] >= 40:
                flags.append("%s.%s is %.0f%% empty — aggregates over it may mislead."
                             % (t["name"], c["name"], c["null_pct"]))
            if c["distinct"] == 1 and t["rows"] > 1:
                flags.append("%s.%s has a single value throughout." % (t["name"], c["name"]))
        if t["rows"] == 0:
            flags.append("%s has no rows." % t["name"])
    return flags
