from sqlalchemy import create_engine, text
from app.core.config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, future=True)

def init_db():
    with engine.begin() as conn:
        conn.execute(text("""CREATE TABLE IF NOT EXISTS products (
            sku VARCHAR(120) PRIMARY KEY,
            input_json TEXT NOT NULL,
            output_json TEXT,
            status VARCHAR(40) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )"""))
