"""Join-key inference across uploaded files.

Users upload files with no declared relationships, but the brief requires
cross-file analysis. Something has to work out how the tables connect.

A silently wrong join produces a confidently wrong number — the worst failure an
analytics tool has — so every inferred relationship is scored, explained, and
shown to the user for confirmation rather than applied invisibly.
"""

from typing import Dict, List

import pandas as pd

MAX_VALUES_SAMPLED = 5000
MIN_CONFIDENCE = 0.35

_COMPATIBLE = {
    ("INTEGER", "INTEGER"), ("VARCHAR", "VARCHAR"), ("DOUBLE", "DOUBLE"),
    ("INTEGER", "DOUBLE"), ("DOUBLE", "INTEGER"),
    ("INTEGER", "VARCHAR"), ("VARCHAR", "INTEGER"),  # ids read as text in one file
}


def _name_score(a: str, b: str) -> float:
    """How much the two column names suggest a relationship."""
    if a == b:
        return 1.0
    if a.endswith("_id") and b.endswith("_id"):
        # employee_id vs emp_id, manager_id vs employee_id
        stem_a, stem_b = a[:-3], b[:-3]
        if stem_a.startswith(stem_b) or stem_b.startswith(stem_a):
            return 0.8
        return 0.45
    if (a.endswith("_id") and b == "id") or (b.endswith("_id") and a == "id"):
        return 0.7
    if a in b or b in a:
        return 0.5
    return 0.0


def _overlap(left: pd.Series, right: pd.Series) -> float:
    """Containment: what fraction of the smaller distinct set appears in the larger.

    Containment rather than Jaccard, because a legitimate foreign key is usually a
    small set (400 employees) pointing into a large one (10k attendance rows), and
    Jaccard would punish that asymmetry.
    """
    lv = left.dropna().astype(str).unique()[:MAX_VALUES_SAMPLED]
    rv = right.dropna().astype(str).unique()[:MAX_VALUES_SAMPLED]
    if len(lv) == 0 or len(rv) == 0:
        return 0.0
    ls, rs = set(lv), set(rv)
    return len(ls & rs) / float(min(len(ls), len(rs)))


def _type_of(schema: Dict, col: str) -> str:
    for c in schema["columns"]:
        if c["name"] == col:
            return c["type"]
    return "VARCHAR"


def infer_joins(tables: Dict[str, pd.DataFrame], schemas: List[Dict]) -> List[Dict]:
    """Rank candidate relationships between every pair of tables.

    Confidence blends name similarity and actual value overlap, weighted towards
    overlap — column names lie, data does not.
    """
    by_name = {s["name"]: s for s in schemas}
    names = list(tables.keys())
    candidates: List[Dict] = []

    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            ln, rn = names[i], names[j]
            ldf, rdf = tables[ln], tables[rn]
            for lc in ldf.columns:
                lt = _type_of(by_name[ln], lc)
                for rc in rdf.columns:
                    rt = _type_of(by_name[rn], rc)
                    if (lt, rt) not in _COMPATIBLE:
                        continue
                    name_score = _name_score(lc, rc)
                    if name_score == 0.0:
                        continue
                    # a key candidate must be reasonably distinct on at least one side
                    l_uniq = ldf[lc].nunique(dropna=True) / max(len(ldf), 1)
                    r_uniq = rdf[rc].nunique(dropna=True) / max(len(rdf), 1)
                    if max(l_uniq, r_uniq) < 0.05:
                        continue
                    ov = _overlap(ldf[lc], rdf[rc])
                    if ov < 0.2:
                        continue
                    confidence = 0.35 * name_score + 0.65 * ov
                    if confidence < MIN_CONFIDENCE:
                        continue
                    cardinality = ("one-to-one" if l_uniq > 0.95 and r_uniq > 0.95
                                   else "one-to-many" if l_uniq > 0.95
                                   else "many-to-one" if r_uniq > 0.95
                                   else "many-to-many")
                    candidates.append({
                        "left_table": ln, "left_column": lc,
                        "right_table": rn, "right_column": rc,
                        "confidence": round(confidence, 3),
                        "overlap": round(ov, 3),
                        "cardinality": cardinality,
                        "explanation": "%.0f%% of values overlap; names %s" % (
                            100 * ov,
                            "match exactly" if lc == rc else "are similar"),
                    })

    candidates.sort(key=lambda c: -c["confidence"])

    # Drop many-to-many candidates when both tables already join to a shared table.
    #
    # performance.employee_id = attendance.employee_id is *technically* true, but
    # joining two fact tables directly fans out rows and silently corrupts every
    # aggregate computed over them. The correct path is through the dimension table
    # they both reference, so we only keep a many-to-many link when no such table
    # exists to route through.
    keyed: Dict[str, List[Dict]] = {}
    for c in candidates:
        if c["cardinality"] != "many-to-many":
            keyed.setdefault(c["left_table"], []).append(c)
            keyed.setdefault(c["right_table"], []).append(c)

    def has_shared_dimension(a: str, b: str) -> bool:
        def partners(t):
            out = set()
            for c in keyed.get(t, []):
                other = c["right_table"] if c["left_table"] == t else c["left_table"]
                unique_side = ("one-to-many" if c["left_table"] == other else "many-to-one")
                if c["cardinality"] in ("one-to-one", unique_side):
                    out.add(other)
            return out
        return bool(partners(a) & partners(b))

    filtered = [c for c in candidates
                if c["cardinality"] != "many-to-many"
                or not has_shared_dimension(c["left_table"], c["right_table"])]

    # keep the strongest relationship per table pair, plus one more if it is very strong
    kept: List[Dict] = []
    seen_pairs: Dict[str, int] = {}
    for c in filtered:
        key = "%s|%s" % tuple(sorted([c["left_table"], c["right_table"]]))
        count = seen_pairs.get(key, 0)
        if count == 0 or (count == 1 and c["confidence"] >= 0.85):
            seen_pairs[key] = count + 1
            kept.append(c)
    return kept


def joins_to_prompt(joins: List[Dict]) -> str:
    """Hand the model the relationships so it does not have to guess them."""
    if not joins:
        return "No relationships detected between the tables."
    lines = ["Known relationships between tables:"]
    for j in joins:
        lines.append("  %s.%s = %s.%s   (%s, confidence %.0f%%)" % (
            j["left_table"], j["left_column"], j["right_table"], j["right_column"],
            j["cardinality"], 100 * j["confidence"]))
    return "\n".join(lines)
