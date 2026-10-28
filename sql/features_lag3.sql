WITH lagged AS (
      SELECT month,product,complaints,LAG(complaints,3) OVER w AS lag_3, LAG(month,3) OVER w AS source_month_3,
LAG(complaints,4) OVER w AS lag_4, LAG(month,4) OVER w AS source_month_4,
LAG(complaints,5) OVER w AS lag_5, LAG(month,5) OVER w AS source_month_5,
LAG(complaints,12) OVER w AS lag_12, LAG(month,12) OVER w AS source_month_12
      FROM product_counts
      WINDOW w AS (PARTITION BY product ORDER BY month)
    ) SELECT * FROM lagged WHERE month >= '2019-01-01'
      AND product IN (?,?,?,?,?,?) ORDER BY month,product;