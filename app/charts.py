"""Chart selection from result shape.

Deliberately deterministic: the shape of the result set decides the visual, not the
language model. One less thing that can hallucinate, and it makes the same question
render the same way every time.
"""

from typing import Dict, Optional

import pandas as pd

MAX_CATEGORIES_FOR_BAR = 30
_TIMEISH = ("month", "date", "year", "quarter", "week", "period", "cycle", "day")


def _is_numeric(s: pd.Series) -> bool:
    return pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s)


def _is_temporal(name: str, s: pd.Series) -> bool:
    if pd.api.types.is_datetime64_any_dtype(s):
        return True
    if any(t in name.lower() for t in _TIMEISH):
        # '2025-03' style buckets arrive as strings but are still a time axis
        sample = s.dropna().astype(str).head(20)
        return bool(len(sample)) and sample.str.match(r"^\d{4}([-/]\d{1,2})?").mean() > 0.8
    return False


def choose_chart(df: pd.DataFrame) -> Dict:
    """Returns {'kind': metric|line|bar|grouped_bar|table, ...}."""
    if df is None or df.empty:
        return {"kind": "empty"}

    numeric = [c for c in df.columns if _is_numeric(df[c])]
    non_numeric = [c for c in df.columns if c not in numeric]

    # a single number is an answer, not a chart
    if df.shape == (1, 1) and numeric:
        return {"kind": "metric", "column": df.columns[0], "value": df.iloc[0, 0]}
    if len(df) == 1 and len(numeric) == len(df.columns) and len(df.columns) <= 4:
        return {"kind": "metric_row", "columns": list(df.columns)}

    if len(df.columns) == 2 and len(numeric) == 1 and len(non_numeric) == 1:
        cat, val = non_numeric[0], numeric[0]
        if _is_temporal(cat, df[cat]):
            return {"kind": "line", "x": cat, "y": val}
        if df[cat].nunique() <= MAX_CATEGORIES_FOR_BAR:
            return {"kind": "bar", "x": cat, "y": val}
        return {"kind": "table"}

    # date + category + measure -> one line per series
    if len(df.columns) == 3 and len(numeric) == 1 and len(non_numeric) == 2:
        val = numeric[0]
        temporal = [c for c in non_numeric if _is_temporal(c, df[c])]
        other = [c for c in non_numeric if c not in temporal]
        if temporal and other and df[other[0]].nunique() <= 12:
            return {"kind": "multi_line", "x": temporal[0], "y": val, "color": other[0]}
        if (not temporal and df[non_numeric[0]].nunique() <= MAX_CATEGORIES_FOR_BAR
                and df[non_numeric[1]].nunique() <= 8):
            return {"kind": "grouped_bar", "x": non_numeric[0], "y": val,
                    "color": non_numeric[1]}

    # a small breakdown with several measures still reads well as bars
    if len(non_numeric) == 1 and len(numeric) >= 2 and len(df) <= MAX_CATEGORIES_FOR_BAR:
        return {"kind": "bar", "x": non_numeric[0], "y": numeric[0], "extra_measures": numeric[1:]}

    return {"kind": "table"}


def format_value(value) -> str:
    """Readable numbers in the big-number card."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    if v != v:  # NaN
        return "—"
    if abs(v) >= 1e7:
        return "%.2f Cr" % (v / 1e7)
    if abs(v) >= 1e5:
        return "%.2f L" % (v / 1e5)
    if abs(v) >= 1000:
        return "{:,.0f}".format(v)
    if float(v).is_integer():
        return "{:,.0f}".format(v)
    return "%.2f" % v


def build_figure(df: pd.DataFrame, spec: Dict) -> Optional[object]:
    import plotly.express as px

    kind = spec.get("kind")
    common = {"template": "plotly_white"}
    if kind == "bar":
        fig = px.bar(df, x=spec["x"], y=spec["y"], **common)
    elif kind == "grouped_bar":
        fig = px.bar(df, x=spec["x"], y=spec["y"], color=spec["color"],
                     barmode="group", **common)
    elif kind == "line":
        fig = px.line(df, x=spec["x"], y=spec["y"], markers=True, **common)
    elif kind == "multi_line":
        fig = px.line(df, x=spec["x"], y=spec["y"], color=spec["color"],
                      markers=True, **common)
    else:
        return None
    fig.update_layout(margin=dict(l=10, r=10, t=30, b=10), height=380)
    return fig
