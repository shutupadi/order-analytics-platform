-- Top 10 customers by total spend, with order count and average order value.
SELECT c.customer_id,
       c.name,
       c.city,
       COUNT(o.order_id)              AS orders,
       ROUND(SUM(o.total_amount), 2)  AS total_spend,
       ROUND(AVG(o.total_amount), 2)  AS avg_order_value
FROM customers c
JOIN orders o ON o.customer_id = c.customer_id
WHERE o.status <> 'CANCELLED'
GROUP BY c.customer_id, c.name, c.city
ORDER BY total_spend DESC
LIMIT 10;
