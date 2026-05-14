DROP VIEW IF EXISTS public.procurement_south_mvp;

CREATE VIEW public.procurement_south_mvp AS

WITH priority_products AS (
    SELECT
        NULL::text AS product_id_hex,
        product_code,
        MAX(product_name) AS product_name,
        SUM(qty) AS sales_qty_60d,
        ROUND(SUM(qty) / 60.0, 2) AS avg_daily_sales,
        MIN(sale_date) AS first_sale_date,
        MAX(sale_date) AS last_sale_date
    FROM public.sales_south_krasnodar
    WHERE product_code IN (
        'ОФ000006259'
    )
      AND sale_date >= (
          SELECT MAX(sale_date) - INTERVAL '120 days'
          FROM public.sales_south_krasnodar
      )
    GROUP BY product_code
),

base AS (
    SELECT
        COALESCE(s.product_id_hex, st.product_code::text, pp.product_id_hex, pp.product_code::text) AS product_id_hex,
        COALESCE(s.product_code, st.product_code, pp.product_code) AS product_code,
        COALESCE(s.product_name, st.product_name, pp.product_name) AS product_name,

        COALESCE(st.stock_qty, 0) AS stock_qty,
        COALESCE(s.sales_qty_60d, pp.sales_qty_60d, 0) AS sales_qty_60d,
        COALESCE(s.avg_daily_sales, pp.avg_daily_sales, 0) AS avg_daily_sales,

        st.stock_period,
        st.as_of_date,

        COALESCE(s.first_sale_date, pp.first_sale_date) AS first_sale_date,
        COALESCE(s.last_sale_date, pp.last_sale_date) AS last_sale_date
    FROM public.sales_south_krasnodar_60d s
    FULL OUTER JOIN public.stock_south_warehouse_agg st
        ON st.product_code = s.product_code
    FULL OUTER JOIN priority_products pp
        ON pp.product_code = COALESCE(s.product_code, st.product_code)
),

calc AS (
    SELECT
        *,
        CASE
            WHEN avg_daily_sales > 0
                THEN ROUND(stock_qty / avg_daily_sales, 1)
            ELSE NULL
        END AS days_of_cover,

        CASE
            WHEN sales_qty_60d <= 0 THEN 'no_sales'
            WHEN stock_qty <= 0 THEN 'out_of_stock'
            WHEN avg_daily_sales > 0 AND stock_qty / avg_daily_sales < 14 THEN 'critical'
            WHEN avg_daily_sales > 0 AND stock_qty / avg_daily_sales < 30 THEN 'low'
            ELSE 'ok'
        END AS stock_status,

        CASE
            WHEN sales_qty_60d <= 0 THEN 0
            WHEN stock_qty <= 0 THEN CEIL(avg_daily_sales * 30)
            WHEN avg_daily_sales > 0 AND stock_qty / avg_daily_sales < 14
                THEN CEIL((avg_daily_sales * 30) - stock_qty)
            ELSE 0
        END AS recommended_order_qty
    FROM base
)

SELECT
    product_id_hex,
    product_code,
    product_name,
    stock_qty,
    sales_qty_60d,
    avg_daily_sales,
    days_of_cover,
    stock_status,
    recommended_order_qty,
    stock_period,
    as_of_date,
    first_sale_date,
    last_sale_date
FROM calc
WHERE product_name IS NOT NULL
ORDER BY recommended_order_qty DESC, sales_qty_60d DESC;