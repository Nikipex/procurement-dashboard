DROP VIEW IF EXISTS public.sales_south_krasnodar;

CREATE VIEW public.sales_south_krasnodar AS
SELECT
    a._period AS sale_period,
    a._period::date AS sale_date,

    n._code AS product_code,
    n._description AS product_name,
    a._fld9301rref AS product_id,
    encode(a._fld9301rref, 'hex') AS product_id_hex,

    a._fld9300rref AS warehouse_id,
    encode(a._fld9300rref, 'hex') AS warehouse_id_hex,

    d._fld6015rref AS client_id,
    encode(d._fld6015rref, 'hex') AS client_id_hex,
    c._description AS client_name,

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
      FROM public.clients_krasnodar
  )
  AND a._fld9305 <> 0;