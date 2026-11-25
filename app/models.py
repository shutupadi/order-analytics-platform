"""The relational (normalised) order / inventory data model.

customers 1───* orders 1───* order_items *───1 products 1───1 inventory
"""
from datetime import datetime

from sqlalchemy import (CheckConstraint, DateTime, ForeignKey, Integer, Numeric,
                        String, create_engine)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from app import config


class Base(DeclarativeBase):
    pass


class Customer(Base):
    __tablename__ = "customers"
    customer_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(120), unique=True)
    city: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    orders: Mapped[list["Order"]] = relationship(back_populates="customer")


class Product(Base):
    __tablename__ = "products"
    product_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sku: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(50))
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2))

    inventory: Mapped["Inventory"] = relationship(back_populates="product", uselist=False)

    __table_args__ = (CheckConstraint("unit_price > 0", name="ck_price_positive"),)


class Inventory(Base):
    __tablename__ = "inventory"
    product_id: Mapped[int] = mapped_column(ForeignKey("products.product_id"), primary_key=True)
    quantity_on_hand: Mapped[int] = mapped_column(Integer, default=0)
    reorder_level: Mapped[int] = mapped_column(Integer, default=10)

    product: Mapped[Product] = relationship(back_populates="inventory")

    __table_args__ = (CheckConstraint("quantity_on_hand >= 0", name="ck_stock_not_negative"),)


class Order(Base):
    __tablename__ = "orders"
    order_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.customer_id"))
    order_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    # PLACED -> SHIPPED -> DELIVERED, or PLACED -> CANCELLED
    status: Mapped[str] = mapped_column(String(20), default="PLACED")
    total_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)

    customer: Mapped[Customer] = relationship(back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"
    order_item_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.order_id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.product_id"))
    quantity: Mapped[int] = mapped_column(Integer)
    # Price is copied at the time of sale, so later price changes don't rewrite history
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2))

    order: Mapped[Order] = relationship(back_populates="items")
    product: Mapped[Product] = relationship()

    __table_args__ = (CheckConstraint("quantity > 0", name="ck_qty_positive"),)


def get_engine(url=None):
    return create_engine(url or config.DATABASE_URL)


def init_db(engine):
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)
