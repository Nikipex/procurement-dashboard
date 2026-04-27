import pandas as pd

from app.db.connection import get_engine
from app.db.torg_queries import load_invoice_lines


config = {
    "database": {
        "host": "localhost",
        "port": 5433,
        "dbname": "torg_full",
        "user": "nikitos",
        "password": "nikitos",
    }
}

engine = get_engine(config)

df = load_invoice_lines(engine)

print(df.head())
print(df.info())
print("rows:", len(df))
print("revenue:", df["line_amount"].sum())

df.to_csv("data/exports/invoice_lines_90d.csv", index=False)

print("CSV saved")
top_products = (
    df.groupby("product_name", as_index=False)["line_amount"]
      .sum()
      .sort_values("line_amount", ascending=False)
      .head(20)
)

print(top_products)
top_products.to_csv("data/exports/top_products_90d.csv", index=False)
print("TOP products saved")