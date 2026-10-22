"""Presentation aggregates for the operations dashboard; no database writes."""

from collections import Counter, defaultdict


def _bars(counts):
    maximum = max(counts.values(), default=0) or 1
    return [{"label": label, "value": value, "maximum": maximum} for label, value in counts.items()]


def build_operations_dashboard(documents, events, usage):
    states = Counter(d.state for d in documents)
    successful = sum(states[s] for s in ("RECORDED", "READY_TO_RECORD", "NEEDS_REVIEW"))
    completed = successful + states["FAILED"]
    stats = {
        "documents": len(documents),
        "completed": completed,
        "successful": successful,
        "failed": states["FAILED"],
        "review": states["NEEDS_REVIEW"],
        "recorded": states["RECORDED"],
        "pending": states["RECEIVED"] + states["PROCESSING"],
        "dismissed": states["DISMISSED"],
        "success_rate": round(100 * successful / completed, 1) if completed else None,
    }
    daily = Counter(e.timestamp.strftime("%Y-%m-%d") for e in events)
    stages = Counter(e.stage or "Unspecified" for e in events)
    providers = defaultdict(lambda: {"known": 0.0, "unknown": 0, "calls": 0})
    for item in usage:
        row = providers[item.provider or "Unspecified"]
        row["calls"] += 1
        if item.estimated_usd is None:
            row["unknown"] += 1
        else:
            row["known"] += float(item.estimated_usd)
    maximum = max((r["known"] for r in providers.values()), default=0) or 1
    return {
        "stats": stats,
        "states": _bars(dict(sorted(states.items()))),
        "daily_events": _bars(dict(sorted(daily.items()))),
        "stages": _bars(dict(stages.most_common())),
        "event_statuses": sorted({e.status for e in events}),
        "provider_costs": [
            {"label": name, **row, "maximum": maximum} for name, row in sorted(providers.items())
        ],
        "known_cost": sum(r["known"] for r in providers.values()),
        "unknown_cost_calls": sum(r["unknown"] for r in providers.values()),
    }
