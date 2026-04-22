import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
from loguru import logger

# 1C hierarchical export: the second column usually contains
# customer / order / product text.
HIERARCHY_COLUMN_IDX = 1

# Metric columns by positional indices in raw Excel row.
METRIC_COLUMN_INDICES = {
    "sale_amount": 2,
    "cost": 3,
    "profit": 4,
    "expense_amount": 5,
    "net_profit": 6,
    "planned_cost": 7,
    "planned_profit": 8,
}

# In some 1C exports quantity is stored outside the main financial metric block.
# We therefore try a few explicit candidate columns first, then fall back to a
# heuristic scan of the whole row.
QUANTITY_CANDIDATE_INDICES = [0, 9, 10, 11, 12, 13, 14]

SERVICE_PREFIXES = [
    "период",
    "показатели",
    "группировки",
    "отборы",
    "номенклатура",
    "покупатель",
]

SERVICE_EXACT = {
    "",
    "итог",
    "итого",
    "всего",
}

CUSTOMER_INDICATORS = ["ооо", "ип", "ао", "зао", "пао"]

PRODUCT_PATTERNS = [
    r"(котел|радиатор|колонка|бойлер|труба|муфта|отвод|кран|фильтр|колено|насос|удлинение|манжета|грибок|дюбель|прокладк)",
    r"(baxi|bosch|royal thermo|лемакс|viterm|navien|valfex|aquatec|eco nova|eco life|turbo|classic|сиберия|kermi|koer|rens|unipump)",
    r"\d+//\d+\*\d+",
    r"\d+\s*[xх*]\s*\d+",
    r"\(\d+,\d+\)\s*$",
    r"^\d{3,}([\-\/\s]\d+)*$",
    r"\b(vc|vcu|vk|c11|c22|c33)\b",
]


FIO_PATTERNS = [
    r"^[А-ЯЁ][а-яё]+ [А-ЯЁ][а-яё]+$",
    r"^[А-ЯЁ][а-яё]+ [А-ЯЁ][а-яё]+ [А-ЯЁ][а-яё]+$",
    r"^[А-ЯЁ][а-яё]+ [А-ЯЁ]\.[А-ЯЁ]\.$",
    r"^[А-ЯЁ][а-яё]+ [А-ЯЁ]\.[А-ЯЁ]\.,?\s*ИП$",
]


def detect_quantity_column_index(df: pd.DataFrame) -> Optional[int]:
    """
    Try to detect a real quantity column from the service/header rows of the raw 1C export.

    We scan the first rows for cells containing markers like:
    - "Количество"
    - "Кол-во"
    - "В ед. хранения"
    - "Ед. хранения"

    If found, return that column index so product rows can read quantity from the
    correct physical column instead of relying only on heuristics.
    """
    quantity_markers = [
        "количество",
        "кол-во",
        "в ед. хранения",
        "ед. хранения",
    ]

    search_limit = min(len(df), 25)
    for row_idx in range(search_limit):
        row = df.iloc[row_idx]
        for col_idx in range(len(row)):
            cell_value = row.iloc[col_idx]
            cell_text = normalize_text(cell_value)
            if not cell_text:
                continue
            if any(marker in cell_text for marker in quantity_markers):
                logger.info(
                    f"Detected quantity column candidate in header area: row={row_idx}, col={col_idx}, value='{cell_value}'"
                )
                return col_idx

    logger.warning("Could not detect quantity column from header rows; will use heuristic extraction only")
    return None


def normalize_text(text) -> str:
    if pd.isna(text):
        return ""
    value = str(text).strip().lower()
    value = re.sub(r"\s+", " ", value)
    value = value.replace("ё", "е")
    return value


def normalize_product_name(name) -> str:
    return normalize_text(name)


def normalize_customer_name(name) -> str:
    return normalize_text(name)


def extract_date_from_order_text(text) -> Optional[datetime]:
    if pd.isna(text):
        return None
    value = str(text)
    date_match = re.search(r"(\d{2}\.\d{2}\.\d{4})", value)
    if date_match:
        try:
            return datetime.strptime(date_match.group(1), "%d.%m.%Y")
        except Exception:
            return None
    return None


def safe_numeric_value(value) -> float:
    if pd.isna(value):
        return 0.0
    try:
        if isinstance(value, str):
            value = value.replace(" ", "").replace(",", ".").strip()
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def _is_quantity_like(value: float) -> bool:
    if value <= 0:
        return False
    if value > 10000:
        return False
    return abs(value - round(value)) < 1e-6



def extract_quantity_from_row(row: pd.Series, quantity_column_idx: Optional[int] = None) -> float:
    """
    Best-effort quantity extraction for hierarchical 1C sales export.

    Strategy:
    1. If a quantity column was detected from header rows, use it first.
    2. Check several explicit candidate columns that often contain quantity.
    3. If nothing found, scan the whole row and pick a small integer-like value
       that is not one of the already parsed financial metrics.
    """
    metric_values = []
    for metric_idx in METRIC_COLUMN_INDICES.values():
        if metric_idx < len(row):
            metric_values.append(safe_numeric_value(row.iloc[metric_idx]))

    # Step 1: detected header-based quantity column
    if quantity_column_idx is not None and quantity_column_idx < len(row) and quantity_column_idx != HIERARCHY_COLUMN_IDX:
        value = safe_numeric_value(row.iloc[quantity_column_idx])
        if _is_quantity_like(value):
            return float(round(value))

    # Step 2: preferred candidate columns
    for idx in QUANTITY_CANDIDATE_INDICES:
        if idx >= len(row) or idx == HIERARCHY_COLUMN_IDX:
            continue
        value = safe_numeric_value(row.iloc[idx])
        if _is_quantity_like(value):
            return float(round(value))

    # Step 3: heuristic scan of the full row
    best_candidate = 0.0
    best_priority = None

    for idx in range(len(row)):
        if idx == HIERARCHY_COLUMN_IDX:
            continue

        value = safe_numeric_value(row.iloc[idx])
        if not _is_quantity_like(value):
            continue

        # Skip values that are actually one of the money metrics.
        if any(abs(value - metric_value) < 1e-6 for metric_value in metric_values if metric_value != 0):
            continue

        # Prefer columns closer to the financial block, because quantity in 1C
        # often sits just before or just after money columns.
        priority = abs(idx - 2)
        if best_priority is None or priority < best_priority:
            best_candidate = float(round(value))
            best_priority = priority

    return best_candidate


def log_dataframe_debug(df: pd.DataFrame, stage: str, file_name: str) -> None:
    logger.debug(f"[{file_name}] {stage} - Shape: {df.shape}")
    logger.debug(f"[{file_name}] {stage} - Columns: {df.columns.tolist()}")
    if not df.empty:
        logger.debug(f"[{file_name}] {stage} - First 15 rows:\n{df.head(15).to_string()}")


def get_hierarchy_value(row: pd.Series) -> str:
    try:
        value = row.iloc[HIERARCHY_COLUMN_IDX]
        if pd.isna(value):
            return ""
        return str(value).strip()
    except Exception:
        return ""


def is_service_row(value: str) -> bool:
    if value is None:
        return True

    value_str = str(value).strip()
    if value_str == "":
        return True

    value_lower = normalize_text(value_str)

    if value_lower in SERVICE_EXACT:
        return True

    for prefix in SERVICE_PREFIXES:
        if value_lower.startswith(prefix):
            return True

    return False


def is_order_row(value: str) -> bool:
    if not value:
        return False
    value_lower = normalize_text(value)
    return "заказ покупателя" in value_lower


def looks_like_product(value: str) -> bool:
    if not value:
        return False

    value_str = str(value).strip()
    value_lower = normalize_text(value_str)

    for pattern in PRODUCT_PATTERNS:
        if re.search(pattern, value_lower):
            return True

    # Long descriptive strings in 1C are often product names.
    if len(value_str) >= 25:
        return True

    return False


def is_customer_row(value: str) -> bool:
    if not value:
        return False

    value_str = str(value).strip()
    value_lower = normalize_text(value_str)

    if is_service_row(value_str):
        return False

    if is_order_row(value_str):
        return False

    if looks_like_product(value_str):
        return False

    for indicator in CUSTOMER_INDICATORS:
        if re.search(rf"\b{re.escape(indicator)}\b", value_lower):
            return True

    for pattern in FIO_PATTERNS:
        if re.match(pattern, value_str):
            return True

    return False



def extract_metrics_from_row(row: pd.Series, quantity_column_idx: Optional[int] = None) -> dict:
    sale_amount = 0.0
    cost = 0.0
    profit = 0.0
    expense_amount = 0.0
    net_profit = 0.0
    planned_cost = 0.0
    planned_profit = 0.0

    try:
        if METRIC_COLUMN_INDICES["sale_amount"] < len(row):
            sale_amount = safe_numeric_value(row.iloc[METRIC_COLUMN_INDICES["sale_amount"]])
        if METRIC_COLUMN_INDICES["cost"] < len(row):
            cost = safe_numeric_value(row.iloc[METRIC_COLUMN_INDICES["cost"]])
        if METRIC_COLUMN_INDICES["profit"] < len(row):
            profit = safe_numeric_value(row.iloc[METRIC_COLUMN_INDICES["profit"]])
        if METRIC_COLUMN_INDICES["expense_amount"] < len(row):
            expense_amount = safe_numeric_value(row.iloc[METRIC_COLUMN_INDICES["expense_amount"]])
        if METRIC_COLUMN_INDICES["net_profit"] < len(row):
            net_profit = safe_numeric_value(row.iloc[METRIC_COLUMN_INDICES["net_profit"]])
        if METRIC_COLUMN_INDICES["planned_cost"] < len(row):
            planned_cost = safe_numeric_value(row.iloc[METRIC_COLUMN_INDICES["planned_cost"]])
        if METRIC_COLUMN_INDICES["planned_profit"] < len(row):
            planned_profit = safe_numeric_value(row.iloc[METRIC_COLUMN_INDICES["planned_profit"]])
    except Exception:
        pass

    if net_profit == 0.0:
        net_profit = profit - expense_amount

    quantity = extract_quantity_from_row(row, quantity_column_idx=quantity_column_idx)

    return {
        "sale_amount": sale_amount,
        "cost": cost,
        "profit": profit,
        "expense_amount": expense_amount,
        "net_profit": net_profit,
        "planned_cost": planned_cost,
        "planned_profit": planned_profit,
        "quantity": quantity,
    }


def adapt_sales_report_for_pdf(file_path: Path) -> pd.DataFrame:
    logger.info(f"Adapting Sales Report for PDF: {file_path.name}")

    if not file_path.exists():
        logger.error(f"[{file_path.name}] File does not exist: {file_path}")
        return pd.DataFrame()

    try:
        df = pd.read_excel(file_path, engine="openpyxl", header=None)
    except Exception as exc:
        logger.error(f"Failed to read Sales PDF file {file_path.name}: {exc}")
        return pd.DataFrame()

    if df.empty:
        logger.error(f"[{file_path.name}] DataFrame is empty immediately after reading")
        return pd.DataFrame()

    log_dataframe_debug(df, "After reading Excel", file_path.name)
    quantity_column_idx = detect_quantity_column_index(df)
    logger.info(f"[{file_path.name}] Quantity column index for PDF parsing: {quantity_column_idx}")

    current_customer = None
    current_order = None
    current_order_date = None

    customer_rows_detected = 0
    order_rows_detected = 0
    product_rows_detected = 0
    skipped_rows = 0
    ambiguous_rows = 0
    product_rows_without_customer = 0

    parsed_rows = []

    for idx in range(len(df)):
        row = df.iloc[idx]
        hierarchy_value = get_hierarchy_value(row)

        if hierarchy_value == "":
            skipped_rows += 1
            continue

        # 1. Order row
        if is_order_row(hierarchy_value):
            current_order = hierarchy_value
            current_order_date = extract_date_from_order_text(hierarchy_value)
            order_rows_detected += 1

            parsed_rows.append(
                {
                    "row_type": "order",
                    "sale_date": current_order_date,
                    "customer_name": current_customer,
                    "customer_order": current_order,
                    "product_name": None,
                    "sale_amount": 0.0,
                    "cost": 0.0,
                    "profit": 0.0,
                    "expense_amount": 0.0,
                    "net_profit": 0.0,
                    "planned_cost": 0.0,
                    "planned_profit": 0.0,
                    "quantity": 0.0,
                    "product_key": "",
                    "customer_key": normalize_customer_name(current_customer),
                }
            )

            logger.debug(f"[{file_path.name}] Row {idx}: Order detected: {current_order}")
            continue

        if is_service_row(hierarchy_value):
            skipped_rows += 1
            continue

        # 2. Customer row
        if is_customer_row(hierarchy_value):
            current_customer = str(hierarchy_value).strip()
            current_order = None
            current_order_date = None
            customer_rows_detected += 1

            metrics = extract_metrics_from_row(row, quantity_column_idx=quantity_column_idx)

            parsed_rows.append(
                {
                    "row_type": "customer",
                    "sale_date": None,
                    "customer_name": current_customer,
                    "customer_order": None,
                    "product_name": None,
                    "sale_amount": metrics["sale_amount"],
                    "cost": metrics["cost"],
                    "profit": metrics["profit"],
                    "expense_amount": metrics["expense_amount"],
                    "net_profit": metrics["net_profit"],
                    "planned_cost": metrics["planned_cost"],
                    "planned_profit": metrics["planned_profit"],
                    "quantity": metrics["quantity"],
                    "product_key": "",
                    "customer_key": normalize_customer_name(current_customer),
                }
            )

            logger.debug(f"[{file_path.name}] Row {idx}: Customer detected: {current_customer}")
            continue

        # 3. Product row
        # Important difference from main sales_adapter:
        # product row requires customer context, but DOES NOT require order context.
        if current_customer is None:
            product_rows_without_customer += 1
            skipped_rows += 1
            logger.debug(
                f"[{file_path.name}] Row {idx}: Product-like row without customer context, skipping: {hierarchy_value}"
            )
            continue

        if not looks_like_product(hierarchy_value):
            ambiguous_rows += 1
            skipped_rows += 1
            logger.debug(
                f"[{file_path.name}] Row {idx}: Ambiguous non-product row under customer context, skipping: {hierarchy_value}"
            )
            continue

        product_name = hierarchy_value
        product_rows_detected += 1
        metrics = extract_metrics_from_row(row, quantity_column_idx=quantity_column_idx)

        parsed_rows.append(
            {
                "row_type": "product",
                "sale_date": current_order_date,
                "customer_name": current_customer,
                "customer_order": current_order,
                "product_name": product_name,
                "sale_amount": metrics["sale_amount"],
                "cost": metrics["cost"],
                "profit": metrics["profit"],
                "expense_amount": metrics["expense_amount"],
                "net_profit": metrics["net_profit"],
                "planned_cost": metrics["planned_cost"],
                "planned_profit": metrics["planned_profit"],
                "quantity": metrics["quantity"],
                "product_key": normalize_product_name(product_name),
                "customer_key": normalize_customer_name(current_customer),
            }
        )

        logger.debug(
            f"[{file_path.name}] Row {idx}: Product row: '{product_name[:60]}...', "
            f"customer='{str(current_customer)[:40]}...', qty={metrics['quantity']}, amount={metrics['sale_amount']}"
        )

    logger.info(f"[{file_path.name}] PDF parser summary:")
    logger.info(f"[{file_path.name}]   Customer rows detected: {customer_rows_detected}")
    logger.info(f"[{file_path.name}]   Order rows detected: {order_rows_detected}")
    logger.info(f"[{file_path.name}]   Product rows detected: {product_rows_detected}")
    logger.info(f"[{file_path.name}]   Skipped rows: {skipped_rows}")
    logger.info(f"[{file_path.name}]   Ambiguous rows skipped: {ambiguous_rows}")
    logger.info(f"[{file_path.name}]   Product rows without customer: {product_rows_without_customer}")

    if not parsed_rows:
        logger.error(f"[{file_path.name}] No rows collected")
        logger.error(f"[{file_path.name}] First 20 rows of raw data:\n{df.head(20).to_string()}")
        return pd.DataFrame()

    output_df = pd.DataFrame(parsed_rows)

    product_df = output_df[output_df["row_type"] == "product"].copy()
    customer_df = output_df[output_df["row_type"] == "customer"].copy()

    if product_df.empty:
        logger.warning(f"[{file_path.name}] No product rows found in PDF sales adapter output")

    unique_products = product_df["product_key"].nunique() if not product_df.empty else 0
    total_sale_amount = product_df["sale_amount"].sum() if not product_df.empty else 0.0
    total_quantity = product_df["quantity"].sum() if not product_df.empty else 0.0

    if unique_products <= 1 and not product_df.empty:
        logger.warning(
            f"[{file_path.name}] Suspicious product_key cardinality: unique_products={unique_products}"
        )

    logger.info(
        f"[{file_path.name}] Final parsed rows: customers={len(customer_df)}, products={len(product_df)}"
    )
    logger.info(
        f"[{file_path.name}] Product statistics: total_amount={total_sale_amount:.2f}, "
        f"total_quantity={total_quantity:.2f}, unique_products={unique_products}"
    )
    if not product_df.empty:
        qty_non_zero = int((product_df["quantity"] > 0).sum())
        logger.info(
            f"[{file_path.name}] Quantity diagnostics: non_zero_product_rows={qty_non_zero}, "
            f"zero_product_rows={len(product_df) - qty_non_zero}"
        )
    logger.info(
        f"[{file_path.name}] Customer statistics: total_customer_amount={customer_df['sale_amount'].sum():.2f}, "
        f"unique_customers={customer_df['customer_key'].nunique() if not customer_df.empty else 0}"
    )

    if not product_df.empty:
        diagnostic_cols = ["product_name", "product_key", "quantity", "sale_amount", "customer_order"]
        logger.debug(
            f"[{file_path.name}] First 20 product rows:\n"
            f"{product_df[diagnostic_cols].head(20).to_string(index=False)}"
        )
        logger.debug(
            f"[{file_path.name}] Top 20 product_key counts:\n"
            f"{product_df['product_key'].value_counts().head(20).to_string()}"
        )

    log_dataframe_debug(output_df, "Final output DataFrame", file_path.name)

    logger.success(
        f"Sales Report for PDF adapted: {len(product_df)} product rows, {len(customer_df)} customer rows."
    )

    return output_df