from fastapi import APIRouter, HTTPException
from app.models.dto import AskRequest, AskResponse
from app.services.planner import plan
from app.services.executor import run_sql
from app.services.chart_builder import build_time_series
from app.services.narrator import narrate_insights
import numpy as np
import pandas as pd

router = APIRouter(prefix="/ask", tags=["ask"])

@router.post("", response_model=AskResponse)
def ask(req: AskRequest):
    try:
        sql, meta = plan(req.question, req.start, req.end, req.dims)
        df = run_sql(sql)
        if df.empty:
            raise ValueError("No data for the selected period/filters.")

        # Expect columns: period, value, [dimension]
        df.columns = [c.lower() for c in df.columns]
        # ensure period sorted
        df = df.sort_values(df.columns[0])
        unit = meta.get("unit")

        # If grouped by a dimension, compute shares in last period
        top_contrib = None
        if len(df.columns) >= 3:
            period_col, value_col, dim_col = df.columns[:3]
            last_period = df[period_col].iloc[-1]
            snap = df[df[period_col] == last_period]
            total_last = snap[value_col].sum() or 1.0
            snap["share"] = snap[value_col] / total_last * 100.0
            snap = snap.sort_values("share", ascending=False)
            top_contrib = [(row[dim_col], float(row[value_col]), float(row["share"])) for _, row in snap.iterrows()]

            # collapse to overall for time-series stats (sum by period)
            agg = df.groupby(period_col)[value_col].sum().reset_index()
            s = agg[value_col].values
            periods = agg[period_col].astype(str).values
        else:
            period_col, value_col = df.columns[:2]
            s = df[value_col].fillna(0).values
            periods = df[period_col].astype(str).values

        # compute deltas
        start_val = float(s[0])
        end_val   = float(s[-1])
        total_delta_pct = ((end_val - start_val) / (start_val or 1)) * 100.0
        # month-over-month average percentage change
        if len(s) > 1:
            pct_changes = []
            for i in range(1, len(s)):
                base = s[i-1] if s[i-1] != 0 else 1.0
                pct_changes.append((s[i]-s[i-1]) / base * 100.0)
            avg_mom = float(np.mean(pct_changes))
        else:
            avg_mom = 0.0

        peak_i, low_i = int(np.argmax(s)), int(np.argmin(s))
        stats = {
            "unit": unit,
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

        return AskResponse(chart=chart, insights=bullets, sql=[sql])

    except Exception as e:
        # Return JSON error so the client never gets HTML -> JSONDecodeError
        raise HTTPException(status_code=400, detail=str(e))
