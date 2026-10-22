import hmac
import json
import secrets
from collections import defaultdict
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from pathlib import Path
from time import monotonic, perf_counter
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI, Form, Header, HTTPException, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session, sessionmaker
from starlette.middleware.sessions import SessionMiddleware

from app import financial
from app.ai import ProviderError
from app.config import Settings
from app.db import make_engine, query_metrics
from app.errors import map_error
from app.exchange_rates import latest_rates
from app.inspection import FileRejected
from app.integrations import IntegrationError, Storage
from app.models import (
    AccessToken,
    Attempt,
    Category,
    Delivery,
    Document,
    Event,
    Expense,
    Issue,
    Project,
    Usage,
    uid,
)
from app.observability import cost_summary, current_request, emit
from app.operations import build_operations_dashboard
from app.schemas import (
    CategoryCreate,
    CategoryInput,
    ConfirmInput,
    ReviewInput,
)
from app.workspace import install_workspace_routes

ROOT = Path(__file__).parent


def record(value):
    return jsonable_encoder(
        {col.name: getattr(value, col.name) for col in value.__table__.columns},
        custom_encoder={Decimal: str},
    )


def create_app(settings=None, engine=None):
    cfg = settings or Settings()
    if cfg.database_url.get_secret_value():
        cfg.require_runtime()
        engine = engine or make_engine(cfg.database_url.get_secret_value())
    sessions = sessionmaker(engine, expire_on_commit=False) if engine is not None else None
    application = FastAPI(title="Impact workspace", version="0.1.0")
    application.state.settings, application.state.engine = cfg, engine
    application.state.sessions = sessions
    application.add_middleware(
        SessionMiddleware,
        secret_key=cfg.session_secret.get_secret_value() or secrets.token_hex(32),
        https_only=cfg.secure_cookies,
        same_site="strict",
        max_age=3600,
    )
    templates = Jinja2Templates(directory=str(ROOT / "templates"))
    templates.env.globals["map_error"] = map_error
    application.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")
    attempts = defaultdict(list)

    def db():
        if sessions is None:
            raise HTTPException(503, "Configure the database and run the setup command first")
        with sessions() as session:
            try:
                yield session
            except Exception:
                session.rollback()
                raise

    def authenticated(request: Request):
        expected = cfg.reviewer_token.get_secret_value()
        if not expected:
            raise HTTPException(503, "Reviewer authentication is not configured")
        authorization = request.headers.get("authorization", "")
        if authorization.startswith("Bearer "):
            token_val = authorization[7:].strip()
            if hmac.compare_digest(token_val, expected):
                return "demo-reviewer" if cfg.mode == "demo" else "internal-reviewer"
            if sessions:
                with sessions() as s:
                    member_token = s.scalar(
                        select(AccessToken).where(
                            AccessToken.token == token_val, AccessToken.active.is_(True)
                        )
                    )
                    if member_token:
                        return member_token.name
            raise HTTPException(401, "Invalid API token")
        if not request.session.get("reviewer"):
            raise HTTPException(401, "Sign in to continue")
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            if not hmac.compare_digest(
                request.headers.get("x-csrf-token", ""), request.session.get("csrf", "invalid")
            ):
                raise HTTPException(403, "Invalid CSRF token")
        return request.session["reviewer"]

    DB = Annotated[Session, Depends(db)]
    Actor = Annotated[str, Depends(authenticated)]

    @application.middleware("http")
    async def activity(request: Request, call_next):
        request_id, started = uid(), perf_counter()
        request.state.request_id = request_id
        metrics = {"count": 0, "duration_ms": 0, "slow_count": 0}
        token = query_metrics.set(metrics)
        correlation = current_request.set(request_id)
        try:
            if request.method == "POST" and request.url.path == "/api/v1/documents":
                length = request.headers.get("content-length")
                if not length or not length.isdigit():
                    return JSONResponse({"detail": "Content-Length is required"}, status_code=411)
                if int(length) > cfg.max_file_bytes + 65536:
                    return JSONResponse({"detail": "Upload too large"}, status_code=413)
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Referrer-Policy"] = "same-origin"
            response.headers["Cache-Control"] = "no-store"
            if sessions:
                with sessions() as session:
                    emit(
                        session,
                        "http",
                        request.method,
                        str(response.status_code),
                        request_id=request_id,
                        duration_ms=int((perf_counter() - started) * 1000),
                        path=request.url.path,
                        db_queries=metrics["count"],
                        db_duration_ms=round(metrics["duration_ms"], 2),
                        slow_queries=metrics["slow_count"],
                    )
                    if metrics["slow_count"]:
                        emit(
                            session,
                            "database",
                            "slow_query",
                            "warning",
                            request_id=request_id,
                            count=metrics["slow_count"],
                        )
                    session.commit()
            return response
        finally:
            query_metrics.reset(token)
            current_request.reset(correlation)

    @application.exception_handler(financial.Conflict)
    async def conflict(request, exc):
        err = map_error(str(exc))
        return JSONResponse({"detail": str(exc), "error": err.to_dict()}, status_code=409)

    @application.exception_handler(FileRejected)
    async def rejected(request, exc):
        err = map_error(str(exc))
        return JSONResponse({"detail": str(exc), "error": err.to_dict()}, status_code=422)

    @application.exception_handler(ProviderError)
    @application.exception_handler(IntegrationError)
    async def provider_failure(request, exc):
        err = map_error(str(exc))
        return JSONResponse({"detail": str(exc), "error": err.to_dict()}, status_code=503)

    @application.exception_handler(httpx.HTTPError)
    async def transport_failure(request, exc):
        return JSONResponse(
            {"detail": "External service unavailable; check Operations"}, status_code=503
        )

    @application.get("/health")
    def health():
        return {"status": "ok", "service": "impact-workspace", "configured": sessions is not None}

    @application.get("/api/v1/readiness")
    def readiness(actor: Actor, session: DB):
        session.execute(text("SELECT 1"))
        return {
            "database": "reachable",
            "mode": cfg.mode,
            "provider": cfg.provider,
            "sheets": "configured" if cfg.sheets_spreadsheet_id else "not_configured",
            "tracing": "disabled" if cfg.tracing_backends == "none" else "unverified",
        }

    @application.get("/login", response_class=HTMLResponse)
    def login_page(request: Request):
        return templates.TemplateResponse(request, "login.html", {"mode": cfg.mode})

    @application.post("/login")
    def login(request: Request, token: Annotated[str, Form()]):
        host = request.client.host if request.client else "unknown"
        attempts[host] = [t for t in attempts[host] if monotonic() - t < 60]
        if len(attempts[host]) >= 10:
            raise HTTPException(429, "Too many attempts; wait one minute")
        attempts[host].append(monotonic())
        expected = cfg.reviewer_token.get_secret_value()
        user_name = None
        user_role = "reviewer"
        if expected and hmac.compare_digest(token, expected):
            user_name = "demo-reviewer" if cfg.mode == "demo" else "internal-reviewer"
            user_role = "admin"
        elif sessions:
            with sessions() as s:
                member_token = s.scalar(
                    select(AccessToken).where(
                        AccessToken.token == token, AccessToken.active.is_(True)
                    )
                )
                if member_token:
                    user_name = member_token.name
                    user_role = member_token.role

        if not user_name:
            raise HTTPException(401, "Invalid reviewer token")
        request.session.clear()
        request.session.update(
            reviewer=user_name,
            role=user_role,
            csrf=secrets.token_urlsafe(32),
        )
        return RedirectResponse("/", status_code=303)

    @application.post("/logout")
    def logout(request: Request, actor: Actor):
        request.session.clear()
        return {"status": "signed_out"}

    @contextmanager
    def page_session(request):
        if not request.session.get("reviewer"):
            raise HTTPException(401)
        if sessions is None:
            raise HTTPException(503, "Database is not configured")
        with sessions() as session:
            yield session

    def render(request, template, **context):
        context.update(
            mode=cfg.mode,
            provider=cfg.provider,
            csrf=request.session.get("csrf", ""),
            reviewer=request.session.get("reviewer", ""),
            path=request.url.path,
            report_currency=request.query_params.get("report_currency", "USD").upper(),
        )
        return templates.TemplateResponse(request, template, context)

    install_workspace_routes(application, cfg, db, authenticated, render)

    @application.get("/", response_class=HTMLResponse)
    def overview(
        request: Request,
        project: str = "",
        category: str = "",
        currency: str = "",
        report_currency: str = "USD",
        start: str = "",
        end: str = "",
        sort_by: str = "added",
        sort_order: str = "desc",
    ):
        if not request.session.get("reviewer"):
            return RedirectResponse("/login", 303)
        report_currency = report_currency.upper()
        if report_currency not in {"USD", "EUR", "EGP"}:
            report_currency = "USD"
        with page_session(request) as session:
            records = financial.expenses(
                session,
                project,
                category,
                currency,
                start,
                end,
                sort_by=sort_by,
                sort_order=sort_order,
            )
            documents = session.scalars(select(Document)).all()
            deliveries = session.scalars(select(Delivery)).all()
            duplicate_count = len(
                session.scalars(
                    select(Issue).where(
                        Issue.code == "POSSIBLE_DUPLICATE", Issue.resolution.is_(None)
                    )
                ).all()
            )
            summ = financial.summary(records)
            source_currencies = sorted({e.currency for e in records if e.currency})
            available_currencies = sorted(
                {"USD", "EUR", "EGP"}
                | {e.currency for e in session.scalars(select(Expense)).all() if e.currency}
            )
            pipeline_stats = {
                "recorded": sum(1 for d in documents if d.state == "RECORDED"),
                "review": sum(1 for d in documents if d.state == "NEEDS_REVIEW"),
                "ready": sum(1 for d in documents if d.state == "READY_TO_RECORD"),
                "failed": sum(1 for d in documents if d.state == "FAILED"),
                "dismissed": sum(1 for d in documents if d.state == "DISMISSED"),
                "duplicates": duplicate_count,
            }
            return render(
                request,
                "finance.html",
                records=records,
                summary=summ,
                report_currency=report_currency,
                report_currencies=["USD", "EUR", "EGP"],
                source_currencies=source_currencies,
                expense_conversion_data=[
                    {
                        "id": e.id,
                        "amount": str(e.total),
                        "currency": e.currency,
                        "category": e.category_id or "unknown",
                        "month": (e.date or "unknown")[:7],
                    }
                    for e in records
                ],
                projects=session.scalars(select(Project)).all(),
                categories=session.scalars(select(Category)).all(),
                documents=documents,
                deliveries=deliveries,
                duplicate_count=duplicate_count,
                pipeline_stats=pipeline_stats,
                available_currencies=available_currencies,
                filters=dict(
                    project=project,
                    category=category,
                    currency=currency,
                    start=start,
                    end=end,
                    sort_by=sort_by,
                    sort_order=sort_order,
                ),
            )

    @application.get("/review", response_class=HTMLResponse)
    def review(request: Request, project: str = ""):
        if not request.session.get("reviewer"):
            return RedirectResponse("/login", 303)
        with page_session(request) as session:
            docs = session.scalars(
                select(Document)
                .where(Document.state.not_in(["RECORDED", "DISMISSED"]))
                .where(Document.project_id == project if project else True)
                .order_by(Document.created_at.desc())
            ).all()
            return render(request, "review.html", documents=docs)

    @application.get("/documents/{document_id}", response_class=HTMLResponse)
    def document_page(request: Request, document_id: str):
        if not request.session.get("reviewer"):
            return RedirectResponse("/login", 303)
        with page_session(request) as session:
            doc = session.get(Document, document_id)
            if not doc:
                raise HTTPException(404)
            return render(
                request,
                "document.html",
                document=doc,
                candidate_json=json.dumps(doc.candidate or {}, indent=2),
                issues=session.scalars(
                    select(Issue).where(Issue.document_id == doc.id, Issue.resolution.is_(None))
                ).all(),
                attempts=session.scalars(
                    select(Attempt)
                    .where(Attempt.document_id == doc.id)
                    .order_by(Attempt.created_at.desc())
                ).all(),
                categories=session.scalars(select(Category)).all(),
            )

    @application.get("/operations", response_class=HTMLResponse)
    def operations(request: Request, q: str = "", project: str = ""):
        if not request.session.get("reviewer"):
            return RedirectResponse("/login", 303)
        with page_session(request) as session:
            selected_project = session.get(Project, project) if project else None
            if project and not selected_project:
                raise HTTPException(404, "Project not found")
            include_http = request.query_params.get("include_http") == "true"
            query = select(Event).order_by(Event.timestamp.desc()).limit(200)
            if not include_http and not q:
                query = query.where(Event.stage.not_in(["http", "database"]))
            project_docs = select(Document.id).where(Document.project_id == project)
            project_runs = select(Attempt.run_id).where(Attempt.document_id.in_(project_docs))
            if project:
                query = query.where(or_(
                    Event.resource_id.in_(project_docs), Event.run_id.in_(project_runs)
                ))
            if q:
                query = query.where(
                    or_(Event.run_id == q, Event.resource_id == q, Event.request_id == q)
                )
            usage_query = select(Usage)
            if project:
                usage_query = usage_query.where(Usage.run_id.in_(project_runs))
            if q:
                matching_runs = select(Event.run_id).where(
                    or_(Event.resource_id == q, Event.request_id == q),
                    Event.run_id.is_not(None),
                )
                document_runs = select(Attempt.run_id).where(Attempt.document_id == q)
                usage_query = usage_query.where(or_(
                    Usage.run_id == q, Usage.run_id.in_(matching_runs),
                    Usage.run_id.in_(document_runs),
                ))
            usage_rows = session.scalars(usage_query).all()
            all_documents = session.scalars(select(Document).where(
                Document.project_id == project if project else True
            )).all()
            recent_events = session.scalars(query).all()
            dashboard = build_operations_dashboard(all_documents, recent_events, usage_rows)
            operations_stats = dashboard["stats"]
            stage_durations = defaultdict(list)
            status_counts = defaultdict(int)
            for ev in recent_events:
                status_counts[ev.status] += 1
                if ev.duration_ms is not None and ev.duration_ms > 0:
                    stage_durations[ev.stage].append(ev.duration_ms)
            stage_averages = {
                stage: round(sum(durs) / len(durs), 1)
                for stage, durs in stage_durations.items()
            }
            ops_chart_data = {
                "stages": list(stage_averages.keys()),
                "avg_latencies": list(stage_averages.values()),
                "status_labels": list(status_counts.keys()),
                "status_values": list(status_counts.values()),
            }
            doc_map = {d.id: d.filename for d in all_documents}
            return render(
                request,
                "operations.html",
                events=recent_events,
                usage=usage_rows,
                costs=cost_summary(usage_rows),
                stats=operations_stats,
                dashboard=dashboard,
                doc_map=doc_map,
                include_http=include_http,
                projects=session.scalars(select(Project).order_by(Project.name)).all(),
                project_id=project,
                selected_project=selected_project,
                ops_chart_data=ops_chart_data,
                q=q,
                tracing=cfg.tracing_backends,
            )

    @application.get("/categories", response_class=HTMLResponse)
    def category_page(request: Request):
        if not request.session.get("reviewer"):
            return RedirectResponse("/login", 303)
        with page_session(request) as session:
            return render(
                request, "categories.html", categories=session.scalars(select(Category)).all()
            )

    @application.post("/api/v1/documents")
    def upload(
        file: UploadFile,
        project_id: Annotated[str, Form()],
        session: DB,
        actor: Actor,
        idempotency_key: Annotated[str | None, Header(max_length=200)] = None,
        auto_record: Annotated[bool | None, Form()] = None,
    ):
        data = file.file.read(cfg.max_file_bytes + 1)
        doc, created = financial.upload(
            session, cfg, data, file.filename or "document", project_id, actor, idempotency_key
        )
        if created:
            doc = financial.process(session, cfg, doc.id, actor, auto_record=auto_record)
        issues = session.scalars(
            select(Issue).where(Issue.document_id == doc.id, Issue.resolution.is_(None))
        ).all()
        doc_dict = record(doc)
        if doc.error_code:
            doc_dict["human_error"] = map_error(doc.error_code).to_dict()
        return {
            "document": doc_dict,
            "reused": not created,
            "duplicate": not created,
            "issues": [record(i) for i in issues],
            "auto_recorded": doc.state == "RECORDED",
        }

    @application.post("/api/v1/batch-upload")
    def batch_upload(
        files: list[UploadFile],
        project_id: Annotated[str, Form()],
        session: DB,
        actor: Actor,
        auto_record: Annotated[bool | None, Form()] = None,
    ):
        results = []
        for file in files:
            fname = file.filename or "document"
            try:
                data = file.file.read(cfg.max_file_bytes + 1)
                doc, created = financial.upload(
                    session, cfg, data, fname, project_id, actor
                )
                if created:
                    doc = financial.process(session, cfg, doc.id, actor, auto_record=auto_record)
                issues = session.scalars(
                    select(Issue).where(Issue.document_id == doc.id, Issue.resolution.is_(None))
                ).all()
                doc_dict = record(doc)
                if doc.error_code:
                    doc_dict["human_error"] = map_error(doc.error_code).to_dict()
                results.append({
                    "filename": fname,
                    "document": doc_dict,
                    "reused": not created,
                    "state": doc.state,
                    "auto_recorded": doc.state == "RECORDED",
                    "issues": [record(i) for i in issues],
                    "status": "success",
                })
            except Exception as exc:
                err = map_error(exc)
                results.append({
                    "filename": fname,
                    "document": None,
                    "state": "FAILED",
                    "auto_recorded": False,
                    "issues": [],
                    "human_error": err.to_dict(),
                    "status": "error",
                })
        return {
            "total": len(results),
            "recorded": sum(1 for r in results if r.get("auto_recorded")),
            "review": sum(1 for r in results if r.get("state") == "NEEDS_REVIEW"),
            "failed": sum(
                1 for r in results if r.get("state") == "FAILED" or r.get("status") == "error"
            ),
            "results": results,
        }

    @application.get("/api/v1/documents/{document_id}")
    def document_status(document_id: str, session: DB, actor: Actor):
        doc = session.get(Document, document_id)
        if not doc:
            raise HTTPException(404)
        return {
            "document": record(doc),
            "issues": [
                record(i)
                for i in session.scalars(select(Issue).where(Issue.document_id == document_id))
            ],
            "attempts": [
                record(a)
                for a in session.scalars(select(Attempt).where(Attempt.document_id == document_id))
            ],
        }

    @application.get("/api/v1/reviews")
    def reviews(session: DB, actor: Actor):
        return [
            record(d)
            for d in session.scalars(select(Document).where(Document.state == "NEEDS_REVIEW"))
        ]

    @application.get("/api/v1/documents/{document_id}/original")
    def original(document_id: str, session: DB, actor: Actor):
        doc = session.get(Document, document_id)
        if not doc:
            raise HTTPException(404)
        return Response(
            Storage(cfg).get(doc.storage_key),
            media_type=doc.mime,
            headers={
                "Content-Disposition": 'inline; filename="document"',
                "Content-Security-Policy": "sandbox",
            },
        )

    @application.patch("/api/v1/documents/{document_id}/fields")
    def amend(document_id: str, body: ReviewInput, session: DB, actor: Actor):
        return record(financial.edit(session, document_id, body.version, body.candidate, actor))

    @application.post("/api/v1/documents/{document_id}/confirm")
    def confirm(document_id: str, body: ConfirmInput, session: DB, actor: Actor):
        expense = financial.confirm(session, document_id, body.version, body.justification, actor)
        financial.sync_sheets(session, cfg, expense.id)
        return record(expense)

    @application.post("/api/v1/documents/{document_id}/dismiss")
    def dismiss(document_id: str, body: ConfirmInput, session: DB, actor: Actor):
        financial.dismiss(session, document_id, body.version, body.justification, actor)
        return {"state": "DISMISSED"}

    @application.post("/api/v1/documents/{document_id}/reextract")
    def reextract(document_id: str, session: DB, actor: Actor):
        return record(financial.process(session, cfg, document_id, actor))

    @application.get("/api/v1/expenses")
    def tracker(
        session: DB,
        actor: Actor,
        project: str = "",
        category: str = "",
        currency: str = "",
        start: date | None = None,
        end: date | None = None,
    ):
        return [
            record(e)
            for e in financial.expenses(
                session,
                project,
                category,
                currency,
                start.isoformat() if start else None,
                end.isoformat() if end else None,
            )
        ]

    @application.get("/api/v1/expenses/summary")
    def totals(
        session: DB, actor: Actor, project: str = "", category: str = "", currency: str = ""
    ):
        return financial.summary(financial.expenses(session, project, category, currency))

    @application.get("/api/v1/exchange-rates")
    def exchange_rates(actor: Actor, base: str, symbols: str = ""):
        try:
            return latest_rates(base, symbols.split(",") if symbols else [])
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(503, "Exchange rates are temporarily unavailable") from exc

    @application.get("/api/v1/expenses.csv")
    def export(
        session: DB, actor: Actor, project: str = "", category: str = "", currency: str = ""
    ):
        return Response(
            financial.csv_export(financial.expenses(session, project, category, currency)),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="expense-tracker.csv"'},
        )

    @application.post("/api/v1/expenses/{expense_id}/sync")
    def sync(expense_id: str, session: DB, actor: Actor):
        delivery = financial.sync_sheets(session, cfg, expense_id)
        if not delivery:
            raise HTTPException(404)
        return record(delivery)

    @application.patch("/api/v1/categories/{category_id}")
    def update_category(category_id: str, body: CategoryInput, session: DB, actor: Actor):
        category = session.get(Category, category_id)
        if not category:
            raise HTTPException(404)
        for key, value in body.model_dump().items():
            setattr(category, key, value)
        emit(session, "human", "edit_category", "succeeded", actor=actor, category_id=category_id)
        session.commit()
        return record(category)

    @application.post("/api/v1/categories")
    def create_category(body: CategoryCreate, session: DB, actor: Actor):
        category = financial.create_category(
            session,
            name=body.name,
            definition=body.definition,
            id=body.id,
            active=body.active,
            actor=actor,
        )
        return record(category)

    @application.delete("/api/v1/categories/{category_id}")
    def delete_category(category_id: str, session: DB, actor: Actor):
        category = session.get(Category, category_id)
        if not category:
            raise HTTPException(404, "Category not found")
        session.delete(category)
        session.commit()
        return {"status": "deleted", "id": category_id}

    @application.delete("/api/v1/expenses/{expense_id}")
    def delete_expense(expense_id: str, session: DB, actor: Actor):
        success = financial.delete_expense(session, expense_id, actor)
        if not success:
            raise HTTPException(404, "Expense record not found")
        return {"status": "deleted", "id": expense_id}

    @application.delete("/api/v1/documents/{document_id}")
    def delete_document(document_id: str, session: DB, actor: Actor):
        success = financial.delete_document(session, cfg, document_id, actor)
        if not success:
            raise HTTPException(404, "Document not found")
        return {"status": "deleted", "id": document_id}

    @application.get("/api/v1/tokens")
    def list_tokens(session: DB, actor: Actor):
        tokens = session.scalars(
            select(AccessToken).order_by(AccessToken.created_at.desc())
        ).all()
        return [record(t) for t in tokens]

    @application.post("/api/v1/tokens")
    def create_token_endpoint(body: dict, session: DB, actor: Actor):
        name = (body.get("name") or "").strip()
        role = (body.get("role") or "reviewer").strip()
        if not name:
            raise HTTPException(400, "Name is required")
        slug = "".join(c.lower() if c.isalnum() else "_" for c in name).strip("_")[:12]
        token_str = f"tok_{slug}_{secrets.token_urlsafe(24)}"
        t = AccessToken(token=token_str, name=name, role=role, active=True)
        session.add(t)
        emit(session, "human", "create_token", "succeeded", actor=actor, resource_id=t.id)
        session.commit()
        return record(t)

    @application.delete("/api/v1/tokens/{token_id}")
    def revoke_token_endpoint(token_id: str, session: DB, actor: Actor):
        t = session.get(AccessToken, token_id)
        if not t:
            raise HTTPException(404, "Token not found")
        t.active = False
        emit(session, "human", "revoke_token", "revoked", actor=actor, resource_id=t.id)
        session.commit()
        return {"status": "revoked", "id": token_id}

    return application
