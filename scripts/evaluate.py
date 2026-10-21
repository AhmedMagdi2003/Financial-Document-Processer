"""Routing benchmark by default; optional live model evaluation is explicitly opt-in."""

import argparse
import json
from pathlib import Path
from time import perf_counter

from sqlalchemy.orm import Session

from app.ai import provider_for
from app.config import Settings
from app.db import make_engine
from app.inspection import inspect
from app.models import uid

FIELDS = ("vendor", "date", "document_number", "grand_total", "currency", "tax")


def evaluate(live=False):
    settings = Settings()
    if live and settings.provider in {"fixture", "none"}:
        raise RuntimeError("Configure an explicit live provider before --live evaluation")
    manifest = json.loads(Path("tests/fixtures/ground_truth.json").read_text(encoding="utf-8"))
    results = []
    field_scores = {field: {"correct": 0, "assessed": 0} for field in FIELDS}
    engine = make_engine(settings.database_url.get_secret_value()) if live else None
    for row in manifest:
        started = perf_counter()
        inspected = inspect(
            (Path("tests/fixtures") / row["file"]).read_bytes(),
            settings.max_file_bytes,
            settings.max_pages,
        )
        result = {
            "file": row["file"],
            "route": inspected.route,
            "route_correct": inspected.route == row["route"],
            "routing_ms": round((perf_counter() - started) * 1000, 3),
            "live_candidate": None,
            "live_error": None,
        }
        if live:
            with Session(engine) as session:
                run_id = uid()
                provider = provider_for(settings, session, run_id)
                try:
                    candidate = provider.extract(inspected, row["sha256"])
                    result["live_candidate"] = candidate.model_dump(mode="json")
                    for field in FIELDS:
                        expected = row["candidate"].get(field)
                        actual = result["live_candidate"].get(field)
                        if (
                            field in {"grand_total", "tax"}
                            and actual is not None
                            and expected is not None
                        ):
                            from decimal import Decimal

                            correct = Decimal(actual) == Decimal(expected)
                        else:
                            correct = actual == expected
                        field_scores[field]["assessed"] += 1
                        field_scores[field]["correct"] += int(correct)
                except Exception as exc:
                    result["live_error"] = type(exc).__name__
                result["run_id"] = run_id
                result["llm_calls"] = provider.calls
                session.commit()
        result["elapsed_ms"] = round((perf_counter() - started) * 1000, 3)
        results.append(result)
    report = {
        "sample_size": len(results),
        "live_inference": live,
        "provider": settings.provider if live else None,
        "model": settings.model_name if live else None,
        "routing_correct": sum(r["route_correct"] for r in results),
        "live_field_scores": field_scores,
        "limitation": "Small synthetic set. Routing is not extraction accuracy. "
        "Without --live, no model fields, token usage or cost are evaluated.",
        "documents": results,
    }
    output = Path("sample_outputs")
    output.mkdir(exist_ok=True)
    (output / ("live-evaluation.json" if live else "routing-evaluation.json")).write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(f"Routing: {report['routing_correct']}/{len(results)}. Live inference: {live}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    evaluate(parser.parse_args().live)
