from fastapi import APIRouter
from app.models.dto import AskRequest, AskResponse
from app.services.planner import plan
from app.services.executor import run_sql
from app.services.chart_builder import build_time_series
from app.services.narrator import narrate_basic
import numpy as np

router = APIRouter(prefix="/ask", tags=["ask"])

@router.post("", response_model=AskResponse)
def ask(req: AskRequest):
    sql, meta = plan(req.question, req.start, req.end, req.dims)
    df = run_sql(sql)

    # simple stats for narration
    if not df.empty:
        vals = df.iloc[:,1].fillna(0).values
        periods = df.iloc[:,0].astype(str).values
        delta = (vals[-1]-vals[0]) / (vals[0] or 1) * 100 if len(vals) > 1 else 0
        peak_i, low_i = int(np.argmax(vals)), int(np.argmin(vals))
        stats = {
            "delta": float(delta),
            "percent": meta.get("unit")=="percent",
            "peak": (periods[peak_i], float(vals[peak_i])),
            "lowest": (periods[low_i], float(vals[low_i])),
        }
    else:
        stats = {}

    chart = build_time_series(df, dim_col=meta.get("dimension"), chart_type="line", meta=meta)
    bullets = narrate_basic(stats)

    return AskResponse(chart=chart, insights=bullets, sql=[sql])
