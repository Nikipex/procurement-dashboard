# TORG DB mapping

## Environment

Docker container: `torg-pg10`  
PostgreSQL: 10  
Database: `torg_full`  
Host: `localhost`  
Port: `5433`  
User: `nikitos`  
Password: `nikitos`

## Import notes

Original dump: `~/Downloads/torg.sql`  
Clean dump: `~/Downloads/torg_clean.sql`

Problem:
- Original 1C dump used custom PostgreSQL types/extensions:
  - `public.mvarchar`
  - `public.mchar`
  - `fasttrun`
  - `fulleq`
  - `mchar`
- Cleaned by replacing:
  - `public.mvarchar` → `varchar`
  - `public.mchar` → `char`

## Confirmed table mapping

### `_document162`

Счета.

Fields:
- `_idrref` — internal document id
- `_number` — invoice number
- `_date_time` — invoice created datetime
- `_posted` — posted flag

### `_document162_vt3139`

Строки счетов.

Fields:
- `_document162_idrref` — link to `_document162._idrref`
- `_fld3146rref` — product link to `_reference80._idrref`
- `_fld3143` — quantity
- `_fld3154` — unit price
- `_fld3151` — line amount

### `_reference80`

Номенклатура / товары.

Fields:
- `_idrref` — internal product id
- `_code` — product code
- `_description` — product name

### `_reference31`

Банки / БИК.

Fields:
- `_code` — bank code / BIK
- `_description` — bank name