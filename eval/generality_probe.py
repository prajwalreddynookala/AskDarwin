"""Generality probe: a domain the system has never seen, in a format never tested.

Deliberately adversarial relative to how AskDarwin was built:
  - not HR — a SaaS/e-commerce business
  - a single multi-sheet .xlsx, not CSVs (the Excel path has never been exercised)
  - messy real-world column names: spaces, mixed case, inconsistent id naming
  - questions written to probe capability, none of them in the eval set
"""
import os
import random
import sys
from datetime import date, timedelta

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import ingest, joins, query  # noqa: E402

random.seed(7)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "store_data.xlsx")

CITIES = ["Mumbai", "Bengaluru", "Delhi", "Chennai", "Pune"]
PLANS = ["Free", "Pro", "Enterprise"]
CATS = ["Electronics", "Apparel", "Home", "Books"]
PAY = ["UPI", "Credit Card", "Net Banking", "Wallet"]
PRIO = ["Low", "Medium", "High"]

# --- Customers: note the deliberately awkward column names
customers = []
for i in range(1, 121):
    customers.append({
        "Customer ID": "C%03d" % i,
        "Full Name": "Customer %d" % i,
        "City": random.choice(CITIES),
        "Plan Type": random.choices(PLANS, weights=[50, 35, 15])[0],
        "Signup Date": (date(2024, 1, 1) + timedelta(days=random.randint(0, 700))).isoformat(),
        "Churned": random.choices(["Yes", "No"], weights=[28, 72])[0],
    })

orders = []
oid = 0
for c in customers:
    for _ in range(random.randint(0, 9)):
        oid += 1
        cat = random.choice(CATS)
        base = {"Electronics": 9000, "Apparel": 1800, "Home": 3200, "Books": 600}[cat]
        orders.append({
            "Order ID": "O%05d" % oid,
            "Customer ID": c["Customer ID"],
            "Order Date": (date(2025, 1, 1) + timedelta(days=random.randint(0, 400))).isoformat(),
            "Amount": round(base * random.uniform(0.6, 1.8), 2),
            "Category": cat,
            "Payment Method": random.choice(PAY),
        })

tickets = []
tid = 0
for c in customers:
    for _ in range(random.randint(0, 4)):
        tid += 1
        # Enterprise customers get better CSAT — a real signal to detect
        bump = {"Free": 0.0, "Pro": 0.6, "Enterprise": 1.2}[c["Plan Type"]]
        tickets.append({
            "Ticket ID": "T%05d" % tid,
            "Customer ID": c["Customer ID"],
            "Opened Date": (date(2025, 1, 1) + timedelta(days=random.randint(0, 400))).isoformat(),
            "Priority": random.choice(PRIO),
            "Resolved": random.choices(["Yes", "No"], weights=[85, 15])[0],
            "CSAT Score": max(1, min(5, round(random.gauss(3.2 + bump, 0.9)))),
        })

with pd.ExcelWriter(OUT) as w:
    pd.DataFrame(customers).to_excel(w, sheet_name="Customers", index=False)
    pd.DataFrame(orders).to_excel(w, sheet_name="Orders", index=False)
    pd.DataFrame(tickets).to_excel(w, sheet_name="Support Tickets", index=False)
print("wrote %s — %d customers, %d orders, %d tickets\n"
      % (os.path.basename(OUT), len(customers), len(orders), len(tickets)))

tables, warnings = ingest.load_files([OUT])
print("tables discovered:", list(tables.keys()))
print("warnings:", warnings or "none")
schemas = ingest.profile_all(tables)
rel = joins.infer_joins(tables, schemas)
print()
print(joins.joins_to_prompt(rel))
print()

schema_text = ingest.schema_to_prompt(schemas)
joins_text = joins.joins_to_prompt(rel)
con = query.make_connection(tables)

QUESTIONS = [
    "What is the total order value by city?",
    "Which plan type has the highest average CSAT score?",
    "How many orders were placed in each month of 2025?",
    "Compare the average order amount for churned customers versus active ones",
    "Which payment method is used most often for Electronics orders?",
    "How many support tickets were raised by customers in Mumbai?",
    "What is the average number of days between a customer signing up and their first order?",
    "Which city has the worst average CSAT score?",
]

passed = 0
for q in QUESTIONS:
    print("=" * 78)
    print("Q:", q)
    r = query.answer_question(q, tables, schema_text, joins_text, con)
    if r.get("ok"):
        passed += 1
        print("SQL:", " ".join(r["sql"].split())[:230])
        df = r["dataframe"]
        print("-> %d rows%s" % (len(df), " (retried)" if r.get("retried") else ""))
        print(df.head(6).to_string(index=False))
    elif r.get("refusal"):
        print("REFUSED:", r["refusal"])
    else:
        print("FAILED [%s]: %s" % (r.get("stage"), r.get("error")))
    print()

print("=" * 78)
print("answered without error: %d/%d" % (passed, len(QUESTIONS)))
