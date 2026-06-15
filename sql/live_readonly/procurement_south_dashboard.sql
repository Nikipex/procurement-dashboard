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
sales_south_krasnodar_60d AS (
WITH sales_60d AS (
    SELECT
        product_id_hex,
        product_code,
        product_name,

        SUM(qty) AS sales_qty_60d,

        COUNT(DISTINCT sale_date) AS sales_days,

        MIN(sale_date) AS first_sale_date,
        MAX(sale_date) AS last_sale_date

    FROM sales_south_krasnodar

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
ORDER BY sales_qty_60d DESC
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
        ) AS free_stock_qty,
        COALESCE(t.stock_amount, 0) AS stock_amount
    FROM total_stock t
    FULL OUTER JOIN reserved_stock r
        ON r.product_id = t.product_id
)
SELECT
    st.stock_period,
    n._code::text AS product_code,
    n._description::text AS product_name,
    st.free_stock_qty AS stock_qty,
    st.total_stock_qty,
    st.reserved_stock_qty,
    st.stock_amount
FROM south_stock st
JOIN public._reference80 n
    ON st.product_id = n._idrref
WHERE st.free_stock_qty <> 0
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
),
procurement_south_mvp AS (
WITH priority_products AS (
    SELECT
        NULL::text AS product_id_hex,
        product_code,
        MAX(product_name::text) AS product_name,
        SUM(qty) AS sales_qty_60d,
        ROUND(SUM(qty) / 60.0, 2) AS avg_daily_sales,
        MIN(sale_date) AS first_sale_date,
        MAX(sale_date) AS last_sale_date
    FROM sales_south_krasnodar
    WHERE product_code IN (
        'ОФ000006259'
    )
      AND sale_date >= (
          SELECT MAX(sale_date) - INTERVAL '120 days'
          FROM sales_south_krasnodar
      )
    GROUP BY product_code
),

base AS (
    SELECT
        COALESCE(s.product_id_hex, st.product_code::text, pp.product_id_hex, pp.product_code::text) AS product_id_hex,
        COALESCE(s.product_code::text, st.product_code::text, pp.product_code::text) AS product_code,
        COALESCE(s.product_name::text, st.product_name::text, pp.product_name::text) AS product_name,

        CASE
            WHEN lower(COALESCE(s.product_name::text, st.product_name::text, pp.product_name::text, '')) LIKE '%%baxi%%'
             AND lower(COALESCE(s.product_name::text, st.product_name::text, pp.product_name::text, '')) LIKE '%%eco%%'
             AND lower(COALESCE(s.product_name::text, st.product_name::text, pp.product_name::text, '')) LIKE '%%4s%%'
             AND lower(COALESCE(s.product_name::text, st.product_name::text, pp.product_name::text, '')) LIKE '%%24%%'
             AND lower(COALESCE(s.product_name::text, st.product_name::text, pp.product_name::text, '')) NOT LIKE '%%1.24%%'
            THEN 0
            ELSE COALESCE(st.stock_qty, 0)
        END AS stock_qty,
        COALESCE(s.sales_qty_60d, pp.sales_qty_60d, 0) AS sales_qty_60d,
        COALESCE(s.avg_daily_sales, pp.avg_daily_sales, 0) AS avg_daily_sales,

        st.stock_period,
        st.as_of_date,

        COALESCE(s.first_sale_date, pp.first_sale_date) AS first_sale_date,
        COALESCE(s.last_sale_date, pp.last_sale_date) AS last_sale_date
    FROM sales_south_krasnodar_60d s
    FULL OUTER JOIN stock_south_warehouse_agg st
        ON st.product_code = s.product_code
    FULL OUTER JOIN priority_products pp
        ON pp.product_code::text = COALESCE(s.product_code::text, st.product_code::text)
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
ORDER BY recommended_order_qty DESC, sales_qty_60d DESC
),
camino_products AS (
    SELECT
        _code::text AS product_code
    FROM public._reference80
    WHERE encode(_parentidrref, 'hex') = 'bdcc6a640748b82d11efde156fb54c80'
),

classified AS (
    SELECT
        p.*,

        lower(replace(coalesce(p.product_name::text, ''), 'ё', 'е')) AS product_name_norm,
        regexp_replace(
            lower(replace(coalesce(p.product_name::text, ''), 'ё', 'е')),
            '[^a-zа-я0-9]+',
            '',
            'g'
        ) AS product_name_key,

        CASE
            WHEN EXISTS (
                SELECT 1
                FROM camino_products cp
                WHERE cp.product_code::text = p.product_code::text
            ) THEN 'коаксиалы'
            WHEN lower(replace(coalesce(p.product_name::text, ''), 'ё', 'е')) ILIKE '%%стальной радиатор%%'
              OR lower(replace(coalesce(p.product_name::text, ''), 'ё', 'е')) ILIKE '%%радиатор%%'
                THEN 'радиаторы'

            WHEN lower(replace(coalesce(p.product_name::text, ''), 'ё', 'е')) ILIKE '%%baxi%%'
              OR lower(replace(coalesce(p.product_name::text, ''), 'ё', 'е')) ILIKE '%%navien%%'
              OR lower(replace(coalesce(p.product_name::text, ''), 'ё', 'е')) ILIKE '%%fondital%%'
              OR lower(replace(coalesce(p.product_name::text, ''), 'ё', 'е')) ILIKE '%%котел%%'
                THEN 'котлы'

            WHEN lower(replace(coalesce(p.product_name::text, ''), 'ё', 'е')) ILIKE '%%водонагреватель%%'
              OR lower(replace(coalesce(p.product_name::text, ''), 'ё', 'е')) ILIKE '%%бойлер%%'
              OR lower(replace(coalesce(p.product_name::text, ''), 'ё', 'е')) ILIKE '%%ariston%%'
              OR ((lower(replace(coalesce(p.product_name::text, ''), 'ё', 'е')) ILIKE '%%bugatti%%'
                   OR lower(replace(coalesce(p.product_name::text, ''), 'ё', 'е')) ILIKE '%%federica%%')
                  AND (lower(replace(coalesce(p.product_name::text, ''), 'ё', 'е')) ILIKE '%%водонагреватель%%'
                       OR lower(replace(coalesce(p.product_name::text, ''), 'ё', 'е')) ILIKE '%%бойлер%%'))
                THEN 'бойлеры'

            WHEN lower(replace(coalesce(p.product_name::text, ''), 'ё', 'е')) ILIKE '%%колонк%%'
              OR lower(replace(coalesce(p.product_name::text, ''), 'ё', 'е')) ILIKE '%%warmix%%'
              OR lower(replace(coalesce(p.product_name::text, ''), 'ё', 'е')) ILIKE '%%genberg%%'
              OR lower(replace(coalesce(p.product_name::text, ''), 'ё', 'е')) ILIKE '%%inflame%%'
                THEN 'газовые колонки'

            WHEN lower(replace(coalesce(p.product_name::text, ''), 'ё', 'е')) ILIKE '%%teplocom%%'
              OR lower(replace(coalesce(p.product_name::text, ''), 'ё', 'е')) ILIKE '%%solpi%%'
              OR lower(replace(coalesce(p.product_name::text, ''), 'ё', 'е')) ILIKE '%%стабилизатор%%'
                THEN 'стабилизаторы'

            WHEN lower(replace(coalesce(p.product_name::text, ''), 'ё', 'е')) ILIKE '%%unipump%%'
              OR lower(replace(coalesce(p.product_name::text, ''), 'ё', 'е')) ILIKE '%%насос%%'
                THEN 'насосы'

            ELSE 'прочее'
        END AS product_group

    FROM procurement_south_mvp p
),

flags AS (
    SELECT
        c.*,

        CASE
            -- Стабилизаторы — расширенный whitelist по Solpi / Teplocom
            -- Важный ходовой Solpi-M TSD-500VA добиваем по коду товара из 1С: ОФ000006259
            WHEN product_code = 'ОФ000006259' THEN true
            WHEN product_name_norm LIKE '%%solpi-m tsd-500va%%' THEN true
            WHEN product_name_norm LIKE '%%solpi-m%%' AND product_name_norm LIKE '%%tsd-500%%' THEN true
            WHEN product_name_norm LIKE '%%solpi%%' AND product_name_norm LIKE '%%tsd%%' AND product_name_norm LIKE '%%500%%' THEN true
            WHEN product_name_key LIKE '%%solpimtsd500va%%' THEN true
            WHEN product_name_key LIKE '%%solpimtsd500%%' THEN true
            WHEN product_name_norm LIKE '%%solpi%%' THEN true
            WHEN product_name_key LIKE '%%solpi%%' THEN true
            WHEN product_name_key LIKE '%%tsd500%%' THEN true
            WHEN product_name_norm LIKE '%%teplocom%%' AND product_name_norm LIKE '%%222/500%%' THEN true
            WHEN product_name_norm LIKE '%%teplocom%%' AND product_name_norm LIKE '%%555%%' THEN true
            WHEN product_name_key LIKE '%%teplocomst222500%%' THEN true
            WHEN product_name_key LIKE '%%st222500%%' THEN true
            WHEN product_name_key LIKE '%%teplocomst222500и%%' THEN true
            WHEN product_name_key LIKE '%%teplocomst555%%' THEN true
            WHEN product_name_key LIKE '%%st555%%' THEN true
            WHEN product_name_key LIKE '%%teplocomst555и%%' THEN true

            -- Газовые колонки
            WHEN product_name_norm ~ 'ballu.*warmix.*gwh-10' THEN true
            WHEN product_name_norm ~ 'genberg' THEN true
            WHEN product_name_norm ~ 'inflame' THEN true

            -- Котлы — exact whitelist
            WHEN product_name_norm ~ '^котел baxi eco\s*nova\s*10f$' THEN true
            WHEN product_name_norm ~ '^котел baxi eco\s*nova\s*14f$' THEN true
            WHEN product_name_norm ~ '^котел baxi eco\s*nova\s*18f$' THEN true
            WHEN product_name_norm ~ '^котел baxi eco\s*nova\s*24f$' THEN true
            WHEN product_name_norm ~ '^котел baxi eco\s*4s\s*10\s*f$' THEN true
            WHEN product_name_norm ~ '^котел baxi eco\s*4s\s*18\s*f$' THEN true
            WHEN product_name_norm ~ '^котел baxi eco\s*4s\s*24$' THEN true
            WHEN product_name_norm ~ '^котел baxi eco\s*4s\s*24\s*f$' THEN true
            WHEN product_name_norm ~ '^котел baxi eco\s*four\s*24\s*f$' THEN true
            WHEN product_name_norm ~ '^navien deluxe c coaxial 13k\s*2х контур\.?$' THEN true
            WHEN product_name_norm ~ '^navien deluxe c coaxial 16k\s*2х контур\.?$' THEN true
            WHEN product_name_norm ~ '^navien deluxe c coaxial 24k\s*2х контур\.?$' THEN true
            WHEN product_name_norm ~ '^navien deluxe c coaxial 30k\s*2х контур\.?$' THEN true
            WHEN product_name_norm ~ '^navien deluxe c coaxial 35k\s*2х контур\.?$' THEN true
            WHEN product_name_norm ~ '^navien deluxe c coaxial 40k\s*2х контур\.?$' THEN true
            WHEN product_name_norm ~ '^navien deluxe one 24k\s*1 контур\.?$' THEN true
            WHEN product_name_norm ~ '^navien deluxe one 30k\s*1 контур\.?$' THEN true
            WHEN product_name_norm ~ '^navien deluxe e coaxial 10k\s*2х контур\.?$' THEN true
            WHEN product_name_norm ~ '^navien deluxe e coaxial 13k\s*2х контур\.?$' THEN true
            WHEN product_name_norm ~ '^navien deluxe e coaxial 16k\s*2х контур\.?$' THEN true
            WHEN product_name_norm ~ '^navien deluxe e coaxial 24k\s*2х контур\.?$' THEN true
            WHEN product_name_norm ~ '^navien heatatmo ngb 150 24 a$' THEN true

            -- Fondital / Federica Bugatti — котлы, считаем по схеме BAXI/Navien
            WHEN product_name_norm LIKE '%%fondital%%' THEN true

            -- Federica/Bugatti: котлы только если явно котел/газовый/varme
            WHEN (product_name_norm LIKE '%%federica%%' OR product_name_norm LIKE '%%bugatti%%')
              AND (
                    product_name_norm LIKE '%%котел%%'
                 OR product_name_norm LIKE '%%котёл%%'
                 OR product_name_norm LIKE '%%газовый%%'
                 OR product_name_norm LIKE '%%varme%%'
              )
            THEN true

            -- Federica/Bugatti: бойлеры/водонагреватели в блок бойлеров
            WHEN (product_name_norm LIKE '%%federica%%' OR product_name_norm LIKE '%%bugatti%%')
              AND (
                    product_name_norm LIKE '%%водонагреватель%%'
                 OR product_name_norm LIKE '%%бойлер%%'
              )
            THEN true

            -- Бойлеры — нужные позиции, без Inox / FA / Superlux
            WHEN product_name_norm ~ '^водонагреватель ariston abs vls pro r 50$' THEN true
            WHEN product_name_norm ~ '^водонагреватель ariston abs vls pro r 80$' THEN true
            WHEN product_name_norm ~ '^водонагреватель ariston abs vls pro r 100$' THEN true
            WHEN product_name_norm ~ '^водонагреватель ariston abse vls pro pw 50$' THEN true
            WHEN product_name_norm ~ '^водонагреватель ariston abse vls pro pw 100$' THEN true
            WHEN product_name_norm ~ '^водонагреватель ariston nts 30 v 1\.5k \(su\) slim$' THEN true
            WHEN product_name_norm ~ '^водонагреватель ariston nts 50 v 1\.5k \(su\)$' THEN true
            WHEN product_name_norm ~ '^водонагреватель ariston nts 80 v 1\.5k \(su\)$' THEN true
            WHEN product_name_norm ~ '^водонагреватель ariston nts 100 v 1\.5k \(su\)$' THEN true
            WHEN product_name_norm ~ '^водонагреватель ariston nts fais v 1\.5k$' THEN true

            -- Насосы — whitelist по размеру модели, без привязки к UPC/CP
            WHEN product_name_norm LIKE '%%unipump%%'
              AND product_name_norm LIKE '%%насос%%'
              AND product_name_norm LIKE '%%циркуляц%%'
              AND (
                    (product_name_norm LIKE '%%25-60%%' AND product_name_norm LIKE '%%180%%')
                 OR (product_name_norm LIKE '%%25-60%%' AND product_name_norm LIKE '%%130%%')
                 OR (product_name_norm LIKE '%%25-40%%' AND product_name_norm LIKE '%%180%%')
                 OR (product_name_norm LIKE '%%25-40%%' AND product_name_norm LIKE '%%130%%')
                 OR (product_name_norm LIKE '%%25-80%%' AND product_name_norm LIKE '%%180%%')
                 OR (product_name_norm LIKE '%%32-60%%' AND product_name_norm LIKE '%%180%%')
                 OR (product_name_norm LIKE '%%32-80%%' AND product_name_norm LIKE '%%180%%')
              )
            THEN true

            -- Коаксиалы — всё из папки CAMINO
            WHEN product_group = 'коаксиалы' THEN true

            -- Радиаторы не тащим сюда: для них отдельная витрина radiator_procurement_mvp
            ELSE false
        END AS priority_flag,

        CASE
            -- CAMINO коаксиалы не считаем спецзаказом, иначе их режет правило "дымоход"
            WHEN product_group = 'коаксиалы' THEN false
            WHEN product_name_norm ~ 'конденсац' THEN true
            WHEN product_name_norm ~ '80/125.*конденсац' THEN true
            WHEN product_name_norm ~ 'нержав' THEN true
            WHEN product_name_norm ~ 'ремонт' THEN true
            WHEN product_name_norm ~ 'дымоход' THEN true
            WHEN product_name_norm ~ 'переходн' THEN true
            WHEN product_name_norm ~ 'форсунки' THEN true
            WHEN product_name_norm ~ 'vivat' THEN true
            WHEN product_name_norm ~ 'viessma' THEN true
            WHEN product_name_norm ~ 'ariston,?vaillant' THEN true
            WHEN product_name_norm ~ 'baxi \(кроме' THEN true
            WHEN product_name_norm ~ 'для всех моделей' THEN true
            WHEN product_name_norm ~ 'блок управления' THEN true
            WHEN product_name_norm ~ 'насосная станция' THEN true
            WHEN product_name_norm ~ 'частотн' THEN true
            WHEN product_name_norm ~ 'многоступ' THEN true
            WHEN product_name_norm ~ 'турбипресс' THEN true
            WHEN product_name_norm ~ 'тискотрон' THEN true
            ELSE false
        END AS special_order_flag

    FROM classified c
),

final AS (
    SELECT
        *,
        CASE
            WHEN product_group = 'радиаторы' THEN false
            WHEN priority_flag = true AND special_order_flag = false THEN true
            ELSE false
        END AS show_in_dashboard,

        CASE
            WHEN priority_flag = true AND stock_status IN ('critical', 'out_of_stock') THEN 1
            WHEN priority_flag = true AND stock_status = 'low' THEN 2
            WHEN priority_flag = true THEN 3
            ELSE 99
        END AS procurement_priority
    FROM flags
),

abc_ranked AS (
    SELECT
        f.*,

        GREATEST(COALESCE(f.sales_qty_60d, 0), 0) AS abc_sales_qty,

        SUM(GREATEST(COALESCE(f.sales_qty_60d, 0), 0))
            OVER (PARTITION BY f.product_group) AS abc_group_sales_qty,

        SUM(GREATEST(COALESCE(f.sales_qty_60d, 0), 0))
            OVER (
                PARTITION BY f.product_group
                ORDER BY
                    GREATEST(COALESCE(f.sales_qty_60d, 0), 0) DESC,
                    COALESCE(f.recommended_order_qty, 0) DESC,
                    f.product_name
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ) AS abc_cumulative_sales_qty

    FROM final f
    WHERE f.show_in_dashboard = true
),

abc_classified AS (
    SELECT
        *,
        CASE
            -- Business A whitelist: these are strategic fast-moving SKUs even if the rolling window is noisy.
            WHEN product_group = 'котлы'
                 AND product_name_norm LIKE '%%baxi%%'
                 AND product_name_norm LIKE '%%eco%%'
                 AND product_name_norm LIKE '%%4s%%'
                 AND product_name_norm LIKE '%%24%%'
                THEN 'A'
            WHEN product_group = 'котлы'
                 AND product_name_norm LIKE '%%baxi%%'
                 AND product_name_norm LIKE '%%eco%%'
                 AND product_name_norm LIKE '%%nova%%'
                 AND product_name_norm LIKE '%%24%%'
                THEN 'A'
            WHEN product_group = 'котлы'
                 AND product_name_norm LIKE '%%baxi%%'
                 AND product_name_norm LIKE '%%eco%%'
                 AND product_name_norm LIKE '%%four%%'
                 AND product_name_norm LIKE '%%24%%'
                THEN 'A'
            WHEN product_group = 'котлы'
                 AND product_name_norm LIKE '%%navien%%'
                 AND product_name_norm LIKE '%%deluxe%%'
                 AND product_name_norm LIKE '%%24%%'
                THEN 'A'

            WHEN product_group = 'котлы'
                 AND (
                     product_name_norm LIKE '%%fondital%%'
                     OR product_name_norm LIKE '%%federica%%'
                     OR product_name_norm LIKE '%%bugatti%%'
                 )
                 AND product_name_norm LIKE '%%24%%'
                THEN 'A'

            -- Regular ABC 60/30/10 by sales quantity inside each product group.
            -- Stabilizers intentionally use this branch too; no forced A whitelist here.
            WHEN abc_group_sales_qty <= 0 THEN 'C'
            WHEN ((abc_cumulative_sales_qty - abc_sales_qty) / NULLIF(abc_group_sales_qty, 0)) < 0.60 THEN 'A'
            WHEN ((abc_cumulative_sales_qty - abc_sales_qty) / NULLIF(abc_group_sales_qty, 0)) < 0.90 THEN 'B'
            ELSE 'C'
        END AS abc_class
    FROM abc_ranked
),

deduplicated AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY
                CASE
                    -- Unipump has duplicate rows with different casing/source spelling.
                    -- Deduplicate only Unipump pumps by normalized name.
                    WHEN product_group = 'насосы' AND product_name_norm LIKE '%%unipump%%'
                        THEN regexp_replace(
                            regexp_replace(product_name_norm, '\\b(upc|cp)\\b', '', 'g'),
                            '\\s+',
                            ' ',
                            'g'
                        )
                    ELSE product_group || '|' || COALESCE(product_code, '') || '|' || product_name_norm
                END
            ORDER BY
                COALESCE(sales_qty_60d, 0) DESC,
                COALESCE(avg_daily_sales, 0) DESC,
                COALESCE(recommended_order_qty, 0) DESC,
                COALESCE(stock_qty, 0) DESC,
                product_name
        ) AS dashboard_row_num
    FROM abc_classified
)

SELECT
    product_id_hex,
    product_code,
    product_name,
    product_group,
    abc_class,
    priority_flag,
    special_order_flag,
    show_in_dashboard,
    procurement_priority,
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
FROM deduplicated
WHERE dashboard_row_num = 1
ORDER BY procurement_priority, abc_class, recommended_order_qty DESC, sales_qty_60d DESC
