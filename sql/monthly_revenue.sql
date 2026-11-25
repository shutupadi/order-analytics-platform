-- Revenue and order count per month, with month-over-month growth (LAG window function).
-- Cancelled orders are excluded from revenue.
WITH monthly AS (
    SELECT {month} AS month,
           COUNT(*)            AS orders,
           SUM(total_amount)   AS revenue
    FROM orders
    WHERE status <> 'CANCELLED'
    GROUP BY {month}
)
SELECT month,
       orders,
       ROUND(revenue, 2) AS revenue,
       ROUND(100.0 * (revenue - LAG(revenue) OVER (ORDER BY month))
             / LAG(revenue) OVER (ORDER BY month), 1) AS growth_pct
FROM monthly
ORDER BY month;
