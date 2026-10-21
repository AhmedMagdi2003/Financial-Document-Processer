from contextvars import ContextVar
from time import perf_counter

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.models import Base, Category, Project

query_metrics: ContextVar[dict | None] = ContextVar("query_metrics", default=None)

CATEGORIES = {
    "personnel": ("Personnel", "Staff and contractor compensation for project work"),
    "travel": ("Travel", "Transportation, lodging and travel costs"),
    "equipment": ("Equipment", "Physical equipment and durable hardware"),
    "software": ("Software", "Software licences and digital subscriptions"),
    "events": ("Events", "Workshops, venues and event delivery"),
    "operational": ("Operational", "Office supplies, utilities and administration"),
}


def make_engine(url):
    kwargs = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_engine(url, **kwargs)

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, record):
        if url.startswith("sqlite"):
            connection.execute("PRAGMA foreign_keys=ON")

    @event.listens_for(engine, "before_cursor_execute")
    def before(conn, cursor, statement, parameters, context, executemany):
        context.started_at = perf_counter()

    @event.listens_for(engine, "after_cursor_execute")
    def after(conn, cursor, statement, parameters, context, executemany):
        metrics = query_metrics.get()
        if metrics is not None:
            elapsed = (perf_counter() - context.started_at) * 1000
            metrics["count"] += 1
            metrics["duration_ms"] += elapsed
            metrics["slow_count"] += int(elapsed > 200)

    return engine


def initialize(engine):
    """Explicit setup command, not a side effect of importing or serving the app."""
    Base.metadata.create_all(engine)
    with sessionmaker(engine)() as session, session.begin():
        for key, (name, definition) in CATEGORIES.items():
            if not session.get(Category, key):
                session.add(Category(id=key, name=name, definition=definition))
        for key, name in [
            ("river", "River Research (fictional)"),
            ("skills", "Skills Lab (fictional)"),
        ]:
            if not session.get(Project, key):
                session.add(Project(id=key, name=name))
