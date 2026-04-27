SELECT '_fld6004rref -> reference97' AS link, COUNT(*) AS matches
FROM public._document240 d
JOIN public._reference97 r ON d._fld6004rref = r._idrref

UNION ALL
SELECT '_fld6005rref -> reference97', COUNT(*)
FROM public._document240 d
JOIN public._reference97 r ON d._fld6005rref = r._idrref

UNION ALL
SELECT '_fld6006rref -> reference97', COUNT(*)
FROM public._document240 d
JOIN public._reference97 r ON d._fld6006rref = r._idrref

UNION ALL
SELECT '_fld6004rref -> reference80', COUNT(*)
FROM public._document240 d
JOIN public._reference80 r ON d._fld6004rref = r._idrref

UNION ALL
SELECT '_fld6005rref -> reference80', COUNT(*)
FROM public._document240 d
JOIN public._reference80 r ON d._fld6005rref = r._idrref

UNION ALL
SELECT '_fld6006rref -> reference80', COUNT(*)
FROM public._document240 d
JOIN public._reference80 r ON d._fld6006rref = r._idrref

UNION ALL
SELECT '_fld6004rref -> reference55', COUNT(*)
FROM public._document240 d
JOIN public._reference55 r ON d._fld6004rref = r._idrref

UNION ALL
SELECT '_fld6005rref -> reference55', COUNT(*)
FROM public._document240 d
JOIN public._reference55 r ON d._fld6005rref = r._idrref

UNION ALL
SELECT '_fld6006rref -> reference55', COUNT(*)
FROM public._document240 d
JOIN public._reference55 r ON d._fld6006rref = r._idrref

UNION ALL
SELECT '_fld6004rref -> reference51', COUNT(*)
FROM public._document240 d
JOIN public._reference51 r ON d._fld6004rref = r._idrref

UNION ALL
SELECT '_fld6005rref -> reference51', COUNT(*)
FROM public._document240 d
JOIN public._reference51 r ON d._fld6005rref = r._idrref

UNION ALL
SELECT '_fld6006rref -> reference51', COUNT(*)
FROM public._document240 d
JOIN public._reference51 r ON d._fld6006rref = r._idrref

UNION ALL
SELECT '_fld6004rref -> reference44', COUNT(*)
FROM public._document240 d
JOIN public._reference44 r ON d._fld6004rref = r._idrref

UNION ALL
SELECT '_fld6005rref -> reference44', COUNT(*)
FROM public._document240 d
JOIN public._reference44 r ON d._fld6005rref = r._idrref

UNION ALL
SELECT '_fld6006rref -> reference44', COUNT(*)
FROM public._document240 d
JOIN public._reference44 r ON d._fld6006rref = r._idrref

ORDER BY matches DESC;