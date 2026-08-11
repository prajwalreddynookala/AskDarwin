# AskDarwin — approach, key decisions, and what I'd build next

**Sai Prajwal Reddy Nookala** · Live: **prajwalsaskdarwin.streamlit.app** ·
Repo: **github.com/prajwalreddynookala/AskDarwin**

## The user, because the brief didn't name one

**An HR Business Partner who can't write a formula.** She files a request for "attrition in
Sales by tenure band," waits three days, gets a static slide. The real cost isn't the wait —
it's the **questions never asked**, because when asking is expensive people stop, and the
organisation runs on intuition.

A second user shapes the design: **the analyst**, a queue rather than a skill gap, blamed
when a number is wrong. HRBP *asks*, analyst *verifies* — which is why the SQL is shown, not
hidden.

## Approach

The brief left "correct" undefined. I defined it: **computed from source data by executable
code, reproducible, query visible** — not "the model sounded confident."

That killed the obvious build, since pasting rows into a prompt hallucinates arithmetic. So
**the model never sees the data. It sees the schema, writes SQL, and DuckDB does every
calculation.** The constraint helped: schema-to-SQL is narrow enough for a small open-weights
model; analytical reasoning isn't.

## Key decisions

**Schema-only, with one exception.** Sample values go only from low-cardinality categorical
columns — never names, IDs, salary. The model must know `department` holds `"Sales"` not
`"SLS"`. The app shows the literal payload, so privacy is inspectable, not promised.

**Join inference, surfaced.** Files arrive with no declared relationships. The system infers
them from name similarity *and* real value overlap, then shows what it decided. A silently
wrong join returns a confidently wrong number.

**It refuses** when the data can't answer. A plausible wrong number is more dangerous than
none.

## How I know it works

17 gold-query questions, execution accuracy: **100% on `gpt-oss-120b`, 71% on a local 7B.** A
generality probe on what it wasn't built for — new domain, multi-sheet Excel, messy columns —
answered 8/8, five verified exactly. The harness caught three things:

- **My regression.** Detailed prompt guidance dropped accuracy 71% → 65%; two lines got 82%.
  Small models degrade when you add instructions.
- **My wrong gold query.** "Offer-to-join conversion rate" has no single meaning, so no ground
  truth could be right and the model's disagreement was correct. **That's the argument for a
  governed metric layer** — an undefined metric makes a correct system disagree with its own
  test, and two teams disagree in a board meeting.
- **A licence violation.** My local model was non-commercial, not open source. I swapped it
  and re-measured *downward*, 82% → 71%.

17 questions is a smoke test, not a benchmark.

## What I'd measure

North star: **trusted self-serve answers per HRBP per month** — answered *and* not escalated
back to the queue. Not "questions asked," which rewards confusion.

The one I'd watch: **SQL-expand rate.** High early means checking; staying high means
distrust; falling while acceptance holds means trust earned. Guardrails: refusal rate
(two-sided), join-override rate as early warning, analyst requests deflected as the number
that funds the product.

## What I'd build next

**v2 — trust and fit.** Follow-ups (the cut I'd reverse first), editable join keys, a **live
connection to Darwinbox tables that removes the export step**, **row-level access control by
asker identity**, audit log. Access control is what a general assistant structurally cannot
do — whoever holds an exported file sees every salary in it.

**v3 — governed semantics.** One company definition of "attrition" matching the board deck. My
clearest eval failure — summing every historical salary row instead of the latest — is exactly
what a semantic layer fixes.

**Not on the roadmap:** predictive attrition scoring. Observational data doesn't support the
causal claim, and the fairness exposure is real.

**Cut deliberately:** follow-ups, auth, persistence, semantic layer, forecasting, data-quality
repair (flagged, never silently fixed), visual polish. All models open-weights Apache 2.0; no
paid APIs or metered credits.
