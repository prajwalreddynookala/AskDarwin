"""Generate the AskDarwin demo HR dataset.

Five files spanning the employee lifecycle: hiring -> onboarding -> in-role -> exit.
Deliberately correlated (low performers churn more, referrals convert better) so that
analytical questions have interesting, non-random answers.

Stdlib only, deterministic seed. Run:  python data/generate_demo_data.py
"""

import csv
import os
import random
from datetime import date, timedelta

SEED = 20260811
random.seed(SEED)

TODAY = date(2026, 8, 11)
OUT = os.path.dirname(os.path.abspath(__file__))

DEPARTMENTS = [
    # (name, headcount weight, attrition multiplier, salary multiplier)
    ("Engineering", 30, 0.8, 1.35),
    ("Sales", 20, 1.6, 1.10),
    ("Customer Success", 13, 1.4, 0.90),
    ("Marketing", 8, 1.0, 0.95),
    ("Product", 7, 0.7, 1.30),
    ("Finance", 7, 0.7, 1.00),
    ("Operations", 9, 1.1, 0.80),
    ("Human Resources", 6, 0.9, 0.85),
]
LOCATIONS = ["Hyderabad", "Bengaluru", "Mumbai", "Delhi NCR", "Pune", "Remote"]
LOCATION_W = [30, 25, 12, 10, 13, 10]
GRADES = ["L1", "L2", "L3", "L4", "L5", "L6"]
GRADE_W = [22, 26, 22, 16, 9, 5]
GRADE_BASE = {"L1": 600000, "L2": 950000, "L3": 1500000, "L4": 2400000, "L5": 3600000, "L6": 5500000}
GENDERS = ["Female", "Male"]
SOURCES = [
    # (name, share, quality bias)
    ("Employee Referral", 22, 0.35),
    ("LinkedIn", 24, 0.05),
    ("Naukri", 18, -0.10),
    ("Careers Site", 12, 0.00),
    ("Campus", 12, -0.05),
    ("Recruitment Agency", 12, -0.15),
]
EXIT_REASONS = [
    ("Better opportunity", 34), ("Compensation", 22), ("Relocation", 10),
    ("Performance", 9), ("Higher education", 7), ("Personal reasons", 12),
    ("Involuntary - restructuring", 6),
]
LEAVE_TYPES = ["Casual", "Sick", "Earned", "Unpaid", "None"]

FIRST = ["Aarav","Aditi","Ananya","Arjun","Bhavya","Chetan","Deepika","Dhruv","Farhan","Gaurav",
         "Harini","Ishaan","Jaya","Kabir","Kavya","Lakshmi","Manish","Meera","Nikhil","Neha",
         "Omkar","Pooja","Pranav","Priya","Rahul","Rhea","Rohit","Sanjana","Shreya","Siddharth",
         "Tanvi","Tarun","Uma","Varun","Vidya","Vikram","Yash","Zoya","Ritu","Nandini"]
LAST = ["Sharma","Reddy","Iyer","Nair","Patel","Menon","Gupta","Rao","Desai","Kulkarni",
        "Banerjee","Chatterjee","Joshi","Malhotra","Verma","Pillai","Bose","Shetty","Kapoor","Mehta"]


def weighted(pairs):
    names = [p[0] for p in pairs]
    wts = [p[1] for p in pairs]
    return random.choices(names, weights=wts, k=1)[0]


def rand_date(start, end):
    return start + timedelta(days=random.randint(0, (end - start).days))


def month_str(d):
    return "%04d-%02d" % (d.year, d.month)


def add_months(d, n):
    y, m = divmod((d.year * 12 + d.month - 1) + n, 12)
    return date(y, m + 1, 1)


# ---------------------------------------------------------------- employees
N = 420
employees = []
dept_pairs = [(d[0], d[1]) for d in DEPARTMENTS]
dept_attr = {d[0]: d[2] for d in DEPARTMENTS}
dept_sal = {d[0]: d[3] for d in DEPARTMENTS}

for i in range(1, N + 1):
    emp_id = "EMP%04d" % i
    dept = weighted(dept_pairs)
    grade = random.choices(GRADES, weights=GRADE_W, k=1)[0]
    doj = rand_date(date(2019, 1, 7), date(2026, 6, 30))

    # quality score drives rating and attrition; set here so files stay consistent
    quality = random.gauss(0, 1)

    tenure_days = (TODAY - doj).days
    # base exit probability rises with tenure, scaled by department and quality
    p_exit = min(0.62, 0.05 + tenure_days / 4200.0) * dept_attr[dept]
    p_exit *= 1.5 if quality < -0.8 else (0.6 if quality > 0.8 else 1.0)

    if random.random() < p_exit and tenure_days > 200:
        exit_date = rand_date(doj + timedelta(days=180), min(TODAY, doj + timedelta(days=2600)))
        if exit_date > TODAY:
            exit_date = TODAY - timedelta(days=random.randint(1, 60))
        status = "Exited"
        reason = "Performance" if quality < -1.0 and random.random() < 0.5 else weighted(EXIT_REASONS)
    else:
        exit_date, status, reason = None, "Active", None

    employees.append({
        "employee_id": emp_id,
        "full_name": "%s %s" % (random.choice(FIRST), random.choice(LAST)),
        "department": dept,
        "location": random.choices(LOCATIONS, weights=LOCATION_W, k=1)[0],
        "grade": grade,
        "gender": random.choices(GENDERS, weights=[44, 56], k=1)[0],
        "date_of_joining": doj.isoformat(),
        "exit_date": exit_date.isoformat() if exit_date else "",
        "exit_reason": reason or "",
        "employment_status": status,
        "_quality": quality,
        "_doj": doj,
        "_exit": exit_date,
    })

# managers: assign a longer-tenured employee from the same department
by_dept = {}
for e in employees:
    by_dept.setdefault(e["department"], []).append(e)
for e in employees:
    pool = [m for m in by_dept[e["department"]]
            if m["employee_id"] != e["employee_id"] and m["_doj"] < e["_doj"] and m["grade"] >= e["grade"]]
    e["manager_id"] = random.choice(pool)["employee_id"] if pool else ""

# ------------------------------------------------------------- recruitment
# every employee has a winning application; plus rejected candidates per requisition
recruitment = []
cand_n = 0
req_n = 0
STAGES = ["Applied", "Screened", "Interviewed", "Offered", "Joined"]

for e in employees:
    req_n += 1
    req_id = "REQ%04d" % req_n
    src = weighted([(s[0], s[1]) for s in SOURCES])
    applied = e["_doj"] - timedelta(days=random.randint(28, 110))
    offered = e["_doj"] - timedelta(days=random.randint(10, 27))
    cand_n += 1
    recruitment.append({
        "requisition_id": req_id, "candidate_id": "CAND%05d" % cand_n,
        "department": e["department"], "grade": e["grade"], "source": src,
        "applied_date": applied.isoformat(), "offer_date": offered.isoformat(),
        "final_stage": "Joined", "joined_flag": "Yes", "employee_id": e["employee_id"],
    })
    # unsuccessful candidates for the same requisition
    for _ in range(random.randint(3, 9)):
        cand_n += 1
        s2 = weighted([(s[0], s[1]) for s in SOURCES])
        bias = dict((x[0], x[2]) for x in SOURCES)[s2]
        r = random.random() + bias
        stage = "Applied" if r < 0.45 else ("Screened" if r < 0.75 else ("Interviewed" if r < 0.93 else "Offered"))
        a2 = applied + timedelta(days=random.randint(-14, 21))
        recruitment.append({
            "requisition_id": req_id, "candidate_id": "CAND%05d" % cand_n,
            "department": e["department"], "grade": e["grade"], "source": s2,
            "applied_date": a2.isoformat(),
            "offer_date": (a2 + timedelta(days=random.randint(20, 45))).isoformat() if stage == "Offered" else "",
            "final_stage": stage, "joined_flag": "No", "employee_id": "",
        })

# ------------------------------------------------------------- performance
performance = []
CYCLES = [("FY25-H1", date(2025, 4, 1)), ("FY25-H2", date(2025, 10, 1)), ("FY26-H1", date(2026, 4, 1))]
for e in employees:
    for cycle, cdate in CYCLES:
        if e["_doj"] > cdate - timedelta(days=90):
            continue
        if e["_exit"] and e["_exit"] < cdate:
            continue
        q = e["_quality"] + random.gauss(0, 0.5)
        rating = 1 if q < -1.4 else 2 if q < -0.6 else 3 if q < 0.7 else 4 if q < 1.5 else 5
        performance.append({
            "employee_id": e["employee_id"], "review_cycle": cycle, "rating": rating,
            "potential_flag": "High" if (rating >= 4 and random.random() < 0.45) else "Standard",
            "reviewer_id": e["manager_id"],
        })

# -------------------------------------------------------------- attendance
attendance = []
start_m = date(2025, 3, 1)
for k in range(17):
    m = add_months(start_m, k)
    if m > date(TODAY.year, TODAY.month, 1):
        break
    working = random.choice([20, 21, 22])
    for e in employees:
        if e["_doj"] > m:
            continue
        if e["_exit"] and e["_exit"] < m:
            continue
        # people on their way out disengage; low performers take more unplanned leave
        drift = 0.0
        if e["_exit"] and 0 <= (e["_exit"] - m).days <= 120:
            drift += 1.6
        if e["_quality"] < -0.8:
            drift += 0.8
        absent = max(0, min(working, int(round(random.gauss(1.4 + drift, 1.2)))))
        attendance.append({
            "employee_id": e["employee_id"], "month": month_str(m),
            "working_days": working, "days_present": working - absent, "days_absent": absent,
            "leave_type": random.choice(LEAVE_TYPES) if absent else "None",
        })

# ------------------------------------------------------------ compensation
compensation = []
for e in employees:
    base = GRADE_BASE[e["grade"]] * dept_sal[e["department"]]
    base *= random.uniform(0.88, 1.14)
    if e["location"] in ("Mumbai", "Bengaluru"):
        base *= 1.07
    eff = e["_doj"]
    salary = base
    while True:
        end = e["_exit"] or TODAY
        if eff > end:
            break
        bonus = salary * random.uniform(0.0, 0.18) * (1.4 if e["_quality"] > 0.8 else 1.0)
        compensation.append({
            "employee_id": e["employee_id"], "effective_month": month_str(eff),
            "base_salary": int(round(salary, -3)), "bonus": int(round(bonus, -3)),
            "currency": "INR",
        })
        nxt = date(eff.year + 1, 4, 1) if eff.month >= 4 else date(eff.year, 4, 1)
        if nxt <= eff:
            nxt = date(eff.year + 1, 4, 1)
        eff = nxt
        hike = 1.06 + (0.08 if e["_quality"] > 0.8 else 0.0) + random.uniform(0, 0.05)
        salary *= hike

# ------------------------------------------------------------------ write
def write(name, rows, cols):
    path = os.path.join(OUT, name)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print("%-22s %6d rows" % (name, len(rows)))


write("employees.csv", employees,
      ["employee_id", "full_name", "department", "location", "grade", "gender",
       "manager_id", "date_of_joining", "exit_date", "exit_reason", "employment_status"])
write("recruitment.csv", recruitment,
      ["requisition_id", "candidate_id", "department", "grade", "source",
       "applied_date", "offer_date", "final_stage", "joined_flag", "employee_id"])
write("performance.csv", performance,
      ["employee_id", "review_cycle", "rating", "potential_flag", "reviewer_id"])
write("attendance.csv", attendance,
      ["employee_id", "month", "working_days", "days_present", "days_absent", "leave_type"])
write("compensation.csv", compensation,
      ["employee_id", "effective_month", "base_salary", "bonus", "currency"])

active = sum(1 for e in employees if e["employment_status"] == "Active")
print("\nactive %d / exited %d  (attrition %.1f%%)" % (
    active, len(employees) - active, 100.0 * (len(employees) - active) / len(employees)))
