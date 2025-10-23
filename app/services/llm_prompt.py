from __future__ import annotations
from typing import Dict, Any, List
from pathlib import Path
import yaml

# Builds a compact prompt including KPI glossary and schema columns
def build_prompt(question: str, kpis_yaml: Path, dims: List[str] | None) -> str:
    spec = yaml.safe_load(kpis_yaml.read_text(encoding="utf-8"))
    kpi_lines = []
    for k in spec.get("kpis", []):
        kpi_lines.append(f"- {k['key']}: {k.get('name')} | unit={k.get('unit')} | dims={k.get('allow_dimensions',[])}")
    dim_lines = []
    for d in spec.get("dimensions", []):
        dim_lines.append(f"- {d['name']}: column={d['column']} alias={d.get('alias', d['name'])}")

    schema = {
        "accounts": ["account_id","account_name","industry","country","signup_date","referral_source","plan_tier","seats","is_trial","churn_flag"],
        "subscriptions": ["subscription_id","account_id","start_date","end_date","plan_tier","seats","mrr_amount","arr_amount","is_trial","upgrade_flag","downgrade_flag","churn_flag","billing_frequency","auto_renew_flag"],
        "feature_usage": ["usage_id","subscription_id","usage_date","feature_name","usage_count","usage_duration_secs","error_count","is_beta_feature"],
        "support_tickets": ["ticket_id","account_id","submitted_at","closed_at","resolution_time_hours","priority","first_response_time_minutes","satisfaction_score","escalation_flag"],
        "churn_events": ["churn_event_id","account_id","churn_date","reason_code","refund_amount_usd","preceding_upgrade_flag","preceding_downgrade_flag","is_reactivation","feedback_text"],
    }

    fewshots = [
        {
            "q": "Compare revenue by region in 2024",
            "intent": {"kpi": "revenue_net", "dims": ["region"], "start": "2024-01-01", "end": "2024-12-31"},
        },
        {
            "q": "Show churn rate by month for 2024",
            "intent": {"kpi": "churn_rate", "dims": [], "start": "2024-01-01", "end": "2024-12-31"},
        },
        {
            "q": "Average ticket resolution time by region, 2024",
            "intent": {"kpi": "avg_resolution_time", "dims": ["region"], "start": "2024-01-01", "end": "2024-12-31"},
        },
        {
            "q": "Feature adoption by plan tier for 2024",
            "intent": {"kpi": "feature_adoption", "dims": ["plan_tier"], "start": "2024-01-01", "end": "2024-12-31"},
        },
    ]

    dims_txt = ", ".join(dims or [])
    prompt = f"""
You are a careful analytics planner. Map a user question to a KPI + dimensions + a single safe SQLite SQL query.

Constraints:
- Use only SELECT/CTE.
- No PRAGMA/DDL/DML/ATTACH/REINDEX/REPLACE.
- Use only allowed tables/columns listed below.
- Include named placeholders :start and :end when time-bounding.
- If a dimension is requested, include it as a column and GROUP BY it.
- Return STRICT JSON with keys: kpi, dims (array), sql (string). Nothing else.

Available KPIs:
{chr(10).join(kpi_lines)}

Available dimensions:
{chr(10).join(dim_lines)}

Schema (allowlisted):
{schema}

Few-shot intents (examples):
{fewshots}

User question: {question}
User-chosen dimensions (optional): {dims_txt or "[]"}
Respond with JSON: {{"kpi":"...", "dims": ["..."], "sql":"..."}}
"""
    return prompt.strip()
