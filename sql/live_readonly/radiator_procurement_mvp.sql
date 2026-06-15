WITH
clients_krasnodar AS (
WITH RECURSIVE krasnodar_tree AS (
    SELECT
        _idrref,
        _parentidrref,
        _description,
        0 AS level
    FROM public._reference71
    WHERE _idrref = decode('bae66a640748b82d11eda92c459f243c', 'hex')

    UNION ALL

    SELECT
        c._idrref,
        c._parentidrref,
        c._description,
        t.level + 1
    FROM public._reference71 c
    JOIN krasnodar_tree t
        ON c._parentidrref = t._idrref
)
SELECT
    _idrref AS client_id,
    encode(_idrref, 'hex') AS client_id_hex,
    encode(_parentidrref, 'hex') AS parent_id_hex,
    _description AS client_name,
    level
FROM krasnodar_tree
WHERE level >= 2
),
sales_south_krasnodar AS (
SELECT
    a._period AS sale_period,
    a._period::date AS sale_date,

    n._code::text AS product_code,
    n._description::text AS product_name,
    a._fld9301rref AS product_id,
    encode(a._fld9301rref, 'hex') AS product_id_hex,

    a._fld9300rref AS warehouse_id,
    encode(a._fld9300rref, 'hex') AS warehouse_id_hex,

    d._fld6015rref AS client_id,
    encode(d._fld6015rref, 'hex') AS client_id_hex,
    c._description::text AS client_name,

    a._fld9305 AS qty

FROM public._accumrg9299 a

JOIN public._document240 d
    ON a._recorderrref = d._idrref

JOIN public._reference80 n
    ON n._idrref = a._fld9301rref

JOIN public._reference71 c
    ON c._idrref = d._fld6015rref

WHERE a._recordertref = decode('000000f0', 'hex')
  AND d._posted = true
  AND a._active = true
  AND a._fld9300rref = decode('83ee60f67771497111e9dbb16ec97a48', 'hex')
  AND d._fld6015rref IN (
      SELECT client_id
      FROM clients_krasnodar
  )
  AND a._fld9305 <> 0
),
stock_south_warehouse AS (
WITH total_stock AS (
    SELECT
        s._period AS stock_period,
        s._fld9098rref AS product_id,
        SUM(s._fld9106) AS total_stock_qty,
        SUM(s._fld9107) AS stock_amount
    FROM public._accumrgt9117 s
    WHERE s._fld9099rref = decode('83ee60f67771497111e9dbb16ec97a48','hex')
      AND s._period = TIMESTAMP '3999-11-01 00:00:00'
    GROUP BY s._period, s._fld9098rref
),
reserved_stock AS (
    SELECT
        r._fld9301rref AS product_id,
        SUM(GREATEST(COALESCE(r._fld9305, 0), 0)) AS reserved_stock_qty
    FROM public._accumrgt9308 r
    WHERE r._fld9300rref = decode('83ee60f67771497111e9dbb16ec97a48','hex')
      AND r._period = TIMESTAMP '3999-11-01 00:00:00'
    GROUP BY r._fld9301rref
),
south_stock AS (
    SELECT
        COALESCE(t.product_id, r.product_id) AS product_id,
        COALESCE(t.stock_period, TIMESTAMP '3999-11-01 00:00:00') AS stock_period,
        COALESCE(t.total_stock_qty, 0) AS total_stock_qty,
        COALESCE(r.reserved_stock_qty, 0) AS reserved_stock_qty,
        GREATEST(
            COALESCE(t.total_stock_qty, 0) - COALESCE(r.reserved_stock_qty, 0),
            0
        ) AS stock_qty,
        COALESCE(t.stock_amount, 0) AS stock_amount
    FROM total_stock t
    FULL OUTER JOIN reserved_stock r
        ON r.product_id = t.product_id
)
SELECT
    st.stock_period,
    n._code::text AS product_code,
    n._description::text AS product_name,
    st.stock_qty,
    st.stock_amount
FROM south_stock st
JOIN public._reference80 n
    ON st.product_id = n._idrref
WHERE st.stock_qty <> 0
),
stock_south_warehouse_agg AS (
WITH current_stock AS (
    -- В 1С итоговые таблицы остатков используют технический период 3999-11-01
    -- как актуальный срез состояния регистра.
    -- Поэтому для текущего свободного остатка берём именно этот период,
    -- а не MAX(stock_period) по календарным датам.
    SELECT
        product_code,
        product_name,
        stock_qty,
        stock_amount,
        stock_period
    FROM stock_south_warehouse
    WHERE stock_period = TIMESTAMP '3999-11-01 00:00:00'
      AND stock_qty <> 0
),
base AS (
    SELECT
        product_code,
        product_name,
        stock_qty,
        stock_amount,
        stock_period,

        -- Мягкая нормализация: чистим пробелы и регистр,
        -- но НЕ удаляем (1,2), RUTERM, VK, universal и другие варианты исполнения,
        -- потому что это разные реальные позиции в отчёте 1С.
        TRIM(
            REGEXP_REPLACE(
                LOWER(product_name::text),
                '\s+',
                ' ',
                'g'
            )
        ) AS normalized_name
    FROM current_stock
)
SELECT
    MIN(product_code::text) AS product_code,
    normalized_name AS product_name,
    SUM(stock_qty) AS stock_qty,
    SUM(stock_amount) AS stock_amount,
    MAX(stock_period) AS stock_period,
    (SELECT MAX(sale_period)::date FROM sales_south_krasnodar) AS as_of_date
FROM base
GROUP BY normalized_name
HAVING SUM(stock_qty) <> 0
)
,
radiator_sales_monthly AS (
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
        ) AS radiator_qty_apr_2026,

        SUM(s.qty) FILTER (
            WHERE s.sale_date >= DATE '2026-05-01'
              AND s.sale_date < DATE '2026-06-01'
        ) AS radiator_qty_may_2026,

        SUM(s.qty) FILTER (
            WHERE s.sale_date >= DATE '2026-06-01'
              AND s.sale_date < DATE '2026-07-01'
        ) AS radiator_qty_jun_2026

    FROM sales_south_krasnodar s
    WHERE LOWER(s.product_name::text) ~ 'стальной\s+радиатор\s+(200|300|500)//(11|22)\*\d{4}'
      AND POSITION('1,2' IN LOWER(s.product_name::text)) > 0
      AND LOWER(s.product_name::text) !~ 'ral|цвет|колор|color|colour|дизайн|коричнев|черн|чёрн|бел(ый|ая|ое)|графит|антрацит|сер(ый|ая|ое)|n\d{4,}|abm|абм|сервис|ruterm|orso|sanline|proexpert|\bvcr\b|\bvcu\b'
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
    FROM stock_south_warehouse_agg
    WHERE LOWER(product_name::text) ~ 'стальной\s+радиатор\s+(200|300|500)//(11|22)\*\d{4}'
      AND POSITION('1,2' IN LOWER(product_name::text)) > 0
      AND LOWER(product_name::text) !~ 'ral|цвет|колор|color|colour|дизайн|коричнев|черн|чёрн|бел(ый|ая|ое)|графит|антрацит|сер(ый|ая|ое)|n\d{4,}|abm|абм|сервис|ruterm|orso|sanline|proexpert|\bvcr\b|\bvcu\b'
),

base AS (
    SELECT
        COALESCE(rs.product_id_hex, st.product_code::text) AS product_id_hex,
        COALESCE(rs.product_code::text, st.product_code::text) AS product_code,
        COALESCE(rs.product_name::text, st.product_name::text) AS product_name,

        COALESCE(st.stock_qty, 0) AS stock_qty,

        COALESCE(rs.radiator_qty_jan_2026, 0) AS radiator_qty_jan_2026,
        COALESCE(rs.radiator_qty_feb_2026, 0) AS radiator_qty_feb_2026,
        COALESCE(rs.radiator_qty_mar_2026, 0) AS radiator_qty_mar_2026,
        COALESCE(rs.radiator_qty_apr_2026, 0) AS radiator_qty_apr_2026,
        COALESCE(rs.radiator_qty_may_2026, 0) AS radiator_qty_may_2026,
        COALESCE(rs.radiator_qty_jun_2026, 0) AS radiator_qty_jun_2026,

        st.stock_period,
        st.as_of_date

    FROM radiator_sales_monthly rs
    FULL OUTER JOIN stock st
        ON st.product_code::text = rs.product_code::text
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
    radiator_qty_may_2026,
    radiator_qty_jun_2026,

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
    radiator_monthly_demand DESC
