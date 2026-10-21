import json
import logging

from app.models import Event

logger = logging.getLogger("impact.events")


def emit(
    session,
    stage,
    operation,
    status,
    *,
    run_id=None,
    request_id=None,
    resource_id=None,
    duration_ms=None,
    error_code=None,
    **safe,
):
    """Only call-site supplied counters, codes and IDs belong here, never source text."""
    entry = Event(
        stage=stage,
        operation=operation,
        status=status,
        run_id=run_id,
        request_id=request_id,
        resource_id=resource_id,
        duration_ms=duration_ms,
        error_code=error_code,
        safe_metadata=safe,
    )
    session.add(entry)
    logger.info(
        json.dumps(
            {
                "stage": stage,
                "operation": operation,
                "status": status,
                "run_id": run_id,
                "request_id": request_id,
                "resource_id": resource_id,
                "error_code": error_code,
                "duration_ms": duration_ms,
                "safe_metadata": safe,
            }
        )
    )
    return entry
