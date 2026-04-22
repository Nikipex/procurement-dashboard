import pandas as pd
from pathlib import Path
from loguru import logger
import re
from datetime import datetime

# Positional structure in 1C export
HIERARCHY_COLUMN_IDX = 1

# Metric columns by position in raw Excel row
# Important: quantity is often absent in this report, so we handle it conservatively
METRIC_COLUMN_INDICES = {
    "sale_amount": 2,
    "cost": 3,
    "profit": 4,
    "expense_amount": 5,
    "net_profit": 6,       # if present in export
    "planned_cost": 7,
    "planned_profit": 8,
}

SERVICE_PREFIXES = [
    "Период:",
    "Показатели:",
    "Группировки строк:",
    "Отборы:",
    "Период",
    "Показатели",
    "Группировки",
    "Отборы",
    "Итого",
    "Всего",
    "Покупатель",
    "Заказ покупателя",
    "Номенклатура",
]


def normalize_product_name(name) -> str:
    if pd.isna(name):
        return ""
    name = str(name).strip().lower()
    name = re.sub(r"\s+", " ", name)
    name = name.replace("ё", "е")
    return name


def normalize_customer_name(name) -> str:
    if pd.isna(name):
        return ""
    name = str(name).strip()
    name = re.sub(r"\s+", " ", name)
    return name


def extract_date_from_order_text(text) -> datetime:
    if pd.isna(text):
        return None
    text = str(text)
    date_match = re.search(r"(\d{2}\.\d{2}\.\d{4})", text)
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
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def log_dataframe_debug(df: pd.DataFrame, stage: str, file_name: str):
    logger.debug(f"[{file_name}] {stage} - Shape: {df.shape}")
    logger.debug(f"[{file_name}] {stage} - Columns: {df.columns.tolist()}")
    logger.debug(f"[{file_name}] {stage} - First 15 rows:\n{df.head(15).to_string()}")


def get_hierarchy_value(row) -> str:
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

    value_lower = value_str.lower()
    for prefix in SERVICE_PREFIXES:
        if value_lower == prefix.lower():
            return True
        if value_lower.startswith(prefix.lower()):
            return True

    return False


def is_order_row(value: str) -> bool:
    if not value:
        return False
    return str(value).strip().startswith("Заказ покупателя")


def looks_like_product_row(value: str) -> bool:
    """
    Detect likely product / technical rows.
    """
    if not value:
        return False

    value_str = str(value).strip()
    low = value_str.lower()

    product_patterns = [
        r"(котел|радиатор|колонка|бойлер|труба|муфта|отвод|кран|фильтр|колено|насос|удлинение|манжета|грибок|дюбель|прокладк)",
        r"(baxi|bosch|royal thermo|лемакс|viterm|navien|valfex|aquatec|eco nova|eco life|turbo|classic|сиберия)",
        r"\d+//\d+\*\d+",
        r"\(\d+,\d+\)\s*$",
        r"^\d{3,}([\-\/\s]\d+)*$",
    ]

    for pattern in product_patterns:
        if re.search(pattern, low):
            return True

    # very long descriptive strings are usually products
    if len(value_str) > 35:
        return True

    return False


def looks_like_customer_name(value: str) -> bool:
    if not value:
        return False

    value_str = str(value).strip()

    if len(value_str) < 4:
        return False

    if looks_like_product_row(value_str):
        return False

    # Typical customer markers
    customer_patterns = [
        r"\b(ИП|ООО|ОАО|ПАО|АО|ЗАО)\b",
        r"[А-ЯЁ][а-яё]+ [А-ЯЁ][а-яё]+",
        r"[A-Z][a-z]+ [A-Z][a-z]+",
    ]

    for pattern in customer_patterns:
        if re.search(pattern, value_str):
            return True

    return False


def extract_metrics_from_row(row) -> dict:
    """
    Extract financial metrics from row by positional indices.
    Quantity in this report is unreliable / often absent, so we do not force it.
    """
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

    # fallback if explicit net profit column is empty
    if net_profit == 0.0:
        net_profit = profit - expense_amount

    return {
        "sale_amount": sale_amount,
        "cost": cost,
        "profit": profit,
        "expense_amount": expense_amount,
        "net_profit": net_profit,
        "planned_cost": planned_cost,
        "planned_profit": planned_profit,
    }


def find_next_meaningful_value(df: pd.DataFrame, start_idx: int) -> str:
    """
    Look ahead to the next non-empty, non-service hierarchy value.
    """
    for j in range(start_idx + 1, len(df)):
        next_value = get_hierarchy_value(df.iloc[j])
        if next_value == "":
            continue
        if is_service_row(next_value):
            continue
        return next_value
    return ""


def adapt_sales_report(file_path: Path) -> pd.DataFrame:
    logger.info(f"Adapting Sales Report: {file_path.name}")

    try:
        # Read raw file without headers
        df = pd.read_excel(file_path, engine="openpyxl", header=None)
    except Exception as e:
        logger.error(f"Failed to read Sales file {file_path.name}: {e}")
        return pd.DataFrame()

    if df.empty:
        logger.error(f"[{file_path.name}] DataFrame is empty immediately after reading")
        return pd.DataFrame()

    log_dataframe_debug(df, "After reading Excel", file_path.name)

    current_customer = None
    current_order = None
    current_order_date = None

    customer_rows_detected = 0
    order_rows_detected = 0
    product_rows_detected = 0
    service_rows_skipped = 0
    product_rows_without_context = 0

    parsed_rows = []

    for idx in range(len(df)):
        row = df.iloc[idx]
        hierarchy_value = get_hierarchy_value(row)

        if hierarchy_value == "" or is_service_row(hierarchy_value):
            service_rows_skipped += 1
            continue

        next_value = find_next_meaningful_value(df, idx)

        # 1) Order row
        if is_order_row(hierarchy_value):
            current_order = hierarchy_value
            current_order_date = extract_date_from_order_text(hierarchy_value)
            order_rows_detected += 1
            logger.debug(f"[{file_path.name}] Row {idx}: Order detected: {current_order}")
            continue

        # 2) Customer row
        # Main rule: if next meaningful row is an order row, current row is customer
        # Backup: explicit customer-like text
        if is_order_row(next_value) or (looks_like_customer_name(hierarchy_value) and not looks_like_product_row(hierarchy_value)):
            current_customer = normalize_customer_name(hierarchy_value)
            current_order = None
            current_order_date = None
            customer_rows_detected += 1

            metrics = extract_metrics_from_row(row)

            parsed_rows.append({
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
                "quantity": 0.0,
                "product_key": "",
                "customer_key": normalize_customer_name(current_customer).lower(),
            })

            logger.debug(f"[{file_path.name}] Row {idx}: Customer detected: {current_customer}")
            continue

        # 3) Product row
        if current_customer is None or current_order is None:
            logger.debug(f"[{file_path.name}] Row {idx}: Product row without customer/order context, skipping: {hierarchy_value}")
            product_rows_without_context += 1
            continue

        product_name = hierarchy_value
        product_rows_detected += 1
        metrics = extract_metrics_from_row(row)

        parsed_rows.append({
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
            "quantity": 0.0,
            "product_key": normalize_product_name(product_name),
            "customer_key": normalize_customer_name(current_customer).lower(),
        })

        logger.debug(
            f"[{file_path.name}] Row {idx}: Product row: '{product_name[:60]}...', "
            f"customer='{current_customer[:40]}...', amount={metrics['sale_amount']}"
        )

    logger.info(f"[{file_path.name}] State machine complete:")
    logger.info(f"[{file_path.name}]   Customer rows detected: {customer_rows_detected}")
    logger.info(f"[{file_path.name}]   Order rows detected: {order_rows_detected}")
    logger.info(f"[{file_path.name}]   Product rows detected: {product_rows_detected}")
    logger.info(f"[{file_path.name}]   Service rows skipped: {service_rows_skipped}")
    logger.info(f"[{file_path.name}]   Product rows without context: {product_rows_without_context}")

    if not parsed_rows:
        logger.error(f"[{file_path.name}] No rows collected")
        logger.error(f"[{file_path.name}] First 20 rows of raw data:\n{df.head(20).to_string()}")
        return pd.DataFrame()

    output_df = pd.DataFrame(parsed_rows)

    # Clean product rows with empty product_key
    product_mask = output_df["row_type"] == "product"
    empty_product_keys = ((output_df["product_key"] == "") & product_mask).sum()
    if empty_product_keys > 0:
        logger.debug(f"[{file_path.name}] Removing {empty_product_keys} product rows with empty product_key")
        output_df = output_df[~((output_df["row_type"] == "product") & (output_df["product_key"] == ""))]

    if output_df.empty:
        logger.error(f"[{file_path.name}] Output DataFrame is empty after cleanup")
        return pd.DataFrame()

    log_dataframe_debug(output_df, "Final output DataFrame", file_path.name)

    product_df = output_df[output_df["row_type"] == "product"].copy()
    customer_df = output_df[output_df["row_type"] == "customer"].copy()

    logger.info(
        f"[{file_path.name}] Final parsed rows: "
        f"customers={len(customer_df)}, products={len(product_df)}"
    )

    logger.info(
        f"[{file_path.name}] Product statistics: "
        f"total_amount={product_df['sale_amount'].sum():.2f}, "
        f"unique_products={product_df['product_key'].nunique() if not product_df.empty else 0}"
    )

    logger.info(
        f"[{file_path.name}] Customer statistics: "
        f"total_customer_amount={customer_df['sale_amount'].sum():.2f}, "
        f"unique_customers={customer_df['customer_key'].nunique() if not customer_df.empty else 0}"
    )

    logger.success(
        f"Sales Report adapted: {len(product_df)} product rows, "
        f"{len(customer_df)} customer rows."
    )

    return output_df