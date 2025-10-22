from typing import Tuple, Dict
import re
from datetime import date

# ultra-simple intent resolver: revenue vs churn
def plan(question: str, start: str|None, end: str|None, dims: list[str]|None):
    q = question.lower()
    start = start or "2024-01-01"
    end   = end   or "2024-12-31"
    dim = None
    if dims:
        dim = dims[0]
    elif "region" in q or "country" in q:
        dim = "region"

    if any(w in q for w in ["revenue","sales","mrr","arr"]):
    # Monthly ACTIVE MRR: a subscription counts in a month if it overlaps that month.
        sql = f"""
        WITH RECURSIVE months(mstart) AS (
        SELECT date('{start}', 'start of month')
        UNION ALL
        SELECT date(mstart, '+1 month')
        FROM months
        WHERE mstart < date('{end}', 'start of month')
        ),
        subs AS (
        SELECT s.subscription_id, s.account_id, s.mrr_amount,
                date(s.start_date) AS sstart,
                date(COALESCE(s.end_date, '9999-12-31')) AS send
        FROM subscriptions s
        )
        SELECT
        m.mstart AS period,
        SUM(COALESCE(subs.mrr_amount,0)) AS value
        {", a.country AS region" if dim == "region" else ""}
        FROM months m
        JOIN subs
        ON subs.sstart <= date(m.mstart, 'start of month', '+1 month', '-1 day') -- month_end
        AND subs.send  >= m.mstart                                                  -- month_start
        JOIN accounts a ON a.account_id = subs.account_id
        GROUP BY 1 {", 3" if dim == "region" else ""}
        ORDER BY 1;
        """
        meta = {"kpi": "revenue_net", "unit": "USD", "dimension": dim}
        return sql, meta
