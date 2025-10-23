from __future__ import annotations
import json, os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from pathlib import Path
import openai

from app.services.sql_safety import validate_sql
from app.services.llm_prompt import build_prompt
from app.services.planner_registry import plan_from_registry, REG_PATH  # fallback
from app.services.executor import run_sql, run_sql_explain  # add explain in executor (below)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
TIMEOUT = int(os.getenv("LLM_TIMEOUT", "12"))
MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "600"))

def _call_llm(prompt: str) -> Optional[str]:
    if not OPENAI_API_KEY:
        return None  # no LLM configured → force fallback
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[{"role":"user","content":prompt}],
            temperature=0.2,
            max_tokens=MAX_TOKENS,
            timeout=TIMEOUT,
        )
        return resp.choices[0].message.content
    except Exception as e:
        return None

def plan_with_llm(question: str, start: str, end: str, dims: Optional[List[str]]) -> Dict[str, Any]:
    prompt = build_prompt(question, Path(REG_PATH), dims or [])
    raw = _call_llm(prompt)
    if not raw:
        # fallback to registry
        # return plan_from_registry(question, start, end, dims)
        return None

    # must be strict JSON
    try:
        payload = json.loads(raw)
        kpi = payload.get("kpi")
        sql = payload.get("sql")
        idims = payload.get("dims") or []
        if not isinstance(sql, str) or not isinstance(idims, list) or not kpi:
            raise ValueError("LLM JSON missing keys")
    except Exception:
        return plan_from_registry(question, start, end, dims)

    # safety checks
    ok, msg = validate_sql(sql)
    if not ok:
        # refuse unsafe SQL; fallback
        return plan_from_registry(question, start, end, dims)

    # **EXPLAIN** gate (no execution; just ensure SQLite parses it)
    try:
        run_sql_explain(sql.replace(":start", f"'{start}'").replace(":end", f"'{end}'"))
    except Exception:
        return plan_from_registry(question, start, end, dims)

    # Plan accepted
    meta = {
        "kpi": kpi,
        "unit": None,         # narrator can fill from KPI registry if needed
        "dimension": (idims[0] if idims else None),
        "start": start, "end": end,
        "planner":"llm",
    }
    return {"sql": sql, "meta": meta}
