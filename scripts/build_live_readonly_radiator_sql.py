from pathlib import Path
import re

BASE = Path(__file__).resolve().parents[1]

def body(path: str, view_name: str) -> str:
    text = (BASE / path).read_text(encoding="utf-8")
    m = re.search(
        rf"CREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+public\.{view_name}\s+AS\s*(.*)",
        text,
        flags=re.I | re.S,
    )
    if not m:
        raise SystemExit(f"Cannot extract {view_name} from {path}")
    sql = m.group(1).strip()
    sql = re.sub(r";\s*$", "", sql)
    return sql

clients = body("sql/views/clients_krasnodar.sql", "clients_krasnodar")

sales = body("sql/views/sales_south_krasnodar.sql", "sales_south_krasnodar")
sales = sales.replace("public.clients_krasnodar", "clients_krasnodar")

stock = body("sql/views/stock_south_warehouse.sql", "stock_south_warehouse")

stock_agg = body("sql/views/stock_south_warehouse_agg.sql", "stock_south_warehouse_agg")
stock_agg = stock_agg.replace("public.stock_south_warehouse", "stock_south_warehouse")
stock_agg = stock_agg.replace("public.sales_south_warehouse", "sales_south_krasnodar")

radiator = body("sql/marts/radiator_procurement_mvp.sql", "radiator_procurement_mvp")
radiator = radiator.replace("public.sales_south_krasnodar", "sales_south_krasnodar")
radiator = radiator.replace("public.stock_south_warehouse_agg", "stock_south_warehouse_agg")

# original radiator view starts with WITH; we append it after dependency CTEs
radiator = re.sub(r"^\s*WITH\s+", ",\n", radiator, flags=re.I)

out = f"""
WITH
clients_krasnodar AS (
{clients}
),
sales_south_krasnodar AS (
{sales}
),
stock_south_warehouse AS (
{stock}
),
stock_south_warehouse_agg AS (
{stock_agg}
)
{radiator}
"""

# 1C mvarchar/mchar casts
out = out.replace("n._code AS product_code", "n._code::text AS product_code")
out = out.replace("n._description AS product_name", "n._description::text AS product_name")
out = out.replace("c._description AS client_name", "c._description::text AS client_name")
out = out.replace("LOWER(product_name)", "LOWER(product_name::text)")
out = out.replace("LOWER(s.product_name)", "LOWER(s.product_name::text)")
out = out.replace("LOWER(r.product_name)", "LOWER(r.product_name::text)")
out = out.replace("LOWER(product_name::text::text)", "LOWER(product_name::text)")

out = out.replace("COALESCE(rs.product_code, st.product_code)", "COALESCE(rs.product_code::text, st.product_code::text)")
out = out.replace("COALESCE(rs.product_name, st.product_name)", "COALESCE(rs.product_name::text, st.product_name::text)")
out = out.replace("st.product_code = rs.product_code", "st.product_code::text = rs.product_code::text")
out = out.replace("MIN(product_code) AS product_code", "MIN(product_code::text) AS product_code")

# pandas/psycopg2 percent escaping
out = out.replace("%", "%%")

target = BASE / "sql/live_readonly/radiator_procurement_mvp.sql"
target.write_text(out.strip() + "\n", encoding="utf-8")
print(f"written: {target}")
