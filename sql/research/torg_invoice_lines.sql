SELECT '_fld6013rref' fld, r._description
FROM public._document240 d
JOIN public._reference97 r ON d._fld6013rref = r._idrref
LIMIT 5

UNION ALL
SELECT '_fld6014rref', r._description
FROM public._document240 d
JOIN public._reference97 r ON d._fld6014rref = r._idrref
LIMIT 5

UNION ALL
SELECT '_fld6015rref', r._description
FROM public._document240 d
JOIN public._reference97 r ON d._fld6015rref = r._idrref
LIMIT 5

UNION ALL
SELECT '_fld6016rref', r._description
FROM public._document240 d
JOIN public._reference97 r ON d._fld6016rref = r._idrref
LIMIT 5

UNION ALL
SELECT '_fld6030rref', r._description
FROM public._document240 d
JOIN public._reference97 r ON d._fld6030rref = r._idrref
LIMIT 5;