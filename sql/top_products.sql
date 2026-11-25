-- Top 3 products by revenue inside each category (RANK window function).
WITH product_sales AS (
    SELECT p.category,
           p.sku,
           p.name,
           SUM(oi.quantity)                 AS units_sold,
           SUM(oi.quantity * oi.unit_price) AS revenue
    FROM order_items oi
    JOIN orders   o ON o.order_id   = oi.order_id
    JOIN products p ON p.product_id = oi.product_id
    WHERE o.status <> 'CANCELLED'
    GROUP BY p.category, p.sku, p.name
),
ranked AS (
    SELECT *, RANK() OVER (PARTITION BY category ORDER BY revenue DESC) AS rank_in_category
    FROM product_sales
)
SELECT category, rank_in_category, sku, name, units_sold, ROUND(revenue, 2) AS revenue
FROM ranked
WHERE rank_in_category <= 3
ORDER BY category, rank_in_category;
