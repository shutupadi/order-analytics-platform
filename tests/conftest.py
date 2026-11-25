import os

import pytest
from sqlalchemy import text

from app.api import create_app
from app.models import Base, Customer, Inventory, Product, get_engine, init_db

# Tests use a temporary SQLite file by default. CI sets TEST_DATABASE_URL to a real PostgreSQL.
TEST_DB = os.getenv("TEST_DATABASE_URL")


@pytest.fixture
def db_url(tmp_path):
    if TEST_DB:
        engine = get_engine(TEST_DB)
        Base.metadata.drop_all(engine)
        engine.dispose()
        return TEST_DB
    return f"sqlite:///{tmp_path / 'test.db'}"


@pytest.fixture
def engine(db_url):
    engine = get_engine(db_url)
    Base.metadata.drop_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine):
    """A small, known dataset: 1 customer, 2 products (stock 10 and 5)."""
    Session = init_db(engine)
    with Session() as s:
        s.add(Customer(name="Test Customer", email="test@example.com", city="Jaipur"))
        p1 = Product(sku="SKU-A", name="Earbuds", category="Electronics", unit_price=100)
        p1.inventory = Inventory(quantity_on_hand=10, reorder_level=3)
        p2 = Product(sku="SKU-B", name="T-Shirt", category="Fashion", unit_price=50)
        p2.inventory = Inventory(quantity_on_hand=5, reorder_level=3)
        s.add_all([p1, p2])
        s.commit()
        yield s


@pytest.fixture
def client(db_url, session):
    app = create_app(db_url)
    app.config["TESTING"] = True
    return app.test_client()
