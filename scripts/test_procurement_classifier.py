

import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

from app.services.product_classifier import classify_product_group


BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError(f"DATABASE_URL not found in {BASE_DIR / '.env'}")

engine = create_engine(DATABASE_URL)


def main() -> None:
    df = pd.read_sql(
        "SELECT * FROM public.procurement_south_mvp",
        engine,
    )

    df["product_group"] = df["product_name"].apply(classify_product_group)

    print("\n=== GROUP COUNTS ===")
    print(df["product_group"].value_counts())

    df_target = df[df["product_group"] != "прочее"].copy()

    print("\n=== TARGET DATASET SUMMARY ===")
    print(f"Total rows: {len(df)}")
    print(f"Target rows: {len(df_target)}")
    print(f"Other rows: {len(df) - len(df_target)}")

    print("\n=== CRITICAL TARGET PRODUCTS ===")
    critical = df_target[df_target["stock_status"] == "critical"].copy()

    if critical.empty:
        print("No critical target products found.")
    else:
        critical = critical.sort_values(
            by=["product_group", "days_of_cover", "sales_qty_60d"],
            ascending=[True, True, False],
        )

        print(
            critical[
                [
                    "product_group",
                    "product_code",
                    "product_name",
                    "stock_qty",
                    "sales_qty_60d",
                    "avg_daily_sales",
                    "days_of_cover",
                    "stock_status",
                ]
            ]
            .head(100)
            .to_string(index=False)
        )

    print("\n=== TOP TARGET SALES 60D ===")
    print(
        df_target[
            [
                "product_group",
                "product_code",
                "product_name",
                "stock_qty",
                "sales_qty_60d",
                "avg_daily_sales",
                "days_of_cover",
                "stock_status",
            ]
        ]
        .sort_values("sales_qty_60d", ascending=False)
        .head(50)
        .to_string(index=False)
    )

    output_path = BASE_DIR / "output" / "procurement_south_mvp_classified.xlsx"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df_target.to_excel(output_path, index=False)

    print(f"\nSaved: {output_path}")


if __name__ == "__main__":
    main()