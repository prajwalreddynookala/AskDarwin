"""Natural language -> DuckDB SQL.

Provider-abstracted so the same app runs on Groq's free tier (hosted demo) or a
local Ollama model (offline). Both serve open-weights models, so the brief's
"open-source models, no paid APIs" constraint holds either way.

The model receives the schema and the question. It never receives table rows.
"""

import json
import os
import re
import time
import urllib.error
import urllib.request
from typing import Dict, List, Optional, Tuple

GROQ_URL = "https://api.groq.com/openai/v1"
OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")

# Groq's edge rejects the default urllib User-Agent with a Cloudflare 403 (error 1010),
# so every request sets one explicitly.
USER_AGENT = "AskDarwin/1.0"

# Preference order; the first one the provider actually serves wins. Groq deprecates
# models periodically, so we resolve against the live catalogue instead of pinning.
GROQ_MODEL_PREFERENCE = [
    "openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.6-27b",
    "llama-3.3-70b-versatile", "llama-3.1-8b-instant",
]
# Apache 2.0. Note that qwen2.5-coder:3b is *not* — it ships under the Qwen Research
# License, which is non-commercial, so it fails the brief's "open-source models" test
# despite downloading freely from the same registry. The 0.5b/1.5b/7b/14b/32b sizes are
# Apache 2.0. Measured on the eval set: 7b 71%, 1.5b 47%. Set OLLAMA_MODEL to
# qwen2.5-coder:1.5b on a memory-constrained machine, or 14b/32b on a larger one.
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:7b")

CANNOT_ANSWER = "CANNOT_ANSWER"

SYSTEM_PROMPT = """You translate questions about tabular data into a single DuckDB SQL query.

Rules:
- Output ONLY the SQL. No prose, no markdown fences, no explanation.
- Exactly one statement. It must be a SELECT (a leading WITH clause is fine).
- Use only the tables and columns listed in the schema. Never invent a column.
- Give every computed column a clear alias, e.g. AS avg_tenure_years.
- When a question groups by something, return the grouping column AND the measure.
- Rates, ratios and percentages are derived with arithmetic over existing columns, e.g.
  COUNT(*) FILTER (WHERE status = 'Exited') * 100.0 / COUNT(*). Answer these.
- Only if the underlying facts are in no table, output exactly:
  CANNOT_ANSWER: <one short sentence explaining what is missing>

DuckDB dialect notes (these differ from MySQL and are a common source of errors):
- Date difference: date_diff('day', start_date, end_date). There is no DATEDIFF(a, b).
- Years between dates: date_diff('year', start_date, end_date)
- Current date: CURRENT_DATE
- Month bucket from a date: strftime(the_date, '%Y-%m')
- Cast text to date: CAST(col AS DATE) or strptime(col, '%Y-%m-%d')
- Safe division: use NULLIF(denominator, 0)

Worked example:
Schema:
TABLE employees  -- 420 rows
  employee_id VARCHAR
  department VARCHAR  values: "Sales", "Engineering"
  date_of_joining DATE
  exit_date DATE  62% null
TABLE performance  -- 720 rows
  employee_id VARCHAR
  rating INTEGER  range: 1 to 5
Relationships: employees.employee_id = performance.employee_id (one-to-many)
Question: Compare average tenure in years for employees rated 5 versus rated 1.
SQL:
SELECT p.rating,
       AVG(date_diff('day', e.date_of_joining, COALESCE(e.exit_date, CURRENT_DATE)) / 365.25) AS avg_tenure_years,
       COUNT(DISTINCT e.employee_id) AS employee_count
FROM employees e
JOIN performance p ON e.employee_id = p.employee_id
WHERE p.rating IN (1, 5)
GROUP BY p.rating
ORDER BY p.rating"""

_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|attach|detach|copy|install|load|"
    r"pragma|export|import|set|call|truncate|grant|revoke|vacuum)\b", re.I)


class LLMError(Exception):
    pass


# --------------------------------------------------------------- providers

MAX_RATE_LIMIT_RETRIES = 3


def _post_json(url: str, payload: Dict, headers: Optional[Dict] = None,
               timeout: int = 90) -> Dict:
    """POST with backoff on rate limits.

    Free-tier inference is capped on tokens per minute, and a schema prompt is not
    small. Rather than failing the user's question, wait for the window the provider
    tells us about and try again.
    """
    data = json.dumps(payload).encode("utf-8")
    hdrs = {"Content-Type": "application/json", "User-Agent": USER_AGENT}
    hdrs.update(headers or {})

    for attempt in range(MAX_RATE_LIMIT_RETRIES):
        req = urllib.request.Request(url, data=data, headers=hdrs, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")
            if exc.code == 429 and attempt < MAX_RATE_LIMIT_RETRIES - 1:
                time.sleep(_retry_after_seconds(exc, body, attempt))
                continue
            if exc.code == 429:
                raise LLMError(
                    "The free-tier rate limit is in effect. Wait a moment and ask again.")
            raise LLMError("Provider returned HTTP %s: %s" % (exc.code, body[:300]))
        except Exception as exc:
            raise LLMError(str(exc))
    raise LLMError("Provider did not respond.")


def _retry_after_seconds(exc, body: str, attempt: int) -> float:
    """Honour the provider's own wait hint; fall back to exponential backoff."""
    header = exc.headers.get("retry-after") if getattr(exc, "headers", None) else None
    if header:
        try:
            return min(float(header) + 0.5, 30.0)
        except ValueError:
            pass
    match = re.search(r"try again in ([\d.]+)s", body, re.I)
    if match:
        return min(float(match.group(1)) + 0.5, 30.0)
    return min(2.0 * (2 ** attempt), 30.0)


def _groq_key() -> Optional[str]:
    """Environment first, then Streamlit secrets in any of the shapes people write.

    A secrets.toml written with a `[secrets]` or `[general]` header nests the key one
    level down, so a plain top-level lookup silently returns None and the app quietly
    falls back to a local model. Checking the common sections turns a confusing
    misconfiguration into a non-issue.
    """
    key = os.environ.get("GROQ_API_KEY")
    if key:
        return key
    try:
        import streamlit as st
        top = st.secrets.get("GROQ_API_KEY")
        if top:
            return top
        for section in ("secrets", "general", "groq"):
            try:
                nested = st.secrets[section].get("GROQ_API_KEY")
            except Exception:
                continue
            if nested:
                return nested
    except Exception:
        pass
    return _key_from_repo_secrets()


def _key_from_repo_secrets() -> Optional[str]:
    """Last resort: read the repo's own secrets.toml.

    Streamlit resolves secrets relative to the working directory, so launching from a
    parent directory finds nothing and the app silently falls back to a local model
    with a perfectly valid key sitting on disk. Look next to the code as well.
    """
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        ".streamlit", "secrets.toml")
    try:
        with open(path) as handle:
            match = re.search(r'^\s*GROQ_API_KEY\s*=\s*["\']([^"\']+)["\']',
                              handle.read(), re.M)
        return match.group(1) if match else None
    except OSError:
        return None


def _groq_model(key: str) -> str:
    override = os.environ.get("GROQ_MODEL")
    if override:
        return override
    try:
        req = urllib.request.Request(
            GROQ_URL + "/models",
            headers={"Authorization": "Bearer " + key, "User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=20) as resp:
            available = {m["id"] for m in json.loads(resp.read().decode())["data"]}
        for candidate in GROQ_MODEL_PREFERENCE:
            if candidate in available:
                return candidate
        for m in sorted(available):  # anything that is not audio/vision
            if not any(x in m for x in ("whisper", "tts", "guard", "vision")):
                return m
    except Exception:
        pass
    return GROQ_MODEL_PREFERENCE[-1]


def _ollama_available() -> bool:
    try:
        with urllib.request.urlopen(OLLAMA_URL + "/api/tags", timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False


def active_provider() -> Tuple[str, str]:
    """(provider, model). Groq when a key is present, else local Ollama."""
    forced = os.environ.get("ASKDARWIN_PROVIDER")
    key = _groq_key()
    if forced == "ollama" or (not key and _ollama_available()):
        return "ollama", OLLAMA_MODEL
    if key:
        return "groq", _groq_model(key)
    raise LLMError(
        "No model available. Set GROQ_API_KEY (free tier) or run Ollama locally.")


def _complete(prompt: str, system: Optional[str] = None, max_tokens: int = 700) -> str:
    system = system or SYSTEM_PROMPT
    provider, model = active_provider()
    if provider == "groq":
        out = _post_json(
            GROQ_URL + "/chat/completions",
            {"model": model,
             "messages": [{"role": "system", "content": system},
                          {"role": "user", "content": prompt}],
             "temperature": 0, "max_tokens": max_tokens},
            {"Authorization": "Bearer " + _groq_key()})
        return out["choices"][0]["message"]["content"]
    out = _post_json(
        OLLAMA_URL + "/api/generate",
        {"model": model, "system": system, "prompt": prompt,
         "stream": False, "options": {"temperature": 0, "num_predict": max_tokens}})
    return out.get("response", "")


# ------------------------------------------------- dataset orientation

ORIENT_SYSTEM = """You help someone understand a dataset they have just uploaded.

You are given only the schema — table names, column names, types, and sometimes a few
sample values from categorical columns. You never see the rows.

Return ONLY a JSON object, no markdown fences, with exactly these keys:
{
  "summary": "2-3 plain sentences: what this data appears to describe, and what the
              tables represent. Address the reader as 'you'. No preamble, no hedging
              about being an AI. If the domain is unclear, say so plainly.",
  "tables": [{"name": "<exact table name>", "describes": "<one short clause>"}],
  "questions": ["<6 questions this specific data can actually answer>"]
}

Rules for the questions:
- Use the real column and value names from this schema. Never invent a column.
- Make at least two of them span more than one table, if more than one table exists.
- Include a mix: a total or average, a breakdown by category, a ranking, a trend over
  time if any date column exists, and a comparison between two groups.
- Write them the way a person would type them, not as SQL descriptions.
- Keep each under 90 characters."""


def describe_dataset(schema_text: str, joins_text: str) -> Optional[Dict]:
    """One call that orients the user: what this data is, and what to ask of it.

    Sends schema only, exactly like query generation. Returns None on any failure —
    the UI falls back to a deterministic description rather than blocking upload.
    """
    prompt = "Schema:\n%s\n\n%s\n\nJSON:" % (schema_text, joins_text)
    try:
        raw = _complete(prompt, system=ORIENT_SYSTEM, max_tokens=900)
    except LLMError:
        return None

    text = (raw or "").strip()
    fence = re.search(r"```(?:json)?\s*(.+?)```", text, re.S | re.I)
    if fence:
        text = fence.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except ValueError:
        return None

    questions = [str(q).strip() for q in data.get("questions", []) if str(q).strip()]
    tables = [t for t in data.get("tables", [])
              if isinstance(t, dict) and t.get("name") and t.get("describes")]
    summary = str(data.get("summary", "")).strip()
    if not summary and not questions:
        return None
    return {"summary": summary, "tables": tables, "questions": questions[:6]}


# ------------------------------------------------------ sanitise + validate

def sanitise(raw: str) -> str:
    """Strip the wrapping that models add despite being told not to."""
    text = (raw or "").strip()
    fence = re.search(r"```(?:sql)?\s*(.+?)```", text, re.S | re.I)
    if fence:
        text = fence.group(1)
    text = re.sub(r"^\s*(?:here'?s?|the sql is|query)[^\n]*:\s*", "", text, flags=re.I)
    # models sometimes emit reasoning before the statement; start at the real keyword
    m = re.search(r"\b(WITH|SELECT)\b", text, re.I)
    if m:
        text = text[m.start():]
    text = text.strip().rstrip(";").strip()
    return text


def validate(sql: str) -> None:
    """SELECT-only. This is both the correctness guard and the security guard,
    because whatever comes back from the model is about to be executed."""
    if not sql:
        raise LLMError("The model returned an empty query.")
    if ";" in sql:
        raise LLMError("Only a single statement is allowed.")
    if not re.match(r"^\s*(with|select)\b", sql, re.I):
        raise LLMError("Only SELECT queries are allowed.")
    stripped = re.sub(r"'[^']*'", "''", sql)  # ignore keywords inside string literals
    hit = _FORBIDDEN.search(stripped)
    if hit:
        raise LLMError("Query contains a disallowed keyword: %s" % hit.group(0).upper())


def build_prompt(schema_text: str, joins_text: str, question: str,
                 previous_error: Optional[str] = None,
                 previous_sql: Optional[str] = None) -> str:
    parts = ["Schema:", schema_text, "", joins_text, "", "Question: " + question]
    if previous_error:
        parts += ["",
                  "Your previous query failed. Fix it and return corrected SQL only.",
                  "Previous SQL:", previous_sql or "",
                  "Error: " + previous_error]
    parts += ["", "SQL:"]
    return "\n".join(parts)


def generate_sql(schema_text: str, joins_text: str, question: str,
                 previous_error: Optional[str] = None,
                 previous_sql: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
    """Returns (sql, refusal). Exactly one of them is set."""
    raw = _complete(build_prompt(schema_text, joins_text, question,
                                 previous_error, previous_sql))
    if CANNOT_ANSWER in (raw or "").upper():
        idx = raw.upper().index(CANNOT_ANSWER)
        reason = raw[idx + len(CANNOT_ANSWER):].lstrip(": ").strip()
        return None, (reason or "The uploaded data does not contain what this question needs.")
    sql = sanitise(raw)
    validate(sql)
    return sql, None
