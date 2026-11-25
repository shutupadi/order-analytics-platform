"""Tests for the analytical SQL in sql/ (run against the seeded demo dataset)."""
import pytest

from app.reports import REPORTS, run_report
from seed import seed


@pytest.fixture
def seeded(engine, db_url):
    seed(db_url, n_orders=120)
    return engine


@pytest.mark.parametrize("name", REPORTS)
def test_every_report_runs(seeded, name):
    assert isinstance(run_report(seeded, name), list)


def test_monthly_revenue_matches_raw_total(seeded):
    from sqlalchemy import text
    with seeded.connect() as conn:
        expected = conn.execute(text(
            "SELECT SUM(total_amount) FROM orders WHERE status <> 'CANCELLED'")).scalar()
    rows = run_report(seeded, "monthly_revenue")
    assert sum(float(r["revenue"]) for r in rows) == pytest.approx(float(expected), abs=0.05)
    assert rows[0]["growth_pct"] is None          # first month has nothing to compare to
    assert [r["month"] for r in rows] == sorted(r["month"] for r in rows)


def test_category_shares_add_up_to_100(seeded):
    rows = run_report(seeded, "revenue_by_category")
    assert sum(float(r["revenue_share_pct"]) for r in rows) == pytest.approx(100, abs=0.5)


def test_top_products_max_three_per_category(seeded):
    rows = run_report(seeded, "top_products")
    for category in {r["category"] for r in rows}:
        ranks = [r["rank_in_category"] for r in rows if r["category"] == category]
        assert max(ranks) <= 3
