from app.db.connection import get_engine
from app.db.torg_queries import load_sales_lines_gross_profit


config = {
    "database": {
        "host": "localhost",
        "port": 5433,
        "dbname": "torg_full",
        "user": "nikitos",
        "password": "nikitos",
    }
}


def main():
    engine = get_engine(config)
    df = load_sales_lines_gross_profit(engine)

    print(df.head())
    print(df.info())
    print("rows:", len(df))
    print("qty:", df["qty"].sum())
    print("revenue:", df["revenue"].sum())
    print("cost_or_profit_amount:", df["cost_or_profit_amount"].sum())
    print("extra_amount:", df["extra_amount"].sum())

    df.to_csv("data/exports/sales_lines_gross_profit_90d.csv", index=False)
    print("CSV saved: data/exports/sales_lines_gross_profit_90d.csv")


if __name__ == "__main__":
    main()