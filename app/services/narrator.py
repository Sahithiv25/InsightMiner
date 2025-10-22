from typing import List
import math

def narrate_basic(stats: dict) -> List[str]:
    bullets = []
    if "delta" in stats:
        d = stats["delta"]
        bullets.append(f"Change over period: {d:+.1f}{'%' if stats.get('percent') else ''}.")
    if "peak" in stats:
        bullets.append(f"Peak at {stats['peak'][0]} → {stats['peak'][1]:,.0f}.")
    if "lowest" in stats:
        bullets.append(f"Lowest at {stats['lowest'][0]} → {stats['lowest'][1]:,.0f}.")
    return bullets or ["Trend generated from selected KPI and timeframe."]
