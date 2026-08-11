# AskDarwin — Panel Prep Doc

*Long-form reasoning. The submitted write-up is a 1-page compression of this.*

Product: **AskDarwin** — ask your HR spreadsheets anything.
Task: Darwinbox PM (Data) take-home. Build an AI-powered data Q&A web app.

---

## Stage 1 — Framing: what the brief didn't say

The brief is deliberately underspecified. Ten things it leaves open, and what I decided for each.

| # | Ambiguity | Decision | Why |
|---|---|---|---|
| 1 | **Who is the user?** Never stated. | HR Business Partner as primary asker; HR/People Analyst as the verifier who has to trust the output. | Determines whether the interface is natural language or a query builder, and whether "show your working" is required. |
| 2 | **What data domain?** Any CSV, per the brief. | Engine stays domain-agnostic; demo, dataset and narrative are HR workforce data. | Brief asks for "reasonably general" capability, so crippling the engine would fail it. A specific demo makes the value legible. |
| 3 | **What does "correct" mean?** Undefined — and it's the crux. | Correct = the number is **computed from the source data by executable code**, is **reproducible**, and the user can **see the query that produced it**. Not "the model sounded confident." | This single definition drives the entire architecture (see Stage 6). |
| 4 | **How big is the data?** Unstated. | Up to ~100k rows / ~50MB per session, held in memory. No warehouse, no streaming. | Sets the ceiling on in-memory pandas/DuckDB. Above this the product needs a different backend — that's a v2 problem, stated not ignored. |
| 5 | **How are files related?** Cross-file analysis is required, but no schema or keys are given. | The system must **infer join keys** from column names, types and value overlap, then **show the user what it inferred** and let them correct it. | This is the hardest acceptance criterion. Silent joins produce silently wrong numbers. |
| 6 | **Single question or conversation?** "Ask analytical questions" — ambiguous. | Single-shot per question, with visible question history. No conversational memory in v1. | Follow-up context ("and for Sales?") is a real need but a v2 feature. Cutting it protects the 4–6h budget. |
| 7 | **Where does the data live?** Unstated. | **Local-only. No data leaves the machine** — files are parsed locally, only *schema* is sent to a locally-running model. | HR data is salary, performance and medical leave. This isn't just an assumption, it's a product advantage worth pitching. |
| 8 | **Excel specifics** — multi-sheet, merged cells, headers? | Assume first row is the header. Each sheet in a workbook is treated as its own table. Merged cells and pivot-style layouts are out of scope, detected and flagged rather than silently mangled. | Real HR exports are messy; failing loudly beats failing quietly. |
| 9 | **Auth, persistence, multi-user?** Unstated. | Out of scope. Single session, nothing persisted. | Not what's being tested, and it would eat the entire budget. |
| 10 | **How general is "reasonably general"?** | Defined explicitly as seven question classes (below). Anything in those classes should work; anything outside is out of scope by design. | Turns a vague acceptance criterion into a testable definition of done. |

### The question taxonomy — our definition of "done"

This doubles as the evaluation test set in Stage 9.

1. **Aggregation** — "What's the total payroll cost?"
2. **Filtered aggregation** — "Average tenure in the Sales team?"
3. **Group-by / breakdown** — "Headcount by department"
4. **Ranking / top-N** — "Top 5 departments by attrition"
5. **Comparison** — "Compare average salary of top-rated vs bottom-rated employees"
6. **Trend over time** — "Monthly absenteeism trend for the last year"
7. **Cross-file join** — any of the above spanning two or more uploaded files

**Explicitly out of scope:** forecasting, causal inference ("*why* is attrition high?"), free-form ML, anything needing data not in the uploaded files.

### The riskiest assumption

**That join-key inference is reliable enough to trust.** If it silently picks the wrong key, the product confidently returns wrong numbers — the worst possible failure for an analytics tool. Mitigation: show the inferred relationship, let the user override it, and surface row counts so a bad join is visually obvious.
