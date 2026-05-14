CREATE OR REPLACE VIEW public.sales_south_warehouse AS
SELECT
    a._period AS sale_period,

    n._code AS product_code,
    n._description AS product_name,

    a._fld9301rref AS product_id,
    a._fld9300rref AS warehouse_id,

    a._fld9305 AS qty

FROM public._accumrg9299 a
JOIN public._reference80 n
    ON a._fld9301rref = n._idrref
WHERE a._fld9300rref = decode('83ee60f67771497111e9dbb16ec97a48','hex')
  AND a._active = true
  AND a._fld9305 <> 0;