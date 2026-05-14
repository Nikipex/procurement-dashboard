import os
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError(f"DATABASE_URL not found in {BASE_DIR / '.env'}")

engine = create_engine(DATABASE_URL)

SOUTH_ID_HEX = "83ee60f67771497111e9dbb16ec97a48"

CANDIDATES = [
    "_accumrg9288",
    "_accumrg9310",
    "_accumrg9321",
    "_accumrg9333",
    "_accumrg9346",
    "_accumrg9358",
    "_accumrg9224",
    "_accumrg9258",
    "_accumrgt9026",
    "_accumrgt9117",
    "_accumrgt9266",
]

def get_columns(table: str):
    sql = """
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = :table
    ORDER BY ordinal_position;
    """
    return pd.read_sql(text(sql), engine, params={"table": table})


def test_rref_column(table: str, column: str):
    sql = f"""
    SELECT COUNT(*) AS cnt
    FROM public.{table}
    WHERE {column} = decode(:south_id, 'hex');
    """
    return pd.read_sql(
        text(sql),
        engine,
        params={"south_id": SOUTH_ID_HEX},
    )["cnt"].iloc[0]


def preview_table(table: str, warehouse_col: str):
    sql = f"""
    SELECT *
    FROM public.{table}
    WHERE {warehouse_col} = decode(:south_id, 'hex')
    LIMIT 20;
    """
    return pd.read_sql(
        text(sql),
        engine,
        params={"south_id": SOUTH_ID_HEX},
    )


def main():
    for table in CANDIDATES:
        print("\n" + "=" * 100)
        print(f"TABLE: {table}")

        try:
            cols = get_columns(table)
        except Exception as e:
            print(f"ERROR reading columns: {e}")
            continue

        print(cols.to_string(index=False))

        rref_cols = cols[cols["column_name"].str.endswith("rref")]["column_name"].tolist()
        numeric_cols = cols[
            cols["data_type"].isin(["numeric", "double precision", "real", "integer", "bigint"])
        ]["column_name"].tolist()

        print(f"\nRREF columns: {rref_cols}")
        print(f"Numeric columns: {numeric_cols}")

        for col in rref_cols:
            try:
                cnt = test_rref_column(table, col)
                if cnt > 0:
                    print(f"\nFOUND SOUTH MATCH: {table}.{col} = {cnt} rows")

                    preview = preview_table(table, col)
                    print(preview.head(20).to_string(index=False))

            except Exception as e:
                print(f"Error testing {table}.{col}: {e}")


if __name__ == "__main__":
    main()