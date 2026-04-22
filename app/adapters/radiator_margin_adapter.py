import pandas as pd
from pathlib import Path
from loguru import logger
import re
from app.normalization import normalize_radiator_product_name
def find_metric_columns_by_position(df: pd.DataFrame, text_col: str) -> tuple[str | None, str | None, str | None]:
    """
    Fallback metric detection for messy 1C exports where header cells are merged
    and aliases collapse into one long text column.

    Expected layout after the text column:
    - first numeric column  -> quantity
    - second numeric column -> revenue
    - third numeric column  -> gross profit
    """
    try:
        text_idx = list(df.columns).index(text_col)
    except ValueError:
        return None, None, None

    numeric_candidates = []

    for col in df.columns[text_idx + 1:]:
        series = df[col]
        numeric_count = series.apply(lambda x: safe_numeric_value(x) != 0).sum()
        non_null_count = series.notna().sum()

        if non_null_count == 0:
            continue

        if numeric_count > 0:
            numeric_candidates.append(col)

    qty_col = numeric_candidates[0] if len(numeric_candidates) > 0 else None
    revenue_col = numeric_candidates[1] if len(numeric_candidates) > 1 else None
    profit_col = numeric_candidates[2] if len(numeric_candidates) > 2 else None

    return qty_col, revenue_col, profit_col


# Service rows to skip
SERVICE_KEYWORDS = [
    "итог", "итого", "всего", "всего по",
    "период:", "показатели:", "группировки", "отборы",
    "покупатель", "заказ", "<объект", "валовая прибыль", "маржинальность",
]


# Expected column names in radiator margin report
COLUMN_ALIASES = {
    "quantity": [
        "Количество",
        "Количество (Шт.)",
        "Кол-во",
        "Qty",
        "Quantity",
    ],
    "revenue": [
        "Стоимость продажи",
        "Стоимость продажи (Руб.) С НДС",
        "Стоимость продажи (Руб.) Без НДС",
        "Сумма продажи",
        "Выручка",
        "Revenue",
        "Сумма",
    ],
    "gross_profit": [
        "Валовая прибыль",
        "Gross profit",
        "ВП",
        "Прибыль валовая",
    ],
}

MONTH_OUTPUT_SUFFIXES = {
    "январ": "jan_2026",
    "феврал": "feb_2026",
    "март": "mar_2026",
    "апрел": "apr_2026",
}


def infer_month_output_suffix(filename: str) -> str:
    """
    Infer output suffix for monthly radiator files.
    Falls back to 'month_unknown' if the file name does not match.
    """
    filename_lower = normalize_text(filename)

    for keyword, suffix in MONTH_OUTPUT_SUFFIXES.items():
        if keyword in filename_lower:
            return suffix

    return "month_unknown"


def normalize_text(text) -> str:
    """Normalize text for comparison."""
    if pd.isna(text):
        return ""
    text = str(text).replace("﻿", "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    text = text.replace("ё", "е")
    return text


def is_service_row(value) -> bool:
    """Check if row value is a service/header row to skip."""
    if pd.isna(value):
        return True

    value_str = str(value).replace("﻿", "").strip()
    if value_str == "":
        return True

    value_lower = value_str.lower()
    for keyword in SERVICE_KEYWORDS:
        if keyword in value_lower:
            return True
    return False


def is_radiator_product_row(value) -> bool:
    """
    Detect radiator product rows by naming pattern.
    Examples:
    - Стальной радиатор 500//11*0800 (1,2)
    - Стальной радиатор 300//22*0500 VK (1,2) нижнее подкл.
    """
    if pd.isna(value):
        return False

    value_str = str(value).replace("﻿", "").strip()
    if value_str == "":
        return False

    if is_service_row(value):
        return False

    pattern = r"^стальной\s+радиатор\s+(200|300|500)//(11|22)\*\d{4}.*1,2"
    return re.search(pattern, value_str.lower()) is not None


def find_header_row(df: pd.DataFrame) -> int | None:
    """
    Robust header detection for messy 1C exports.
    Picks the row with the best score, not just first weak match.
    """
    best_idx = None
    best_score = -1

    for i in range(min(len(df), 40)):
        row_values = [str(v).strip().lower() for v in df.iloc[i].tolist() if pd.notna(v)]
        row_text = " | ".join(row_values)

        score = 0
        if "номенклатура" in row_text:
            score += 3
        if "количество" in row_text:
            score += 3
        if "стоимость продажи" in row_text:
            score += 2
        if "валовая прибыль" in row_text:
            score += 2

        if score > best_score:
            best_score = score
            best_idx = i

    if best_score >= 4:
        return best_idx

    return None


def make_unique_columns(columns: list) -> list[str]:
    """
    Make column names unique to avoid df[col] returning DataFrame for duplicate names.
    """
    result = []
    seen = {}

    for col in columns:
        col_str = str(col).strip()
        if col_str in seen:
            seen[col_str] += 1
            result.append(f"{col_str}_{seen[col_str]}")
        else:
            seen[col_str] = 0
            result.append(col_str)

    return result


def find_column_by_aliases(df: pd.DataFrame, aliases: list[str], prefer_contains: str | None = None) -> str | None:
    """
    Find column name matching any of the provided aliases.
    If prefer_contains is set, prefer columns containing that substring.
    """
    candidates = []

    for col in df.columns:
        col_str = str(col).strip()
        col_lower = col_str.lower()

        for alias in aliases:
            if alias.lower() in col_lower:
                candidates.append(col_str)
                break

    if not candidates:
        return None

    if prefer_contains:
        for col in candidates:
            if prefer_contains.lower() in col.lower():
                return col

    return candidates[0]


def safe_numeric_value(value) -> float:
    """Safely convert value to numeric, returning 0 if invalid."""
    if pd.isna(value):
        return 0.0
    try:
        if isinstance(value, str):
            value = value.replace("\xa0", "").replace(" ", "").replace(",", ".").strip()
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def log_dataframe_debug(df: pd.DataFrame, stage: str, file_name: str):
    """Log debug information about DataFrame structure."""
    logger.debug(f"[{file_name}] {stage} - Shape: {df.shape}")
    logger.debug(f"[{file_name}] {stage} - Columns: {df.columns.tolist()}")
    if len(df) > 0:
        logger.debug(f"[{file_name}] {stage} - First 10 rows:\n{df.head(10).to_string()}")


def adapt_radiator_margin_report(file_path: Path) -> pd.DataFrame:
    """
    Adapts radiator gross margin Excel report.

    Input: Excel file with hierarchical structure (customer -> products)
    Output: DataFrame with aggregated radiator metrics

    Output columns:
    - product_name
    - product_key
    - radiator_qty_<month_suffix>
    - radiator_revenue_<month_suffix>
    - radiator_gross_profit_<month_suffix>
    """
    logger.info(f"Adapting Radiator Margin Report: {file_path.name}")

    month_suffix = infer_month_output_suffix(file_path.name)
    qty_output_col = f"radiator_qty_{month_suffix}"
    revenue_output_col = f"radiator_revenue_{month_suffix}"
    gross_profit_output_col = f"radiator_gross_profit_{month_suffix}"

    logger.info(
        f"[{file_path.name}] Output columns will use suffix '{month_suffix}': "
        f"qty={qty_output_col}, revenue={revenue_output_col}, gross_profit={gross_profit_output_col}"
    )

    if not file_path.exists():
        logger.warning(f"Radiator margin file not found: {file_path}")
        return pd.DataFrame()

    try:
        df = pd.read_excel(file_path, engine="openpyxl", header=None)
    except Exception as e:
        logger.error(f"Failed to read radiator margin file {file_path.name}: {e}")
        return pd.DataFrame()

    if df.empty:
        logger.warning(f"[{file_path.name}] DataFrame is empty after reading")
        return pd.DataFrame()

    log_dataframe_debug(df, "After reading Excel", file_path.name)

    # Detect header row dynamically
    header_row_idx = find_header_row(df)
    if header_row_idx is None:
        logger.error(f"[{file_path.name}] Could not detect header row")
        return pd.DataFrame()

    raw_columns = df.iloc[header_row_idx].tolist()
    raw_columns = [str(c).strip() for c in raw_columns]
    df.columns = make_unique_columns(raw_columns)
    df = df[header_row_idx + 1:].reset_index(drop=True)

    log_dataframe_debug(df, "After setting detected headers", file_path.name)

    logger.info(f"[{file_path.name}] Final columns after header normalization: {df.columns.tolist()}")

    # Find text column containing nomenclature
    text_col = None

    for col in df.columns:
        col_lower = str(col).strip().lower()
        if "номенклатура" in col_lower:
            text_col = col
            break

    if text_col is None:
        # Fallback by content, but safely via column position
        for col_idx in range(len(df.columns)):
            series = df.iloc[:, col_idx]
            if series.astype(str).str.contains("Стальной радиатор", case=False, na=False).any():
                text_col = df.columns[col_idx]
                break

    if text_col is None:
        logger.error(f"[{file_path.name}] Could not find text column with radiator products")
        return pd.DataFrame()

    # Find metric columns after text column is known
    qty_col = find_column_by_aliases(df, COLUMN_ALIASES["quantity"])
    revenue_col = find_column_by_aliases(df, COLUMN_ALIASES["revenue"], prefer_contains="с ндс")
    profit_col = find_column_by_aliases(df, COLUMN_ALIASES["gross_profit"])

    # If aliases collapsed to the same merged header/text column, fallback to positional detection
    duplicate_metric_cols = {qty_col, revenue_col, profit_col}
    if text_col in duplicate_metric_cols or len([c for c in duplicate_metric_cols if c is not None]) < 3:
        pos_qty_col, pos_revenue_col, pos_profit_col = find_metric_columns_by_position(df, text_col)
        if pos_qty_col is not None:
            qty_col = pos_qty_col
        if pos_revenue_col is not None:
            revenue_col = pos_revenue_col
        if pos_profit_col is not None:
            profit_col = pos_profit_col

    logger.info(
        f"[{file_path.name}] Detected columns: qty={qty_col}, "
        f"revenue={revenue_col}, profit={profit_col}"
    )
    logger.info(f"[{file_path.name}] Using text column: {text_col}")

    radiator_rows = []
    skipped_rows = 0
    radiator_detected = 0

    for idx in range(len(df)):
        row = df.iloc[idx]

        try:
            text_value = row[text_col] if text_col in df.columns else None
        except (IndexError, KeyError):
            skipped_rows += 1
            continue

        if is_service_row(text_value):
            skipped_rows += 1
            continue

        if is_radiator_product_row(text_value):
            product_name = str(text_value).replace("﻿", "").strip()
            radiator_detected += 1

            quantity = safe_numeric_value(row[qty_col]) if qty_col and qty_col in df.columns else 0.0
            revenue = safe_numeric_value(row[revenue_col]) if revenue_col and revenue_col in df.columns else 0.0
            gross_profit = safe_numeric_value(row[profit_col]) if profit_col and profit_col in df.columns else 0.0

            radiator_rows.append(
                {
                    "product_name": product_name,
                    "product_key": normalize_radiator_product_name(product_name),
                    qty_output_col: quantity,
                    revenue_output_col: revenue,
                    gross_profit_output_col: gross_profit,
                }
            )

            logger.debug(
                f"[{file_path.name}] Row {idx}: Radiator '{product_name[:60]}...', "
                f"Qty={quantity}, Revenue={revenue}, GrossProfit={gross_profit}"
            )
        else:
            skipped_rows += 1

    logger.info(
        f"[{file_path.name}] Found {radiator_detected} radiator product rows, "
        f"skipped {skipped_rows} rows"
    )

    if not radiator_rows:
        logger.warning(f"[{file_path.name}] No radiator product rows found")
        return pd.DataFrame()

    output_df = pd.DataFrame(radiator_rows)

    logger.info(
        f"[{file_path.name}] Raw radiator rows preview before aggregation:\n"
        + output_df.head(30).to_string()
    )

    aggregated = (
        output_df.groupby("product_key", as_index=False)
        .agg(
            {
                "product_name": "first",
                qty_output_col: "sum",
                revenue_output_col: "sum",
                gross_profit_output_col: "sum",
            }
        )
    )

    for col in [qty_output_col, revenue_output_col, gross_profit_output_col]:
        aggregated[col] = aggregated[col].round(2)

    logger.info(
        f"[{file_path.name}] Monthly radiator aggregation preview:\n"
        + aggregated.head(20).to_string()
    )

    logger.success(
        f"Radiator Margin Report adapted: {len(aggregated)} unique radiator products"
    )

    return aggregated