-- Revenue, units and share of total revenue per product category.
SELECT p.category,
       SUM(oi.quantity)                          AS units_sold,
       ROUND(SUM(oi.quantity * oi.unit_price), 2) AS revenue,
       ROUND(100.0 * SUM(oi.quantity * oi.unit_price)
             / SUM(SUM(oi.quantity * oi.unit_price)) OVER (), 1) AS revenue_share_pct
FROM order_items oi
JOIN orders   o ON o.order_id   = oi.order_id
JOIN products p ON p.product_id = oi.product_id
WHERE o.status <> 'CANCELLED'
GROUP BY p.category
ORDER BY revenue DESC;
