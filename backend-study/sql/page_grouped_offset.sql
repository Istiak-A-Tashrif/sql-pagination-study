WITH page AS MATERIALIZED (SELECT p.* FROM @S@.products p  ORDER BY p.id LIMIT $1 OFFSET $2),
o AS (SELECT oi.product_id,COUNT(DISTINCT oi.order_id) total_orders FROM @S@.order_items oi JOIN page k ON k.id=oi.product_id GROUP BY oi.product_id),
r AS (SELECT rv.product_id,AVG(rv.rating) avg_rating FROM @S@.reviews rv JOIN page k ON k.id=rv.product_id GROUP BY rv.product_id)
SELECT p.id,p.name,c.name AS category,COALESCE(o.total_orders,0) AS total_orders,
 COALESCE(r.avg_rating,0) AS avg_rating,COALESCE(i.stock,0) AS stock FROM page p LEFT JOIN @S@.categories c ON c.id=p.category_id
LEFT JOIN o ON o.product_id=p.id LEFT JOIN r ON r.product_id=p.id
LEFT JOIN @S@.inventory i ON i.product_id=p.id ORDER BY p.id
