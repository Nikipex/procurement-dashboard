DROP VIEW IF EXISTS public.sales_south_krasnodar_60d;

CREATE VIEW public.sales_south_krasnodar_60d AS

WITH sales_60d AS (
    SELECT
        product_id_hex,
        product_code,
        product_name,

        SUM(qty) AS sales_qty_60d,

        COUNT(DISTINCT sale_date) AS sales_days,

        MIN(sale_date) AS first_sale_date,
        MAX(sale_date) AS last_sale_date

    FROM public.sales_south_krasnodar

    WHERE sale_date >= CURRENT_DATE - INTERVAL '60 days'

    GROUP BY
        product_id_hex,
        product_code,
        product_name
),

calc AS (
    SELECT
        product_id_hex,
        product_code,
        product_name,

        sales_qty_60d,

        ROUND(
            sales_qty_60d / 60.0,
            2
        ) AS avg_daily_sales,

        sales_days,

        first_sale_date,
        last_sale_date

    FROM sales_60d
)

SELECT *
FROM calc
WHERE sales_qty_60d > 0
ORDER BY sales_qty_60d DESC;