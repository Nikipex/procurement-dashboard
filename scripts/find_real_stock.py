

import os
from pathlib import Path
from typing import Iterable

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text


BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError(f"DATABASE_URL not found in {BASE_DIR / '.env'}")

engine = create_engine(DATABASE_URL)

SOUTH_ID_HEX = "83ee60f67771497111e9dbb16ec97a48"
PRODUCT_SEARCH = "500//22*1000"


SKIP_NUMERIC_COLUMNS = {
    "_dimhash",
    "_lineno",
    "_recordkind",
}


def get_accum_total_tables() -> list[str]:
    sql = """
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public'
      AND table_name LIKE '\\_accumrgt%' ESCAPE '\\'
    ORDER BY table_name;
    """
    df = pd.read_sql(text(sql), engine)
    return df["table_name"].tolist()


def get_columns(table: str) -> pd.DataFrame:
    sql = """
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = :table
    ORDER BY ordinal_position;
    """
    return pd.read_sql(text(sql), engine, params={"table": table})


def find_matching_products(search_text: str) -> pd.DataFrame:
    sql = """
    SELECT
        encode(_idrref, 'hex') AS product_id_hex,
        _code AS product_code,
        _description AS product_name
    FROM public._reference80
    WHERE _description ILIKE :pattern
    ORDER BY _description
    LIMIT 20;
    """
    return pd.read_sql(text(sql), engine, params={"pattern": f"%{search_text}%"})


def count_value_matches(table: str, column: str, value_hex: str) -> int:
    sql = f"""
    SELECT COUNT(*) AS cnt
    FROM public.{table}
    WHERE {column} = decode(:value_hex, 'hex');
    """
    return int(pd.read_sql(text(sql), engine, params={"value_hex": value_hex})["cnt"].iloc[0])


def candidate_rref_columns(columns: pd.DataFrame) -> list[str]:
    return [
        col
        for col in columns["column_name"].tolist()
        if col.endswith("rref") or col.endswith("rrref")
    ]


def candidate_numeric_columns(columns: pd.DataFrame) -> list[str]:
    numeric_types = {"numeric", "integer", "bigint", "double precision", "real"}
    result = []
    for _, row in columns.iterrows():
        col = row["column_name"]
        if row["data_type"] in numeric_types and col not in SKIP_NUMERIC_COLUMNS:
            result.append(col)
    return result


def preview_candidate(
    table: str,
    warehouse_col: str,
    product_col: str,
    numeric_cols: Iterable[str],
    product_id_hex: str,
) -> pd.DataFrame:
    numeric_select = ",\n        ".join([f"s.{col} AS {col}" for col in numeric_cols])
    sql = f"""
    SELECT
        '{table}' AS source_table,
        s._period AS period,
        n._code AS product_code,
        n._description AS product_name,
        {numeric_select}
    FROM public.{table} s
    JOIN public._reference80 n
        ON s.{product_col} = n._idrref
    WHERE s.{warehouse_col} = decode(:south_id, 'hex')
      AND s.{product_col} = decode(:product_id, 'hex')
    ORDER BY s._period DESC
    LIMIT 50;
    """
    return pd.read_sql(
        text(sql),
        engine,
        params={"south_id": SOUTH_ID_HEX, "product_id": product_id_hex},
    )


def summarize_candidate(
    table: str,
    warehouse_col: str,
    product_col: str,
    numeric_cols: Iterable[str],
    product_id_hex: str,
) -> pd.DataFrame:
    numeric_exprs = []
    for col in numeric_cols:
        numeric_exprs.append(f"SUM(s.{col}) AS sum_{col}")
        numeric_exprs.append(f"MAX(s.{col}) AS max_{col}")
        numeric_exprs.append(f"MIN(s.{col}) AS min_{col}")

    numeric_select = ",\n        ".join(numeric_exprs)

    sql = f"""
    SELECT
        '{table}' AS source_table,
        '{warehouse_col}' AS warehouse_col,
        '{product_col}' AS product_col,
        COUNT(*) AS rows_count,
        MIN(s._period) AS min_period,
        MAX(s._period) AS max_period,
        {numeric_select}
    FROM public.{table} s
    WHERE s.{warehouse_col} = decode(:south_id, 'hex')
      AND s.{product_col} = decode(:product_id, 'hex');
    """
    return pd.read_sql(
        text(sql),
        engine,
        params={"south_id": SOUTH_ID_HEX, "product_id": product_id_hex},
    )


def scan_for_product(product_id_hex: str) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    summaries: list[pd.DataFrame] = []
    previews: dict[str, pd.DataFrame] = {}

    tables = get_accum_total_tables()
    print(f"Found accum total tables: {len(tables)}")

    for table in tables:
        try:
            cols = get_columns(table)
            rref_cols = candidate_rref_columns(cols)
            numeric_cols = candidate_numeric_columns(cols)

            if not rref_cols or not numeric_cols:
                continue

            warehouse_cols = []
            product_cols = []

            for col in rref_cols:
                south_count = count_value_matches(table, col, SOUTH_ID_HEX)
                if south_count > 0:
                    warehouse_cols.append(col)

                product_count = count_value_matches(table, col, product_id_hex)
                if product_count > 0:
                    product_cols.append(col)

            if not warehouse_cols or not product_cols:
                continue

            for warehouse_col in warehouse_cols:
                for product_col in product_cols:
                    if warehouse_col == product_col:
                        continue

                    summary = summarize_candidate(
                        table=table,
                        warehouse_col=warehouse_col,
                        product_col=product_col,
                        numeric_cols=numeric_cols,
                        product_id_hex=product_id_hex,
                    )

                    if summary.empty or int(summary["rows_count"].iloc[0]) == 0:
                        continue

                    summaries.append(summary)

                    preview_key = f"{table}.{warehouse_col}.{product_col}"
                    previews[preview_key] = preview_candidate(
                        table=table,
                        warehouse_col=warehouse_col,
                        product_col=product_col,
                        numeric_cols=numeric_cols,
                        product_id_hex=product_id_hex,
                    )

                    print("\n" + "=" * 120)
                    print(f"CANDIDATE: {preview_key}")
                    print(summary.to_string(index=False))
                    print("\nPREVIEW:")
                    print(previews[preview_key].head(20).to_string(index=False))

        except Exception as exc:
            print(f"ERROR scanning {table}: {exc}")

    if not summaries:
        return pd.DataFrame(), previews

    return pd.concat(summaries, ignore_index=True), previews


def main() -> None:
    print("=" * 120)
    print("REAL STOCK REGISTER SCANNER")
    print(f"South warehouse ID: {SOUTH_ID_HEX}")
    print(f"Product search: {PRODUCT_SEARCH}")

    products = find_matching_products(PRODUCT_SEARCH)
    print("\nMATCHING PRODUCTS:")
    print(products.to_string(index=False))

    if products.empty:
        print("No products found. Change PRODUCT_SEARCH and try again.")
        return

    product_id_hex = products.iloc[0]["product_id_hex"]
    product_name = products.iloc[0]["product_name"]
    print(f"\nUsing product: {product_name}")
    print(f"Product ID: {product_id_hex}")

    summaries, _ = scan_for_product(product_id_hex)

    if summaries.empty:
        print("\nNo candidate stock registers found.")
        return

    output_path = BASE_DIR / "output" / "real_stock_candidates.xlsx"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summaries.to_excel(output_path, index=False)

    print("\n" + "=" * 120)
    print("SUMMARY CANDIDATES:")
    print(summaries.to_string(index=False))
    print(f"\nSaved summary: {output_path}")
    print("\nLook for candidates where numeric values look like real stock, not accumulated huge totals.")


if __name__ == "__main__":
    main()