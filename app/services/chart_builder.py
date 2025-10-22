from typing import Dict, List
from app.models.dto import ChartPayload, ChartSeries

def build_time_series(df, dim_col=None, chart_type="line", meta: Dict=None) -> ChartPayload:
    series: List[ChartSeries] = []
    cols = df.columns.tolist()
    # expected: period, value, [dimension]
    for _, row in df.iterrows():
        series.append(ChartSeries(
            period=str(row[cols[0]]),
            value=float(row[cols[1]]) if row[cols[1]] is not None else 0.0,
            dimension=(str(row[cols[2]]) if dim_col and cols.__len__() > 2 else None)
        ))
    return ChartPayload(type=chart_type, series=series, meta=meta or {})
