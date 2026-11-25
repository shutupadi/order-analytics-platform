"""ETL job: orders database (RDS) -> clean star-schema CSVs -> S3 (or a local folder) -> Power BI.

Extract : read the 5 operational tables with SQL
Transform: build one fact table (one row per order line) + dimension tables, add derived
           columns, and run data-quality checks
Load     : write CSVs to S3 when S3_BUCKET is set, otherwise to the local ./exports folder

Runs three ways:
  python -m etl.etl_job          (locally)
  AWS Lambda, handler = etl.etl_job.lambda_handler  (scheduled daily by EventBridge)
  imported in tests              (run_etl(engine, output_dir))
"""
import io
import os
from datetime import date

import pandas as pd

from app import config
from app.models import get_engine

FACT_SQL = """
SELECT oi.order_item_id,
       o.order_id,
       o.order_date,
       o.status,
       o.customer_id,
       oi.product_id,
       oi.quantity,
       oi.unit_price
FROM order_items oi
JOIN orders o ON o.order_id = oi.order_id
"""


# ---------- Extract ----------
def extract(engine):
    return {
        "order_lines": pd.read_sql(FACT_SQL, engine, parse_dates=["order_date"]),
        "customers": pd.read_sql("SELECT customer_id, name, city, created_at FROM customers", engine),
        "products": pd.read_sql("SELECT product_id, sku, name, category, unit_price FROM products",
                                engine),
        "inventory": pd.read_sql("SELECT product_id, quantity_on_hand, reorder_level FROM inventory",
                                 engine),
    }


# ---------- Transform ----------
def transform(raw):
    fact = raw["order_lines"].copy()
    fact["unit_price"] = fact["unit_price"].astype(float)
    fact["line_revenue"] = (fact["quantity"] * fact["unit_price"]).round(2)
    fact["is_cancelled"] = fact["status"] == "CANCELLED"
    # Cancelled orders keep their row (for cancellation-rate analysis) but count as 0 net revenue
    fact["net_revenue"] = fact["line_revenue"].where(~fact["is_cancelled"], 0.0)
    fact["date_key"] = fact["order_date"].dt.strftime("%Y%m%d").astype(int)
    fact["order_date"] = fact["order_date"].dt.date

    dim_customer = raw["customers"].rename(columns={"name": "customer_name"})
    dim_customer["created_at"] = pd.to_datetime(dim_customer["created_at"]).dt.date
    dim_product = raw["products"].rename(columns={"name": "product_name"})
    dim_product["unit_price"] = dim_product["unit_price"].astype(float)

    # Date dimension: one row per calendar day between the first and last order
    days = pd.date_range(min(fact["order_date"]), max(fact["order_date"]), freq="D")
    dim_date = pd.DataFrame({
        "date_key": days.strftime("%Y%m%d").astype(int),
        "date": days.date,
        "year": days.year,
        "quarter": "Q" + days.quarter.astype(str),
        "month_num": days.month,
        "month_name": days.strftime("%b"),
        "year_month": days.strftime("%Y-%m"),
        "weekday": days.strftime("%a"),
    })

    inventory = raw["inventory"].merge(raw["products"][["product_id", "sku", "name"]],
                                       on="product_id")
    inventory["needs_reorder"] = inventory["quantity_on_hand"] <= inventory["reorder_level"]
    inventory["snapshot_date"] = date.today()

    tables = {"fact_sales": fact, "dim_customer": dim_customer, "dim_product": dim_product,
              "dim_date": dim_date, "inventory_snapshot": inventory}
    check_quality(tables)
    return tables


def check_quality(tables):
    """Stop the load if the data is wrong, so Power BI never shows bad numbers."""
    fact = tables["fact_sales"]
    problems = []
    if fact["order_item_id"].duplicated().any():
        problems.append("duplicate order lines")
    if (fact["quantity"] <= 0).any():
        problems.append("non-positive quantity")
    if not fact["customer_id"].isin(tables["dim_customer"]["customer_id"]).all():
        problems.append("order lines with unknown customer")
    if not fact["product_id"].isin(tables["dim_product"]["product_id"]).all():
        problems.append("order lines with unknown product")
    if not fact["date_key"].isin(tables["dim_date"]["date_key"]).all():
        problems.append("order lines with date outside dim_date")
    if problems:
        raise ValueError("Data quality check failed: " + ", ".join(problems))


# ---------- Load ----------
def load(tables, output_dir=None, s3_bucket=None):
    written = []
    if s3_bucket:
        import boto3
        s3 = boto3.client("s3")
        for name, df in tables.items():
            key = f"powerbi/{name}.csv"
            buf = io.StringIO()
            df.to_csv(buf, index=False)
            s3.put_object(Bucket=s3_bucket, Key=key, Body=buf.getvalue().encode())
            written.append(f"s3://{s3_bucket}/{key}")
    else:
        os.makedirs(output_dir, exist_ok=True)
        for name, df in tables.items():
            path = os.path.join(output_dir, f"{name}.csv")
            df.to_csv(path, index=False)
            written.append(path)
    return written


def run_etl(engine=None, output_dir=None, s3_bucket=None):
    engine = engine or get_engine()
    tables = transform(extract(engine))
    files = load(tables, output_dir or config.EXPORT_DIR,
                 config.S3_BUCKET if s3_bucket is None else s3_bucket)
    summary = {"rows": {name: len(df) for name, df in tables.items()}, "files": files}
    print(summary)
    return summary


def lambda_handler(event, context):
    """AWS Lambda entry point. Lambda can only write to /tmp, so S3_BUCKET must be set there."""
    return run_etl()


if __name__ == "__main__":
    run_etl()
