# AskDarwin

**Ask your HR spreadsheets anything.** Upload CSV or Excel files, ask a question in
plain English, get an answer — with the query that produced it.

**▶ Live demo: https://prajwalsaskdarwin.streamlit.app**

---

## Who this is for

The brief never named a user, so this is the first decision the product makes.

**Primary — the HR Business Partner.** Non-technical. Owns a business unit's people
outcomes. Lives in Excel, cannot write SQL and mostly cannot write a VLOOKUP.

> *When* I need a people number to make or defend a decision,
> *I want* to get it myself without filing a request,
> *so that* I can move at the speed of the conversation I am in.

**Secondary — the HR / People Analyst.** Can write SQL. Is not the bottleneck because
they lack skill; they are the bottleneck because they are a **queue**.

> *When* an HRBP asks me for a number,
> *I want* them to self-serve the routine ones,
> *so that* I can spend my time on analysis only I can do.

**Why the pairing is the whole design.** The HRBP *asks*; the analyst *verifies* and gets
blamed when a number is wrong. That duality is the reason the generated SQL is surfaced in
the interface instead of hidden. Built for the HRBP alone, you would hide the SQL as
clutter. Built for the analyst alone, you would not need natural language at all.

**The problem is a queue, not a capability gap.** Today an HRBP who needs "attrition in
Sales for the last two quarters, split by tenure band" files a request, waits days, and
receives a static slide. The obvious follow-up starts the cycle again. Three costs, and
only the first is visible:

1. **Latency** — decisions get made before the data arrives, or without it
2. **Analyst opportunity cost** — senior analysts spend their week on lookups
3. **Questions never asked** — the largest and least measurable. If asking is expensive,
   people stop asking, and the organisation runs on intuition

---

## The idea in one line

**The model never sees your data. It sees the schema, writes SQL, and DuckDB does the
arithmetic.**

That single decision is what makes an answer *correct* rather than merely plausible:
every number is computed by a database engine over your actual rows, and the query is
shown to you so you can check it.

```
question + schema  ──▶  open-weights LLM  ──▶  DuckDB SQL
                                                   │
                                    validated (SELECT-only)
                                                   │
                                    executed over your data
                                                   │
                              answer + chart + the SQL that produced it
```

## What it does

- **Multi-file upload** — several CSV/Excel files in one session; each Excel sheet
  becomes its own table
- **Cross-file analysis** — infers how your files relate by comparing column names
  *and* actual value overlap, then shows you what it inferred so you can catch a bad guess
- **Visual insights** — picks a chart from the shape of the result (single number, bar,
  line, grouped bar, table). Chart choice is deterministic, not model-generated
- **Says no** — if the uploaded files cannot answer the question, it says so instead of
  inventing a number
- **Shows its working** — the generated SQL, tables used, rows scanned, execution time

## Quick start

```bash
git clone https://github.com/prajwalreddynookala/AskDarwin.git
cd AskDarwin
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
python data/generate_demo_data.py      # writes the demo HR dataset
```

Then pick a model provider — either works, both are free and both run open-weights models.

**Option A — Groq free tier (no credit card, fastest):**

```bash
export GROQ_API_KEY=your_free_key_from_console.groq.com
./.venv/bin/streamlit run app/main.py
```

**Option B — fully local with Ollama (no account, works offline):**

```bash
ollama pull qwen2.5-coder:7b
ASKDARWIN_PROVIDER=ollama ./.venv/bin/streamlit run app/main.py
```

On a memory-constrained machine use `qwen2.5-coder:1.5b` and set
`OLLAMA_MODEL=qwen2.5-coder:1.5b` — faster, less accurate. Both are Apache 2.0.

Open http://localhost:8501, click **Load demo HR dataset** in the sidebar, and ask
something. Or upload your own files.

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| UI | Streamlit | Fastest path to a working data app; file upload and dataframes built in |
| Execution | DuckDB | In-process SQL over pandas frames; fast joins, no server |
| Data handling | pandas, openpyxl | CSV and Excel parsing, type inference, profiling |
| Charts | Plotly | Rendered from result shape, chosen deterministically |
| Model (hosted) | Groq free tier — `openai/gpt-oss-120b` | Apache 2.0 open weights; no card, no metered billing |
| Model (local) | Ollama + `qwen2.5-coder:7b` | Apache 2.0; fully offline, zero accounts |
| Hosting | Streamlit Community Cloud | Free, deploys straight from a public GitHub repo |

No paid APIs, no metered credits, no vendor lock-in on the model layer — the provider
is a swap in [`app/llm.py`](app/llm.py).

**Runtime requirements:** Python 3.9+. No Node, no Docker, no database server, no
Homebrew. Everything runs in one virtualenv.

### How the pieces fit together

```
  ┌──────────────┐   upload CSV / XLSX
  │  Streamlit   │ ────────────────────────┐
  │  app/main.py │                         ▼
  └──────────────┘                 ┌────────────────┐
         ▲                         │ app/ingest.py  │  parse, normalise column names,
         │                         │                │  infer types, profile schema,
         │                         └───────┬────────┘  apply PII sampling rules
         │                                 ▼
         │                         ┌────────────────┐
         │                         │ app/joins.py   │  infer relationships from name
         │                         │                │  similarity + real value overlap
         │                         └───────┬────────┘
         │                                 ▼
         │   question + SCHEMA ONLY ┌────────────────┐   open-weights LLM
         │ ◀───────────────────────▶│  app/llm.py    │ ◀─────────────────▶ Groq / Ollama
         │                          └───────┬────────┘   (no rows ever sent)
         │                                  ▼ SQL
         │                          ┌────────────────┐
         │                          │ app/query.py   │  validate SELECT-only,
         │                          │                │  execute in DuckDB,
         │                          └───────┬────────┘  retry once on error
         │                                  ▼
         │                          ┌────────────────┐
         └──────────────────────────│ app/charts.py  │  pick a chart from result shape
            answer + chart + SQL    └────────────────┘  (deterministic, no model)
```

### What each module is responsible for

| Module | Responsibility | The interesting part |
|---|---|---|
| `app/ingest.py` | Read CSV/Excel, normalise column names, infer types, profile each table | Decides **which sample values may be sent** to the model — the privacy boundary lives here as `PII_PATTERNS` |
| `app/joins.py` | Work out how uploaded files relate | Scores candidates on **actual value overlap**, not just column names, and drops many-to-many fan-outs when a shared dimension exists |
| `app/llm.py` | Provider abstraction, prompting, sanitising, validation | Same interface for Groq and Ollama; also generates the dataset summary and the suggested questions |
| `app/query.py` | Execute generated SQL, orchestrate the retry | DuckDB runs with **external file and network access disabled** — generated SQL is untrusted input |
| `app/charts.py` | Choose a visual from the result shape | Deterministic rules, so the same question always renders the same way |
| `app/main.py` | The interface | Upload → **review what was understood** → ask → answer card |

### The three-step flow, and why it is not two

Upload → **review** → ask. The middle step exists because the product's real risk is not
failing to answer. It is answering confidently from a relationship it guessed wrong. So
before you can ask anything, the app shows you what it inferred and invites you to catch
a bad guess.

## How correctness is enforced

A small open-weights model writes usable SQL but makes predictable mistakes. Four
guardrails, each built in response to an observed failure:

1. **Dialect grounding** — DuckDB's date functions are pinned in the prompt with a
   worked example, because models reach for MySQL's `DATEDIFF()` by default
2. **Execute-and-retry** — if the query errors, the error text is fed back once and the
   model corrects it. The engine's own error message is a better correction signal than
   any amount of prompt wording
3. **Output sanitising** — strips markdown fences and any preamble
4. **SELECT-only validation** — rejects DDL/DML and multi-statement output. This is the
   correctness guard *and* the security guard, since generated SQL is about to be executed.
   DuckDB additionally runs with external file and network access disabled

## Evaluation

Correctness is measured, not asserted. `eval/questions.yaml` holds questions with
hand-written **gold queries**; the harness runs both and compares result sets, ignoring
column names and row order — standard execution accuracy.

```bash
./.venv/bin/python eval/run_eval.py
```

| Provider | Model | License | Score | Cross-file joins | Time |
|---|---|---|---|---|---|
| Groq free tier | `openai/gpt-oss-120b` | Apache 2.0 | **17/17 (100%)** | 4/4 | 24s |
| Local Ollama | `qwen2.5-coder:7b` | Apache 2.0 | **12/17 (71%)** | 2/4 | 275s |
| Local Ollama | `qwen2.5-coder:1.5b` | Apache 2.0 | 8/17 (47%) | 2/4 | 32s |

Same architecture and prompt throughout; the gap sits almost entirely in cross-file joins,
where smaller models mishandle grain — summing every historical salary row instead of
taking the latest per employee.

Covers all seven question types the prototype targets — aggregation, filtered aggregation,
group-by, ranking, comparison, trend, cross-file join — plus two questions it is *supposed*
to decline.

**Read the 100% honestly:** 17 questions is a smoke test, not a benchmark. It means no
regressions on the cases I thought to write, and the number arrived only after fixing two
bugs in the harness itself — including one gold query that was simply wrong, where the
model's disagreeing answer turned out to be correct. The full account is in
[`docs/writeup.md`](docs/writeup.md).

### How that accuracy was reached

The number moved three times, and each move taught something worth writing down.

| # | Change | Score (local model) | What it showed |
|---|---|---|---|
| 1 | Baseline prompt | **71%** (12/17) | **Zero SQL syntax errors** — the dialect grounding worked. Every failure was *semantic*, and 3 of 5 were the model **refusing questions it could answer** |
| 2 | Added detailed guidance and worked examples to fix the over-refusal | **65%** (11/17) | **A regression.** It broke two previously-passing questions and started hallucinating table names |
| 3 | Replaced that guidance with two lines | **82%** (14/17) | Best result. Over-refusal fixed without the noise |

**Lesson 1 — small models get *worse* when you add instructions.** Instruction volume
trades against instruction adherence. Without a harness, step 2 ships as an "improvement."

**Lesson 2 — model size mattered exactly where predicted.** Same architecture, same
prompt, larger model: cross-file joins went 2/4 → 4/4. The larger model correctly took the
*latest* salary row per employee instead of summing every historical revision.

**Lesson 3 — two of the remaining failures were defects in the test, not the system.**

- One question compared averages; the model returned the correct averages **plus** a
  supporting row count. The comparison demanded an exact measure count, so a *more
  informative* correct answer was scored as a failure. Relaxed to: every expected value
  must appear, extras allowed.
- One gold query was **simply wrong**. The question asked for "offer-to-join conversion
  rate" and the reference divided joins by *all candidates* — that is applicant-to-join.
  The model read it correctly and disagreed. A second attempt divided by those reaching an
  offer, which this dataset does not model cleanly. The model's own answer also varied
  between runs.

  **The defect was the question.** "Conversion rate" has no single meaning without a
  definition, so no ground truth could be right. It was rephrased to be unambiguous and
  kept. **This is the clearest argument in the whole exercise for a governed metric
  layer:** an undefined metric makes a correct system disagree with its own test, and in
  production it makes two teams disagree in a board meeting.

**Lesson 4 — a licence audit caught a constraint violation.** The 82% above was measured
on `qwen2.5-coder:3b`, which ships under the non-commercial **Qwen Research License**. It
was replaced with the Apache 2.0 `7b` and the score **re-measured downward to 71%** rather
than keeping the better number. See *Licence and cost compliance* below.

### Generality probe

Because a score on my own questions over my own data proves little, `eval/generality_probe.py`
runs the system against everything it was *not* built for: a different domain
(SaaS/e-commerce), a **multi-sheet `.xlsx`** rather than CSVs, messy column names
(`Customer ID`, `CSAT Score`), and eight questions written fresh.

```bash
./.venv/bin/python eval/generality_probe.py
```

**8/8 answered, 5 spot-checked against independent pandas computations and exact.** Both
cross-sheet relationships were inferred with no configuration.

## Decision log

Every decision, the alternative rejected, and what the choice cost.

| # | Decision | Chosen | Rejected | Cost paid |
|---|---|---|---|---|
| 1 | **What "correct" means** | Computed by executable code, reproducible, query visible | "The model sounded confident" | Rules out fuzzy/semantic questions entirely |
| 2 | **Where the arithmetic happens** | A deterministic engine (DuckDB) | The model's own reasoning | Cannot answer questions that need judgement over values |
| 3 | **Query language** | SQL | Generated pandas/Python | Slightly less expressive |
| 4 | **What the model sees** | Schema + selective sample values | Full rows / no samples at all | Model cannot see value formats in redacted columns |
| 5 | **Join handling** | Infer, score, **show for correction** | Join silently, or ask the user every time | An extra review step before the first question |
| 6 | **Chart selection** | Deterministic, from result shape | Let the model choose | Occasionally a duller chart than a human would pick |
| 7 | **Behaviour when unsure** | Explicit refusal | Best-effort guess | Over-refusal risk — which the eval caught and fixed |
| 8 | **Model provider** | Abstracted: Groq hosted **and** local Ollama | A single provider | Two paths to test and document |
| 9 | **Follow-up questions** | **Cut** | Build conversational context | "And for Sales?" does not resolve |
| 10 | **Dirty data** | Detect and flag | Silently repair | User must fix the file themselves |

### Why SQL rather than generated Python

- **Validation** — SQL can be constrained to a single `SELECT` and checked. Generated
  Python is arbitrary code execution
- **Readability** — the *verifier* persona already reads SQL; that is the language of the
  people who sign off on numbers
- **Joins** — DuckDB does them natively and fast over registered dataframes

### The one that took the most thought: sample values

Sample values *are* data, so sending them is a real privacy decision. But the model needs
to know a `department` column contains `"Sales"` and not `"SLS"`, or it cannot write a
correct `WHERE` clause. So it is a dial, not a switch:

- Sent **only** for low-cardinality categorical columns (≤ 25 distinct values)
- **Never** for anything matching name, email, phone, address, salary, or free-text patterns
- The app shows you the literal payload, so this is inspectable rather than a promise

### What was deliberately not built

Named as cuts, with reasons — not oversights:

| Cut | Why |
|---|---|
| Conversational follow-ups | New failure modes on a small model. A correct single-shot answer beats a fluent conversation containing a wrong number |
| Auth, persistence, multi-user | Not what the exercise tests; would consume the entire budget |
| Semantic layer | The correct long-term answer, impossible against arbitrary uploaded files |
| Forecasting and causal "why" questions | A different product. Causal inference over observational HR data is a trap |
| Self-join inference | Real gap; the model often infers `manager_id → employee_id` from names anyway |
| Data-quality repair | Silent repair is how you get confidently wrong numbers |
| Visual polish | Design effort went entirely into the answer card and the review step |

## Metrics I would track

Instrumentation is not built into this prototype — it is a single-session tool with no
backend — but these are the metrics that would decide whether it is working, and the
events needed to compute them.

### North star

**Trusted self-serve answers per active HRBP per month.**

Not "questions asked," which rewards confusion. *Trusted* means answered **and** not
escalated to the analyst queue afterwards. It is the only metric that captures the actual
job: a person got a number they were willing to act on, without filing a request.

### The metric tree

| Layer | Metric | Why it matters |
|---|---|---|
| **Activation** | % of uploads that reach a first answered question · time-to-first-answer | If people upload and bounce, the review step is too heavy |
| **Engagement** | Questions per session · weekly repeat askers · questions per HRBP per month | Repeat use is the only honest signal of trust |
| **Quality** | Execution success rate · **refusal rate** · retry rate · answer acceptance | Refusal rate is two-sided: too high means over-refusal, too low means guessing |
| **Trust** | **SQL-expand rate** — how often users open the generated query | See below |
| **Guardrail** | p95 latency · wrong-answer reports · **join-override rate** | Join overrides tell you inference is failing *before* users complain |
| **Business** | Ad-hoc requests deflected from the analyst queue · analyst hours returned | The number that funds the product |

### The metric I would actually watch: SQL-expand rate

Early on it should be **high** — users are checking the tool's working. What happens next
is the signal:

- **Stays high** → they do not trust it. The product has not earned confidence
- **Falls while acceptance stays high** → trust has been earned. This is the goal
- **Falls while acceptance also falls** → they have stopped checking *and* stopped
  believing. They are about to get burned by a wrong number

It is the rare metric where the **direction of travel matters more than the level**, which
is why it needs a trend view rather than a threshold alert.

### Event instrumentation spec

```
file_uploaded         {file_count, total_rows, total_columns, has_excel, bytes}
schema_profiled       {tables, columns, pii_columns_redacted, quality_flags}
joins_inferred        {count, max_confidence, min_confidence}
join_overridden       {from_key, to_key}          -- inference is failing
suggestion_clicked    {index, question_length}    -- are our suggestions useful?
question_asked        {source: typed | suggested, char_length}
sql_generated         {provider, model, latency_ms}
sql_validation_failed {reason}                    -- robustness / security signal
query_executed        {success, retry_count, rows_returned, rows_scanned,
                       duration_ms, table_count}  -- table_count > 1 = cross-file
answer_rendered       {chart_kind}
answer_refused        {reason_category}           -- feeds the refusal-rate metric
sql_expanded          {}                          -- the trust signal
answer_feedback       {helpful: bool}
```

**If I could only instrument one event:** `query_executed`. It carries `success`,
`retry_count` and `table_count` — telling me whether the product works, how hard it is
working, and whether anyone is attempting the cross-file questions that are the hard part
and the real value.

### How accuracy would be monitored in production

The eval harness in this repo is the offline version. In production I would:

1. Run the gold-query suite in CI on every prompt or model change — the regression in
   step 2 above is exactly what that catches
2. Track **refusal rate** and **retry rate** as live proxies for model quality, since
   neither needs ground truth
3. Sample answers where the user expanded the SQL but gave no positive feedback — that is
   the population most likely to contain quiet wrong answers
4. Feed every thumbs-down into the eval set, so the suite grows from real failures rather
   than from what I imagined

## Licence and cost compliance

Every runtime component is open-source-licensed and free, with no metered billing and no
payment method on file:

| Component | Licence / terms |
|---|---|
| `openai/gpt-oss-120b` (hosted model) | Apache 2.0, open weights |
| Groq free tier (inference) | Free, no credit card, serves open-weights models only |
| `qwen2.5-coder:7b` / `:1.5b` (local models) | Apache 2.0 |
| Ollama | MIT |
| Streamlit, pyarrow | Apache 2.0 |
| DuckDB, openpyxl, Plotly, PyYAML | MIT |
| pandas, NumPy, Altair | BSD |
| Streamlit Community Cloud, GitHub | Free tier, no card |

**One finding worth recording.** This project was originally benchmarked on
`qwen2.5-coder:3b`, which ships under the **Qwen Research License** — non-commercial, and
therefore not open source, despite downloading freely from the same registry as its
siblings. It is the only size in that family that isn't Apache 2.0. It was replaced and
the accuracy re-measured on the compliant model rather than keeping the better number.

Note that `openai/gpt-oss-120b` is OpenAI's **open-weights** release under Apache 2.0,
running on Groq's hardware — not the paid OpenAI API.

## Privacy

**Your rows never go to the model.** What is sent is the **schema**: table names, column
names, types, null rates, cardinality, numeric ranges, and sample values **only** from
low-cardinality categorical columns.

Where the rows themselves sit depends on how you run it:

- **Local install** — nothing leaves your machine at all. Files, DuckDB and the model all
  run locally
- **Hosted demo** — files are parsed and queried on the server running the app; only the
  schema reaches the inference provider
- **Real deployment** — it would run on the customer's own infrastructure, which is the point

Columns matching name, email, phone, address, salary, or free-text patterns never have
their values sampled — see `PII_PATTERNS` in [`app/ingest.py`](app/ingest.py). This is
what makes the hosted demo defensible for HR data, which is among the most sensitive
data an enterprise holds.

## Known limitations

Deliberate scope cuts for a 4–6 hour build, not oversights:

- **No conversational follow-ups.** Each question is answered independently; "and for
  Sales?" will not resolve against the previous question. First thing I would build next
- **No persistence or auth.** Single session, nothing stored
- **In-memory only.** Suited to files up to ~100k rows. Beyond that the execution layer
  needs a warehouse — the NL-to-SQL layer would be unchanged
- **Self-joins are not inferred.** `manager_id → employee_id` within one table is not
  detected, though the model often works it out from column names
- **Excel edge cases.** Assumes the first row is the header; merged cells and
  pivot-style layouts are flagged, not parsed
- **No semantic layer.** "Attrition" means whatever the generated SQL says it means.
  Governed metric definitions are the right long-term answer and are out of scope here

## Repository layout

```
app/ingest.py    file loading, type inference, schema profiling, PII rules
app/joins.py     join-key inference via name similarity + value overlap
app/llm.py       provider abstraction, prompting, sanitising, validation
app/query.py     DuckDB execution and the generate → execute → retry loop
app/charts.py    deterministic chart selection from result shape
app/main.py      Streamlit UI
data/            demo HR dataset + its generator
eval/            gold-query evaluation harness + generality probe
docs/writeup.md  one-page write-up: approach, decisions, what's next
```

## Why this is a product and not a ChatGPT habit

A general assistant *can* analyse a CSV — that premise is worth conceding openly. The
differentiation is never model capability:

1. **The data legally cannot go there.** Salary, performance ratings, medical leave.
   Data processing agreements, enterprise IT policy, and cross-border transfer of employee
   personal data nobody consented to. Procurement blocks it; engineering cannot route around it
2. **Somebody had to export the file.** A general assistant is a destination you carry data
   to — manual, instantly stale, disconnected from the system of record. **In this
   prototype, upload stands in for a connection**
3. **Definitions drift silently.** "Attrition" computed three ways in three sessions, never
   disclosed. An HRMS needs one company-defined meaning
4. **Access control.** A CHRO sees all compensation; a line manager sees their team. A
   general assistant has no notion of *who is asking* — whoever holds the exported file sees
   every salary in it. Structurally impossible to fix in the chat model
5. **Auditability.** Which number reached the board deck, and can last quarter's be
   reproduced? A personal chat history is not an audit trail

> ChatGPT answers the question once, for one person, on a file they had to export. A data
> product answers it consistently, for everyone, on data nobody exported — and shows each
> person only what they are allowed to see.
