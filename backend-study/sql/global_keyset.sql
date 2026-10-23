SELECT p.id,p.name,c.name AS category,COALESCE(o.total_orders,0) AS total_orders,
 COALESCE(r.avg_rating,0) AS avg_rating,COALESCE(i.stock,0) AS stock
FROM @S@.products p LEFT JOIN @S@.categories c ON c.id=p.category_id
LEFT JOIN (SELECT product_id,COUNT(DISTINCT order_id) total_orders FROM @S@.order_items GROUP BY product_id) o ON o.product_id=p.id
LEFT JOIN (SELECT product_id,AVG(rating) avg_rating FROM @S@.reviews GROUP BY product_id) r ON r.product_id=p.id
LEFT JOIN @S@.inventory i ON i.product_id=p.id
WHERE p.id>$2 ORDER BY p.id LIMIT $1
