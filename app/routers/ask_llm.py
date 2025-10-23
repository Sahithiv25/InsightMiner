from fastapi import APIRouter, HTTPException, Response
import numpy as np, pandas as pd

from app.models.dto import AskRequest, AskResponse
from app.services.planner_llm import plan_with_llm
from app.services.executor import run_sql
from app.services.chart_builder import build_time_series
from app.services.narrator import narrate_insights as deterministic_narrator
from app.services.narrator_llm import narrate_with_llm
from app.core.config import settings

router = APIRouter(prefix="/ask-llm", tags=["ask-llm"])

@router.post("", response_model=AskResponse)
def ask_llm(req: AskRequest, response: Response):
    try:
        start = req.start or "2024-01-01"
        end   = req.end   or "2024-12-31"

        plan = plan_with_llm(req.question, start, end, req.dims or [])
        if not plan or "sql" not in plan or "meta" not in plan:
            raise ValueError("Planner returned no plan")

        sql, meta = plan["sql"], plan["meta"]
        response.headers["X-Planner"] = meta.get("planner", "unknown")

        df = run_sql(sql.replace(":start", f"'{start}'").replace(":end", f"'{end}'"))
        if df.empty:
            raise ValueError("No data for the selected period/filters.")

        df.columns = [c.lower() for c in df.columns]
        df = df.sort_values(df.columns[0])  # period asc

        # ---------- compute stats for narrator ----------
        period_col, value_col = df.columns[0], df.columns[1]
        if len(df.columns) >= 3:
            agg = df.groupby(period_col)[value_col].sum().reset_index()
        else:
            agg = df[[period_col, value_col]]

        s = agg[value_col].fillna(0).to_numpy()
        periods = agg[period_col].astype(str).to_numpy()
        start_val, end_val = float(s[0]), float(s[-1])
        total_delta_pct = ((end_val - start_val) / (start_val or 1)) * 100.0
        pct_changes = [((s[i]-s[i-1])/(s[i-1] or 1)*100.0) for i in range(1,len(s))] if len(s)>1 else [0.0]
        avg_mom = float(np.mean(pct_changes))
        peak_i, low_i = int(np.argmax(s)), int(np.argmin(s))
        stats = {
            "unit": meta.get("unit"),
            "start_value": start_val,
            "end_value": end_val,
            "total_delta_pct": total_delta_pct,
            "avg_mom_pct": avg_mom,
            "peak": (periods[peak_i], float(s[peak_i])),
            "lowest": (periods[low_i], float(s[low_i])),
        }

        # ---------- choose narrator ----------
        mode = (settings.INSIGHTS_MODE or "auto").lower()
        bullets = None
        source = "deterministic"

        if mode in ("llm", "auto"):
            bullets = narrate_with_llm(stats, df)
            if bullets:
                source = "llm"
            elif mode == "llm":
                # if forced LLM but failed, still fallback
                bullets = deterministic_narrator(stats)
                source = "fallback"

        if bullets is None:
            bullets = deterministic_narrator(stats)
            source = "deterministic"

        response.headers["X-Insights-Source"] = source
        meta["insights_source"] = source  # surface in JSON too

        chart = build_time_series(df, dim_col=meta.get("dimension"), chart_type="line", meta=meta)
        return AskResponse(chart=chart, insights=bullets, sql=[sql])

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
