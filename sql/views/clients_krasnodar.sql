DROP VIEW IF EXISTS public.clients_krasnodar;

CREATE VIEW public.clients_krasnodar AS
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
WHERE level >= 2;