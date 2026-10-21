from sqlalchemy import text

from app.config import Settings
from app.db import initialize, make_engine
from app.models import Base

if __name__ == "__main__":
    settings = Settings()
    settings.require_runtime()
    engine = make_engine(settings.database_url.get_secret_value())
    initialize(engine)
    if settings.mode == "cloud":
        with engine.begin() as connection:
            for table in Base.metadata.sorted_tables:
                connection.execute(text(f'ALTER TABLE "{table.name}" ENABLE ROW LEVEL SECURITY'))
            connection.execute(
                text(
                    "INSERT INTO storage.buckets (id, name, public) "
                    "VALUES (:bucket, :bucket, false) ON CONFLICT (id) DO UPDATE SET public=false"
                ),
                {"bucket": settings.storage_bucket},
            )
    print("Schema and fictional projects/categories initialized.")
