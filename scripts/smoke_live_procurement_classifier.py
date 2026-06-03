from dotenv import load_dotenv
from sqlalchemy import create_engine
import os
import pandas as pd

from app.services.product_classifier import classify_product_group

load_dotenv(".env", override=True)

engine = create_engine(os.getenv("DATABASE_URL"))

sql = """
WITH total_stock AS (
    SELECT
        s._fld9098rref AS product_id,
        SUM(s._fld9106) AS total_stock_qty,
        SUM(s._fld9107) AS stock_amount
    FROM public._accumrgt9117 s
    WHERE s._fld9099rref = decode('83ee60f67771497111e9dbb16ec97a48','hex')
      AND s._period = TIMESTAMP '3999-11-01 00:00:00'
    GROUP BY s._fld9098rref
),
reserved_stock AS (
    SELECT
        r._fld9301rref AS product_id,
        SUM(r._fld9305) AS reserved_stock_qty
    FROM public._accumrgt9308 r
    GROUP BY r._fld9301rref
),
stock_live AS (
    SELECT
        n._code::text AS product_code,
        n._description::text AS product_name,
        COALESCE(t.total_stock_qty, 0) AS total_stock_qty,
        COALESCE(r.reserved_stock_qty, 0) AS reserved_stock_qty,
        GREATEST(
            COALESCE(t.total_stock_qty, 0) - COALESCE(r.reserved_stock_qty, 0),
            0
        ) AS free_stock_qty,
        CASE
            WHEN COALESCE(t.total_stock_qty, 0) > 0
            THEN ROUND(COALESCE(t.stock_amount, 0) / NULLIF(t.total_stock_qty, 0), 2)
            ELSE NULL
        END AS avg_stock_price
    FROM public._reference80 n
    LEFT JOIN total_stock t ON t.product_id = n._idrref
    LEFT JOIN reserved_stock r ON r.product_id = n._idrref
)
SELECT *
FROM stock_live
WHERE total_stock_qty <> 0
ORDER BY total_stock_qty DESC
LIMIT 200
"""

df = pd.read_sql(sql, engine)
df["product_group"] = df["product_name"].apply(classify_product_group)

print(df.head(20))
print(df["product_group"].value_counts())
print("rows:", len(df))
