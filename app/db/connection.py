import os
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy import create_engine


def build_db_url(config: dict) -> str:
    db = config["database"]
    password = quote_plus(db["password"])
    return (
        f"postgresql+psycopg2://{db['user']}:{password}"
        f"@{db['host']}:{db['port']}/{db['dbname']}"
    )


def get_engine(config: dict):
    load_dotenv(".env", override=True)

    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return create_engine(database_url)

    return create_engine(build_db_url(config))
