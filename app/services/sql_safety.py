import re
from typing import Dict, List, Tuple

# Allowlist = the only tables/columns queries are allowed to reference
ALLOWLIST: Dict[str, List[str]] = {
    "accounts": [
        "account_id","account_name","industry","country","signup_date","referral_source",
        "plan_tier","seats","is_trial","churn_flag"
    ],
    "subscriptions": [
        "subscription_id","account_id","start_date","end_date","plan_tier","seats",
        "mrr_amount","arr_amount","is_trial","upgrade_flag","downgrade_flag","churn_flag",
        "billing_frequency","auto_renew_flag"
    ],
    "feature_usage": [
        "usage_id","subscription_id","usage_date","feature_name","usage_count",
        "usage_duration_secs","error_count","is_beta_feature"
    ],
    "support_tickets": [
        "ticket_id","account_id","submitted_at","closed_at","resolution_time_hours",
        "priority","first_response_time_minutes","satisfaction_score","escalation_flag"
    ],
    "churn_events": [
        "churn_event_id","account_id","churn_date","reason_code","refund_amount_usd",
        "preceding_upgrade_flag","preceding_downgrade_flag","is_reactivation","feedback_text"
    ],
}

DANGEROUS = re.compile(
    r"(;)|\b(update|delete|insert|drop|create|alter|pragma|attach|vacuum|reindex|replace)\b",
    re.IGNORECASE
)

def _all_columns() -> List[str]:
    cols = []
    for t, cs in ALLOWLIST.items():
        cols.extend([f"{t}.{c}" for c in cs])
        cols.extend(cs)
    return cols

def validate_sql(sql: str) -> Tuple[bool, str]:
    s = sql.strip()

    # 1) Only one statement
    if s.count(";") > 1:
        return False, "Multiple statements detected"
    # allow single trailing ; by stripping it for checks
    s_no_sc = s[:-1] if s.endswith(";") else s

    # 2) Must begin with SELECT or WITH
    if not re.match(r"^\s*(select|with)\b", s_no_sc, re.IGNORECASE):
        return False, "Only SELECT/CTE queries are allowed"

    # 3) No dangerous keywords
    if DANGEROUS.search(s_no_sc):
        return False, "Dangerous SQL keyword detected"

    # 4) Referenced tables must be in allowlist
    referenced = re.findall(r"\b(from|join)\s+([a-zA-Z_][\w\.]*)", s_no_sc, re.IGNORECASE)
    for _, name in referenced:
        base = name.split(".")[0]
        # strip aliasing like "accounts as a"
        base = base.replace(",", "")
        if base.lower() not in ALLOWLIST.keys():
            return False, f"Table not allowlisted: {base}"

    # 5) Columns check (best-effort)
    # If columns are qualified, ensure they are in allowlist
    qualified_cols = set(re.findall(r"\b([a-zA-Z_][\w]*)\.([a-zA-Z_][\w]*)\b", s_no_sc))
    for t, c in qualified_cols:
        if t.lower() not in ALLOWLIST or c not in ALLOWLIST[t.lower()]:
            return False, f"Column not allowlisted: {t}.{c}"

    # 6) Require date bounds placeholders for time-series KPIs (best-effort)
    if ":start" in s_no_sc and ":end" in s_no_sc:
        return True, "ok"
    # If not present, still allow (some queries may not be time-bounded), but warn
    return True, "ok (no :start/:end placeholders found)"
