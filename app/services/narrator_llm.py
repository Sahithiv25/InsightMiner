from __future__ import annotations
import os, json
from typing import List, Dict, Any, Optional
import pandas as pd
from app.core.config import settings

def _build_stats_block(stats: Dict[str, Any]) -> str:
    unit = stats.get("unit") or ""
    sv   = stats.get("start_value")
    ev   = stats.get("end_value")
    tdp  = stats.get("total_delta_pct")
    amp  = stats.get("avg_mom_pct")
    peak = stats.get("peak")   # (period, value)
    low  = stats.get("lowest") # (period, value)
    def _fmt(v):
        if v is None: return "null"
        if isinstance(v, float): 
            return round(v, 3)
        return v
    return (
        f"unit={unit}\n"
        f"start_value={_fmt(sv)}\n"
        f"end_value={_fmt(ev)}\n"
        f"total_delta_pct={_fmt(tdp)}\n"
        f"avg_mom_pct={_fmt(amp)}\n"
        f"peak_period={_fmt(peak[0] if peak else None)} peak_value={_fmt(peak[1] if peak else None)}\n"
        f"low_period={_fmt(low[0] if low else None)} low_value={_fmt(low[1] if low else None)}\n"
    )

def _slice_table(df: pd.DataFrame, max_rows: int = 6) -> str:
    # Provide a tiny sample (first & last few rows). Remove free text columns if any
    keep = [c for c in df.columns if c not in {"feedback_text", "account_name"}]
    sdf = df[keep]
    head = sdf.head(max_rows//2)
    tail = sdf.tail(max_rows - len(head))
    sample = pd.concat([head, tail]) if len(sdf) > max_rows else sdf
    # Render as CSV-like text to keep tokens low
    return sample.to_csv(index=False)[:1200]  # hard cap

PROMPT_TMPL = """You are a terse analytics writer.
Write 2–3 executive bullet points about the KPI trend using ONLY the provided stats and tiny data sample.
Avoid restating the raw numbers unless adding insight (e.g., growth drivers, seasonality, spikes).
Be concise, neutral, and non-hypey. Do not invent causes not supported by the data.
If unit is 'USD', format with $ and commas (no decimals). If percent, show like 12.3%.

Return plain text with each bullet starting with '- '. No preamble, no title.

STATS:
{stats_block}

SAMPLE (CSV):
{table_block}
"""

def _call_openai(prompt: str) -> Optional[str]:
    key = settings.OPENAI_API_KEY
    if not key:
        return None
    try:
        import openai  # openai>=1.0
        client = openai.OpenAI(api_key=key)
        resp = client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[{"role":"user","content":prompt}],
            temperature=0.2,
            max_tokens=settings.LLM_MAX_TOKENS,
            timeout=settings.LLM_TIMEOUT,
        )
        return resp.choices[0].message.content
    except Exception:
        return None

def narrate_with_llm(stats: Dict[str, Any], df: pd.DataFrame) -> Optional[List[str]]:
    prompt = PROMPT_TMPL.format(
        stats_block=_build_stats_block(stats),
        table_block=_slice_table(df),
    )
    text = _call_openai(prompt)
    if not text:
        return None
    # Expect bullets prefixed with "- "
    lines = [ln.strip() for ln in text.splitlines() if ln.strip().startswith("- ")]
    # minimal cleanup
    bullets = [ln[2:].strip() for ln in lines][:3]
    return bullets or None
