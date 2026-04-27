SELECT
  d._number AS invoice_number,
  d._date_time AS invoice_created_at,
  d._posted AS is_posted,
  n._code AS product_code,
  n._description AS product_name,
  t._fld3143 AS qty,
  t._fld3154 AS unit_price,
  t._fld3151 AS line_amount
FROM public._document162 d
JOIN public._document162_vt3139 t
  ON d._idrref = t._document162_idrref
JOIN public._reference80 n
  ON t._fld3146rref = n._idrref
WHERE d._posted = true
  AND d._date_time >= CURRENT_DATE - INTERVAL '90 days'
ORDER BY d._date_time DESC
LIMIT 500;