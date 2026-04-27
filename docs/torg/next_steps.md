# Next steps

## Stage 1 — SQL foundation

- [ ] Save invoice lines query in `sql/views/invoice_lines.sql`
- [ ] Test query in DBeaver
- [ ] Confirm 90-day data looks correct
- [ ] Add fixed-period variant for testing
- [ ] Find manager/customer fields in `_document162`
- [ ] Find stock/warehouse tables
- [ ] Find purchase/order tables

## Stage 2 — Python integration

- [ ] Add DB config
- [ ] Add SQLAlchemy engine
- [ ] Add function `load_invoice_lines()`
- [ ] Load query into pandas
- [ ] Export first CSV to `data/exports/invoice_lines_90d.csv`

## Stage 3 — Dashboard

- [ ] Revenue 90d
- [ ] Quantity 90d
- [ ] Top products by revenue
- [ ] Top products by qty
- [ ] Daily revenue chart
- [ ] Product group classification

## Stage 4 — Production prep

- [ ] Ask for read-only DB access
- [ ] Confirm production host/port/db/user
- [ ] Verify table names match dump
- [ ] Test same SQL against prod readonly
- [ ] Move credentials to `.env`