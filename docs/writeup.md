# AskDarwin — approach, key decisions, and what I'd build next

**Sai Prajwal Reddy Nookala** · Live: **prajwalsaskdarwin.streamlit.app** ·
Repo: **github.com/prajwalreddynookala/AskDarwin**

## The user, because the brief didn't name one

**An HR Business Partner who cannot write a formula.** When she needs "attrition in Sales
last two quarters by tenure band," she files a request, waits three days, and gets a static
slide. The follow-up costs another three days. The real cost isn't the waiting — it's the
**questions that never get asked**, because when asking is expensive people stop asking and
the organisation runs on intuition.

A second user shapes the design: **the analyst**, who is a queue rather than a skill gap, and
who gets blamed when a number is wrong. The HRBP *asks*, the analyst *verifies* — which is
exactly why the generated SQL is shown rather than hidden.

## Approach

The brief left "correct" undefined, and everything followed from how I defined it: **an
answer is correct if it was computed from source data by executable code, is reproducible,
and the user can see the query** — not "the model sounded confident."

That eliminated the obvious build. Pasting rows into a prompt hallucinates arithmetic and
produces numbers nobody can check. So **the model never sees the data. It sees the schema,
writes SQL, and DuckDB does every calculation.** The constraint helped: schema-to-SQL is
narrow enough for a small open-weights model, whereas analytical reasoning is not.

## Key decisions

**Schema-only, with a deliberate exception.** Sample values reach the model only from
low-cardinality categorical columns — never names, IDs or salary. The model must know
`department` holds `"Sales"` not `"SLS"` to filter correctly. The app displays the literal
payload, so privacy is inspectable rather than promised.

**Join inference, surfaced not hidden.** Files arrive with no declared relationships, so the
system infers them from name similarity *and* real value overlap, then shows what it decided.
A silently wrong join returns a confidently wrong number — the worst failure this tool has.

**It refuses** when the data can't answer the question. A plausible wrong number is more
dangerous than no number.

## How I know it works

17 questions with hand-written gold queries, scored on execution accuracy: **100% on
`gpt-oss-120b`, 71% on a local 7B.** A separate generality probe — different domain,
multi-sheet Excel, messy columns, fresh questions — answered 8/8, five verified exactly. The
harness earned its keep three times:

- **It caught my regression.** Detailed prompt guidance dropped accuracy 71% → 65%; two lines
  instead got 82%. Small models degrade when you add instructions — I'd have shipped that as
  an improvement.
- **It caught a wrong gold query.** I'd asked for "offer-to-join conversion rate," a phrase
  with no single meaning, so no ground truth could be right and the model's disagreement was
  correct. **That is the clearest argument for a governed metric layer** — an undefined metric
  makes a correct system disagree with its own test, and in production makes two teams
  disagree in a board meeting.
- **A licence audit caught a violation.** My local model was under a non-commercial research
  licence. I swapped it and **re-measured downward**, 82% → 71%, rather than keep the better
  number.

Stated plainly: 17 questions is a smoke test, not a benchmark.

## What I'd measure

North star: **trusted self-serve answers per HRBP per month** — answered *and* not escalated
back to the analyst queue. Not "questions asked," which rewards confusion.

The metric I'd watch is **SQL-expand rate**: high early means users are checking; staying high
means they don't trust it; falling while acceptance holds means trust is earned. Guardrails:
refusal rate (two-sided — too high is useless, too low is guessing), join-override rate as
early warning that inference is failing, and analyst requests deflected as the number that
funds the product.

## What I'd build next

**v2 — trust and fit.** Follow-up questions (the cut I'd reverse first); editable join keys; a
**live connection to Darwinbox tables that removes the export step**; **row-level access
control by asker identity**; an audit log. Access control is the thing a general assistant
structurally cannot do — whoever holds an exported file sees every salary in it.

**v3 — governed semantics.** One company-defined meaning for "attrition" that matches the
board deck. My clearest eval failure — summing every historical salary row instead of the
latest per employee — is exactly what a semantic layer fixes.

**Not on the roadmap:** predictive attrition scoring. Observational HR data doesn't support
the causal claims it implies, and the fairness exposure is real.

**Cut deliberately:** follow-ups, auth, persistence, semantic layer, forecasting, data-quality
repair (flagged, never silently fixed), visual polish. All models are open-weights and Apache
2.0; no paid APIs or metered credits.
