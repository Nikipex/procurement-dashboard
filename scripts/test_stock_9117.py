import os
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

SOUTH_ID_HEX = "83ee60f67771497111e9dbb16ec97a48"

PRODUCT_CANDIDATES = [
    "_fld9098rref",
    "_fld9100rref",
    "_fld9101rref",
    "_fld9102_rrref",
    "_fld9103rref",
    "_fld9104rref",
    "_fld9105rref",
]

def test_product_col(col: str):
    sql = f"""
    SELECT
        s._period,
        n._code AS product_code,
        n._description AS product_name,
        s._fld9106 AS qty,
        s._fld9107 AS amount
    FROM public._accumrgt9117 s
    JOIN public._reference80 n
        ON s.{col} = n._idrref
    WHERE s._fld9099rref = decode(:south_id, 'hex')
      AND s._fld9106 <> 0
    LIMIT 30;
    """

    try:
        df = pd.read_sql(text(sql), engine, params={"south_id": SOUTH_ID_HEX})
        print("\n" + "=" * 100)
        print(f"PRODUCT COL CANDIDATE: {col}")
        print(f"rows: {len(df)}")

        if len(df) > 0:
            print(df.to_string(index=False))

    except Exception as e:
        print("\n" + "=" * 100)
        print(f"PRODUCT COL CANDIDATE: {col}")
        print(f"ERROR: {e}")


def main():
    for col in PRODUCT_CANDIDATES:
        test_product_col(col)


if __name__ == "__main__":
    main()