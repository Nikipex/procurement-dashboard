import pandas as pd
from pathlib import Path
from loguru import logger
import re

from app.normalization import normalize_product_name

# Target Warehouse (MVP fallback)
TARGET_WAREHOUSE = "ЮЖНЫЙ склад"

# Column indices (0-based)
PRODUCT_COLUMN_IDX = 1  # Second column contains product names

# Metric column mapping within a 6-column warehouse block
METRIC_MAPPING = {
    "sold_qty_60d": 0,
    "days_sold": 1,
    "avg_daily_sales_1c": 2,
    "stock_at_purchase_start": 3,
    "required_purchase_qty_1c": 4,
    "planned_sales_qty": 5
}

# Service rows to skip
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
    "<Объект не найден>",
    "<Объект>",
]

def normalize_text(text) -> str:
    """
    Normalize text for comparison:
    - strip whitespace
    - lowercase
    - collapse duplicate spaces
    """
    if pd.isna(text):
        return ""
    text = str(text).strip().lower()
    text = re.sub(r'\s+', ' ', text)
    return text


def is_service_row(value) -> bool:
    """Check if row value is a service/header row to skip."""
    if pd.isna(value):
        return False
    value_str = str(value).strip()
    if value_str == "":
        return True
    value_normalized = normalize_text(value_str)
    for prefix in SERVICE_PREFIXES:
        if value_normalized.startswith(normalize_text(prefix)):
            return True
    return False

def is_valid_product_row(value) -> bool:
    """
    Check if row is a valid product row.
    - Not a service row
    - Has a meaningful product name
    """
    if pd.isna(value):
        return False
    value_str = str(value).strip()
    if value_str == "":
        return False
    if is_service_row(value):
        return False
    # Product name should have some content
    if len(value_str) < 2:
        return False
    return True

def safe_numeric_value(value) -> float:
    """
    Safely convert value to numeric, returning 0 if invalid.
    """
    if pd.isna(value):
        return 0.0
    try:
        if isinstance(value, str):
            value = value.replace('\xa0', '').replace(' ', '').replace(',', '.').strip()
        return float(value)
    except (ValueError, TypeError):
        return 0.0

def log_dataframe_debug(df: pd.DataFrame, stage: str, file_name: str):
    """Log debug information about DataFrame structure."""
    logger.debug(f"[{file_name}] {stage} - Shape: {df.shape}")
    logger.debug(f"[{file_name}] {stage} - Columns: {df.columns.tolist()}")
    logger.debug(f"[{file_name}] {stage} - First 15 rows:\n{df.head(15).to_string()}")

def find_metric_block(df: pd.DataFrame, file_name: str) -> dict:
    """
    Find the first meaningful 6-column metric block in the dataframe.
    Uses pragmatic MVP fallback: select first block with numeric values for product rows.
    
    Returns:
        dict with 'start_col' and 'end_col' indices for the selected block
    """
    if len(df.columns) < 7:  # Need at least product column + 6 metric columns
        logger.error(f"[{file_name}] Not enough columns for metric block. Need at least 7, have {len(df.columns)}")
        return None
    
    total_columns = len(df.columns)
    candidate_blocks = []
    
    # Scan for 6-column blocks starting after product column (index 1)
    # Block can start from column index 2 onwards
    for start_col in range(2, total_columns - 5):
        end_col = start_col + 6
        if end_col > total_columns:
            break
        
        # Check if this block has numeric values in product rows
        numeric_count = 0
        sample_rows_checked = 0
        
        for idx in range(min(20, len(df))):  # Check first 20 rows
            row = df.iloc[idx]
            product_value = row.iloc[PRODUCT_COLUMN_IDX] if PRODUCT_COLUMN_IDX < len(row) else None
            
            # Only check rows that look like products
            if is_valid_product_row(product_value):
                sample_rows_checked += 1
                # Count numeric values in the 6-column block
                for col_idx in range(start_col, end_col):
                    if col_idx < len(row):
                        val = row.iloc[col_idx]
                        if pd.notna(val):
                            try:
                                float(val)
                                numeric_count += 1
                            except (ValueError, TypeError):
                                pass
        
        if sample_rows_checked > 0 and numeric_count > 0:
            candidate_blocks.append({
                "start_col": start_col,
                "end_col": end_col,
                "numeric_count": numeric_count,
                "sample_rows": sample_rows_checked
            })
            logger.debug(f"[{file_name}] Candidate block found: columns {start_col}-{end_col}, numeric values: {numeric_count}, product rows: {sample_rows_checked}")
    
    if not candidate_blocks:
        logger.warning(f"[{file_name}] No candidate metric blocks found with numeric values")
        # Fallback: use first available 6-column block after product column
        if total_columns >= 7:
            fallback_block = {
                "start_col": 2,
                "end_col": 8,
                "numeric_count": 0,
                "sample_rows": 0
            }
            logger.warning(f"[{file_name}] Using fallback block: columns {fallback_block['start_col']}-{fallback_block['end_col']}")
            return fallback_block
        return None
    
    # Select the block with most numeric values (most likely to be the main warehouse)
    selected_block = max(candidate_blocks, key=lambda x: x["numeric_count"])
    logger.info(f"[{file_name}] Selected metric block: columns {selected_block['start_col']}-{selected_block['end_col']}, numeric values: {selected_block['numeric_count']}")
    
    return selected_block

def adapt_planning_report(file_path: Path) -> pd.DataFrame:
    """
    Adapts raw 1C Planning Excel report ("Планирование закупок.xlsx").
    Uses row-based parsing with pragmatic MVP fallback for warehouse block detection.
    """
    logger.info(f"Adapting Planning Report: {file_path.name}")
    
    try:
        # Read without header to capture all rows including metric labels
        df = pd.read_excel(file_path, engine="openpyxl", header=None)
    except Exception as e:
        logger.error(f"Failed to read Planning file {file_path.name}: {e}")
        return pd.DataFrame()

    if df.empty:
        logger.error(f"[{file_path.name}] DataFrame is empty immediately after reading")
        return df

    # DEBUG: Log initial structure
    log_dataframe_debug(df, "After reading Excel", file_path.name)
    logger.debug(f"[{file_path.name}] Total columns detected: {len(df.columns)}")
    logger.debug(f"[{file_path.name}] Using PRODUCT_COLUMN_IDX={PRODUCT_COLUMN_IDX}")

    # Set column names based on first row
    if len(df) > 0:
        df.columns = df.iloc[0].tolist()
        df = df[1:].reset_index(drop=True)
    
    # DEBUG: Log structure after setting headers
    log_dataframe_debug(df, "After setting headers from row 0", file_path.name)

    # Check if we have enough columns for product column
    if len(df.columns) <= PRODUCT_COLUMN_IDX:
        logger.error(f"[{file_path.name}] Not enough columns for product access. Need at least {PRODUCT_COLUMN_IDX + 1} columns, have {len(df.columns)}")
        logger.error(f"[{file_path.name}] Available columns: {df.columns.tolist()}")
        return pd.DataFrame()

    # Find metric block
    metric_block = find_metric_block(df, file_path.name)
    
    if metric_block is None:
        logger.error(f"[{file_path.name}] Could not find metric block for warehouse data")
        logger.error(f"[{file_path.name}] First 15 rows of raw data:\n{df.head(15).to_string()}")
        return pd.DataFrame()
    
    start_col = metric_block["start_col"]
    end_col = metric_block["end_col"]
    
    logger.info(f"[{file_path.name}] Using metric block columns {start_col}-{end_col} for warehouse '{TARGET_WAREHOUSE}'")

    # Collect product rows
    product_rows = []
    skipped_rows = 0
    rows_with_metrics = 0
    rows_without_metrics = 0
    
    # Iterate through rows using iloc for positional access
    for idx in range(len(df)):
        row = df.iloc[idx]
        
        # Get product name from second column (index 1)
        try:
            product_value = row.iloc[PRODUCT_COLUMN_IDX]
        except (IndexError, KeyError):
            logger.debug(f"[{file_path.name}] Row {idx}: Cannot access product column at index {PRODUCT_COLUMN_IDX}")
            skipped_rows += 1
            continue
        
        # Skip service rows
        if is_service_row(product_value):
            logger.debug(f"[{file_path.name}] Row {idx}: Skipping service row: {product_value}")
            skipped_rows += 1
            continue
        
        # Check for product row
        if is_valid_product_row(product_value):
            product_name = str(product_value).strip()
            
            # Extract metrics from the selected 6-column block
            metrics = {}
            has_numeric_metrics = False
            
            for metric_name, col_offset in METRIC_MAPPING.items():
                col_idx = start_col + col_offset
                if col_idx < len(row):
                    value = row.iloc[col_idx]
                    metrics[metric_name] = safe_numeric_value(value)
                    if safe_numeric_value(value) > 0:
                        has_numeric_metrics = True
                else:
                    metrics[metric_name] = 0.0
            
            if has_numeric_metrics:
                rows_with_metrics += 1
            else:
                rows_without_metrics += 1
            
            product_rows.append({
                "product_name": product_name,
                "warehouse": TARGET_WAREHOUSE,
                "sold_qty_60d": metrics["sold_qty_60d"],
                "days_sold": metrics["days_sold"],
                "avg_daily_sales_1c": metrics["avg_daily_sales_1c"],
                "stock_at_purchase_start": metrics["stock_at_purchase_start"],
                "required_purchase_qty_1c": metrics["required_purchase_qty_1c"],
                "planned_sales_qty": metrics["planned_sales_qty"]
            })
            logger.debug(f"[{file_path.name}] Row {idx}: Product '{product_name[:50]}...', Avg Sales: {metrics['avg_daily_sales_1c']}")
        else:
            logger.debug(f"[{file_path.name}] Row {idx}: Invalid product row, skipping: {product_value}")
            skipped_rows += 1
    
    logger.info(f"[{file_path.name}] State machine complete: {len(product_rows)} product rows collected")
    logger.info(f"[{file_path.name}] Skipped rows: {skipped_rows}")
    logger.info(f"[{file_path.name}] Rows with numeric metrics: {rows_with_metrics}")
    logger.info(f"[{file_path.name}] Rows without numeric metrics: {rows_without_metrics}")
    
    if not product_rows:
        logger.error(f"[{file_path.name}] No product rows collected")
        logger.error(f"[{file_path.name}] Expected product column index: {PRODUCT_COLUMN_IDX}")
        logger.error(f"[{file_path.name}] Expected metric block: columns {start_col}-{end_col}")
        logger.error(f"[{file_path.name}] First 15 rows of raw data:\n{df.head(15).to_string()}")
        return pd.DataFrame()
    
    # Create output DataFrame
    output_df = pd.DataFrame(product_rows)
    
    # DEBUG: Log first 10 parsed rows with metrics
    logger.debug(f"[{file_path.name}] First 10 parsed rows (with metrics):")
    for i, row in output_df.head(10).iterrows():
        logger.debug(f"  Row {i}: product='{row['product_name'][:50]}...', sold={row['sold_qty_60d']}, avg_daily={row['avg_daily_sales_1c']}, stock={row['stock_at_purchase_start']}, required={row['required_purchase_qty_1c']}")
    
    # Normalize product_name for later merging
    output_df["product_key"] = output_df["product_name"].apply(normalize_product_name)
    pump_debug_mask = output_df["product_name"].astype(str).str.contains("unipump", case=False, na=False)
    if pump_debug_mask.any():
        logger.info(
            f"[{file_path.name}][DEBUG] Unipump rows after normalization:\n"
            + output_df.loc[
                pump_debug_mask,
                ["product_name", "product_key", "avg_daily_sales_1c", "required_purchase_qty_1c"],
            ].to_string()
        )
    
    # Remove rows with empty product_key
    empty_key_count = (output_df["product_key"] == "").sum()
    if empty_key_count > 0:
        logger.debug(f"[{file_path.name}] Removing {empty_key_count} rows with empty product_key")
    output_df = output_df[output_df["product_key"] != ""]
    
    if output_df.empty:
        logger.error(f"[{file_path.name}] Output DataFrame is empty after removing empty product_keys")
        logger.error(f"[{file_path.name}] First 15 rows:\n{output_df.head(15).to_string()}")
        return pd.DataFrame()

    # DEBUG: Log final structure
    log_dataframe_debug(output_df, "Final output DataFrame", file_path.name)
    
    # Log metrics statistics
    total_sold = output_df["sold_qty_60d"].sum()
    avg_daily_total = output_df["avg_daily_sales_1c"].sum()
    total_required = output_df["required_purchase_qty_1c"].sum()
    total_planned = output_df["planned_sales_qty"].sum()
    logger.info(f"[{file_path.name}] Metrics statistics: total_sold={total_sold}, total_avg_daily={avg_daily_total:.2f}, total_required={total_required}, total_planned={total_planned}")

    logger.success(f"Planning Report adapted: {len(output_df)} products for {TARGET_WAREHOUSE}.")
    return output_df