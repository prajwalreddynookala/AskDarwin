# AskDarwin — approach, decisions, and what's next

**github.com/prajwalreddynookala/AskDarwin** · Sai Prajwal Reddy Nookala

Upload CSV/Excel files, ask a question in plain English, get an answer with the query that
produced it.

## Approach

The brief left "correct" undefined, and everything followed from how I defined it: **an
answer is correct if it was computed from the source data by executable code, is
reproducible, and the user can see the query** — not "the model sounded confident."

That eliminated the obvious build. Pasting rows into the prompt hallucinates arithmetic,
breaks past context limits, and produces numbers nobody can check. So **the model never
sees the data. It sees the schema, writes DuckDB SQL, and the database does every
calculation.**

```
question + schema → open-weights LLM → SQL → validated → executed → answer + chart + the SQL
```

This also resolved the constraint: schema-to-SQL is narrow enough for a small open-weights
model, whereas analytical reasoning is not. "No paid APIs" pushed me toward the more
correct architecture, not away from it.

## Key decisions

**Schema-only, with a deliberate exception.** The model gets column names, types, null
rates and cardinality — plus sample values *only* from low-cardinality categorical columns,
never names, IDs, salary or free text. It needs to know `department` holds `"Sales"` not
`"SLS"` to write a correct filter. The app shows you the literal payload it sends.

**Join inference, surfaced not hidden.** Files arrive with no declared relationships, so
the system infers them from name similarity *and* actual value overlap, scores confidence,
and shows what it decided. A silently wrong join produces a confidently wrong number — the
worst failure an analytics tool has. Many-to-many candidates are dropped when a shared
dimension exists, since fan-out joins corrupt every aggregate.

**Guardrails from observed failures.** The first smoke test emitted MySQL `DATEDIFF()`,
invalid in DuckDB. Hence dialect grounding, execute-and-retry feeding the engine's own
error back once, output sanitising, and SELECT-only validation — the correctness guard
*and* the security guard, since generated SQL is about to execute.

**Correctness is measured**, not asserted: 17 questions with hand-written gold queries,
scored on execution accuracy. **82% on a local 3B model.** Aggregation, filtering, ranking,
comparison, trend and refusal all pass; **cross-file joins are weakest (2/4)** — the hard
category, where I expected to be weak.

The harness's most useful catch was my own regression: adding detailed prompt guidance
dropped accuracy from 71% to 65% and made the model hallucinate table names. Cutting it to
two lines got 82%. **Small models degrade when you add instructions** — I'd have shipped
that as an improvement.

## Cut deliberately

Conversational follow-ups · auth and persistence · semantic layer · forecasting and causal
"why" questions · data-quality repair (flagged, never silently fixed) · visual polish.
Design effort went entirely into the answer card and the review step.

## What I'd build next

**v2 — trust and fit.** Follow-up questions; editable join keys; a live connection to
Darwinbox tables that removes the export step; **row-level access control by asker
identity**; an audit log. Access control is the thing a general assistant structurally
cannot do — whoever holds an exported file sees every salary in it.

**v3 — governed semantics.** One company-defined meaning for "attrition" that matches the
board deck, with certified metrics separated from ad-hoc exploration. My clearest eval
failure — summing every historical salary row instead of the latest per employee — is
exactly what a semantic layer exists to fix.

**Not on the roadmap:** predictive attrition scoring. Observational HR data doesn't support
the causal claims it implies, and the fairness exposure is real.

## Assumptions

Open-weights models only — Groq's free tier (no card, open models) hosted, local Ollama
offline. No paid APIs or metered credits. AI coding tools were used to build it, as the
brief encourages. Files up to ~100k rows are held in memory; beyond that the execution
layer needs a warehouse, though the NL-to-SQL layer is unchanged.
