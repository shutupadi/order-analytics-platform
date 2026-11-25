"""Loads demo data for a simulated retail client: 40 customers, 20 products, ~400 orders (Jan-Nov 2026).

Run:  python seed.py          (uses DATABASE_URL, default SQLite orders.db)
Orders are created through services.place_order, so stock is reduced by the same rules the API uses.
"""
import random
from datetime import datetime, timedelta

from app import services
from app.models import Base, Customer, Inventory, Product, get_engine, init_db

CATALOG = {
    "Electronics": [("Wireless Earbuds", 2499), ("Smart Watch", 4999),
                    ("Power Bank 10000mAh", 1299), ("Bluetooth Speaker", 1999)],
    "Home & Kitchen": [("Non-stick Pan", 899), ("Electric Kettle", 1199),
                       ("Dinner Set", 2199), ("Storage Containers", 499)],
    "Fashion": [("Cotton T-Shirt", 599), ("Denim Jeans", 1499),
                ("Running Shoes", 2799), ("Backpack", 1099)],
    "Grocery": [("Basmati Rice 5kg", 649), ("Green Tea 100 bags", 349),
                ("Dry Fruits Mix 1kg", 999), ("Olive Oil 1L", 799)],
    "Beauty": [("Face Wash", 249), ("Sunscreen SPF50", 449),
               ("Hair Oil", 199), ("Perfume", 1599)],
}
CITIES = ["Jaipur", "Delhi", "Mumbai", "Bengaluru", "Pune", "Hyderabad", "Chennai", "Kolkata"]
FIRST = ["Aarav", "Diya", "Rohan", "Isha", "Kabir", "Ananya", "Vivaan", "Meera",
         "Arjun", "Sara", "Karan", "Priya", "Dev", "Nisha", "Yash", "Riya", "Aditi", "Rahul",
         "Sneha", "Vikram"]
LAST = ["Sharma", "Verma", "Gupta", "Iyer", "Khan", "Reddy"]


def seed(database_url=None, n_orders=400, rng_seed=42):
    rng = random.Random(rng_seed)          # fixed seed -> same data every run
    engine = get_engine(database_url)
    Base.metadata.drop_all(engine)
    Session = init_db(engine)

    with Session() as s:
        for i in range(40):
            name = f"{FIRST[i % len(FIRST)]} {LAST[i % len(LAST)]}"
            s.add(Customer(name=name, email=f"customer{i + 1}@example.com",
                           city=rng.choice(CITIES), created_at=datetime(2026, 1, 1)))

        sku = 1
        for category, items in CATALOG.items():
            for name, price in items:
                product = Product(sku=f"SKU-{sku:03d}", name=name, category=category,
                                  unit_price=price)
                product.inventory = Inventory(quantity_on_hand=rng.randint(75, 140),
                                              reorder_level=20)
                s.add(product)
                sku += 1
        s.commit()

        # Orders spread over Jan-Nov 2026; later months get more orders (business is growing)
        start = datetime(2026, 1, 1)
        days = (datetime(2026, 11, 20) - start).days
        placed = 0
        for _ in range(n_orders):
            day = int(days * rng.random() ** 0.8)
            order_date = start + timedelta(days=day, hours=rng.randint(8, 22))
            items = [{"product_id": pid, "quantity": rng.randint(1, 3)}
                     for pid in rng.sample(range(1, 21), rng.randint(1, 3))]
            try:
                order = services.place_order(s, rng.randint(1, 40), items, order_date)
            except services.OrderError:
                continue                    # out of stock: order rejected, same as the API
            placed += 1

            # Older orders are mostly delivered; recent ones are still in progress
            age_days = days - day
            roll = rng.random()
            if roll < 0.06:
                services.update_status(s, order.order_id, "CANCELLED")
            elif age_days > 10 or roll < 0.5:
                services.update_status(s, order.order_id, "SHIPPED")
                if age_days > 5:
                    services.update_status(s, order.order_id, "DELIVERED")
    print(f"Seeded 40 customers, 20 products, {placed} orders")
    return placed


if __name__ == "__main__":
    seed()
