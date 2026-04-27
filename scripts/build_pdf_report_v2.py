from pathlib import Path

from app.db.connection import get_engine
from app.db.torg_queries import load_invoice_lines
from app.reports.pdf_report_v2 import build_pdf_report


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
    df = load_invoice_lines(engine)

    output_path = Path("output/sales_report_v2.pdf")
    build_pdf_report(df, output_path)

    print(f"PDF saved: {output_path}")


if __name__ == "__main__":
    main()