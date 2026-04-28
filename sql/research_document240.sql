-- document240 research
-- hypothesis:
-- _document240 = накладные / отгрузки
-- _document240_vt6039 = строки накладных
-- _fld6047rref = товар -> _reference80._idrref
-- _fld6044 = количество

-- 1. Структура шапки document240
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = '_document240'
ORDER BY ordinal_position;

-- 2. Структура строк document240_vt6039
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = '_document240_vt6039'
ORDER BY ordinal_position;

-- 3. Проверка шапки документа
SELECT _number, _date_time, _posted
FROM public._document240
LIMIT 20;

-- 4. Поля-ссылки в строках
SELECT column_name
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = '_document240_vt6039'
  AND column_name LIKE '%rref'
ORDER BY ordinal_position;

-- 5. Проверка связи строк с номенклатурой
SELECT
  d._number,
  d._date_time,
  n._description AS product_name,
  t._fld6044 AS qty,
  t._fld6046,
  t._fld6048
FROM public._document240 d
JOIN public._document240_vt6039 t
  ON d._idrref = t._document240_idrref
JOIN public._reference80 n
  ON t._fld6047rref = n._idrref
WHERE d._posted = true
  AND d._date_time >= DATE '2026-01-20'
  AND d._date_time < DATE '2026-03-21'
  AND n._description ILIKE '%ECO four 24 F%'
LIMIT 50;

-- 6. Итог по Eco Four 24F из document240
SELECT
  n._description AS product_name,
  SUM(t._fld6044) AS qty,
  COUNT(DISTINCT d._number) AS document_count,
  COUNT(*) AS line_count
FROM public._document240 d
JOIN public._document240_vt6039 t
  ON d._idrref = t._document240_idrref
JOIN public._reference80 n
  ON t._fld6047rref = n._idrref
WHERE d._posted = true
  AND d._date_time >= DATE '2026-01-20'
  AND d._date_time < DATE '2026-03-21'
  AND n._description ILIKE '%ECO four 24 F%'
GROUP BY n._description;

-- 7. Все rref поля в шапке document240
SELECT column_name
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = '_document240'
  AND column_name LIKE '%rref'
ORDER BY ordinal_position;

-- 8. TODO:
-- найти клиента / склад / организацию в _document240
-- проверить поля:
-- _fld6004rref
-- _fld6005rref
-- _fld6006rref
-- _fld6030rref
-- _fld6032rref
-- _fld6033rref