import re
from pathlib import Path
from typing import Optional

import pandas as pd
from loguru import logger

from app.normalization import normalize_product_name


# Whitelist rules for priority products (regex patterns)
WHITELIST_RULES = {
    "котлы": [
        # BAXI ECO NOVA
        r"^котел baxi eco\s*nova\s*10f$",
        r"^котел baxi eco\s*nova\s*14f$",
        r"^котел baxi eco\s*nova\s*18f$",
        r"^котел baxi eco\s*nova\s*24f$",

        # BAXI ECO 4S
        r"^котел baxi eco\s*4s\s*10\s*f$",
        r"^котел baxi eco\s*4s\s*18\s*f$",
        r"^котел baxi eco\s*4s\s*24$",
        r"^котел baxi eco\s*4s\s*24\s*f$",

        # BAXI ECO FOUR
        r"^котел baxi eco\s*four\s*24\s*f$",

        # Navien Deluxe C Coaxial
        r"^navien deluxe c coaxial 13k\s*2х контур\.?$",
        r"^navien deluxe c coaxial 16k\s*2х контур\.?$",
        r"^navien deluxe c coaxial 24k\s*2х контур\.?$",
        r"^navien deluxe c coaxial 30k\s*2х контур\.?$",
        r"^navien deluxe c coaxial 35k\s*2х контур\.?$",
        r"^navien deluxe c coaxial 40k\s*2х контур\.?$",

        # Navien Deluxe ONE
        r"^navien deluxe one 24k\s*1 контур\.?$",
        r"^navien deluxe one 30k\s*1 контур\.?$",

        # Navien Deluxe E Coaxial
        r"^navien deluxe e coaxial 10k\s*2х контур\.?$",
        r"^navien deluxe e coaxial 13k\s*2х контур\.?$",
        r"^navien deluxe e coaxial 16k\s*2х контур\.?$",
        r"^navien deluxe e coaxial 24k\s*2х контур\.?$",

        # Heatatmo
        r"^navien heatatmo ngb 150 24 a$",
    ],
    "газовые колонки": [
        r"genberg",
        r"inflame",
        r"ballu.*warmix.*gwh-10",
    ],
    "бойлеры": [
        r"ariston.*abs vls pro r",
        r"ariston.*abse vls pro pw",
        r"ariston.*nts fais",
        r"ariston.*nts",
        r"ariston.*pro 1 r v pl",
    ],
    "коаксиалы": [
        r"camino",
    ],
    # Насосы обрабатываем отдельно через точный size-key
    "насосы": [],
    "стабилизаторы": [
        r"^стабилизатор напряжения solpi-m tsd-500va$",
        r"^стабилизатор teplocom st-222/500$",
        r"^стабилизатор teplocom st-222/500-[иi]$",
        r"^стабилизатор teplocom st-555$",
        r"^стабилизатор teplocom st-555-[иi]$",
    ],
}

# Жёсткий список насосов, которые должны входить в закупочную логику
TARGET_UNIPUMP_PUMP_KEYS = {
    "unipump upc 25-40 130",
    "unipump upc 25-40 180",
    "unipump upc 25-60 130",
    "unipump upc 25-60 180",
    "unipump upc 25-80 180",
    "unipump upc 32-60 180",
    "unipump upc 32-80 180",
    "unipump cp 25-40 180",
    "unipump cp 25-60 130",
    "unipump cp 25-60 180",
}

UNIPUMP_PUMP_SIZE_PATTERN = re.compile(r"\b(25|32)-(40|60|80)\s*(130|180)\b")

# Patterns to detect radiator products (to exclude) - minimal set
RADIATOR_PATTERNS = [
    r"радиатор",
    r"\d{3}//\d{2}\*",  # e.g., 200//22*, 300//22*, 500//11*
]

# Service row prefixes (startswith check)
SERVICE_PREFIXES = [
    "период:",
    "показатели:",
    "группировки",
    "отборы",
    "покупатель",
    "заказ",
    "<объект",
]

# Service row exact matches
SERVICE_EXACT = [
    "итог",
    "итого",
    "всего",
]

# Column aliases for flexible detection
COLUMN_ALIASES = {
    "product": ["номенклатура", "товар", "наименование", "продукт", "продукция"],
    "quantity": ["ед. хранения", "количество", "кол-во", "qty", "единицы"],
}


def normalize_text(text: str) -> str:
    """
    Normalize text for comparison:
    - lowercase
    - strip whitespace
    - collapse duplicate spaces
    - normalize ё -> е
    """
    if pd.isna(text):
        return ""
    text = str(text).strip().lower()
    text = re.sub(r"\s+", " ", text)
    text = text.replace("ё", "е")
    return text


def extract_unipump_pump_key(value: str) -> str:
    """
    Extract canonical Unipump pump key, keeping UPC and CP as different models.
    Only the exact models from the agreed business list should pass further.
    """
    if pd.isna(value):
        return ""

    text = normalize_text(value)

    if "unipump" not in text or "насос" not in text:
        return ""

    text = text.replace("upс", "upc")  # кириллическая С
    text = text.replace("ср", "cp")
    text = text.replace("циркуляц.", "циркуляц")
    text = text.replace("(отопл.)", "")
    text = text.replace("(отопл)", "")
    text = text.replace("отопл.", "")
    text = text.replace("отопл", "")
    text = re.sub(r"\s+", " ", text).strip()

    if re.search(r"\bupc\b", text):
        model = "upc"
    elif re.search(r"\bcp\b", text):
        model = "cp"
    else:
        return ""

    match = UNIPUMP_PUMP_SIZE_PATTERN.search(text)
    if not match:
        return ""

    diameter, head, mount = match.groups()
    return f"unipump {model} {diameter}-{head} {mount}"


def is_service_row(value) -> bool:
    """
    Check if row value is a service/header row to skip.
    Uses startswith for prefixes and exact match for short keywords.
    """
    if pd.isna(value):
        return True

    value_lower = normalize_text(value)
    if value_lower == "":
        return True

    for prefix in SERVICE_PREFIXES:
        if value_lower.startswith(prefix):
            return True

    if value_lower in SERVICE_EXACT:
        return True

    return False


def is_radiator_row(value) -> bool:
    """
    Check if row contains a radiator product (to exclude).
    Matches radiator keyword or dimension patterns like 200//22*.
    """
    if pd.isna(value):
        return False

    value_str = str(value).strip()
    if value_str == "":
        return False

    value_lower = value_str.lower()

    if "радиатор" in value_lower:
        return True

    for pattern in RADIATOR_PATTERNS:
        if re.search(pattern, value_lower, re.IGNORECASE):
            return True

    return False


def is_excluded_nonstock_row(value) -> bool:
    """
    Exclude non-stock / service-like positions that should not enter procurement logic.
    """
    if pd.isna(value):
        return False

    value_lower = normalize_text(value)

    aggregate_exact = {
        "абсолют",
        "итог",
        "итого",
        "всего",
    }
    if value_lower in aggregate_exact:
        return True

    excluded_patterns = [
        r"ремонт",
        r"комплект",
        r"дымоход",
        r"переходн",
        r"форсунки",
        r"vivat",
        r"viessma",
        r"ariston,?vaillant",
        r"baxi \(кроме",
        r"для всех моделей",
    ]

    return any(re.search(pattern, value_lower, re.IGNORECASE) for pattern in excluded_patterns)


def is_whitelist_item(value) -> bool:
    """
    Check if product matches any whitelist rule.
    Returns True if product should be included.
    """
    if pd.isna(value):
        return False

    value_lower = normalize_text(value)

    # Сначала — жёсткая логика для насосов
    pump_key = extract_unipump_pump_key(value)
    if pump_key:
        if pump_key in TARGET_UNIPUMP_PUMP_KEYS:
            logger.debug(
                f"Whitelist match: '{str(value)[:50]}...' -> category 'насосы' via key '{pump_key}'"
            )
            return True
        return False

    # Потом — обычный whitelist для остальных групп
    for category, patterns in WHITELIST_RULES.items():
        for pattern in patterns:
            if re.search(pattern, value_lower, re.IGNORECASE):
                logger.debug(f"Whitelist match: '{str(value)[:50]}...' -> category '{category}'")
                return True

    return False


def safe_numeric_value(value) -> float:
    """
    Safely convert value to numeric, returning 0 if invalid.
    Handles Russian decimal comma format.
    """
    if pd.isna(value):
        return 0.0
    try:
        if isinstance(value, str):
            value = value.replace("\xa0", "").replace(" ", "").replace(",", ".").strip()
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def find_column_by_aliases(df: pd.DataFrame, aliases: list) -> Optional[str]:
    """Find column name matching any of the provided aliases."""
    for col in df.columns:
        if pd.isna(col):
            continue
        col_str = str(col).strip().lower()
        for alias in aliases:
            if alias in col_str:
                return col
    return None


def find_header_row(df: pd.DataFrame) -> Optional[int]:
    """
    Find the header row in the dataframe.

    Searches first 30 rows for a row that contains BOTH:
    - a product column indicator (номенклатура)
    - a quantity column indicator (ед. хранения)

    Returns:
        Index of header row, or None if not found
    """
    product_keywords = ["номенклатура", "товар", "наименование"]
    quantity_keywords = ["ед. хранения", "количество", "кол-во"]

    max_search_rows = min(30, len(df))

    for row_idx in range(max_search_rows):
        row_values = [
            normalize_text(v)
            for v in df.iloc[row_idx].tolist()
            if pd.notna(v)
        ]
        row_text = " ".join(row_values)

        has_product_col = any(kw in row_text for kw in product_keywords)
        has_quantity_col = any(kw in row_text for kw in quantity_keywords)

        if has_product_col and has_quantity_col:
            logger.debug(f"Found header row at index {row_idx}: {df.iloc[row_idx].tolist()}")
            return row_idx

    logger.warning("Could not find header row with both product and quantity columns")
    return None


def log_dataframe_debug(df: pd.DataFrame, stage: str, file_name: str):
    """Log debug information about DataFrame structure."""
    logger.debug(f"[{file_name}] {stage} - Shape: {df.shape}")
    logger.debug(f"[{file_name}] {stage} - Columns: {df.columns.tolist()}")
    if len(df) > 0:
        logger.debug(f"[{file_name}] {stage} - First 10 rows:\n{df.head(10).to_string()}")


def adapt_gross_profit_year_report(file_path: Path) -> pd.DataFrame:
    """
    Adapts gross profit year Excel report ("Валовая прибыль за год.xlsx").

    Reads hierarchical 1C report, filters whitelist products,
    excludes radiators, aggregates quantities by product.

    Output columns:
    - product_name: Raw product name
    - product_key: Normalized name for merging
    - gross_profit_year_qty: Total quantity sold (from "Ед. хранения")
    - avg_weekly_sales: gross_profit_year_qty / 52
    """
    logger.info(f"Adapting Gross Profit Year Report: {file_path.name}")

    if not file_path.exists():
        logger.warning(f"Gross profit year file not found: {file_path}")
        return pd.DataFrame()

    try:
        df = pd.read_excel(file_path, engine="openpyxl", header=None)
    except Exception as e:
        logger.error(f"Failed to read gross profit file {file_path.name}: {e}")
        return pd.DataFrame()

    if df.empty:
        logger.warning(f"[{file_path.name}] DataFrame is empty after reading")
        return pd.DataFrame()

    total_rows_read = len(df)
    logger.info(f"[{file_path.name}] Total rows read: {total_rows_read}")

    log_dataframe_debug(df, "After reading Excel", file_path.name)

    header_idx = find_header_row(df)

    if header_idx is not None:
        df.columns = df.iloc[header_idx].tolist()
        df = df[header_idx + 1:].reset_index(drop=True)
        logger.info(f"[{file_path.name}] Header found at row {header_idx}, trimmed dataframe")
    else:
        if df.iloc[0].notna().sum() > 2:
            df.columns = df.iloc[0].tolist()
            df = df[1:].reset_index(drop=True)
            logger.warning(f"[{file_path.name}] Using first row as header (fallback)")

    logger.info(f"[{file_path.name}] Final columns: {df.columns.tolist()}")
    log_dataframe_debug(df, "After header assignment", file_path.name)

    product_col = find_column_by_aliases(df, COLUMN_ALIASES["product"])
    quantity_col = find_column_by_aliases(df, COLUMN_ALIASES["quantity"])

    if product_col is None:
        logger.error(f"[{file_path.name}] Could not find product column. Available: {df.columns.tolist()}")
        return pd.DataFrame()

    if quantity_col is None:
        logger.error(
            f"[{file_path.name}] Could not find quantity column ('Ед. хранения'). "
            f"Available: {df.columns.tolist()}"
        )
        return pd.DataFrame()

    logger.info(f"[{file_path.name}] Using columns: product='{product_col}', quantity='{quantity_col}'")

    valid_rows = []
    service_rows_skipped = 0
    radiator_rows_skipped = 0
    whitelist_rejected = 0
    valid_products_found = 0

    for idx in range(len(df)):
        row = df.iloc[idx]

        try:
            product_value = row[product_col] if product_col in df.columns else None
        except (IndexError, KeyError):
            service_rows_skipped += 1
            continue

        if is_service_row(product_value):
            service_rows_skipped += 1
            continue

        if is_radiator_row(product_value):
            radiator_rows_skipped += 1
            continue

        if is_excluded_nonstock_row(product_value):
            whitelist_rejected += 1
            continue

        if not is_whitelist_item(product_value):
            whitelist_rejected += 1
            continue

        product_name = str(product_value).strip()
        valid_products_found += 1

        quantity = 0.0
        if quantity_col and quantity_col in df.columns:
            quantity = safe_numeric_value(row[quantity_col])

        valid_rows.append(
            {
                "product_name": product_name,
                "product_key": normalize_product_name(product_name),
                "gross_profit_year_qty": quantity,
            }
        )

        logger.debug(f"[{file_path.name}] Row {idx}: Valid product '{product_name[:50]}...', Qty: {quantity}")

    logger.info(f"[{file_path.name}] Processing summary:")
    logger.info(f"  - Total rows read: {total_rows_read}")
    logger.info(f"  - Service rows skipped: {service_rows_skipped}")
    logger.info(f"  - Radiator rows excluded: {radiator_rows_skipped}")
    logger.info(f"  - Non-whitelist rejected: {whitelist_rejected}")
    logger.info(f"  - Valid product rows found: {valid_products_found}")

    if not valid_rows:
        logger.warning(f"[{file_path.name}] No valid whitelist product rows found")
        logger.warning(f"[{file_path.name}] Whitelist categories: {list(WHITELIST_RULES.keys())}")
        return pd.DataFrame()

    output_df = pd.DataFrame(valid_rows)

    debug_skus = [
        "Ariston Abs Vls Pro R 100",
        "Teplocom ST-555-И",
        "Solpi-M TSD-500VA",
        "Unipump",
    ]
    for debug_sku in debug_skus:
        debug_mask = output_df["product_name"].astype(str).str.contains(debug_sku, case=False, na=False)
        if debug_mask.any():
            logger.info(
                f"[{file_path.name}][DEBUG] Matched rows for '{debug_sku}':\n"
                + output_df.loc[debug_mask].to_string()
            )

    pump_debug_mask = output_df["product_name"].astype(str).str.contains("unipump", case=False, na=False)
    if pump_debug_mask.any():
        pump_debug_df = output_df.loc[
            pump_debug_mask,
            ["product_name", "product_key", "gross_profit_year_qty"],
        ].copy()
        pump_debug_df["pump_model_key"] = pump_debug_df["product_name"].apply(extract_unipump_pump_key)

        logger.info(
            f"[{file_path.name}][DEBUG] Unipump rows after normalization:\n"
            + pump_debug_df.to_string()
        )

    aggregated = (
        output_df.groupby("product_key", as_index=False)
        .agg(
            product_name=("product_name", "first"),
            gross_profit_year_qty=("gross_profit_year_qty", "sum"),
        )
    )

    aggregated["avg_weekly_sales"] = aggregated["gross_profit_year_qty"] / 52.0

    for col in ["gross_profit_year_qty", "avg_weekly_sales"]:
        aggregated[col] = aggregated[col].round(2)

    final_columns = ["product_name", "product_key", "gross_profit_year_qty", "avg_weekly_sales"]
    aggregated = aggregated[final_columns]

    aggregated = aggregated[aggregated["product_key"] != ""]

    unique_products = aggregated["product_key"].nunique()
    total_qty = aggregated["gross_profit_year_qty"].sum()

    logger.info(f"[{file_path.name}] Aggregation complete: {unique_products} unique products, total qty: {total_qty}")
    logger.success(f"Gross Profit Year Report adapted: {len(aggregated)} whitelist products")

    return aggregated