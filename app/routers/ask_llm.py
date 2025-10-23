from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import text
from app.models.dto import AskRequest, AskResponse, ChartPayload, ChartSeries
from app.services.planner_llm import plan_with_llm
from app.services.executor import run_sql
from app.services.chart_builder import build_time_series
from app.services.narrator import narrate_insights
import numpy as np
import pandas as pd

router = APIRouter(prefix="/ask-llm", tags=["ask-llm"])

@router.post("", response_model=AskResponse)
def ask_llm(req: AskRequest, response: Response):
    try:
        start = req.start or "2024-01-01"
        end   = req.end   or "2024-12-31"

        plan = plan_with_llm(req.question, start, end, req.dims or [])
        sql, meta = plan["sql"], plan["meta"]

        planner = plan["meta"].get("planner", "unknown")
        response.headers["X-Planner"] = planner  # <--- heade

        df = run_sql(sql.replace(":start", f"'{start}'").replace(":end", f"'{end}'"))
        if df.empty:
            raise ValueError("No data for the selected period/filters.")

        df.columns = [c.lower() for c in df.columns]
        df = df.sort_values(df.columns[0])

        # summarize for insights
        period_col, value_col = df.columns[0], df.columns[1]
        if len(df.columns) >= 3:
            agg = df.groupby(period_col)[value_col].sum().reset_index()
        else:
            agg = df[[period_col, value_col]]
        s = agg[value_col].fillna(0).values
        periods = agg[period_col].astype(str).values
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

        chart = build_time_series(df, dim_col=meta.get("dimension"), chart_type="line", meta=meta)
        bullets = narrate_insights(stats)
        return AskResponse(chart=chart, insights=bullets, sql=[sql])

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
