"""Unit tests: business rules in app/services.py."""
import pytest

from app import services
from app.models import Inventory


def stock(session, product_id):
    session.expire_all()
    return session.get(Inventory, product_id).quantity_on_hand


def test_place_order_calculates_total_and_reduces_stock(session):
    order = services.place_order(session, 1, [{"product_id": 1, "quantity": 2},
                                              {"product_id": 2, "quantity": 3}])
    assert float(order.total_amount) == 2 * 100 + 3 * 50
    assert order.status == "PLACED"
    assert stock(session, 1) == 8
    assert stock(session, 2) == 2


def test_order_rejected_when_not_enough_stock(session):
    with pytest.raises(services.OrderError, match="Not enough stock"):
        services.place_order(session, 1, [{"product_id": 2, "quantity": 6}])
    assert stock(session, 2) == 5


def test_order_is_all_or_nothing(session):
    # First item is fine, second is short: stock of the first must NOT change
    with pytest.raises(services.OrderError):
        services.place_order(session, 1, [{"product_id": 1, "quantity": 2},
                                          {"product_id": 2, "quantity": 99}])
    assert stock(session, 1) == 10


@pytest.mark.parametrize("items", [[], [{"product_id": 1, "quantity": 0}],
                                   [{"product_id": 999, "quantity": 1}]])
def test_invalid_orders_rejected(session, items):
    with pytest.raises(services.OrderError):
        services.place_order(session, 1, items)


def test_price_is_copied_at_time_of_sale(session):
    order = services.place_order(session, 1, [{"product_id": 1, "quantity": 1}])
    order.items[0].product.unit_price = 999
    session.commit()
    assert float(order.items[0].unit_price) == 100


def test_cancel_puts_stock_back(session):
    order = services.place_order(session, 1, [{"product_id": 1, "quantity": 4}])
    services.update_status(session, order.order_id, "CANCELLED")
    assert stock(session, 1) == 10


def test_status_flow(session):
    order = services.place_order(session, 1, [{"product_id": 1, "quantity": 1}])
    services.update_status(session, order.order_id, "SHIPPED")
    services.update_status(session, order.order_id, "DELIVERED")
    with pytest.raises(services.OrderError, match="Cannot change"):
        services.update_status(session, order.order_id, "CANCELLED")


def test_restock_and_low_stock(session):
    services.place_order(session, 1, [{"product_id": 2, "quantity": 3}])   # 5 -> 2
    assert [i.product_id for i in services.low_stock(session)] == [2]
    services.restock(session, 2, 20)
    assert services.low_stock(session) == []
