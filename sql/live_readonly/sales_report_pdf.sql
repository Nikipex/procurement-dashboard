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
),
clients_krasnodar AS (
    SELECT
        _idrref AS client_id,
        encode(_idrref, 'hex') AS client_id_hex,
        encode(_parentidrref, 'hex') AS parent_id_hex,
        _description::text AS client_name,
        level
    FROM krasnodar_tree
    WHERE level >= 2
)
SELECT
    d._date_time::date AS sale_date,
    d._number::text AS document_number,

    encode(COALESCE(n1._idrref, n2._idrref, n3._idrref, n4._idrref), 'hex') AS product_id_hex,
    COALESCE(n1._code::text, n2._code::text, n3._code::text, n4._code::text) AS product_code,
    COALESCE(n1._description::text, n2._description::text, n3._description::text, n4._description::text) AS product_name,

    encode(c._idrref, 'hex') AS client_id_hex,
    c._description::text AS client_name,

    vt._fld6044 AS qty,
    vt._fld6052 AS revenue,
    vt._fld6053 AS cost,
    vt._fld6055 AS profit,
    vt._fld6052 / NULLIF(vt._fld6044, 0) AS price_per_unit,
    vt._fld6055 / NULLIF(vt._fld6052, 0) * 100 AS margin_percent
FROM public._document240 d
JOIN public._document240_vt6039 vt
    ON vt._document240_idrref = d._idrref

LEFT JOIN public._reference80 n1 ON n1._idrref = vt._fld6041rref
LEFT JOIN public._reference80 n2 ON n2._idrref = vt._fld6042rref
LEFT JOIN public._reference80 n3 ON n3._idrref = vt._fld6043rref
LEFT JOIN public._reference80 n4 ON n4._idrref = vt._fld6047rref

JOIN clients_krasnodar ck
    ON ck.client_id = d._fld6015rref

JOIN public._reference71 c
    ON c._idrref = ck.client_id

WHERE d._posted = true
  AND vt._fld6044 <> 0
  AND d._date_time::date >= CURRENT_DATE - INTERVAL '3 months'
  AND d._date_time::date <= CURRENT_DATE
