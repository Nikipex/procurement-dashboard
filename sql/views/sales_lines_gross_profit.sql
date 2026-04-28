SELECT
  d._number AS document_number,
  d._date_time AS document_created_at,
  d._posted AS is_posted,

  n._code AS product_code,
  n._description AS product_name,

  t._fld6044 AS qty,
  t._fld6052 AS revenue,
  t._fld6053 AS cost_or_profit_amount,
  t._fld6055 AS extra_amount,

  ROUND(t._fld6052 / NULLIF(t._fld6044, 0), 2) AS revenue_per_unit,
  ROUND(t._fld6053 / NULLIF(t._fld6044, 0), 2) AS cost_or_profit_per_unit,
  ROUND(t._fld6055 / NULLIF(t._fld6044, 0), 2) AS extra_per_unit

FROM public._document240 d
JOIN public._document240_vt6039 t
  ON d._idrref = t._document240_idrref
JOIN public._reference80 n
  ON t._fld6047rref = n._idrref
WHERE d._posted = true
  AND d._date_time >= CURRENT_DATE - INTERVAL '90 days'
ORDER BY d._date_time DESC;