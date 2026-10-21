import csv
import io
import re
from datetime import date, timedelta
from decimal import Decimal
from time import perf_counter
from typing import TypedDict

import httpx
from langgraph.graph import END, START, StateGraph
from langsmith import tracing_context
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from app.ai import ProviderError, digest_bytes, provider_for
from app.inspection import inspect
from app.integrations import IntegrationError, Sheets, Storage, safe_filename
from app.models import (
    Attempt,
    Category,
    Delivery,
    Document,
    Expense,
    Idempotency,
    Issue,
    Project,
    now,
    uid,
)
from app.observability import current_run, emit
from app.schemas import Candidate


class Conflict(ValueError):
    pass


def normalized(value):
    return re.sub(r"[^\w]", "", (value or "").casefold())


def validate(candidate: Candidate):
    issues = []

    def issue(code, severity, field, explanation, **evidence):
        issues.append(
            dict(
                code=code,
                severity=severity,
                field=field,
                explanation=explanation,
                evidence=evidence,
            )
        )

    if candidate.document_type == "credit_note" or (
        candidate.grand_total is not None and candidate.grand_total < 0
    ):
        raise Conflict("Refunds and credit notes are outside this prototype's scope")
    if candidate.grand_total is None or candidate.grand_total == 0:
        issue("MISSING_GRAND_TOTAL", "blocking", "grand_total", "Provide a positive explicit total")
    if candidate.currency is None:
        issue("MISSING_CURRENCY", "blocking", "currency", "Provide the document currency")
    for name in ("subtotal", "tax", "discount"):
        value = getattr(candidate, name)
        if value is not None and value < 0:
            raise Conflict(f"Negative {name} is not supported")
    # Only defensible labeled arithmetic; absent components never become guessed zeros.
    if (
        candidate.subtotal is not None
        and candidate.grand_total is not None
        and candidate.tax_mode in {"inclusive", "exclusive"}
    ):
        expected = candidate.subtotal
        if candidate.tax_mode == "exclusive":
            if candidate.tax is None:
                expected = None
            else:
                expected += candidate.tax
        if candidate.discount is not None:
            if candidate.discount_explicit and expected is not None:
                expected -= candidate.discount
            else:
                expected = None
        if expected is not None and abs(expected - candidate.grand_total) > Decimal("0.02"):
            issue(
                "TOTAL_INCONSISTENCY",
                "review",
                "grand_total",
                "Labeled subtotal/tax/discount conflict with total (tolerance 0.02)",
                expected=str(expected),
                actual=str(candidate.grand_total),
            )
    if not candidate.vendor:
        issue("VENDOR_UNKNOWN", "warning", "vendor", "Vendor absent; nonblocking prototype policy")
    if not candidate.date:
        issue("DATE_UNKNOWN", "warning", "date", "Date absent; nonblocking prototype policy")
    elif candidate.date > date.today() + timedelta(days=7) or candidate.date.year < 2000:
        issue("DATE_IMPLAUSIBLE", "warning", "date", "Check the document date")
    return issues


def find_duplicates(session, candidate, document_id):
    vendor = normalized(candidate.vendor)
    if not vendor:
        return []
    matches = []
    query = select(Expense).where(
        Expense.vendor_normalized == vendor, Expense.document_id != document_id
    )
    for other in session.scalars(query):
        same_number = (
            candidate.document_number
            and other.document_number
            and normalized(candidate.document_number) == other.document_number
        )
        same_purchase = (
            candidate.date
            and str(candidate.date) == other.date
            and candidate.grand_total == other.total
            and candidate.currency == other.currency
        )
        if same_number or same_purchase:
            # Different explicit line descriptions reduce, but do not certify away, matches.
            other_doc = session.get(Document, other.document_id)
            other_items = (other_doc.candidate or {}).get("items", [])
            if not same_number and candidate.items and other_items:
                if (
                    candidate.document_number
                    and other.document_number
                    and candidate.document_number != other.document_number
                ):
                    left = {normalized(i.description) for i in candidate.items}
                    right = {normalized(i["description"]) for i in other_items}
                    if left.isdisjoint(right):
                        continue
            matches.append(other.document_id)
    # Also compare unconfirmed candidates: duplicate checks must not wait for the
    # first receipt to enter the expense tracker. State is indexed; the small
    # pending queue is compared in Python without making JSON provider-specific.
    pending = session.scalars(
        select(Document).where(
            Document.id != document_id, Document.state.in_(["READY_TO_RECORD", "NEEDS_REVIEW"])
        )
    ).all()
    for other_doc in pending:
        if not other_doc.candidate:
            continue
        other = Candidate.model_validate(other_doc.candidate)
        if normalized(other.vendor) != vendor:
            continue
        same_number = (
            candidate.document_number
            and other.document_number
            and normalized(candidate.document_number) == normalized(other.document_number)
        )
        same_purchase = (
            candidate.grand_total is not None
            and candidate.currency is not None
            and candidate.date is not None
            and candidate.date == other.date
            and candidate.grand_total == other.grand_total
            and candidate.currency == other.currency
        )
        if not same_number and not same_purchase:
            continue
        if not same_number and candidate.items and other.items:
            if (
                    candidate.document_number
                    and other.document_number
                    and candidate.document_number != other.document_number
                ):
                left = {normalized(item.description) for item in candidate.items}
                right = {normalized(item.description) for item in other.items}
                if left.isdisjoint(right):
                    continue
        matches.append(other_doc.id)
    return list(dict.fromkeys(matches))


def apply_issues(session, document, candidate, actor):
    issues = validate(candidate)
    matches = find_duplicates(session, candidate, document.id)
    if matches:
        issues.append(
            dict(
                code="POSSIBLE_DUPLICATE",
                severity="review",
                field="document_number",
                explanation="Similar business identity; review the linked records",
                evidence={"document_ids": matches},
            )
        )
    category = session.get(Category, candidate.category_id) if candidate.category_id else None
    if not category or not category.active:
        candidate.category_id = None
        issues.append(
            dict(
                code="CATEGORY_UNKNOWN",
                severity="warning",
                field="category_id",
                explanation="Choose a category if known; model advice is ambiguous",
                evidence={},
            )
        )
    for old in session.scalars(
        select(Issue).where(Issue.document_id == document.id, Issue.resolution.is_(None))
    ):
        old.resolution, old.resolved_by, old.resolved_at = "Revalidated", actor, now()
    for issue in issues:
        session.add(Issue(document_id=document.id, **issue))
        emit(session, "validation", issue["code"], issue["severity"], resource_id=document.id)
    document.candidate = candidate.model_dump(mode="json")
    document.state = (
        "NEEDS_REVIEW"
        if any(i["severity"] in {"blocking", "review"} for i in issues)
        else "READY_TO_RECORD"
    )


def upload(session, settings, data, filename, project_id, actor, key=None):
    if not session.get(Project, project_id):
        raise Conflict("Select an existing project")
    inspection = inspect(data, settings.max_file_bytes, settings.max_pages)
    sha = digest_bytes(data)
    fingerprint = digest_bytes(f"{sha}:{project_id}".encode())
    if key:
        prior = session.get(Idempotency, key)
        if prior:
            if prior.fingerprint != fingerprint:
                raise Conflict("Idempotency key reused with different input")
            return session.get(Document, prior.document_id), False
    existing = session.scalar(select(Document).where(Document.sha256 == sha))
    if existing:
        if key:
            session.add(Idempotency(key=key, fingerprint=fingerprint, document_id=existing.id))
            session.commit()
        return existing, False
    doc_id = uid()
    storage_key = f"{doc_id}/original"
    Storage(settings).put(storage_key, data, inspection.mime)
    document = Document(
        id=doc_id,
        sha256=sha,
        filename=safe_filename(filename),
        project_id=project_id,
        uploader=actor,
        storage_key=storage_key,
        mime=inspection.mime,
        pages=inspection.pages,
        state="RECEIVED",
    )
    session.add(document)
    if key:
        session.add(Idempotency(key=key, fingerprint=fingerprint, document_id=doc_id))
    emit(session, "finance", "upload", "RECEIVED", resource_id=doc_id)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = session.scalar(select(Document).where(Document.sha256 == sha))
        if existing:
            return existing, False
        raise Conflict("Concurrent upload conflict; retry with the same idempotency key") from None
    return document, True


class FinanceState(TypedDict, total=False):
    candidate: Candidate
    inspection: object


def auto_record_document(session, settings, document, actor="auto-recorder"):
    if document.state != "READY_TO_RECORD" or not document.candidate:
        return None
    candidate = Candidate.model_validate(document.candidate)
    expense = Expense(
        document_id=document.id,
        project_id=document.project_id,
        category_id=candidate.category_id,
        vendor=candidate.vendor,
        vendor_normalized=normalized(candidate.vendor),
        document_number=normalized(candidate.document_number) or None,
        date=str(candidate.date) if candidate.date else None,
        description=candidate.description,
        total=candidate.grand_total,
        currency=candidate.currency,
    )
    session.add(expense)
    session.flush()
    document.state = "RECORDED"
    document.version += 1
    row = (session.scalar(select(func.max(Delivery.row_number))) or 1) + 1
    session.add(Delivery(id=f"sheets:{expense.id}", expense_id=expense.id, row_number=row))
    emit(session, "automation", "auto_record", "RECORDED", resource_id=document.id, actor=actor)
    try:
        sync_sheets(session, settings, expense.id)
    except Exception:
        pass
    return expense


def process(session, settings, document_id, actor="demo-reviewer", provider=None, auto_record=None):
    document = session.get(Document, document_id)
    if not document or document.state not in {
        "RECEIVED",
        "FAILED",
        "NEEDS_REVIEW",
        "READY_TO_RECORD",
    }:
        raise Conflict("Document cannot be processed in its current state")
    expected = document.version
    claimed = session.execute(
        update(Document)
        .where(
            Document.id == document_id, Document.version == expected, Document.state != "PROCESSING"
        )
        .values(state="PROCESSING", version=expected + 1)
    )
    if claimed.rowcount != 1:
        session.rollback()
        raise Conflict("Document changed; reload before re-extracting")
    session.commit()
    session.refresh(document)
    run_id, started = uid(), perf_counter()
    run_token = current_run.set(run_id)
    provider = provider or provider_for(settings, session, run_id)
    attempt = Attempt(
        document_id=document.id, run_id=run_id, route="unknown", reason="", status="PROCESSING"
    )
    session.add(attempt)

    def inspection_node(state):
        data = Storage(settings).get(document.storage_key)
        result = inspect(data, settings.max_file_bytes, settings.max_pages)
        attempt.route, attempt.reason = result.route, result.reason
        emit(
            session,
            "finance",
            "route",
            result.route,
            run_id=run_id,
            resource_id=document.id,
            reason=result.reason,
        )
        return {"inspection": result}

    def extract_node(state):
        result = provider.extract(state["inspection"], document.sha256)
        attempt.candidate = result.model_dump(mode="json")
        return {"candidate": result}

    def category_node(state):
        categories = [
            {"id": c.id, "definition": c.definition}
            for c in session.scalars(select(Category).where(Category.active.is_(True)))
        ]
        result = provider.categorize(state["candidate"], categories)
        value = state["candidate"].model_copy(
            update={"category_id": result.category_id, "category_rationale": result.rationale}
        )
        return {"candidate": value}

    def persist_node(state):
        document.state = "PROCESSED"
        emit(session, "finance", "extract", "PROCESSED", run_id=run_id, resource_id=document.id)
        apply_issues(session, document, state["candidate"], actor)
        return {}

    graph = StateGraph(FinanceState)
    for name, node in [
        ("inspect", inspection_node),
        ("extract", extract_node),
        ("categorize", category_node),
        ("validate_persist", persist_node),
    ]:
        graph.add_node(name, node)
    graph.add_edge(START, "inspect")
    graph.add_edge("inspect", "extract")
    graph.add_edge("extract", "categorize")
    graph.add_edge("categorize", "validate_persist")
    graph.add_edge("validate_persist", END)
    try:
        with tracing_context(enabled=False):
            graph.compile().invoke({}, {"recursion_limit": 8})
        attempt.status = "succeeded"
        document.error_code = None
    except Exception as exc:
        document.state, attempt.status = "FAILED", "failed"
        document.error_code = str(exc) if isinstance(exc, ProviderError) else "PROCESSING_FAILED"
    if auto_record is None:
        auto_record = getattr(settings, "auto_record", False)
    if auto_record and document.state == "READY_TO_RECORD":
        auto_record_document(session, settings, document, actor=actor)
    emit(
        session,
        "finance",
        "process",
        document.state,
        run_id=run_id,
        resource_id=document.id,
        duration_ms=int((perf_counter() - started) * 1000),
        error_code=document.error_code,
        llm_calls=getattr(provider, "calls", 0),
        fixture=settings.provider == "fixture",
    )
    session.commit()
    session.refresh(document)
    current_run.reset(run_token)
    return document


def edit(session, document_id, version, candidate, actor):
    doc = session.get(Document, document_id)
    if not doc or doc.state not in {"NEEDS_REVIEW", "READY_TO_RECORD", "FAILED"}:
        raise Conflict("This record cannot be edited")
    result = session.execute(
        update(Document)
        .where(Document.id == doc.id, Document.version == version)
        .values(version=version + 1)
    )
    if not result.rowcount:
        session.rollback()
        raise Conflict("Stale edit; reload the record")
    apply_issues(session, doc, candidate, actor)
    session.add(
        Attempt(
            document_id=doc.id,
            run_id=uid(),
            route="human",
            reason="Human amendment",
            candidate=candidate.model_dump(mode="json"),
            status="succeeded",
        )
    )
    emit(session, "human", "edit_revalidate", doc.state, resource_id=doc.id, actor=actor)
    session.commit()
    return doc


def confirm(session, document_id, version, justification, actor):
    # Lock taxonomy serializes duplicate checks and row reservations for this small team.
    session.scalars(select(Category).order_by(Category.id).with_for_update()).all()
    doc = session.scalar(select(Document).where(Document.id == document_id).with_for_update())
    if not doc or doc.state not in {"READY_TO_RECORD", "NEEDS_REVIEW"} or doc.version != version:
        raise Conflict("Stale version or record is not ready for confirmation")
    candidate = Candidate.model_validate(doc.candidate)
    apply_issues(session, doc, candidate, actor)
    session.flush()
    issues = session.scalars(
        select(Issue).where(Issue.document_id == doc.id, Issue.resolution.is_(None))
    ).all()
    if any(i.severity == "blocking" for i in issues):
        session.commit()
        raise Conflict("Supply the missing total/currency before confirmation")
    if any(i.severity == "review" for i in issues) and len(justification.strip()) < 10:
        session.commit()
        raise Conflict("Review issues require a justification of at least 10 characters")
    claimed = session.execute(
        update(Document)
        .where(Document.id == doc.id, Document.version == version)
        .values(version=version + 1, state="RECORDED")
    )
    if claimed.rowcount != 1:
        session.rollback()
        raise Conflict("Concurrent confirmation; reload")
    expense = Expense(
        document_id=doc.id,
        project_id=doc.project_id,
        category_id=candidate.category_id,
        vendor=candidate.vendor,
        vendor_normalized=normalized(candidate.vendor),
        document_number=normalized(candidate.document_number) or None,
        date=str(candidate.date) if candidate.date else None,
        description=candidate.description,
        total=candidate.grand_total,
        currency=candidate.currency,
    )
    session.add(expense)
    session.flush()
    row = (session.scalar(select(func.max(Delivery.row_number))) or 1) + 1
    session.add(Delivery(id=f"sheets:{expense.id}", expense_id=expense.id, row_number=row))
    for issue in issues:
        issue.resolution = justification if issue.severity == "review" else "Confirmed by reviewer"
        issue.resolved_by, issue.resolved_at = actor, now()
    emit(session, "human", "confirm", "RECORDED", resource_id=doc.id, actor=actor)
    session.commit()
    return expense


def dismiss(session, document_id, version, justification, actor):
    if len(justification.strip()) < 10:
        raise Conflict("Dismissal needs a justification of at least 10 characters")
    claimed = session.execute(
        update(Document)
        .where(
            Document.id == document_id,
            Document.version == version,
            Document.state.not_in(["RECORDED", "PROCESSING", "DISMISSED"]),
        )
        .values(state="DISMISSED", version=version + 1)
    )
    if not claimed.rowcount:
        session.rollback()
        raise Conflict("Stale version or this record cannot be dismissed")
    emit(
        session,
        "human",
        "dismiss",
        "DISMISSED",
        resource_id=document_id,
        actor=actor,
        justification_recorded=True,
    )
    session.add(
        Attempt(
            document_id=document_id,
            run_id=uid(),
            route="human",
            reason=justification,
            candidate=None,
            status="DISMISSED",
        )
    )
    session.commit()


def expenses(session, project=None, category=None, currency=None, start=None, end=None):
    query = select(Expense).order_by(Expense.confirmed_at.desc())
    for field, value in [
        (Expense.project_id, project),
        (Expense.category_id, category),
        (Expense.currency, currency),
    ]:
        if value:
            query = query.where(field == value)
    if start:
        query = query.where(Expense.date >= start)
    if end:
        query = query.where(Expense.date <= end)
    return session.scalars(query).all()


def summary(records):
    totals, categories, timeline = {}, {}, {}
    for expense in records:
        currency = expense.currency
        totals[currency] = totals.get(currency, Decimal("0")) + expense.total
        key = (currency, expense.category_id or "unknown")
        categories[key] = categories.get(key, Decimal("0")) + expense.total
        month = (expense.date or "unknown")[:7]
        key = (currency, month)
        timeline[key] = timeline.get(key, Decimal("0")) + expense.total
    return {
        "totals": {key: str(value) for key, value in totals.items()},
        "categories": [
            {"currency": c, "category": k, "total": str(v)} for (c, k), v in categories.items()
        ],
        "timeline": [
            {"currency": c, "month": k, "total": str(v)} for (c, k), v in sorted(timeline.items())
        ],
        "count": len(records),
    }


def csv_export(records):
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(
        ["id", "project", "category", "vendor", "date", "description", "total", "currency"]
    )
    for expense in records:
        values = [
            expense.id,
            expense.project_id,
            expense.category_id,
            expense.vendor,
            expense.date,
            expense.description,
            str(expense.total),
            expense.currency,
        ]
        # Prevent spreadsheet formula injection from source document text.
        writer.writerow(
            [
                "'" + v if isinstance(v, str) and v.lstrip().startswith(("=", "+", "-", "@")) else v
                for v in values
            ]
        )
    return out.getvalue()


def sync_sheets(session, settings, expense_id, transport=None):
    delivery = session.scalar(
        select(Delivery).where(Delivery.expense_id == expense_id).with_for_update()
    )
    if not delivery or delivery.status == "succeeded":
        return delivery
    if delivery.attempts >= 3:
        raise Conflict("Sheets retry ceiling reached")
    adapter = Sheets(settings, transport)
    if not adapter.configured:
        delivery.error = "SHEETS_NOT_CONFIGURED"
        session.commit()
        return delivery
    expense = session.get(Expense, expense_id)
    delivery.attempts += 1
    try:
        adapter.sync(
            delivery.row_number,
            [
                expense.id,
                expense.project_id,
                expense.category_id,
                expense.vendor,
                expense.date,
                expense.description,
                str(expense.total),
                expense.currency,
            ],
        )
        delivery.status, delivery.error = "succeeded", None
    except (IntegrationError, OSError, httpx.HTTPError) as exc:
        delivery.status, delivery.error = "failed", type(exc).__name__
    emit(
        session,
        "integration",
        "sheets",
        delivery.status,
        resource_id=expense.document_id,
        error_code=delivery.error,
        attempt=delivery.attempts,
    )
    session.commit()
    return delivery
