# AskDarwin — approach, key decisions, and what I'd build next

**Sai Prajwal Reddy Nookala** · Live: **prajwalsaskdarwin.streamlit.app** ·
Repo: **github.com/prajwalreddynookala/AskDarwin**

## The user, because the brief didn't name one

**An HR Business Partner who can't write a formula.** She requests "attrition in Sales by
tenure band," waits three days, gets a static slide. The real cost isn't the wait — it's the
**questions never asked**: when asking is expensive, people stop, and the organisation runs
on intuition.

**The analyst** shapes the design too — a queue, not a skill gap, and blamed when a number is
wrong. HRBP *asks*, analyst *verifies*. That is why the SQL is shown, not hidden.

## Approach

The brief left "correct" undefined. I defined it: **computed by executable code,
reproducible, query visible** — not "the model sounded confident." That killed the obvious
build, since rows in a prompt hallucinate arithmetic.

**The model never sees the data. It sees the schema, writes SQL, DuckDB computes.** The
constraint helped: schema-to-SQL suits a small open-weights model; analytical reasoning
doesn't.

## Key decisions

**Schema-only, one exception.** Sample values go only from low-cardinality categorical
columns — never names, IDs, salary. The model must know `department` holds `"Sales"` not
`"SLS"`. The app shows the literal payload, so privacy is inspectable.

**Join inference, surfaced.** Files arrive with no declared relationships. The system infers
them from name similarity *and* real value overlap, then shows its decision. A silent wrong
join returns a confident wrong number.

**It refuses** when the data can't answer. A plausible wrong number is more dangerous than
none.

## How I know it works

17 gold-query questions, execution accuracy: **100% on `gpt-oss-120b`, 71% on a local 7B.** A
generality probe — new domain, multi-sheet Excel, messy columns — answered 8/8, five verified
exactly. The harness caught three things:

- **My regression.** Detailed prompt guidance dropped accuracy 71% → 65%; two lines got 82%.
  Small models degrade when you add instructions.
- **My wrong gold query.** "Offer-to-join conversion rate" has no single meaning, so no ground
  truth could be right and the model's disagreement was correct. **That's the argument for a
  governed metric layer:** an undefined metric makes a correct system disagree with its own
  test, and two teams disagree in a board meeting.
- **A licence violation.** My local model was non-commercial. I swapped it and re-measured
  *downward*, 82% → 71%.

17 questions is a smoke test, not a benchmark.

## What I'd measure

North star: **trusted self-serve answers per HRBP per month** — answered *and* not escalated
back. Not "questions asked," which rewards confusion. The one I'd watch: **SQL-expand rate** —
high early is checking, staying high is distrust, falling while acceptance holds is trust
earned. Guardrails: refusal rate (two-sided), join-override rate, analyst requests deflected.

## What I'd build next

**v2 — trust and fit.** Follow-ups (the cut I'd reverse first), editable join keys, a **live
connection to Darwinbox tables removing the export step**, **row-level access control by asker
identity**, audit log. Access control is what a general assistant structurally can't do —
whoever holds the file sees every salary.

**v3 — governed semantics.** One company definition of "attrition" matching the board deck. My
clearest eval failure — summing every historical salary row instead of the latest — is what a
semantic layer fixes.

**Not on the roadmap:** predictive attrition scoring. Observational data doesn't support the
causal claim, and the fairness exposure is real.

**Cut deliberately:** follow-ups, auth, persistence, semantic layer, forecasting, data-quality
repair, visual polish. All models open-weights Apache 2.0; no paid APIs.
