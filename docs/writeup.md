# AskDarwin — approach, decisions, and what's next

**Repo:** github.com/prajwalreddynookala/AskDarwin · **Sai Prajwal Reddy Nookala**

Upload CSV/Excel files, ask a question in plain English, get an answer with the query that
produced it.

## Approach

The brief left "correct" undefined, and everything followed from how I defined it:
**an answer is correct if it was computed from the source data by executable code, is
reproducible, and the user can see the query.** Not "the model sounded confident."

That eliminated the obvious build — paste rows into the prompt and let the model answer.
LLMs hallucinate arithmetic, break past context limits, and produce numbers nobody can
check. So: **the model never sees the data. It sees the schema, writes DuckDB SQL, and the
database does every calculation.**

```
question + schema → open-weights LLM → SQL → validated → executed → answer + chart + the SQL
```

This also solved the constraint. Schema-to-SQL is a narrow enough task for a small
open-weights model, whereas analytical reasoning is not — the "no paid APIs" limit pushed
me toward the more correct architecture, not away from it.

## Key decisions

**Schema-only, with a deliberate exception.** The model receives table and column names,
types, null rates, cardinality — and sample values *only* from low-cardinality categorical
columns, never names, IDs, salary or free text. It needs to know `department` contains
`"Sales"` not `"SLS"` to write a correct filter. HR data is the most sensitive data an
enterprise holds, so the app shows you the literal payload it sends.

**Join inference, surfaced not hidden.** Files arrive with no declared relationships, so
the system infers them from column-name similarity *and* actual value overlap, scores its
confidence, and shows you what it decided. A silently wrong join produces a confidently
wrong number — the worst failure an analytics tool has. Many-to-many candidates are dropped
when a shared dimension exists, because fan-out joins silently corrupt every aggregate.

**Guardrails built from observed failures, not guesses.** The first smoke test produced
MySQL's `DATEDIFF()`, invalid in DuckDB. So: dialect grounding in the prompt, execute-and-
retry feeding the engine's own error back once, output sanitising, and SELECT-only
validation — which is the correctness guard *and* the security guard, since generated SQL
is about to be executed.

**Correctness is measured.** 17 questions with hand-written gold queries, scored on
execution accuracy. **82% on a local 3B model** — aggregation, filtering, ranking,
comparison, trend and refusal all pass; **cross-file joins are the weak category (2/4)**,
which is the hard one and where I expected to be weak.

The most useful thing the harness caught: my own "improvement" made it worse. Adding
detailed prompt guidance dropped accuracy from 71% to 65% and made the model hallucinate
table names. Cutting it to two lines got 82%. **A small model degrades when you add
instructions** — I'd have shipped the regression as a win.

## Scope I deliberately cut

Conversational follow-ups · auth and persistence · a semantic layer · forecasting and
causal "why" questions · data-quality repair (detected and flagged, never silently fixed) ·
visual polish. Design effort went entirely into the answer card and the review step.

## What I'd build next

**v2 — trust and fit.** Follow-up questions; user-editable join keys; a live connection to
Darwinbox tables that removes the export step entirely; **row-level access control by asker
identity**; an audit log. Access control is the one thing a general assistant structurally
cannot do — whoever holds the exported file sees every salary in it.

**v3 — governed semantics.** A metric layer where "attrition" has one company-defined
meaning that matches the board deck, separating certified metrics from ad-hoc exploration.
The clearest eval failure — summing every historical salary row instead of the latest per
employee — is exactly the problem a semantic layer exists to solve.

**Not on the roadmap:** predictive attrition scoring. Observational HR data doesn't support
the causal claims it implies, and the fairness and legal exposure is real. That's a product
decision, not a technical limit.

## Assumptions

Open-weights models throughout: Groq's free tier (no credit card, open models only) for the
hosted demo, local Ollama for offline use — no paid APIs or metered credits either way.
AI coding tools were used to build it, as the brief encourages. Files up to ~100k rows are
held in memory; beyond that the execution layer needs a warehouse, though the NL-to-SQL
layer would be unchanged.
