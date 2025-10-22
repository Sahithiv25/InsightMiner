from __future__ import annotations
import yaml, re
from dataclasses import dataclass
from jinja2 import Template
from pathlib import Path
from typing import Dict, Any, Optional, List

# ---------- Load registry ----------
REG_PATH = Path("app/data/kpis.yaml")

@dataclass
class DimensionDef:
    name: str
    column: str
    alias: str
    synonyms: List[str]

@dataclass
class KpiDef:
    key: str
    name: str
    description: str
    unit: str
    sql: str
    synonyms: List[str]
    allow_dimensions: List[str]

class Registry:
    def __init__(self, path: Path):
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        self.defaults = raw.get("defaults", {})
        self.dimensions: Dict[str, DimensionDef] = {}
        for d in raw.get("dimensions", []):
            self.dimensions[d["name"]] = DimensionDef(
                name=d["name"], column=d["column"], alias=d.get("alias", d["name"]),
                synonyms=d.get("synonyms", [])
            )
        self.kpis: Dict[str, KpiDef] = {}
        for k in raw.get("kpis", []):
            self.kpis[k["key"]] = KpiDef(
                key=k["key"], name=k["name"], description=k.get("description",""),
                unit=k.get("unit",""), sql=k["sql"], synonyms=k.get("synonyms",[]),
                allow_dimensions=k.get("allow_dimensions", [])
            )

REG = Registry(REG_PATH)

# ---------- Intent resolution ----------
def _find_kpi(question: str) -> KpiDef:
    q = question.lower()
    # exact key or name match
    for k in REG.kpis.values():
        if k.key in q or k.name.lower() in q:
            return k
    # synonym match
    for k in REG.kpis.values():
        if any(syn in q for syn in k.synonyms):
            return k
    # default to revenue
    return REG.kpis["revenue_net"]

def _find_dimension(question: str, dims_param: Optional[List[str]], kpi: KpiDef) -> Optional[DimensionDef]:
    # explicit param
    if dims_param:
        want = dims_param[0]
        if want in kpi.allow_dimensions and want in REG.dimensions:
            return REG.dimensions[want]
    # heuristics from text
    q = question.lower()
    for dim_name, d in REG.dimensions.items():
        if dim_name in kpi.allow_dimensions and (dim_name in q or any(s in q for s in d.synonyms)):
            return d
    return None

# ---------- Render SQL ----------
def plan_from_registry(question: str, start: str, end: str,
                       dims_param: Optional[List[str]] = None) -> Dict[str, Any]:
    kpi = _find_kpi(question)
    dim = _find_dimension(question, dims_param, kpi)

    # Map base tables to aliases used in KPI SQLs
    alias_map = {
        "accounts.": "a.",
        "subscriptions.": "subs.",
        "feature_usage.": "f.",
    }

    if dim:
        dim_col = dim.column
        # Swap base table prefixes to the aliases actually used in the KPI SQL
        for base, alias in alias_map.items():
            if dim_col.startswith(base):
                dim_col = dim_col.replace(base, alias, 1)
                break
        dim_select = f", {dim_col} AS {dim.alias}"
        dim_group  = ", 3"   # period=1, value=2, dimension=3
    else:
        dim_select = ""
        dim_group  = ""

    tmpl = Template(kpi.sql)
    sql = tmpl.render(dim_select=dim_select, dim_group=dim_group)

    meta = {
        "kpi": kpi.key,
        "unit": kpi.unit,
        "dimension": (dim.alias if dim else None),
        "start": start,
        "end": end,
    }
    return {"sql": sql, "meta": meta}