"""Business rules for orders. Kept out of the API layer so they are easy to unit test."""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select

from app.models import Inventory, Order, OrderItem, Product

ALLOWED_STATUS_CHANGES = {
    "PLACED": {"SHIPPED", "CANCELLED"},
    "SHIPPED": {"DELIVERED"},
    "DELIVERED": set(),
    "CANCELLED": set(),
}


class OrderError(ValueError):
    """Raised when an order breaks a business rule (bad input, not enough stock...)."""


def place_order(session, customer_id, items, order_date=None):
    """Create an order. items = [{"product_id": 1, "quantity": 2}, ...]

    All-or-nothing: if any product is short on stock, nothing is saved.
    """
    if not items:
        raise OrderError("An order needs at least one item")

    try:
        order = _build_order(session, customer_id, items, order_date)
    except OrderError:
        session.rollback()          # undo any stock already reserved for earlier items
        raise
    session.add(order)
    session.commit()
    return order


def _build_order(session, customer_id, items, order_date):
    order = Order(customer_id=customer_id, order_date=order_date or datetime.now(),
                  status="PLACED")
    total = Decimal("0")

    for item in items:
        qty = int(item["quantity"])
        if qty <= 0:
            raise OrderError("Quantity must be positive")
        product = session.get(Product, item["product_id"])
        if product is None:
            raise OrderError(f"Product {item['product_id']} not found")
        stock = session.get(Inventory, product.product_id)
        if stock.quantity_on_hand < qty:
            raise OrderError(f"Not enough stock for {product.sku}: "
                             f"{stock.quantity_on_hand} left, {qty} requested")

        stock.quantity_on_hand -= qty
        order.items.append(OrderItem(product_id=product.product_id, quantity=qty,
                                     unit_price=product.unit_price))
        total += Decimal(str(product.unit_price)) * qty

    order.total_amount = total
    return order


def update_status(session, order_id, new_status):
    order = session.get(Order, order_id)
    if order is None:
        raise OrderError(f"Order {order_id} not found")
    if new_status not in ALLOWED_STATUS_CHANGES.get(order.status, set()):
        raise OrderError(f"Cannot change order from {order.status} to {new_status}")

    if new_status == "CANCELLED":
        # Put the items back into stock
        for item in order.items:
            session.get(Inventory, item.product_id).quantity_on_hand += item.quantity

    order.status = new_status
    session.commit()
    return order


def restock(session, product_id, quantity):
    stock = session.get(Inventory, product_id)
    if stock is None:
        raise OrderError(f"Product {product_id} not found")
    if quantity <= 0:
        raise OrderError("Restock quantity must be positive")
    stock.quantity_on_hand += quantity
    session.commit()
    return stock


def low_stock(session):
    return session.scalars(
        select(Inventory).where(Inventory.quantity_on_hand <= Inventory.reorder_level)
    ).all()
