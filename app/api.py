"""Flask REST API for the order-management system. Views stay thin: read JSON -> call service -> return JSON."""
from flask import Flask, jsonify, request
from sqlalchemy import select

from app import reports, services
from app.models import Customer, Order, Product, get_engine, init_db


def order_to_dict(order):
    return {
        "order_id": order.order_id,
        "customer_id": order.customer_id,
        "order_date": order.order_date.isoformat(),
        "status": order.status,
        "total_amount": float(order.total_amount),
        "items": [{"product_id": i.product_id, "quantity": i.quantity,
                   "unit_price": float(i.unit_price)} for i in order.items],
    }


def create_app(database_url=None):
    app = Flask(__name__)
    engine = get_engine(database_url)
    Session = init_db(engine)

    @app.errorhandler(services.OrderError)
    def business_rule_error(err):
        return jsonify(error=str(err)), 400

    @app.get("/")
    def index():
        return jsonify(service="Order Management & Analytics API",
                       endpoints=["GET /products", "POST /customers", "GET /orders",
                                  "POST /orders", "GET /orders/<id>",
                                  "PATCH /orders/<id>/status",
                                  "POST /inventory/<product_id>/restock",
                                  "GET /inventory/low-stock",
                                  "GET /reports/<name>"],
                       reports=reports.REPORTS)

    @app.get("/products")
    def list_products():
        with Session() as s:
            products = s.scalars(select(Product).order_by(Product.product_id)).all()
            return jsonify([{"product_id": p.product_id, "sku": p.sku, "name": p.name,
                             "category": p.category, "unit_price": float(p.unit_price),
                             "stock": p.inventory.quantity_on_hand} for p in products])

    @app.post("/customers")
    def create_customer():
        data = request.get_json(force=True)
        missing = [f for f in ("name", "email", "city") if not data.get(f)]
        if missing:
            return jsonify(error=f"Missing fields: {', '.join(missing)}"), 400
        with Session() as s:
            if s.scalar(select(Customer).where(Customer.email == data["email"])):
                return jsonify(error="Email already exists"), 400
            customer = Customer(name=data["name"], email=data["email"], city=data["city"])
            s.add(customer)
            s.commit()
            return jsonify(customer_id=customer.customer_id), 201

    @app.get("/orders")
    def list_orders():
        status = request.args.get("status")
        with Session() as s:
            query = select(Order).order_by(Order.order_id.desc()).limit(50)
            if status:
                query = query.where(Order.status == status.upper())
            return jsonify([order_to_dict(o) for o in s.scalars(query).all()])

    @app.post("/orders")
    def create_order():
        data = request.get_json(force=True)
        with Session() as s:
            if s.get(Customer, data.get("customer_id")) is None:
                return jsonify(error="Customer not found"), 400
            order = services.place_order(s, data["customer_id"], data.get("items", []))
            return jsonify(order_to_dict(order)), 201

    @app.get("/orders/<int:order_id>")
    def get_order(order_id):
        with Session() as s:
            order = s.get(Order, order_id)
            if order is None:
                return jsonify(error="Order not found"), 404
            return jsonify(order_to_dict(order))

    @app.patch("/orders/<int:order_id>/status")
    def change_status(order_id):
        new_status = request.get_json(force=True).get("status", "").upper()
        with Session() as s:
            order = services.update_status(s, order_id, new_status)
            return jsonify(order_to_dict(order))

    @app.post("/inventory/<int:product_id>/restock")
    def restock(product_id):
        qty = int(request.get_json(force=True).get("quantity", 0))
        with Session() as s:
            stock = services.restock(s, product_id, qty)
            return jsonify(product_id=product_id, quantity_on_hand=stock.quantity_on_hand)

    @app.get("/inventory/low-stock")
    def low_stock():
        return jsonify(reports.run_report(engine, "low_stock"))

    @app.get("/reports/<name>")
    def report(name):
        if name not in reports.REPORTS:
            return jsonify(error=f"Unknown report. Choose one of {reports.REPORTS}"), 404
        return jsonify(reports.run_report(engine, name))

    return app


if __name__ == "__main__":
    create_app().run(debug=True)
