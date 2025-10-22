from pydantic import BaseModel
from typing import List, Optional, Any

class AskRequest(BaseModel):
    question: str
    start: Optional[str] = None  # "2024-01-01"
    end: Optional[str] = None    # "2024-12-31"
    dims: Optional[List[str]] = None  # ["region"]

class ChartSeries(BaseModel):
    period: str
    value: float
    dimension: Optional[str] = None

class ChartPayload(BaseModel):
    type: str
    series: List[ChartSeries]
    meta: dict

class AskResponse(BaseModel):
    chart: ChartPayload
    insights: List[str]
    sql: List[str]
