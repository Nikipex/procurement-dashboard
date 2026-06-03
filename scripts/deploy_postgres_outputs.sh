#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/opt/projects/procurement-dashboard"
WEB_DIR="/var/www/procurement"

cd "$PROJECT_DIR"

PYTHONPATH=. USE_POSTGRES_PIPELINE=1 "$PROJECT_DIR/venv/bin/python" main.py

"$PROJECT_DIR/venv/bin/python" "$PROJECT_DIR/scripts/postprocess_dashboard_html.py"

cp "$PROJECT_DIR/data/output/dashboard_postgres.html" "$WEB_DIR/dashboard_postgres.html"
cp "$PROJECT_DIR/data/output/report_postgres.pdf" "$WEB_DIR/report_postgres.pdf"

echo "Deployed:"
echo "http://138.16.177.123/dashboard_postgres.html"
echo "http://138.16.177.123/report_postgres.pdf"
