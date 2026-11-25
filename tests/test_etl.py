"""Tests for the ETL job: extract -> transform -> load to a local folder, plus data-quality checks."""
import pandas as pd
import pytest

from app import services
from etl.etl_job import check_quality, extract, run_etl, transform


def test_etl_writes_power_bi_files(engine, session, tmp_path):
    order = services.place_order(session, 1, [{"product_id": 1, "quantity": 2},
                                              {"product_id": 2, "quantity": 1}])
    cancelled = services.place_order(session, 1, [{"product_id": 2, "quantity": 1}])
    services.update_status(session, cancelled.order_id, "CANCELLED")

    summary = run_etl(engine, output_dir=str(tmp_path), s3_bucket="")

    assert summary["rows"]["fact_sales"] == 3
    for name in ("fact_sales", "dim_customer", "dim_product", "dim_date", "inventory_snapshot"):
        assert (tmp_path / f"{name}.csv").exists()

    fact = pd.read_csv(tmp_path / "fact_sales.csv")
    assert fact["line_revenue"].sum() == 2 * 100 + 50 + 50
    assert fact["net_revenue"].sum() == 2 * 100 + 50          # cancelled line counts as 0
    assert set(fact.loc[fact.order_id == order.order_id, "status"]) == {"PLACED"}


def test_quality_check_blocks_bad_data(engine, session):
    services.place_order(session, 1, [{"product_id": 1, "quantity": 1}])
    tables = transform(extract(engine))
    tables["fact_sales"].loc[0, "customer_id"] = 999            # orphan row
    with pytest.raises(ValueError, match="unknown customer"):
        check_quality(tables)


def test_lambda_uploads_to_s3_when_bucket_set(engine, session, monkeypatch):
    """No real AWS call: boto3's client is replaced with a fake that records uploads."""
    services.place_order(session, 1, [{"product_id": 1, "quantity": 1}])
    uploaded = {}

    class FakeS3:
        def put_object(self, Bucket, Key, Body):
            uploaded[Key] = Body

    import boto3
    monkeypatch.setattr(boto3, "client", lambda service: FakeS3())
    summary = run_etl(engine, s3_bucket="my-bucket")
    assert "powerbi/fact_sales.csv" in uploaded
    assert summary["files"][0].startswith("s3://my-bucket/powerbi/")
