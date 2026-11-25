-- Products at or below their reorder level: what to restock first.
SELECT p.sku,
       p.name,
       p.category,
       i.quantity_on_hand,
       i.reorder_level
FROM inventory i
JOIN products p ON p.product_id = i.product_id
WHERE i.quantity_on_hand <= i.reorder_level
ORDER BY i.quantity_on_hand;
