from datetime import UTC, datetime
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader

from app.operations import build_operations_dashboard


def test_extraction_outcomes_exclude_dismissed_and_pending():
    documents = [
        SimpleNamespace(state=s)
        for s in (
            "RECORDED",
            "READY_TO_RECORD",
            "NEEDS_REVIEW",
            "FAILED",
            "DISMISSED",
            "RECEIVED",
            "PROCESSING",
            "UNKNOWN",
        )
    ]
    result = build_operations_dashboard(documents, [], [])
    assert result["stats"]["completed"] == 4
    assert result["stats"]["success_rate"] == 75.0
    assert result["stats"]["pending"] == 2
    assert result["stats"]["documents"] == 8


def test_event_counts_and_partial_costs():
    event = SimpleNamespace(
        timestamp=datetime(2026, 1, 2, tzinfo=UTC), stage="extract", status="success"
    )
    usage = [SimpleNamespace(provider="provider", estimated_usd=cost) for cost in (0.02, None, 0)]
    result = build_operations_dashboard([], [event, event], usage)
    assert result["daily_events"][0]["value"] == 2
    assert result["stages"][0]["value"] == 2
    assert result["known_cost"] == 0.02
    assert result["unknown_cost_calls"] == 1
    assert result["provider_costs"][0]["calls"] == 3
    assert result["stats"]["success_rate"] is None


def test_dashboard_empty_state_renders():
    dashboard = build_operations_dashboard([], [], [])
    env = Environment(loader=FileSystemLoader("app/templates"), autoescape=True)
    html = env.get_template("operations.html").render(
        dashboard=dashboard,
        stats=dashboard["stats"],
        events=[],
        usage=[],
        q="",
        tracing="none",
        path="/operations",
        mode="demo",
        csrf="test",
    )
    assert "Upload a document to see the pipeline" in html
    assert "No model calls recorded" in html
    assert "ops-stage" in html
