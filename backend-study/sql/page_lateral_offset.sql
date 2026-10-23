WITH page AS MATERIALIZED (SELECT p.* FROM @S@.products p  ORDER BY p.id LIMIT $1 OFFSET $2)
SELECT p.id,p.name,c.name AS category,COALESCE(o.total_orders,0) AS total_orders,
 COALESCE(r.avg_rating,0) AS avg_rating,COALESCE(i.stock,0) AS stock FROM page p LEFT JOIN @S@.categories c ON c.id=p.category_id
LEFT JOIN LATERAL (SELECT COUNT(DISTINCT order_id) total_orders FROM @S@.order_items oi WHERE oi.product_id=p.id) o ON true
LEFT JOIN LATERAL (SELECT AVG(rating) avg_rating FROM @S@.reviews rv WHERE rv.product_id=p.id) r ON true
LEFT JOIN @S@.inventory i ON i.product_id=p.id ORDER BY p.id
