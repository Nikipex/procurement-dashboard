import pandas as pd
from pathlib import Path
from loguru import logger
import re
from app.normalization import normalize_product_name

# Target Warehouse
TARGET_WAREHOUSE = "ЮЖНЫЙ склад"

# Column indices (0-based)
TEXT_COLUMN_IDX = 1  # Second column contains product/warehouse text
STOCK_COLUMN_IDX = 2  # Third column contains stock values

# Service rows to skip
SERVICE_PREFIXES = [
    "Период:",
    "Показатели:",
    "Группировки строк:",
    "Отборы:",
    "Склад",
    "Номенклатура",
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
        return False  # NaN might be a product row with missing stock
    value_str = str(value).strip()
    if value_str == "":
        return True
    value_normalized = normalize_text(value_str)
    for prefix in SERVICE_PREFIXES:
        if value_normalized.startswith(normalize_text(prefix)):
            return True
    return False

def is_warehouse_row(value) -> bool:
    """
    Detect if row is a warehouse section header.
    Warehouse rows contain warehouse names like "ЮЖНЫЙ склад".
    """
    if pd.isna(value):
        return False
    value_normalized = normalize_text(value)
    # Check if it contains "склад" but isn't a service row
    if "склад" in value_normalized and not is_service_row(value):
        return True
    return False

def matches_target_warehouse(value) -> bool:
    """
    Check if warehouse row matches target warehouse (with normalized comparison).
    """
    if pd.isna(value):
        return False
    value_normalized = normalize_text(value)
    target_normalized = normalize_text(TARGET_WAREHOUSE)
    return value_normalized == target_normalized

def is_valid_product_row(value) -> bool:
    """
    Check if row is a valid product row.
    - Not a service row
    - Not a warehouse row
    - Has a meaningful product name
    """
    if pd.isna(value):
        return False
    value_str = str(value).strip()
    if value_str == "":
        return False
    if is_service_row(value):
        return False
    if is_warehouse_row(value):
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

def adapt_inventory_report(file_path: Path) -> pd.DataFrame:
    """
    Adapts raw 1C Inventory Excel report ("Анализ доступности товаров на складах.xlsx").
    Uses state machine to parse hierarchical warehouse structure.
    Uses positional column access for robustness.
    """
    logger.info(f"Adapting Inventory Report: {file_path.name}")
    
    try:
        # Read without header to capture all rows including service rows
        df = pd.read_excel(file_path, engine="openpyxl", header=None)
    except Exception as e:
        logger.error(f"Failed to read Inventory file {file_path.name}: {e}")
        return pd.DataFrame()

    if df.empty:
        logger.error(f"[{file_path.name}] DataFrame is empty immediately after reading")
        return df

    # DEBUG: Log initial structure
    log_dataframe_debug(df, "After reading Excel", file_path.name)
    logger.debug(f"[{file_path.name}] Total columns detected: {len(df.columns)}")
    logger.debug(f"[{file_path.name}] Using TEXT_COLUMN_IDX={TEXT_COLUMN_IDX}, STOCK_COLUMN_IDX={STOCK_COLUMN_IDX}")

    # Set column names based on first row
    if len(df) > 0:
        df.columns = df.iloc[0].tolist()
        df = df[1:].reset_index(drop=True)
    
    # DEBUG: Log structure after setting headers
    log_dataframe_debug(df, "After setting headers from row 0", file_path.name)

    # Check if we have enough columns for positional access
    if len(df.columns) <= max(TEXT_COLUMN_IDX, STOCK_COLUMN_IDX):
        logger.error(f"[{file_path.name}] Not enough columns for positional access. Need at least {max(TEXT_COLUMN_IDX, STOCK_COLUMN_IDX) + 1} columns, have {len(df.columns)}")
        logger.error(f"[{file_path.name}] Available columns: {df.columns.tolist()}")
        return pd.DataFrame()

    # State machine variables
    current_warehouse = None
    in_target_warehouse = False
    
    # Collect product rows
    product_rows = []
    skipped_rows = 0
    warehouse_matches = 0
    rows_with_stock = 0
    rows_without_stock = 0
    
    # Iterate through rows using iloc for positional access
    for idx in range(len(df)):
        row = df.iloc[idx]
        
        # Get text value from second column (index 1)
        try:
            hierarchy_value = row.iloc[TEXT_COLUMN_IDX]
        except (IndexError, KeyError):
            logger.debug(f"[{file_path.name}] Row {idx}: Cannot access text column at index {TEXT_COLUMN_IDX}")
            skipped_rows += 1
            continue
        
        # Get stock value from third column (index 2)
        try:
            stock_value = row.iloc[STOCK_COLUMN_IDX]
        except (IndexError, KeyError):
            logger.debug(f"[{file_path.name}] Row {idx}: Cannot access stock column at index {STOCK_COLUMN_IDX}")
            stock_value = None
        
        # Check for warehouse row
        if is_warehouse_row(hierarchy_value):
            warehouse_name = str(hierarchy_value).strip()
            warehouse_name_normalized = normalize_text(warehouse_name)
            warehouse_stock = safe_numeric_value(stock_value)
            logger.debug(f"[{file_path.name}] Row {idx}: Warehouse detected: '{warehouse_name}' (normalized: '{warehouse_name_normalized}'), Stock: {warehouse_stock}")
            
            if matches_target_warehouse(hierarchy_value):
                current_warehouse = TARGET_WAREHOUSE
                in_target_warehouse = True
                warehouse_matches += 1
                logger.debug(f"[{file_path.name}] Row {idx}: Matched target warehouse '{TARGET_WAREHOUSE}'")
            else:
                current_warehouse = warehouse_name
                in_target_warehouse = False
                logger.debug(f"[{file_path.name}] Row {idx}: Non-target warehouse '{warehouse_name}', skipping subsequent products")
            continue
        
        # Skip service rows
        if is_service_row(hierarchy_value):
            logger.debug(f"[{file_path.name}] Row {idx}: Skipping service row: {hierarchy_value}")
            skipped_rows += 1
            continue
        
        # Check for product row
        if is_valid_product_row(hierarchy_value):
            if not in_target_warehouse:
                logger.debug(f"[{file_path.name}] Row {idx}: Product row outside target warehouse, skipping")
                continue
            
            product_name = str(hierarchy_value).strip()
            free_stock_qty = safe_numeric_value(stock_value)
            
            # Track stock value statistics
            if free_stock_qty > 0:
                rows_with_stock += 1
            else:
                rows_without_stock += 1
            
            # If stock is NaN/0 but product name looks real, keep the row with stock = 0
            if pd.isna(stock_value) or stock_value == 0:
                logger.debug(f"[{file_path.name}] Row {idx}: Product '{product_name[:50]}...' has NaN/0 stock, keeping with stock=0")
            else:
                logger.debug(f"[{file_path.name}] Row {idx}: Product '{product_name[:50]}...', Stock: {free_stock_qty}")
            
            product_rows.append({
                "warehouse": current_warehouse,
                "product_name": product_name,
                "free_stock_qty": free_stock_qty
            })
        else:
            logger.debug(f"[{file_path.name}] Row {idx}: Invalid product row, skipping: {hierarchy_value}")
            skipped_rows += 1
    
    logger.info(f"[{file_path.name}] State machine complete: {len(product_rows)} product rows collected for {TARGET_WAREHOUSE}")
    logger.info(f"[{file_path.name}] Warehouse matches found: {warehouse_matches}")
    logger.info(f"[{file_path.name}] Skipped rows: {skipped_rows}")
    logger.info(f"[{file_path.name}] Rows with stock > 0: {rows_with_stock}")
    logger.info(f"[{file_path.name}] Rows with stock = 0: {rows_without_stock}")
    
    if not product_rows:
        logger.error(f"[{file_path.name}] No product rows collected for warehouse '{TARGET_WAREHOUSE}'")
        logger.error(f"[{file_path.name}] Expected text column index: {TEXT_COLUMN_IDX}")
        logger.error(f"[{file_path.name}] Expected stock column index: {STOCK_COLUMN_IDX}")
        logger.error(f"[{file_path.name}] First 15 rows of raw data:\n{df.head(15).to_string()}")
        return pd.DataFrame()
    
    # Create output DataFrame
    output_df = pd.DataFrame(product_rows)
    
    # DEBUG: Log first 10 collected rows with stock values
    logger.debug(f"[{file_path.name}] First 10 collected rows (with stock values):")
    for i, row in output_df.head(10).iterrows():
        logger.debug(f"  Row {i}: product='{row['product_name'][:50]}...', stock={row['free_stock_qty']}")
    
    # Normalize product_name for later merging
    output_df["product_key"] = output_df["product_name"].apply(normalize_product_name)
    pump_debug_mask = output_df["product_name"].astype(str).str.contains("unipump", case=False, na=False)
    if pump_debug_mask.any():
        logger.info(
            f"[{file_path.name}][DEBUG] Unipump rows after normalization:\n"
            + output_df.loc[
                pump_debug_mask,
                ["product_name", "product_key", "free_stock_qty"],
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
    
    # Log stock value statistics
    total_stock = output_df["free_stock_qty"].sum()
    avg_stock = output_df["free_stock_qty"].mean()
    max_stock = output_df["free_stock_qty"].max()
    logger.info(f"[{file_path.name}] Stock statistics: total={total_stock}, avg={avg_stock:.2f}, max={max_stock}")

    logger.success(f"Inventory Report adapted: {len(output_df)} products for {TARGET_WAREHOUSE}.")
    return output_df