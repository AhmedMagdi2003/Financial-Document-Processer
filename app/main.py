"""FastAPI entry point; routes delegate to shared Python workflows."""

from app.web import create_app

app = create_app()
