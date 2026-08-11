"""Evaluation harness — execution accuracy against gold queries.

For each question we run the model's generated SQL and a hand-written reference
query over the same data, then compare the result sets ignoring column names and
row order. This is the standard way text-to-SQL systems are scored, and it is the
only way to make "correct" a number rather than an impression.

Usage:
    python eval/run_eval.py                 # whichever provider is configured
    ASKDARWIN_PROVIDER=ollama python eval/run_eval.py
"""

import json
import math
import os
import sys
import time
from typing import Dict, List, Tuple

import pandas as pd
import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import ingest, joins, llm, query  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
DEMO_FILES = ["employees.csv", "recruitment.csv", "performance.csv",
              "attendance.csv", "compensation.csv"]
REL_TOL = 0.01


def _is_number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and not pd.isna(v)


def canonical(df: pd.DataFrame) -> List[Tuple]:
    """Column-name- and order-insensitive form of a result set."""
    rows = []
    for _, row in df.iterrows():
        nums = tuple(sorted(float(v) for v in row if _is_number(v)))
        cats = tuple(sorted(str(v) for v in row if not _is_number(v)))
        rows.append((cats, nums))
    return sorted(rows)


def results_match(gold: pd.DataFrame, pred: pd.DataFrame) -> Tuple[bool, str]:
    if gold.shape[0] != pred.shape[0]:
        return False, "row count %d vs %d" % (gold.shape[0], pred.shape[0])
    g, p = canonical(gold), canonical(pred)
    for (gc, gn), (pc, pn) in zip(g, p):
        if gc != pc:
            return False, "category values differ: %s vs %s" % (gc, pc)
        if len(gn) != len(pn):
            return False, "different number of measures: %d vs %d" % (len(gn), len(pn))
        for a, b in zip(gn, pn):
            if not math.isclose(a, b, rel_tol=REL_TOL, abs_tol=1e-9):
                return False, "value %s != %s" % (a, b)
    return True, ""


def main() -> int:
    with open(os.path.join(ROOT, "eval", "questions.yaml")) as f:
        cases = yaml.safe_load(f)

    paths = [os.path.join(DATA, f) for f in DEMO_FILES]
    missing = [p for p in paths if not os.path.exists(p)]
    if missing:
        print("Demo data missing. Run: python data/generate_demo_data.py")
        return 2

    tables, _ = ingest.load_files(paths)
    schemas = ingest.profile_all(tables)
    relationships = joins.infer_joins(tables, schemas)
    schema_text = ingest.schema_to_prompt(schemas)
    joins_text = joins.joins_to_prompt(relationships)
    con = query.make_connection(tables)

    provider, model = llm.active_provider()
    print("provider: %s (%s)\n" % (provider, model))

    results: List[Dict] = []
    started = time.time()

    for case in cases:
        cid, question = case["id"], case["question"]
        expect_refusal = bool(case.get("expect_refusal"))
        outcome = query.answer_question(question, tables, schema_text, joins_text, con)

        record = {"id": cid, "category": case["category"], "question": question,
                  "retried": bool(outcome.get("retried"))}

        if expect_refusal:
            record["passed"] = bool(outcome.get("refusal"))
            record["detail"] = outcome.get("refusal") or (
                "answered instead of declining: " + (outcome.get("sql") or outcome.get("error", "")))
        elif not outcome.get("ok"):
            record["passed"] = False
            record["detail"] = "%s: %s" % (outcome.get("stage", "error"),
                                           outcome.get("refusal") or outcome.get("error"))
            record["sql"] = outcome.get("sql")
        else:
            gold = con.execute(case["gold_sql"]).fetch_df()
            ok, why = results_match(gold, outcome["dataframe"])
            record["passed"] = ok
            record["detail"] = "" if ok else why
            record["sql"] = outcome["sql"]

        results.append(record)
        print("%-5s %-22s %s%s" % (
            cid, record["category"],
            "PASS" if record["passed"] else "FAIL",
            "" if record["passed"] else "  (%s)" % record["detail"][:90]))

    elapsed = time.time() - started
    passed = sum(1 for r in results if r["passed"])
    retried = sum(1 for r in results if r["retried"])

    print("\n%d/%d passed (%.0f%%) in %.0fs" %
          (passed, len(results), 100.0 * passed / len(results), elapsed))
    print("%d answers required the automatic retry" % retried)

    by_cat: Dict[str, List[bool]] = {}
    for r in results:
        by_cat.setdefault(r["category"], []).append(r["passed"])
    print("\nby category:")
    for cat, vals in sorted(by_cat.items()):
        print("  %-22s %d/%d" % (cat, sum(vals), len(vals)))

    out = os.path.join(ROOT, "eval", "results_%s.json" % provider)
    with open(out, "w") as f:
        json.dump({"provider": provider, "model": model, "passed": passed,
                   "total": len(results), "elapsed_seconds": round(elapsed, 1),
                   "results": results}, f, indent=2)
    print("\nwrote %s" % os.path.relpath(out, ROOT))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
