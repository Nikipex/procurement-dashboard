# Procurement Dashboard

Internal dashboard for procurement department.

## Stack
- Python
- Pandas
- Plotly
- Jinja2

## Features
- stock analysis
- critical items
- supplier metrics
- automated reports

# Procurement Dashboard

Internal BI system for procurement department (gas equipment company).

---

## Project Overview

This project replaces manual Excel-based workflows with a direct PostgreSQL (1C) data pipeline.

It includes:

- Procurement Dashboard (HTML)
- Executive PDF Report
- (Future) Telegram Bot for managers

---

## Data Source

Primary source:

- 1C PostgreSQL dump (read-only)

Key entities discovered:

- Sales documents → `public._document240`
- Sales lines → `public._document240_vt6039`
- Products → `public._reference80`
- Warehouses → `public._reference100`

### South Warehouse

Identified real warehouse:

- Name: Южный склад
- ID: `83ee60f67771497111e9dbb16ec97a48`

---

## SQL Structure

```
sql/
├── views/     # reusable data views
├── research/  # exploratory queries (1C reverse engineering)
├── checks/    # validation & sanity checks
```

### Key Views

- `sales_lines_gross_profit.sql`
- `stock_south_warehouse.sql`

#### stock_south_warehouse

Source: `public._accumrgt9117`

- warehouse → `_fld9099rref`
- product   → `_fld9098rref`
- stock_qty → `_fld9106`
- amount    → `_fld9107`

Provides real stock data for South warehouse.

---

## Stack

- Python 3.12+
- PostgreSQL
- SQLAlchemy
- Pandas
- Plotly
- Jinja2
- ReportLab / WeasyPrint (PDF)
- python-dotenv

---

## Project Structure

```
app/        # business logic (services, reports)
scripts/    # dev & debug scripts
sql/        # SQL layer (views, research, checks)
data/       # raw & processed data
output/     # generated reports
```

---

## Current Status

- ✅ Connected to real 1C PostgreSQL
- ✅ Extracted sales data (90 days)
- ✅ Identified South warehouse
- ✅ Extracted stock data from register `_accumrgt9117`
- ✅ Built working SQL views
- ✅ PDF report v2 working

---

## Next Steps

1. Build `sales_south_warehouse` view
2. Merge stock + sales
3. Calculate:
   - avg daily sales
   - days of cover
   - critical stock
4. Build Procurement Dashboard MVP
5. Build PDF v3
6. Add procurement recommendation logic

---

## Goal

Deliver a production-ready internal tool that:

- reduces manual work
- improves procurement decisions
- provides real-time stock & sales visibility

---

## Notes

- Project uses real company data (read-only)
- SQL layer is the core source of truth
- Designed to evolve into full BI system