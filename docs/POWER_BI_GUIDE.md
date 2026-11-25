# Power BI reporting layer

The ETL job produces a small **star schema**: one fact table and four dimension/snapshot tables.
Sample files from the demo data are already in [`sample_exports/`](../sample_exports), so you can build the report without running anything.

| File | Grain (one row per) | Key columns |
|------|---------------------|-------------|
| `fact_sales.csv` | order line | order_id, date_key, customer_id, product_id, quantity, line_revenue, net_revenue, status, is_cancelled |
| `dim_date.csv` | calendar day | date_key, date, year, quarter, month_name, year_month, weekday |
| `dim_customer.csv` | customer | customer_id, customer_name, city |
| `dim_product.csv` | product | product_id, sku, product_name, category, unit_price |
| `inventory_snapshot.csv` | product (today's stock) | product_id, quantity_on_hand, reorder_level, needs_reorder |

## 1. Load the data
Power BI Desktop → **Get data → Text/CSV** → load all 5 files (or **Get data → Folder** and pick the exports folder).
In Power Query check types: `date` columns as Date, money columns as Decimal number, `is_cancelled` / `needs_reorder` as True/False.

## 2. Relationships (Model view)
```
dim_date[date_key]        1 ──► * fact_sales[date_key]
dim_customer[customer_id] 1 ──► * fact_sales[customer_id]
dim_product[product_id]   1 ──► * fact_sales[product_id]
dim_product[product_id]   1 ──► 1 inventory_snapshot[product_id]
```
Single direction, from dimension to fact. Mark `dim_date` as the date table (Table tools → Mark as date table → `date`).

## 3. DAX measures
```DAX
Total Revenue    = SUM ( fact_sales[net_revenue] )
Total Orders     = CALCULATE ( DISTINCTCOUNT ( fact_sales[order_id] ), fact_sales[is_cancelled] = FALSE () )
Units Sold       = CALCULATE ( SUM ( fact_sales[quantity] ), fact_sales[is_cancelled] = FALSE () )
Avg Order Value  = DIVIDE ( [Total Revenue], [Total Orders] )
Cancellation %   = DIVIDE ( CALCULATE ( DISTINCTCOUNT ( fact_sales[order_id] ), fact_sales[is_cancelled] = TRUE () ),
                            DISTINCTCOUNT ( fact_sales[order_id] ) )
Revenue LM       = CALCULATE ( [Total Revenue], DATEADD ( dim_date[date], -1, MONTH ) )
MoM Growth %     = DIVIDE ( [Total Revenue] - [Revenue LM], [Revenue LM] )
Active Customers = CALCULATE ( DISTINCTCOUNT ( fact_sales[customer_id] ), fact_sales[is_cancelled] = FALSE () )
Products to Reorder = CALCULATE ( COUNTROWS ( inventory_snapshot ), inventory_snapshot[needs_reorder] = TRUE () )
```

## 4. Report pages and visuals

**Page 1: Sales overview (for the client's management)**
| Visual | Fields |
|--------|--------|
| 4 KPI cards | Total Revenue, Total Orders, Avg Order Value, Cancellation % |
| Line chart: revenue trend | X: dim_date[year_month], Y: Total Revenue (add MoM Growth % to tooltip) |
| Clustered bar: revenue by category | Y: dim_product[category], X: Total Revenue |
| Donut: orders by status | Legend: fact_sales[status], Values: count of order_id |
| Slicers | dim_date[year_month], dim_product[category], dim_customer[city] |

**Page 2: Products and customers**
| Visual | Fields |
|--------|--------|
| Table: top products | product_name, category, Units Sold, Total Revenue (sort by revenue, Top N = 10 filter) |
| Bar chart: revenue by city | dim_customer[city], Total Revenue |
| Table: top customers | customer_name, city, Total Orders, Total Revenue, Avg Order Value |

**Page 3: Inventory (for operations)**
| Visual | Fields |
|--------|--------|
| Card | Products to Reorder |
| Table with conditional formatting | sku, name, quantity_on_hand, reorder_level; red background when needs_reorder = True |

## 5. Refresh
- Local demo: run `python -m etl.etl_job`, then **Refresh** in Power BI.
- On AWS: Lambda refreshes the CSVs in S3 daily. Publish the report to Power BI Service and set a scheduled refresh (via a gateway pointing at the synced folder, or connect Power BI directly to RDS).

## What the demo data shows
- Electronics is the largest category (~40% of revenue), driven by the Smart Watch.
- Order volume grows through the year; November is a partial month (data until Nov 20).
- ~5% of orders are cancelled; a few popular products (Power Bank, Denim Jeans) are out of stock, so the inventory page flags them for reorder.
