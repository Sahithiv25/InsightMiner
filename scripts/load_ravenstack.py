import argparse, pathlib, sqlite3, pandas as pd, os, sys
from datetime import datetime

def read_csv(path, **kw):
    return pd.read_csv(path, na_values=["", "null", "None"], keep_default_na=True, **kw)

def normalize_booleans(df, cols):
    for c in cols:
        if c in df.columns:
            df[c] = df[c].astype("boolean")
    return df

def coerce_numeric(df, cols):
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

def _resolve_sqlite_path(db_uri: str) -> pathlib.Path:
    """
    Accepts things like:
      - sqlite:///data/warehouse/kpi_copilot.db
      - data/warehouse/kpi_copilot.db
      - D:\\InsightMiner\\data\\warehouse\\kpi_copilot.db
    Returns an absolute pathlib.Path and ensures parent dirs exist.
    """
    if db_uri.startswith("sqlite:///"):
        p = pathlib.Path(db_uri.replace("sqlite:///", "", 1))
    else:
        p = pathlib.Path(db_uri)
    p = p.expanduser().resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    return p

def load_tables(csv_dir: pathlib.Path, db_uri: str):
    csv_dir = csv_dir.expanduser().resolve()
    if not csv_dir.exists():
        print(f"[ERROR] CSV directory not found: {csv_dir}", file=sys.stderr)
        sys.exit(2)

    db_path = _resolve_sqlite_path(db_uri)

    # Quick write test to catch permission issues early
    try:
        db_path.touch(exist_ok=True)
    except Exception as e:
        print(f"[ERROR] Cannot create DB file at {db_path}: {e}", file=sys.stderr)
        sys.exit(3)

    # Connect
    con = sqlite3.connect(str(db_path))
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA synchronous=NORMAL;")
    con.execute("PRAGMA foreign_keys=ON;")

    # --- accounts
    acc = read_csv(csv_dir/"ravenstack_accounts.csv", parse_dates=["signup_date"])
    acc = normalize_booleans(acc, ["is_trial","churn_flag"])
    acc.to_sql("accounts", con, if_exists="replace", index=False)

    # --- subscriptions
    subs = read_csv(csv_dir/"ravenstack_subscriptions.csv", parse_dates=["start_date","end_date"])
    subs = normalize_booleans(subs, ["is_trial","upgrade_flag","downgrade_flag","churn_flag","auto_renew_flag"])
    subs = coerce_numeric(subs, ["mrr_amount","arr_amount","seats"])
    subs.to_sql("subscriptions", con, if_exists="replace", index=False)

    # --- feature_usage
    fu = read_csv(csv_dir/"ravenstack_feature_usage.csv", parse_dates=["usage_date"])
    fu = normalize_booleans(fu, ["is_beta_feature"])
    fu = coerce_numeric(fu, ["usage_count","usage_duration_secs","error_count"])
    fu.to_sql("feature_usage", con, if_exists="replace", index=False)

    # --- support_tickets
    st = read_csv(csv_dir/"ravenstack_support_tickets.csv", parse_dates=["submitted_at","closed_at"])
    st = normalize_booleans(st, ["escalation_flag"])
    st = coerce_numeric(st, ["resolution_time_hours","first_response_time_minutes","satisfaction_score"])
    st.to_sql("support_tickets", con, if_exists="replace", index=False)

    # --- churn_events
    ce = read_csv(csv_dir/"ravenstack_churn_events.csv", parse_dates=["churn_date"])
    ce = normalize_booleans(ce, ["preceding_upgrade_flag","preceding_downgrade_flag","is_reactivation"])
    ce = coerce_numeric(ce, ["refund_amount_usd"])
    ce.to_sql("churn_events", con, if_exists="replace", index=False)

    con.executescript("""
    CREATE INDEX IF NOT EXISTS idx_accounts_id ON accounts(account_id);
    CREATE INDEX IF NOT EXISTS idx_accounts_country ON accounts(country);
    CREATE INDEX IF NOT EXISTS idx_accounts_signup ON accounts(signup_date);

    CREATE INDEX IF NOT EXISTS idx_subs_id ON subscriptions(subscription_id);
    CREATE INDEX IF NOT EXISTS idx_subs_account ON subscriptions(account_id);
    CREATE INDEX IF NOT EXISTS idx_subs_start ON subscriptions(start_date);
    CREATE INDEX IF NOT EXISTS idx_subs_end ON subscriptions(end_date);
    CREATE INDEX IF NOT EXISTS idx_subs_plan ON subscriptions(plan_tier);

    CREATE INDEX IF NOT EXISTS idx_fu_sub ON feature_usage(subscription_id);
    CREATE INDEX IF NOT EXISTS idx_fu_date ON feature_usage(usage_date);
    CREATE INDEX IF NOT EXISTS idx_fu_feature ON feature_usage(feature_name);

    CREATE INDEX IF NOT EXISTS idx_st_account ON support_tickets(account_id);
    CREATE INDEX IF NOT EXISTS idx_st_submitted ON support_tickets(submitted_at);

    CREATE INDEX IF NOT EXISTS idx_ce_account ON churn_events(account_id);
    CREATE INDEX IF NOT EXISTS idx_ce_date ON churn_events(churn_date);
    """)

    con.commit()
    con.close()
    print(f"[OK] Loaded CSVs into {db_path}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv_dir", required=True, help="path to /data/raw")
    ap.add_argument("--db", default="sqlite:///data/warehouse/kpi_copilot.db")
    args = ap.parse_args()
    load_tables(pathlib.Path(args.csv_dir), args.db)
