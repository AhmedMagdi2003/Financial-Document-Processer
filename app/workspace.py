"""Project administration and integration setup, isolated from document workflows."""

from pathlib import Path
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.integrations import Sheets
from app.models import Project
from app.observability import emit


class ProjectName(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class ProjectCreate(ProjectName):
    id: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")


def install_workspace_routes(app, cfg, db, authenticated, render):
    DB = Annotated[Session, Depends(db)]
    Actor = Annotated[str, Depends(authenticated)]

    @app.get("/projects")
    def projects_page(request: Request, session: DB):
        if not request.session.get("reviewer"):
            return RedirectResponse("/login", 303)
        return render(
            request,
            "projects.html",
            projects=session.scalars(select(Project).order_by(Project.name)).all(),
        )

    @app.get("/api/v1/projects")
    def projects(session: DB, actor: Actor):
        return [
            {"id": p.id, "name": p.name}
            for p in session.scalars(select(Project).order_by(Project.name))
        ]

    @app.post("/api/v1/projects", status_code=201)
    def create_project(body: ProjectCreate, session: DB, actor: Actor):
        if session.get(Project, body.id):
            raise HTTPException(409, "This project ID already exists; choose another ID")
        project = Project(**body.model_dump())
        session.add(project)
        emit(session, "human", "create_project", "succeeded", actor=actor, project_id=body.id)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            raise HTTPException(409, "This project ID already exists") from None
        return {"id": project.id, "name": project.name}

    @app.patch("/api/v1/projects/{project_id}")
    def rename_project(project_id: str, body: ProjectName, session: DB, actor: Actor):
        project = session.get(Project, project_id)
        if not project:
            raise HTTPException(404, "Project not found")
        project.name = body.name
        emit(session, "human", "rename_project", "succeeded", actor=actor, project_id=project.id)
        session.commit()
        return {"id": project.id, "name": project.name}

    @app.get("/integrations")
    def integrations_page(request: Request):
        if not request.session.get("reviewer"):
            return RedirectResponse("/login", 303)
        return render(
            request,
            "integrations.html",
            sheets_configured=Sheets(cfg).configured
            and (
                not cfg.sheets_webhook_url
                or len(cfg.sheets_webhook_secret.get_secret_value()) >= 24
            ),
            sheets_method="Apps Script webhook" if cfg.sheets_webhook_url else "Sheets API",
            hosting_provider=cfg.hosting_provider,
            active_public_url=cfg.active_public_url,
        )

    @app.get("/api/v1/integrations/guide")
    def integration_guide(actor: Actor):
        return FileResponse(
            Path(__file__).parent.parent / "docs" / "INTEGRATION_GUIDE.md",
            media_type="text/markdown",
            filename="INTEGRATION_GUIDE.md",
        )

    @app.get("/api/v1/integrations/scripts/{filename}")
    def integration_script(filename: str, actor: Actor):
        if filename not in {"SheetsWebhook.gs", "DriveIngestion.gs", "google_drive_to_finance_blueprint.json"}:
            raise HTTPException(404)
        if filename == "google_drive_to_finance_blueprint.json":
            return FileResponse(
                Path(__file__).parent.parent / "scripts" / "make" / filename,
                media_type="application/json",
                filename=filename,
            )
        return FileResponse(
            Path(__file__).parent.parent / "scripts" / "google_apps_script" / filename,
            media_type="text/plain",
            filename=filename,
        )
