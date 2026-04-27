import pandas as pd
import yaml
from pathlib import Path

from app.db.connection import get_engine

config_path = Path("torg-pdf-report/config.yaml")

with open(config_path, "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

print(config)

engine = get_engine(config)

query = """
SELECT COUNT(*) AS cnt
FROM public._reference31
"""

df = pd.read_sql(query, engine)
print(df)