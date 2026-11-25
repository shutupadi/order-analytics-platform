-- How many orders are in each status (operations view).
SELECT status,
       COUNT(*)                      AS orders,
       ROUND(SUM(total_amount), 2)   AS amount
FROM orders
GROUP BY status
ORDER BY orders DESC;
