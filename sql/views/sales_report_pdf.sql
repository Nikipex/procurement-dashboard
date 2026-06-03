DROP VIEW IF EXISTS public.sales_report_pdf CASCADE;

CREATE VIEW public.sales_report_pdf AS
SELECT
    d._date_time::date AS sale_date,
    d._number AS document_number,

    encode(COALESCE(n1._idrref, n2._idrref, n3._idrref, n4._idrref), 'hex') AS product_id_hex,
    COALESCE(n1._code, n2._code, n3._code, n4._code) AS product_code,
    COALESCE(n1._description, n2._description, n3._description, n4._description) AS product_name,

    encode(c._idrref, 'hex') AS client_id_hex,
    c._description AS client_name,

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

JOIN public.clients_krasnodar ck
    ON ck.client_id = d._fld6015rref

JOIN public._reference71 c
    ON c._idrref = ck.client_id

WHERE d._posted = true
  AND vt._fld6044 <> 0
  AND d._date_time::date >= CURRENT_DATE - INTERVAL '3 months'
  AND d._date_time::date <= CURRENT_DATE;
