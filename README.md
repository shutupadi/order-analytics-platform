# Cloud Order-Management & Analytics Platform

A small order-management system for a **simulated retail client**, plus the analytics pipeline that turns its orders into a **Power BI** dashboard.

1. **Operate**: a REST API (Flask) to register customers, place orders, ship / deliver / cancel them and restock inventory.
2. **Store**: a normalised relational model (customers, products, inventory, orders, order_items) in **PostgreSQL on Amazon RDS** (SQLite for local runs).
3. **Analyse**: business questions answered in SQL (monthly revenue and growth, top products, best customers, low stock).
4. **ETL**: a Lambda-ready job extracts the tables, builds a star schema, runs data-quality checks and loads CSVs to **S3**.
5. **Report**: Power BI reads those CSVs for a client-facing sales and inventory dashboard.

**Stack:** Python, Flask, SQLAlchemy, SQL (PostgreSQL / SQLite), pandas, AWS (EC2, RDS, Lambda, S3), Power BI, pytest, GitHub Actions.

---

## Architecture

```
  Client staff / Postman
          │ HTTP (JSON)
          ▼
 ┌──────────────────────┐         ┌───────────────────────────┐
 │ EC2: Flask REST API  │──SQL───►│ RDS PostgreSQL            │
 │ app/api.py           │         │ customers, products,      │
 │ app/services.py      │         │ inventory, orders,        │
 └──────────────────────┘         │ order_items               │
                                  └─────────────▲─────────────┘
 EventBridge (daily) ──► Lambda: etl/etl_job.py │ Extract
                              │ Transform (star schema + quality checks)
                              ▼ Load
                    S3: powerbi/fact_sales.csv, dim_*.csv
                              │
                              ▼
                     Power BI dashboard (3 pages)
```

Locally the same code runs with **no AWS account**: SQLite instead of RDS, and the ETL writes to a local `exports/` folder instead of S3.

---

## Database design (normalised, 3NF)

| Table | Key columns | Notes |
|-------|-------------|-------|
| `customers` | customer_id (PK), name, email (unique), city | |
| `products` | product_id (PK), sku (unique), name, category, unit_price | `CHECK unit_price > 0` |
| `inventory` | product_id (PK + FK), quantity_on_hand, reorder_level | one row per product, `CHECK quantity_on_hand >= 0` |
| `orders` | order_id (PK), customer_id (FK), order_date, status, total_amount | status: PLACED → SHIPPED → DELIVERED, or CANCELLED |
| `order_items` | order_item_id (PK), order_id (FK), product_id (FK), quantity, unit_price | `CHECK quantity > 0` |

```
customers 1───* orders 1───* order_items *───1 products 1───1 inventory
```

Design decisions worth mentioning:
- **order_items** resolves the many-to-many between orders and products (one order has many products, one product is in many orders).
- **unit_price is copied into order_items** at the time of sale. If the product price changes later, old orders and revenue reports don't change.
- **Inventory is its own table**, so stock updates don't touch the product catalogue.
- **Database constraints** (unique, foreign keys, CHECK) are a second safety net behind the Python validation.

---

## Business rules (`app/services.py`)

| Rule | How |
|------|-----|
| You can't sell what you don't have | `place_order` checks stock for every item before saving |
| All-or-nothing orders | If any item is short, the whole order is rolled back (a transaction) |
| Correct totals | total = Σ quantity × unit price, calculated on the server, never trusted from the client |
| Valid status flow | PLACED → SHIPPED → DELIVERED; only a PLACED order can be CANCELLED |
| Cancelling restocks | Cancelled items are added back to inventory |
| Reorder alerts | A product is "low stock" when quantity_on_hand ≤ reorder_level |

---

## Analytics SQL (`sql/`)

Each file answers one business question. They are run by `app/reports.py`, exposed at `GET /reports/<name>`, and easy to paste into any SQL client.

| File | Business question | SQL used |
|------|------------------|----------|
| `monthly_revenue.sql` | How is revenue trending month by month? | CTE, GROUP BY, **LAG()** window for month-over-month growth % |
| `revenue_by_category.sql` | Which categories drive revenue? | 3-table JOIN, SUM, **SUM() OVER ()** for share of total |
| `top_products.sql` | Top 3 products in each category | CTE, **RANK() OVER (PARTITION BY category)** |
| `top_customers.sql` | Who are our best customers? | JOIN, COUNT, SUM, AVG (average order value) |
| `order_status_summary.sql` | How many orders are stuck / cancelled? | GROUP BY status |
| `low_stock.sql` | What should we reorder? | JOIN + filter on reorder level |

Cancelled orders are excluded from revenue everywhere. The only SQL difference between SQLite and PostgreSQL is how to get `YYYY-MM` from a date, which `reports.py` swaps in (`strftime` vs `to_char`).

---

## ETL to Power BI (`etl/etl_job.py`)

| Step | What happens |
|------|-------------|
| **Extract** | Read orders + order_items (joined), customers, products, inventory with SQL into pandas |
| **Transform** | Build a **star schema**: `fact_sales` (one row per order line) + `dim_date`, `dim_customer`, `dim_product`, `inventory_snapshot`. Add `line_revenue`, `net_revenue` (0 for cancelled), `is_cancelled`, `date_key` |
| **Quality checks** | No duplicate order lines, no quantity ≤ 0, every fact row matches a customer, product and date. If a check fails, nothing is loaded, so the dashboard never shows bad numbers |
| **Load** | `S3_BUCKET` set → upload to `s3://<bucket>/powerbi/*.csv` (AWS Lambda). Not set → write to `./exports/` |

The same function runs locally (`python -m etl.etl_job`) and in AWS Lambda (`lambda_handler`), scheduled daily by EventBridge.

Power BI model, DAX measures and visuals: **[docs/POWER_BI_GUIDE.md](docs/POWER_BI_GUIDE.md)**. Sample output files are in [`sample_exports/`](sample_exports) so the dashboard can be built straight away.

---

## Code structure

```
app/config.py        Settings from environment variables (DATABASE_URL, S3_BUCKET)
app/models.py        The 5 tables (SQLAlchemy)
app/services.py      Business rules: place_order, update_status, restock, low_stock
app/api.py           Flask REST API (thin: JSON in -> service -> JSON out)
app/reports.py       Runs the analytics SQL files
sql/                 6 analytics queries
etl/etl_job.py       Extract -> Transform -> Load (+ AWS Lambda handler)
seed.py              Demo data: 40 customers, 20 products, ~400 orders (Jan–Nov 2026)
wsgi.py              Entry point for gunicorn on EC2
tests/               pytest: unit, integration (API), SQL and ETL tests
docs/                AWS deployment, Power BI guide, test case sheet
sample_exports/      ETL output from the demo data (for Power BI)
.github/workflows/   CI: tests on SQLite and PostgreSQL on every push
```

---

## Run it locally (about 2 minutes)

```bash
python -m venv venv
venv\Scripts\activate          # Windows   (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
python seed.py                 # creates orders.db with demo data
python -m app.api              # API on http://127.0.0.1:5000
```

In a second terminal:
```bash
python -m etl.etl_job          # writes the Power BI CSVs to ./exports
pytest -v                      # 25 tests
```

To use PostgreSQL instead of SQLite, set
`DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/orders` before running.

### Demo script (what to show)
Open these in the browser:
- http://127.0.0.1:5000/ (list of endpoints)
- http://127.0.0.1:5000/products (catalogue with current stock)
- http://127.0.0.1:5000/reports/monthly_revenue
- http://127.0.0.1:5000/reports/top_products
- http://127.0.0.1:5000/inventory/low-stock

Then place and manage an order (Windows PowerShell: use `curl.exe` instead of `curl`, or Postman):
```bash
# 1. Place an order: stock goes down, total is calculated
curl -X POST http://127.0.0.1:5000/orders -H "Content-Type: application/json" \
     -d "{\"customer_id\": 1, \"items\": [{\"product_id\": 2, \"quantity\": 1}, {\"product_id\": 9, \"quantity\": 2}]}"

# 2. Try to buy an out-of-stock product (Power Bank, SKU-003): 400 "Not enough stock"
curl -X POST http://127.0.0.1:5000/orders -H "Content-Type: application/json" \
     -d "{\"customer_id\": 1, \"items\": [{\"product_id\": 3, \"quantity\": 1}]}"

# 3. Restock it, then ship the order from step 1 (use the order_id it returned)
curl -X POST http://127.0.0.1:5000/inventory/3/restock -H "Content-Type: application/json" -d "{\"quantity\": 50}"
curl -X PATCH http://127.0.0.1:5000/orders/391/status -H "Content-Type: application/json" -d "{\"status\": \"SHIPPED\"}"
```
Finally run the ETL and open Power BI on the CSVs.

### API endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/products` | Catalogue with stock |
| POST | `/customers` | Register a customer `{name, email, city}` |
| GET | `/orders?status=PLACED` | Latest 50 orders, optional status filter |
| POST | `/orders` | Place an order `{customer_id, items: [{product_id, quantity}]}` |
| GET | `/orders/<id>` | One order with its items |
| PATCH | `/orders/<id>/status` | `{status: SHIPPED / DELIVERED / CANCELLED}` |
| POST | `/inventory/<product_id>/restock` | `{quantity}` |
| GET | `/inventory/low-stock` | Products at or below reorder level |
| GET | `/reports/<name>` | Any analytics query from `sql/` |

---

## Testing (QA)

```bash
pytest -v
```

25 tests in four groups (test case sheet: [docs/TEST_CASES.md](docs/TEST_CASES.md)):

| Group | File | What it checks |
|-------|------|----------------|
| Unit | `tests/test_services.py` | Totals, stock checks, all-or-nothing orders, price history, status flow, cancel restocks |
| Integration | `tests/test_api.py` | Full HTTP flow: customer → order → ship → deliver; error responses; report endpoints |
| SQL | `tests/test_reports.py` | Every query runs; monthly revenue reconciles with raw orders; category shares add to 100% |
| ETL | `tests/test_etl.py` | CSVs written correctly; quality check blocks bad data; S3 upload (mocked, no AWS needed) |

GitHub Actions (`.github/workflows/ci.yml`) runs the suite twice on every push: on SQLite and on a real **PostgreSQL 16** container (same engine as RDS).

---

## Deploying on AWS

Step-by-step in **[docs/AWS_DEPLOYMENT.md](docs/AWS_DEPLOYMENT.md)**. In short:

| Service | Role |
|---------|------|
| **RDS (PostgreSQL)** | The order / inventory database. Set `DATABASE_URL` to its endpoint |
| **EC2** | Runs the Flask API with gunicorn: `gunicorn -w 2 -b 0.0.0.0:8000 wsgi:app` |
| **Lambda** | Runs the ETL (`etl.etl_job.lambda_handler`) daily via an EventBridge schedule |
| **S3** | Stores the Power BI CSVs at `s3://<bucket>/powerbi/` |

No code changes between local and AWS: only the environment variables `DATABASE_URL` and `S3_BUCKET`.
