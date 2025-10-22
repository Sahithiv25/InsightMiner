from typing import List, Dict, Tuple
import math

def _fmt_currency(x: float) -> str:
    return f"${x:,.0f}"

def _fmt_pct(x: float) -> str:
    return f"{x:.1f}%"

def narrate_insights(stats: Dict) -> List[str]:
    """
    Expect keys:
      unit: "USD"|"percent"|...
      start_value, end_value, total_delta_pct, avg_mom_pct
      peak: (period, value)
      lowest: (period, value)
      top_contrib: [(dim, value, share_pct)]  # optional
    """
    bullets = []

    # Overall trend
    if stats.get("unit") == "USD":
        bullets.append(
            f"Revenue grew **{_fmt_pct(stats['total_delta_pct'])}** "
            f"(from {_fmt_currency(stats['start_value'])} to {_fmt_currency(stats['end_value'])}). "
            f"Avg MoM change: {_fmt_pct(stats['avg_mom_pct'])}."
        )
    else:
        bullets.append(
            f"KPI changed **{_fmt_pct(stats['total_delta_pct'])}** over the selected period. "
            f"Avg MoM change: {_fmt_pct(stats['avg_mom_pct'])}."
        )

    # Peak / trough
    p = stats.get("peak")
    l = stats.get("lowest")
    if p:
        bullets.append(f"**Peak**: {p[0]} → {(_fmt_currency(p[1]) if stats.get('unit')=='USD' else f'{p[1]:,.2f}')} .")
    if l:
        bullets.append(f"**Lowest**: {l[0]} → {(_fmt_currency(l[1]) if stats.get('unit')=='USD' else f'{l[1]:,.2f}')} .")

    # Top contributors (for grouped charts)
    if stats.get("top_contrib"):
        top = stats["top_contrib"][:3]
        pretty = ", ".join([f"{d} {_fmt_pct(s)}" for d,_,s in top])
        bullets.append(f"**Top contributors (last month)**: {pretty}.")

    return bullets
