from pathlib import Path
import re

BASE = Path(__file__).resolve().parents[1]

def body(path: str, view_name: str) -> str:
    text = (BASE / path).read_text(encoding="utf-8")
    pattern = rf"CREATE\s+VIEW\s+public\.{view_name}\s+AS\s*(.*)"
    m = re.search(pattern, text, flags=re.I | re.S)
    if not m:
        pattern = rf"CREATE\s+OR\s+REPLACE\s+VIEW\s+public\.{view_name}\s+AS\s*(.*)"
        m = re.search(pattern, text, flags=re.I | re.S)
    if not m:
        raise SystemExit(f"Cannot extract {view_name} from {path}")
    sql = m.group(1).strip()
    sql = re.sub(r";\s*$", "", sql)
    return sql

clients = body("sql/views/clients_krasnodar.sql", "clients_krasnodar")

sales = body("sql/views/sales_south_krasnodar.sql", "sales_south_krasnodar")
sales = sales.replace("public.clients_krasnodar", "clients_krasnodar")

sales_60d = body("sql/views/sales_south_krasnodar_60d.sql", "sales_south_krasnodar_60d")
sales_60d = sales_60d.replace("public.sales_south_krasnodar", "sales_south_krasnodar")

stock = body("sql/views/stock_south_warehouse.sql", "stock_south_warehouse")

stock_agg = body("sql/views/stock_south_warehouse_agg.sql", "stock_south_warehouse_agg")
stock_agg = stock_agg.replace("public.stock_south_warehouse", "stock_south_warehouse")
stock_agg = stock_agg.replace("public.sales_south_warehouse", "sales_south_krasnodar")

mvp = body("sql/marts/procurement_south_mvp.sql", "procurement_south_mvp")
mvp = mvp.replace("public.sales_south_krasnodar_60d", "sales_south_krasnodar_60d")
mvp = mvp.replace("public.sales_south_krasnodar", "sales_south_krasnodar")
mvp = mvp.replace("public.stock_south_warehouse_agg", "stock_south_warehouse_agg")

dashboard = body("sql/marts/procurement_south_dashboard.sql", "procurement_south_dashboard")
dashboard = dashboard.replace("public.procurement_south_mvp", "procurement_south_mvp")

# The original dashboard view starts with its own WITH.
# Here it is appended after procurement_south_mvp inside one common WITH-chain.
dashboard = re.sub(r"^\\s*WITH\\s+", ",\n", dashboard, flags=re.I)

out = f"""
WITH
clients_krasnodar AS (
{clients}
),
sales_south_krasnodar AS (
{sales}
),
sales_south_krasnodar_60d AS (
{sales_60d}
),
stock_south_warehouse AS (
{stock}
),
stock_south_warehouse_agg AS (
{stock_agg}
),
procurement_south_mvp AS (
{mvp}
)
{dashboard}
"""

target = BASE / "sql/live_readonly/procurement_south_dashboard.sql"
# 1C PostgreSQL uses mvarchar; PostgreSQL string funcs need explicit text casts.
out = out.replace("LOWER(product_name)", "LOWER(product_name::text)")
out = out.replace("lower(product_name)", "lower(product_name::text)")
out = out.replace("LOWER(product_name::text::text)", "LOWER(product_name::text)")
out = out.replace("lower(product_name::text::text)", "lower(product_name::text)")

out = out.replace("coalesce(p.product_name, '')", "coalesce(p.product_name::text, '')")
out = out.replace("COALESCE(p.product_name, '')", "COALESCE(p.product_name::text, '')")
out = out.replace("coalesce(p.product_name::text::text, '')", "coalesce(p.product_name::text, '')")

# pandas/psycopg2 treats % in raw SQL as param markers.
# We do not pass params here, so literal percent signs must be escaped.
out = out.replace("%", "%%")

target.write_text(out.strip() + "\n", encoding="utf-8")
print(f"written: {target}")
