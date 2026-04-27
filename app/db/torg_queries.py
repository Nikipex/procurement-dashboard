from pathlib import Path

import pandas as pd
from sqlalchemy import Engine


BASE_DIR = Path(__file__).resolve().parents[2]


def read_sql_file(relative_path: str) -> str:
    path = BASE_DIR / relative_path
    return path.read_text(encoding="utf-8")


def load_invoice_lines(engine: Engine) -> pd.DataFrame:
    query = read_sql_file("sql/views/invoice_lines.sql")
    return pd.read_sql(query, engine)