# Test cases (unit + integration)

Run all: `pytest -v` (25 tests). CI runs them on SQLite and on PostgreSQL 16.

| ID | Type | Scenario | Expected result | Test |
|----|------|----------|-----------------|------|
| TC-01 | Unit | Place order with 2 products | Total = sum(qty x price); stock reduced | `test_place_order_calculates_total_and_reduces_stock` |
| TC-02 | Unit | Order more than stock | Rejected with "Not enough stock"; stock unchanged | `test_order_rejected_when_not_enough_stock` |
| TC-03 | Unit | 1 valid + 1 short item | Whole order rejected, no stock reserved (all-or-nothing) | `test_order_is_all_or_nothing` |
| TC-04 | Unit | Empty order / qty 0 / unknown product | Rejected | `test_invalid_orders_rejected` |
| TC-05 | Unit | Product price changes after a sale | Old order keeps the old price | `test_price_is_copied_at_time_of_sale` |
| TC-06 | Unit | Cancel an order | Items go back into stock | `test_cancel_puts_stock_back` |
| TC-07 | Unit | PLACED → SHIPPED → DELIVERED, then cancel | Cancel after delivery is rejected | `test_status_flow` |
| TC-08 | Unit | Stock drops to reorder level, then restock | Appears in low-stock list, then disappears | `test_restock_and_low_stock` |
| TC-09 | Integration | API: create customer → order → ship → deliver | 201/200 responses, stock and status updated | `test_full_order_flow` |
| TC-10 | Integration | API: bad input | Clear 400/404 errors | `test_bad_requests_return_clear_errors` |
| TC-11 | Integration | API: reports | Category revenue and low stock correct | `test_reports_endpoint` |
| TC-12 | SQL | Every analytics query runs | Returns rows, no SQL error | `test_every_report_runs` |
| TC-13 | SQL | Monthly revenue reconciles to raw orders total | Sums match | `test_monthly_revenue_matches_raw_total` |
| TC-14 | SQL | Category revenue shares | Add up to 100% | `test_category_shares_add_up_to_100` |
| TC-15 | SQL | Top products per category | At most rank 3 per category | `test_top_products_max_three_per_category` |
| TC-16 | ETL | Run ETL to a local folder | 5 CSVs written; cancelled lines have 0 net revenue | `test_etl_writes_power_bi_files` |
| TC-17 | ETL | Orphan row in fact table | Data quality check stops the load | `test_quality_check_blocks_bad_data` |
| TC-18 | ETL | S3 bucket configured | Files uploaded to `powerbi/` (S3 mocked, no AWS needed) | `test_lambda_uploads_to_s3_when_bucket_set` |
