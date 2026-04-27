from sqlalchemy import create_engine
from urllib.parse import quote_plus


def build_db_url(config: dict) -> str:
    db = config["database"]
    password = quote_plus(db["password"])
    return (
        f"postgresql+psycopg2://{db['user']}:{password}"
        f"@{db['host']}:{db['port']}/{db['dbname']}"
    )


def get_engine(config: dict):
    return create_engine(build_db_url(config))