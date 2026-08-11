# AskDarwin — Panel Prep Doc

*Long-form reasoning. The submitted write-up (`docs/writeup.md`) is a 1-page compression
of this. This document is the ammunition for the panel conversation.*

Product: **AskDarwin** — ask your HR spreadsheets anything.
Task: Darwinbox PM (Data) take-home — an AI-powered data Q&A web app.

---

## Stage 1 — Framing: what the brief didn't say

The brief is deliberately underspecified. Ten things it leaves open, and what I decided.

| # | Ambiguity | Decision | Why it matters |
|---|---|---|---|
| 1 | **Who is the user?** Never stated. | HRBP as primary asker; HR/People Analyst as the verifier who has to trust the output. | Determines whether the interface is natural language or a query builder, and whether "show your working" is mandatory. |
| 2 | **What data domain?** Any CSV, per the brief. | Engine domain-agnostic; demo, dataset and narrative are HR. | The brief asks for "reasonably general" capability, so crippling the engine would fail it. A specific demo makes the value legible. |
| 3 | **What does "correct" mean?** Undefined — and it's the crux. | Correct = **computed from source data by executable code**, **reproducible**, and the user can **see the query**. Not "the model sounded confident." | This single definition drives the entire architecture. |
| 4 | **How big is the data?** Unstated. | Up to ~100k rows / ~50MB, held in memory. No warehouse. | Sets the ceiling on in-memory execution. Above it, a different backend — stated, not ignored. |
| 5 | **How do the files relate?** Cross-file analysis required, no keys given. | **Infer join keys**, then **show the user what was inferred** and let them correct it. | Hardest acceptance criterion. Silent joins produce silently wrong numbers. |
| 6 | **Single question or conversation?** Ambiguous. | Single-shot per question; history visible but not used as context. | Follow-ups are real, but a v2 feature. Cutting protects the budget. |
| 7 | **Where does the data live?** Unstated. | **Schema-only.** Rows never sent to the model. | HR data is salary, performance, medical leave. Not just an assumption — the product's main argument for existing. |
| 8 | **Excel specifics** — multi-sheet, merged cells, headers? | First row is the header; each sheet is its own table; pivot-style layouts flagged, not parsed. | Real HR exports are messy; failing loudly beats failing quietly. |
| 9 | **Auth, persistence, multi-user?** Unstated. | Out of scope. Single session. | Not what's being tested; would eat the entire budget. |
| 10 | **How general is "reasonably general"?** | Seven named question classes (below). | Turns a vague criterion into a testable definition of done. |

### The question taxonomy — the definition of "done"

Doubles as the evaluation set in Stage 9.

1. **Aggregation** — "What's the total payroll cost?"
2. **Filtered aggregation** — "Average tenure in Sales?"
3. **Group-by** — "Headcount by department"
4. **Ranking** — "Top 5 departments by attrition"
5. **Comparison** — "Average salary of top-rated vs bottom-rated employees"
6. **Trend** — "Monthly absenteeism over the last year"
7. **Cross-file join** — any of the above spanning two or more files

**Out of scope by design:** forecasting, causal "why" questions, ML, anything requiring
data not uploaded.

### The riskiest assumption

**That join-key inference is reliable enough to trust.** A silently wrong key produces
confidently wrong numbers — the worst failure an analytics tool has. Mitigated by making
the inferred relationship visible, overridable, and by surfacing row counts so a bad join
is obvious on sight.

**Panel questions**

> *"The brief didn't name a user. How did you pick one?"* — Two candidates: the HRBP who
can't write formulas, and the analyst drowning in requests. I picked both in different
roles. That's not a hedge: if only the HRBP mattered I'd hide the SQL; because the analyst
has to trust it, I show it.

> *"What does correct mean to you?"* — Reproducible and traceable, not plausible. Every
number comes from executed code over source data, and the user can see that code. An LLM
doing arithmetic in its head is unfalsifiable, and an unfalsifiable number is worse than
no number.

> *"What's your riskiest assumption?"* — Join inference. See above.

---

## Stage 2 — User and job to be done

**Primary: the HR Business Partner.** Non-technical, lives in Excel, owns a business
unit's people outcomes. Cannot write SQL and mostly cannot write a VLOOKUP.

> *When* I need a people number to make or defend a decision,
> *I want* to get it myself without filing a request,
> *so that* I can move at the speed of the conversation I'm in.

**Secondary: the HR / People Analyst.** Can write SQL. Is not the bottleneck because they
lack skill — they're the bottleneck because they're a queue.

> *When* an HRBP asks me for a number,
> *I want* them to self-serve the routine ones,
> *so that* I can work on analysis only I can do.

**Why the pairing changes the product.** The HRBP is the *asker*; the analyst is the
*verifier* and the person who gets blamed when a number is wrong. That duality is the
entire reason the generated SQL is surfaced in the UI instead of hidden. A product built
for the HRBP alone would hide it as clutter. A product built for the analyst alone
wouldn't need natural language at all.

**Panel questions**

> *"Isn't showing SQL to a non-technical user just noise?"* — It's collapsed by default,
so it costs the HRBP nothing. But it's what lets the analyst sign off on a number without
recomputing it, and it's what turns "the tool said so" into "here's the logic." In
analytics, trust is a feature with a UI.

> *"Which persona would you cut if you had to?"* — Neither, because they're one workflow.
If forced: cut the analyst as a *user* but keep them as the *design constraint*.

---

## Stage 3 — Pain and opportunity

**The problem is a queue, not a capability gap.** Today an HRBP needing "attrition in
Sales for the last two quarters, split by tenure band" files a request with the HR
analytics team. It takes days. The answer arrives as a static slide. The obvious follow-up
question starts the cycle again.

Three costs, and only the first is obvious:

1. **Latency** — decisions get made before the data arrives, or without it
2. **Analyst opportunity cost** — senior analysts spend their week on lookups
3. **Questions that never get asked** — the real cost. If asking is expensive, people stop
   asking, and the organisation runs on intuition. Unmeasurable and the largest of the three

**Why a data team owns this**, not a feature team: the hard parts are grain, join
correctness, metric definitions and data quality — data problems, not UI problems.

**Why Darwinbox specifically.** HR data is *structurally* multi-file — employee master,
attendance, payroll, performance, recruitment all live in separate systems and separate
exports. Every interesting HR question is a join. That's precisely the acceptance
criterion the brief flags as hardest, and it's not a coincidence.

**Panel questions**

> *"How would you size this?"* — Bottom-up: number of HRBPs × ad-hoc requests per month ×
analyst hours per request gives you hard cost. The soft cost — unasked questions — I'd
measure post-launch as growth in total questions asked per HRBP, which is only visible
once asking is cheap.

> *"Why hasn't this been solved by BI dashboards?"* — Dashboards answer questions someone
anticipated. The request queue exists precisely for the ones nobody anticipated. This
product targets the long tail, which is why natural language is the right interface and
why a dashboard isn't a competitor.

---

## Stage 4 — Solution space, and the axis that collapses it

Every approach differs on one question: **where does the arithmetic happen?**

| | Approach | Computation lives in | Verdict |
|---|---|---|---|
| A | Data-in-prompt — paste rows, model answers | The model's head | ❌ Hallucinated arithmetic, context limits, unverifiable, all data exposed |
| B | **Schema → generated code → execute** | A deterministic engine | ✅ **Chosen** |
| C | Semantic layer — fixed metric catalog | Pre-built definitions | ❌ v1 (needs known schema) → ✅ **v3 direction** |
| D | RAG over rows | The model's head, on *retrieved* rows | ❌ Retrieval returns *some* rows; aggregation needs *all* |
| E | Fine-tuned text-to-SQL model | Deterministic engine | ❌ No time, no training data. A lever if accuracy stalls |
| F | Agentic multi-step planner | Deterministic engine | ❌ Over-built for 6h; small models plan unreliably |

Once "correct" means reproducible arithmetic, **A and D are eliminated immediately** —
computation cannot live in the model. C is the right long-term answer but impossible
against arbitrary uploads. That leaves B; E and F are refinements of B.

**Within B, SQL over pandas:** SQL can be constrained to a single `SELECT` and validated,
whereas generated Python is arbitrary code execution. And the verifier persona already
reads SQL.

---

## Stage 5 — Scope and the cut list

**Built (v1):** multi-file CSV/Excel upload · schema profiling with PII rules · join
inference with confidence · NL → DuckDB SQL · SELECT-only validation · execute-and-retry ·
deterministic charts · answer card with SQL and provenance · explicit refusal path ·
transparency panel · eval harness.

**Deliberately cut**, with reasons — this list is a scoring artefact, not an apology:

| Cut | Why |
|---|---|
| **Conversational follow-ups** | ~20 min plus new failure modes on a small model. A correct single-shot answer beats a fluent conversation containing a wrong number. First thing I'd build next. |
| **Auth and multi-user** | Not what's being tested; would consume the whole budget |
| **Persistence / saved questions** | Real value, zero learning — pure engineering time |
| **Semantic layer** | The correct long-term answer, impossible against arbitrary uploads. Roadmap v3 |
| **Forecasting and "why" questions** | Different product. Causal inference over observational HR data is a trap and I'd rather refuse than guess |
| **Self-join inference** (`manager_id → employee_id`) | Real gap; the model often infers it anyway from column names |
| **Data-quality repair** | We *detect* and flag; we don't fix. Silent repair is how you get wrong numbers |
| **Polished visual design** | Design effort went entirely into the answer card. No Figma at this budget |

**Panel question**

> *"What would you cut if you had two hours instead of six?"* — Join inference and the
transparency panel, and I'd ship single-file only. I'd keep the eval harness, because
without it I don't know whether anything works.

---

## Stage 6 — Decision log

| Decision | Chosen | Rejected | Cost paid |
|---|---|---|---|
| Where computation happens | Generated SQL, executed | Model computes | Can't answer fuzzy/semantic questions |
| Query language | SQL (DuckDB) | pandas | Slightly less expressive |
| What the model sees | Schema + selective samples | Full rows / no samples | Model can't see value formats in redacted columns |
| Join handling | Infer, score, **show for correction** | Auto-join silently / ask user always | An extra review step before asking |
| Chart selection | Deterministic, from result shape | Model picks | Occasionally a duller chart than a human would choose |
| Failure behaviour | Explicit refusal | Best-effort guess | Over-refusal risk — which the eval caught |
| Model provider | Groq free tier + local Ollama | Single provider | Two paths to test |
| Delivery | Hosted link + local instructions | One or the other | Deploy time |

**On sample values — the subtle one.** Samples *are* data. But the model needs to know
`department` contains `"Sales"` not `"SLS"`, or it can't write a correct `WHERE`. So it's
a dial, not a switch: samples only for **low-cardinality categorical columns**, never for
names, IDs, salary, or free text (`PII_PATTERNS` in `app/ingest.py`). This is what makes
hosting an HR tool defensible.

---

## Stage 7 — Design

Design effort went entirely into **the answer card** and **the review step**. Zero into
branding.

**The flow is deliberately three steps, not two:** upload → *review what was understood* →
ask. The middle step exists because the product's real risk isn't failing to answer, it's
answering confidently from a relationship it guessed wrong.

**The answer card** carries: the number or table · a chart when the result shape warrants
it · rows returned, rows scanned, tables used, elapsed time · the generated SQL, collapsed
· and, when a retry happened, the failed attempt and its error.

**States designed explicitly**, not as error handling:
- *Refusal* — "I can't answer that from these files," with what's missing
- *Empty result* — query valid, no rows matched. A different message from a failure
- *Failure after retry* — show the SQL that failed and why
- *Data quality* — flags surfaced at upload, before any question is asked

---

## Stage 8 — Build and what the evaluation caught

Stack: Streamlit · DuckDB · pandas · Plotly · Groq free tier / local Ollama.
Demo dataset: 5 files, 10,067 rows, spanning hiring → in-role → exit.

**Four guardrails, each built in response to an observed failure**, not anticipated:

1. **Dialect grounding** — the first smoke test produced MySQL `DATEDIFF()`, invalid in DuckDB
2. **Execute-and-retry** — feed the engine's error back once. The DB's own error message is
   a better correction signal than any prompt wording
3. **Output sanitising** — strips fences and preamble
4. **SELECT-only validation** — correctness guard *and* security guard, since generated SQL
   is about to execute. DuckDB additionally runs with external access disabled

### The eval result — and the fix that made it worse

| Attempt | Prompt | Score | Finding |
|---|---|---|---|
| 1 | Baseline | **71%** (12/17) | Zero SQL errors. All failures semantic; 3 were *over-refusal* |
| 2 | Detailed guidance + worked examples | **65%** (11/17) | **Regressed.** Broke two passing cases, started hallucinating table names |
| 3 | Cut to two lines | **82%** (14/17) | Best. Over-refusal fixed without the noise |

**The lesson is counterintuitive: a 3B model gets *worse* when you add instructions.**
Instruction volume trades against instruction adherence. Without the harness, attempt 2
ships as an "improvement."

**By category:** aggregation 2/2 · filtered aggregation 2/2 · comparison 2/2 · ranking 2/2 ·
trend 1/1 · refusal 2/2 · **cross-file join 2/4**.

**Remaining failures**, all cross-file grain problems: a SQL alias binder error; an
integer-division bug in a conversion rate; and summing *all* historical salary rows instead
of the latest per employee. That last one is the clearest argument for a semantic layer.

---

## Stage 9 — Metrics and instrumentation

**North star: trusted self-serve answers per active HRBP per month.** Not "questions
asked" — that rewards confusion. Trusted means answered *and* not escalated to the analyst
queue afterwards.

| Layer | Metric | Why |
|---|---|---|
| **Activation** | % of uploads reaching a first answered question; time-to-first-answer | If they upload and bounce, the schema step is too heavy |
| **Engagement** | Questions per session; weekly repeat askers | Repeat use is the only real signal of trust |
| **Quality** | Execution success rate · refusal rate · retry rate · answer acceptance | Refusal rate is two-sided: too high means over-refusal, too low means guessing |
| **Trust** | **SQL-expand rate** | The most interesting metric in the product — see below |
| **Guardrail** | p95 latency · wrong-answer reports · join-override rate | Join overrides tell you inference is failing before users complain |
| **Business** | Ad-hoc requests deflected from the analyst queue; analyst hours returned | The number that funds the product |

**Why SQL-expand rate is the metric I'd watch.** Early on it should be *high* — users are
checking the tool. If it stays high, they don't trust it. If it falls while acceptance
stays high, trust has been earned. If it falls while acceptance falls too, they've given
up checking and are about to get burned. It's the rare metric where the *direction of
travel* matters more than the level.

### Event instrumentation spec

```
file_uploaded        {file_count, total_rows, total_columns, has_excel, bytes}
schema_profiled      {tables, columns, pii_columns_redacted, quality_flags}
joins_inferred       {count, max_confidence, min_confidence}
join_overridden      {from_key, to_key}            -- inference failure signal
question_asked       {source: typed|suggested, char_length}
sql_generated        {provider, model, latency_ms}
sql_validation_failed{reason}                       -- security/robustness signal
query_executed       {success, retry_count, rows_returned, rows_scanned, duration_ms, table_count}
answer_rendered      {chart_kind}
answer_refused       {reason_category}
sql_expanded         {}                             -- the trust signal
answer_feedback      {helpful: bool}
```

**Panel question**

> *"What would you instrument first if you could only have one event?"* —
`query_executed`, with `success`, `retry_count` and `table_count`. It tells me whether the
product works, how hard it's working, and whether cross-file questions — the hard ones —
are being attempted at all.

---

## Stage 10 — Risks, failure modes, governance

| Risk | Impact | Mitigation |
|---|---|---|
| **Wrong join inferred** | Confidently wrong numbers | Confidence scored, shown, overridable; many-to-many fan-outs dropped when a shared dimension exists |
| **Wrong grain** (summing history) | Inflated totals | *Observed in eval.* Semantic layer is the real fix; currently prompt guidance |
| **Over-refusal** | Product feels useless | *Observed and fixed*; refusal rate is a tracked metric |
| **Dirty data** | Misleading aggregates | Quality flags surfaced at upload; detected, never silently repaired |
| **Generated SQL is untrusted input** | Code execution | SELECT-only validation, single statement, DuckDB external access disabled |
| **Ambiguous questions** | Plausible answer to the wrong question | SQL is shown so the interpretation is visible |
| **Model/provider drift** | Silent quality regression | Eval harness is re-runnable; would be CI in production |

**Governance and PII — the part a generalist would skip.** HR data is the most sensitive
data an enterprise holds: salary, performance, medical leave, disciplinary records.

- **Schema-only architecture** means rows never reach the model. Demonstrable in-product
  via the transparency panel, not merely claimed
- **PII pattern rules** prevent value sampling from name/email/salary/free-text columns
- **Not built, and named as such:** row-level access control by asker identity, audit
  logging, data residency guarantees, retention policy. These are v2 table stakes for
  enterprise and the honest boundary of a 6-hour prototype

**Access control deserves a specific mention** because it's the one thing a general
assistant can never do: a CHRO can see all compensation, a line manager only their team.
Whoever holds the exported file sees everything in it. Permission-aware answering is
structurally impossible in the chat-assistant model and is the core of why this is a
product.

---

## Stage 11 — Roadmap

Each stage retires a *named* risk rather than adding features.

**v1 (built)** — prove the engine: schema-only NL→SQL, join inference, measured accuracy.
*Retires: "can this be made correct at all?"*

**v2 — trust and fit (next 4–6 weeks)**
- Conversational follow-ups (the documented cut)
- Self-join inference and user-editable join keys
- Live connection to Darwinbox tables — **removes the export step, which is the real
  product unlock**
- Row-level access control by asker identity; audit log of every question and query
- Answer feedback loop feeding the eval set
*Retires: "is it safe and usable inside an enterprise?"*

**v3 — governed semantics (quarter after)**
- **Semantic layer**: company-defined metrics — attrition, headcount, time-to-hire — so
  "attrition" means one thing across the org and matches the board deck
- Certified metrics vs ad-hoc exploration, visually distinguished
- Scheduled questions and alerting on metric movement
*Retires: "do two people asking the same question get the same number?"*

**Explicitly not on the roadmap:** predictive attrition scoring. Suggesting who will resign
creates severe fairness, legal and employee-relations exposure, and observational HR data
does not support the causal claims such a feature implies. Refusing it is a product
decision, not a technical limitation.

---

## Positioning: why not just use ChatGPT?

Concede the premise — a general assistant *can* do this. The differentiation is never
model capability:

1. **The data legally can't go there** — DPA, enterprise IT policy, GDPR / India DPDP
   cross-border transfer of employee data nobody consented to. Procurement blocks it
2. **Somebody had to export the file** — manual, instantly stale, disconnected from the
   system of record. *In this prototype, upload is a stand-in for a connection*
3. **Definitions drift silently** — "attrition" three ways in three sessions, never disclosed
4. **Access control** — a general assistant has no notion of who is asking
5. **Org-level auditability** — a personal chat history is not an audit trail

> *ChatGPT answers the question once, for one person, on a file they had to export. A data
> product answers it consistently, for everyone, on data nobody exported — and shows each
> person only what they're allowed to see.*

**Expected counter:** *"So your differentiation is everything you didn't build."* — The
prototype proves the engine under real constraints: schema-only architecture with PII rules
in code, join inference surfaced for correction, a measured accuracy number. The enterprise
wrapper is scoped out of six hours and named on the roadmap.
