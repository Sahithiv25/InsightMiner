from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from app.models.dto import AskRequest, AskResponse
from app.services.planner_registry import plan_from_registry
from app.services.executor import run_sql
from app.services.chart_builder import build_time_series
from app.services.narrator import narrate_insights
import numpy as np
import pandas as pd

router = APIRouter(prefix="/ask", tags=["ask"])

@router.post("/")
def ask(req: AskRequest):
    try:
        start = req.start or "2024-01-01"
        end   = req.end   or "2024-12-31"
        plan = plan_from_registry(req.question, start, end, req.dims)
        sql, meta = plan["sql"], plan["meta"]

        # bind params safely
        sql_parametrized = text(sql).bindparams(start=start, end=end)
        df = run_sql(sql_parametrized.text.replace(":start", f"'{start}'").replace(":end", f"'{end}'"))

        if df.empty:
            raise ValueError("No data for the selected period/filters.")

        # normalize
        df.columns = [c.lower() for c in df.columns]
        df = df.sort_values(df.columns[0])

        # compute stats (same as before)
        if len(df.columns) >= 3:
            period_col, value_col = df.columns[0], df.columns[1]
            agg = df.groupby(period_col)[value_col].sum().reset_index()
            s = agg[value_col].values
            periods = agg[period_col].astype(str).values
        else:
            period_col, value_col = df.columns[0], df.columns[1]
            s = df[value_col].fillna(0).values
            periods = df[period_col].astype(str).values

        start_val = float(s[0]); end_val = float(s[-1])
        total_delta_pct = ((end_val - start_val) / (start_val or 1)) * 100.0
        pct_changes = [((s[i]-s[i-1]) / (s[i-1] or 1) * 100.0) for i in range(1, len(s))] if len(s) > 1 else [0.0]
        avg_mom = float(np.mean(pct_changes))
        peak_i, low_i = int(np.argmax(s)), int(np.argmin(s))

        # top contributors last period if grouped
        top_contrib = None
        if len(df.columns) >= 3:
            dim_col = df.columns[2]
            last_period = periods[-1]
            snap = df[df[period_col] == last_period]
            tot = snap[value_col].sum() or 1.0
            snap = snap.assign(share=snap[value_col] / tot * 100.0).sort_values("share", ascending=False)
            top_contrib = [(row[dim_col], float(row[value_col]), float(row["share"])) for _, row in snap.iterrows()]

        stats = {
            "unit": meta.get("unit"),
            "start_value": start_val,
            "end_value": end_val,
            "total_delta_pct": total_delta_pct,
            "avg_mom_pct": avg_mom,
            "peak": (periods[peak_i], float(s[peak_i])),
            "lowest": (periods[low_i], float(s[low_i])),
            "top_contrib": top_contrib,
        }

        chart = build_time_series(df, dim_col=meta.get("dimension"), chart_type="line", meta=meta)
        bullets = narrate_insights(stats)
        return {
        "chart": chart.model_dump() if hasattr(chart, "model_dump") else chart.__dict__,
        "insights": bullets,
        "sql": [sql],
    }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
