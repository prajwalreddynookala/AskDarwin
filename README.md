# AskDarwin

**Ask your HR spreadsheets anything.** Upload CSV or Excel files, ask a question in
plain English, get an answer — with the query that produced it.

Built as a take-home exercise for the Darwinbox Product Management (Data) interview.
Not affiliated with or endorsed by Darwinbox; the name is a prototype label.

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
| Model (hosted) | Groq free tier — open-weights models | No card required, no metered billing |
| Model (local) | Ollama + `qwen2.5-coder:3b` | Fully offline, zero accounts |

No paid APIs, no metered credits, no vendor lock-in on the model layer — the provider
is a swap in [`app/llm.py`](app/llm.py).

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
eval/            gold-query evaluation harness
docs/            reasoning behind the product decisions
```
