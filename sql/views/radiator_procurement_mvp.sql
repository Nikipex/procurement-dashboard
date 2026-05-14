DROP VIEW IF EXISTS public.radiator_procurement_mvp CASCADE;

CREATE VIEW public.radiator_procurement_mvp AS

WITH radiator_sales_monthly AS (
    SELECT
        s.product_id_hex,
        s.product_code,
        s.product_name,

        SUM(s.qty) FILTER (
            WHERE s.sale_date >= DATE '2026-01-01'
              AND s.sale_date < DATE '2026-02-01'
        ) AS radiator_qty_jan_2026,

        SUM(s.qty) FILTER (
            WHERE s.sale_date >= DATE '2026-02-01'
              AND s.sale_date < DATE '2026-03-01'
        ) AS radiator_qty_feb_2026,

        SUM(s.qty) FILTER (
            WHERE s.sale_date >= DATE '2026-03-01'
              AND s.sale_date < DATE '2026-04-01'
        ) AS radiator_qty_mar_2026,

        SUM(s.qty) FILTER (
            WHERE s.sale_date >= DATE '2026-04-01'
              AND s.sale_date < DATE '2026-05-01'
        ) AS radiator_qty_apr_2026

    FROM public.sales_south_krasnodar s
    WHERE LOWER(s.product_name) ~ 'стальной\s+радиатор\s+(200|300|500)//(11|22)\*\d{4}'
      AND POSITION('1,2' IN LOWER(s.product_name)) > 0
      AND LOWER(s.product_name) !~ 'ral|цвет|колор|color|colour|дизайн|коричнев|черн|чёрн|бел(ый|ая|ое)|графит|антрацит|сер(ый|ая|ое)|n\d{4,}|abm|абм|сервис|ruterm|orso|sanline|proexpert|\bvcr\b|\bvcu\b'
    GROUP BY
        s.product_id_hex,
        s.product_code,
        s.product_name
),

stock AS (
    SELECT
        product_code,
        product_name,
        stock_qty,
        stock_period,
        as_of_date
    FROM public.stock_south_warehouse_agg
    WHERE LOWER(product_name) ~ 'стальной\s+радиатор\s+(200|300|500)//(11|22)\*\d{4}'
      AND POSITION('1,2' IN LOWER(product_name)) > 0
      AND LOWER(product_name) !~ 'ral|цвет|колор|color|colour|дизайн|коричнев|черн|чёрн|бел(ый|ая|ое)|графит|антрацит|сер(ый|ая|ое)|n\d{4,}|abm|абм|сервис|ruterm|orso|sanline|proexpert|\bvcr\b|\bvcu\b'
),

base AS (
    SELECT
        COALESCE(rs.product_id_hex, st.product_code::text) AS product_id_hex,
        COALESCE(rs.product_code, st.product_code) AS product_code,
        COALESCE(rs.product_name, st.product_name) AS product_name,

        COALESCE(st.stock_qty, 0) AS stock_qty,

        COALESCE(rs.radiator_qty_jan_2026, 0) AS radiator_qty_jan_2026,
        COALESCE(rs.radiator_qty_feb_2026, 0) AS radiator_qty_feb_2026,
        COALESCE(rs.radiator_qty_mar_2026, 0) AS radiator_qty_mar_2026,
        COALESCE(rs.radiator_qty_apr_2026, 0) AS radiator_qty_apr_2026,

        st.stock_period,
        st.as_of_date

    FROM radiator_sales_monthly rs
    FULL OUTER JOIN stock st
        ON st.product_code = rs.product_code
),

demand AS (
    SELECT
        *,

        (
            CASE WHEN radiator_qty_jan_2026 > 0 THEN 1 ELSE 0 END
          + CASE WHEN radiator_qty_feb_2026 > 0 THEN 1 ELSE 0 END
          + CASE WHEN radiator_qty_mar_2026 > 0 THEN 1 ELSE 0 END
        ) AS months_with_data,

        ROUND(
            (
                radiator_qty_jan_2026
              + radiator_qty_feb_2026
              + radiator_qty_mar_2026
            )
            / NULLIF(
                (
                    CASE WHEN radiator_qty_jan_2026 > 0 THEN 1 ELSE 0 END
                  + CASE WHEN radiator_qty_feb_2026 > 0 THEN 1 ELSE 0 END
                  + CASE WHEN radiator_qty_mar_2026 > 0 THEN 1 ELSE 0 END
                ),
                0
            ),
            2
        ) AS radiator_monthly_demand

    FROM base
),

abc_ranked AS (
    SELECT
        d.*,
        GREATEST(
            COALESCE(d.radiator_qty_jan_2026, 0)
          + COALESCE(d.radiator_qty_feb_2026, 0)
          + COALESCE(d.radiator_qty_mar_2026, 0),
            0
        ) AS abc_sales_qty,

        SUM(
            GREATEST(
                COALESCE(d.radiator_qty_jan_2026, 0)
              + COALESCE(d.radiator_qty_feb_2026, 0)
              + COALESCE(d.radiator_qty_mar_2026, 0),
                0
            )
        ) OVER () AS abc_total_sales_qty,

        SUM(
            GREATEST(
                COALESCE(d.radiator_qty_jan_2026, 0)
              + COALESCE(d.radiator_qty_feb_2026, 0)
              + COALESCE(d.radiator_qty_mar_2026, 0),
                0
            )
        ) OVER (
            ORDER BY
                GREATEST(
                    COALESCE(d.radiator_qty_jan_2026, 0)
                  + COALESCE(d.radiator_qty_feb_2026, 0)
                  + COALESCE(d.radiator_qty_mar_2026, 0),
                    0
                ) DESC,
                COALESCE(d.radiator_monthly_demand, 0) DESC,
                d.product_name
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS abc_cumulative_sales_qty

    FROM demand d
),

classified AS (
    SELECT
        *,
        CASE
            WHEN abc_total_sales_qty <= 0 THEN 'C'
            WHEN ((abc_cumulative_sales_qty - abc_sales_qty) / NULLIF(abc_total_sales_qty, 0)) < 0.60 THEN 'A'
            WHEN ((abc_cumulative_sales_qty - abc_sales_qty) / NULLIF(abc_total_sales_qty, 0)) < 0.90 THEN 'B'
            ELSE 'C'
        END AS radiator_abc_class
    FROM abc_ranked
),

final AS (
    SELECT
        *,

        CASE
            WHEN radiator_abc_class = 'A' THEN 1.0
            WHEN radiator_abc_class = 'B' THEN 0.7
            ELSE 0.5
        END AS radiator_coverage,

        CASE
            WHEN radiator_abc_class = 'A' THEN 3.0
            WHEN radiator_abc_class = 'B' THEN 2.0
            ELSE 1.0
        END AS radiator_planning_months,

        ROUND(
            COALESCE(radiator_monthly_demand, 0) *
            CASE
                WHEN radiator_abc_class = 'A' THEN 1.0
                WHEN radiator_abc_class = 'B' THEN 0.7
                ELSE 0.5
            END *
            CASE
                WHEN radiator_abc_class = 'A' THEN 3.0
                WHEN radiator_abc_class = 'B' THEN 2.0
                ELSE 1.0
            END,
            2
        ) AS radiator_target_stock_qty

    FROM classified
)

SELECT
    product_id_hex,
    product_code,
    product_name,

    radiator_abc_class,

    stock_qty,
    stock_qty AS free_stock_qty,

    radiator_qty_jan_2026,
    radiator_qty_feb_2026,
    radiator_qty_mar_2026,
    radiator_qty_apr_2026,

    months_with_data,
    COALESCE(radiator_monthly_demand, 0) AS radiator_monthly_demand,

    radiator_coverage,
    radiator_planning_months,
    radiator_target_stock_qty,

    GREATEST(
        CEIL(
            GREATEST(radiator_target_stock_qty - stock_qty, 0)
            / 16.0
        ) * 16,
        0
    ) AS recommended_order_qty,

    GREATEST(
        CEIL(
            GREATEST(radiator_target_stock_qty - stock_qty, 0)
            / 16.0
        ) * 16,
        0
    ) AS recommended_order_qty_display,

    stock_period,
    as_of_date

FROM final
WHERE product_name IS NOT NULL
ORDER BY
    radiator_abc_class,
    recommended_order_qty DESC,
    radiator_monthly_demand DESC;
