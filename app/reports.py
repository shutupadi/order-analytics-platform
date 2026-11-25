"""Runs the analytical SQL queries stored in the sql/ folder."""
from pathlib import Path

from sqlalchemy import text

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"
REPORTS = ["monthly_revenue", "revenue_by_category", "top_products",
           "top_customers", "order_status_summary", "low_stock"]

# The only SQL that differs between SQLite (local) and PostgreSQL (RDS): getting "YYYY-MM"
MONTH_EXPR = {
    "sqlite": "strftime('%Y-%m', order_date)",
    "postgresql": "to_char(order_date, 'YYYY-MM')",
}


def load_sql(name, dialect):
    sql = (SQL_DIR / f"{name}.sql").read_text()
    return sql.replace("{month}", MONTH_EXPR[dialect])


def run_report(engine, name):
    if name not in REPORTS:
        raise KeyError(name)
    with engine.connect() as conn:
        result = conn.execute(text(load_sql(name, engine.dialect.name)))
        return [dict(row._mapping) for row in result]
