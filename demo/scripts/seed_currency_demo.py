"""Create clearly fictional, pre-confirmed expenses for an isolated currency UI demo."""

from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256

from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.db import initialize, make_engine
from app.models import Document, Expense


def main() -> None:
    settings = Settings()
    if settings.mode != "demo" or not settings.database_url.get_secret_value().startswith("sqlite"):
        raise RuntimeError(
            "Refusing to seed anything except an explicit local SQLite demo database"
        )
    db_url = settings.database_url.get_secret_value()
    engine = make_engine(db_url)
    initialize(engine)
    sessions = sessionmaker(engine)
    examples = [
        (
            "fictional-usd-invoice",
            "Fictional demo vendor · transport",
            "TRIP-101",
            "2026-10-05",
            "travel",
            "USD",
            "125.00",
        ),
        (
            "fictional-eur-receipt",
            "Fictional demo vendor · software",
            "SOFT-202",
            "2026-10-12",
            "software",
            "EUR",
            "89.50",
        ),
        (
            "fictional-egp-invoice",
            "Fictional demo vendor · equipment",
            "EQUIP-303",
            "2026-10-18",
            "equipment",
            "EGP",
            "5400.00",
        ),
    ]
    with sessions.begin() as session:
        for number, (doc_id, vendor, invoice, date, category, currency, amount) in enumerate(
            examples, 1
        ):
            if session.get(Document, doc_id):
                raise RuntimeError("Demo DB already contains seed records; refusing to overwrite")
            session.add(
                Document(
                    id=doc_id,
                    sha256=sha256(f"fictional-demo-currency-{number:02d}".encode()).hexdigest(),
                    filename=f"FICTIONAL_DEMO_{number:02d}.pdf",
                    project_id="river",
                    uploader="demo-seed",
                    storage_key=f"fictional-demo/{number:02d}",
                    mime="application/pdf",
                    pages=1,
                    state="RECORDED",
                    candidate={"fictional_demo_data": True},
                    created_at=datetime.now(UTC),
                )
            )
            session.add(
                Expense(
                    id=f"fictional-expense-{number:02d}",
                    document_id=doc_id,
                    project_id="river",
                    category_id=category,
                    vendor=vendor,
                    vendor_normalized=vendor.casefold(),
                    document_number=invoice,
                    date=date,
                    description="Fictional seeded record for currency-reporting demo only",
                    total=Decimal(amount),
                    currency=currency,
                    confirmed_at=datetime.now(UTC),
                )
            )
    print(f"Seeded {len(examples)} fictional sample expenses into isolated SQLite demo DB.")


if __name__ == "__main__":
    main()
