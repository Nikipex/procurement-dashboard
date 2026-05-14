import pandas as pd
from sqlalchemy import create_engine
import os
from dotenv import load_dotenv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

engine = create_engine(os.getenv("DATABASE_URL"))

df = pd.read_sql("SELECT * FROM public.procurement_south_mvp", engine)

print(df.head())
print(df.describe())

# быстрый чек
print("\nCRITICAL:")
print(df[df["stock_status"] == "critical"].head(20))