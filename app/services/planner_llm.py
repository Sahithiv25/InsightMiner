from __future__ import annotations
import json, os, logging
from typing import Any, Dict, List, Optional
from pathlib import Path
from app.services.sql_safety import validate_sql
from app.services.llm_prompt import build_prompt
from app.services.planner_registry import plan_from_registry, REG_PATH
from app.services.executor import run_sql_explain

log = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
TIMEOUT = int(os.getenv("LLM_TIMEOUT", "12"))
MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "600"))

def _call_llm(prompt: str) -> Optional[str]:
    if not OPENAI_API_KEY:
        log.info("planner=registry reason=no_api_key")
        return None
    try:
        import openai  # openai>=1.0.0
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
        log.warning("planner=registry reason=llm_call_failed err=%s", e)
        return None

def _fallback(question: str, start: str, end: str, dims: Optional[List[str]]):
    plan = plan_from_registry(question, start, end, dims or [])
    # ensure shape and tag
    if not plan or "sql" not in plan or "meta" not in plan:
        raise RuntimeError("registry planner returned invalid plan")
    plan["meta"]["planner"] = "registry"
    return plan

def plan_with_llm(question: str, start: str, end: str, dims: Optional[List[str]]):
    try:
        prompt = build_prompt(question, Path(REG_PATH), dims or [])
    except Exception as e:
        log.warning("planner=registry reason=prompt_build_failed err=%s", e)
        return _fallback(question, start, end, dims)

    raw = _call_llm(prompt)
    if not raw:
        return _fallback(question, start, end, dims)

    try:
        payload = json.loads(raw)
        kpi = payload.get("kpi")
        sql = payload.get("sql")
        idims = payload.get("dims") or []
        if not isinstance(sql, str) or not kpi:
            raise ValueError("missing kpi/sql")
    except Exception as e:
        log.warning("planner=registry reason=llm_json_invalid err=%s raw=%s", e, str(raw)[:300])
        return _fallback(question, start, end, dims)

    ok, msg = validate_sql(sql)
    if not ok:
        log.warning("planner=registry reason=unsafe_sql msg=%s", msg)
        return _fallback(question, start, end, dims)

    # EXPLAIN gate (parse only)
    try:
        run_sql_explain(sql.replace(":start", f"'{start}'").replace(":end", f"'{end}'"))
    except Exception as e:
        log.warning("planner=registry reason=explain_failed err=%s", e)
        return _fallback(question, start, end, dims)

    log.info("planner=llm question=%s", question)
    meta = {
        "kpi": kpi,
        "unit": None,
        "dimension": (idims[0] if idims else None),
        "start": start, "end": end,
        "planner": "llm",
    }
    return {"sql": sql, "meta": meta}
