"""Database engines (SQLAlchemy + PyMySQL) for the two Etex databases."""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

load_dotenv()


def _engine_for(db_name: str):
    url = URL.create(
        "mysql+pymysql",
        username=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", 3306)),
        database=db_name,
        query={"charset": "utf8mb4"},
    )
    return create_engine(url, pool_pre_ping=True, pool_recycle=280, future=True)


admin_engine = _engine_for(os.environ.get("DB_ADMIN", "Etex_admin"))
prop_engine = _engine_for(os.environ.get("DB_PROPOSAL", "Etex_Proposal"))


def q(engine, sql: str, params: dict | None = None) -> list[dict]:
    """Run a SELECT and return a list of dict rows."""
    with engine.connect() as c:
        res = c.execute(text(sql), params or {})
        return [dict(r._mapping) for r in res]


def one(engine, sql: str, params: dict | None = None):
    rows = q(engine, sql, params)
    return rows[0] if rows else None


def execute(engine, sql: str, params: dict | None = None):
    """Run an INSERT/UPDATE/DELETE; returns lastrowid + rowcount."""
    with engine.begin() as c:
        res = c.execute(text(sql), params or {})
        return {"lastrowid": res.lastrowid, "rowcount": res.rowcount}
