# Demo recording script — ~4 minutes

Record with the **hosted (Groq) link**, not local — local inference runs ~55s per question.
Have the demo dataset ready to upload from `data/`. Screen + voice. Don't rehearse it into
sounding scripted; the beats matter more than the wording.

**Before you hit record:** open the app cold (no data loaded), close other tabs, and have
the five CSVs in a folder you can drag from.

---

### 0:00 — Open on the problem, not the product *(~20s)*

> "An HR business partner needs to know whether attrition in Sales is getting worse. Today
> that's a request to the analytics team, and it takes three days — and by the time the
> answer arrives, the follow-up question needs another three days. This is AskDarwin. It's
> a prototype for removing that queue."

Don't say "I built an AI app that answers questions about CSVs." Lead with the queue.

### 0:20 — Upload, and name what's hard *(~20s)*

Drag all five files in at once.

> "Five files — employee master, recruitment, attendance, performance, compensation. This
> is what HR data actually looks like: it's never one table. Which means almost every
> real question is a join."

### 0:40 — "What AskDarwin understood" *(~30s)* — **your differentiator**

Open the expander. Point at the detected relationships.

> "Before I ask anything, it tells me what it worked out. These files arrive with no
> declared relationships, so it infers them — from column names *and* from how much the
> actual values overlap — and it shows me its confidence. I can check it.
>
> That matters because a wrong join doesn't throw an error. It returns a confidently wrong
> number, which is the worst thing an analytics tool can do."

### 1:10 — "Exactly what gets sent to the model" *(~20s)* — **the privacy beat**

Open the panel. Point at the three metrics.

> "Zero rows of my data go to the model. Ten thousand rows stay here. Twelve columns had
> their values withheld — names, salaries. The model gets structure and writes SQL; the
> database does the arithmetic locally.
>
> That's not a nice-to-have for HR data. It's the difference between something an
> enterprise can deploy and something their compliance team bans."

### 1:30 — A simple question *(~30s)*

Ask: **"How many employees are currently active, by department?"**

Let the chart render. Then expand the SQL.

> "Answer, chart chosen from the shape of the result, and the query that produced it. The
> number isn't generated — it's computed. I can hand this to an analyst and they can verify
> it in ten seconds."

### 2:00 — The hard one: cross-file *(~40s)*

Ask: **"Compare the average performance rating of employees hired through Employee Referral
versus Recruitment Agency"**

> "That question spans three files — recruitment, employees, performance. Nobody told it how
> those connect."

Expand the SQL to show the three-table join. Then land the insight:

> "And there's a real finding here: referral hires rate meaningfully higher than agency
> hires. That's a sourcing budget conversation, and it took four seconds instead of four days."

### 2:40 — Show it saying no *(~25s)*

Ask something unanswerable: **"Which employees are most likely to resign next quarter?"**

> "It declines, and says why. I'd rather it refuse than guess — a plausible wrong number is
> more dangerous than no number. Refusal rate is something I'd actively monitor: too high
> and it's useless, too low and it's guessing."

### 3:05 — The evaluation *(~35s)* — **the part that separates you**

Cut to the terminal or the results file.

> "I didn't want to claim it works, so I measured it. Seventeen questions with hand-written
> reference queries, scored on execution accuracy — run both, compare the results. 82% on a
> 3-billion-parameter model running locally. Cross-file joins are the weakest category,
> which is the hard one and where I expected to be weak.
>
> The most useful thing it caught was my own mistake. I added detailed guidance to the
> prompt to fix some failures, and accuracy dropped from 71% to 65% — it started
> hallucinating table names. Cutting that back to two lines got it to 82%. Small models get
> worse when you add instructions. Without the harness I'd have shipped the regression
> believing it was an improvement."

### 3:40 — Close on what's next *(~20s)*

> "The upload here is standing in for a connection. Inside Darwinbox this points at the
> real tables and the export step disappears — then row-level access control, so a manager
> sees their team and a CHRO sees everyone. And then one governed definition of 'attrition'
> that matches the board deck.
>
> That last one is what my clearest eval failure was pointing at."

---

## Things to avoid

- **Don't apologise for scope.** "I didn't have time to..." → "I cut X to protect Y."
- **Don't demo the UI.** Demo the decisions. They can click the link themselves.
- **Don't hide the failures.** The 82% and the regression story are assets, not admissions.
- **Don't oversell.** The panel knows ChatGPT can analyse a CSV. Your argument is the data
  boundary, the join transparency, and the measurement — not novelty.

## If something breaks live

Say what you expected, what happened, and what you'd check first. A calm diagnosis under
pressure reads better than a flawless demo — and this is a data role, so debugging out loud
is directly on-brand.
