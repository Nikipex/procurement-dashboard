import pandas as pd
from pathlib import Path
from loguru import logger
import re
from app.normalization import normalize_product_name
from app.normalization import normalize_radiator_product_name

# Target Warehouse (for reference)
TARGET_WAREHOUSE = "ЮЖНЫЙ склад"

# ABC class markers to detect in row text
ABC_CLASS_MARKERS = {
    "A": ["A - класс", "A-класс", "Класс A", "Группа A", "A класс"],
    "B": ["B - класс", "B-класс", "Класс B", "Группа B", "B класс"],
    "C": ["C - класс", "C-класс", "Класс C", "Группа C", "C класс"]
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
    "ABC-анализ",
    "Анализ",
    "Номенклатура",
]

RADIATOR_ABC_FILENAME_MARKERS = [
    "радиаторы",
    "радиатор",
]

RADIATOR_INCLUDE_PATTERNS = [
    r"^стальн.*радиатор",
]

RADIATOR_EXCLUDE_PATTERNS = [
    r"клапан",
    r"кран",
    r"ключ",
    r"комплект",
    r"креплен",
    r"кроншт",
    r"термостат",
    r"монтаж",
    r"напольн",
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
    text = text.replace('ё', 'е')
    return text


def is_radiator_abc_file(file_path: Path) -> bool:
    filename_lower = normalize_text(file_path.name)
    return any(marker in filename_lower for marker in RADIATOR_ABC_FILENAME_MARKERS)


def is_target_radiator_product(value) -> bool:
    """
    Keep only actual radiator SKUs for the dedicated radiator ABC file.
    Exclude radiator accessories such as valves, brackets, keys, kits, etc.
    """
    value_lower = normalize_text(value)
    if value_lower == "":
        return False

    if not any(re.search(pattern, value_lower, re.IGNORECASE) for pattern in RADIATOR_INCLUDE_PATTERNS):
        return False

    if any(re.search(pattern, value_lower, re.IGNORECASE) for pattern in RADIATOR_EXCLUDE_PATTERNS):
        return False

    return True

def is_service_row(value) -> bool:
    """Check if row value is a service/header row to skip."""
    if pd.isna(value):
        return False
    value_str = str(value).strip()
    if value_str == "":
        return True
    value_lower = value_str.lower()
    for prefix in SERVICE_PREFIXES:
        prefix_lower = prefix.lower()
        if value_lower == prefix_lower or value_lower.startswith(prefix_lower):
            return True
    return False

def detect_abc_class(value) -> str:
    """
    Detect if row contains an ABC class marker.
    Returns 'A', 'B', 'C', or None.
    """
    if pd.isna(value):
        return None
    value_str = str(value).strip()
    value_lower = value_str.lower()
    
    for abc_class, markers in ABC_CLASS_MARKERS.items():
        for marker in markers:
            if marker.lower() in value_lower:
                logger.debug(f"Detected ABC class marker '{marker}' in row: {value_str[:50]}...")
                return abc_class
    
    return None

def is_valid_product_row(value, current_class) -> bool:
    """
    Check if row is a valid product row.
    - Not a service row
    - Not a class marker row
    - Has a meaningful product name
    - Has a current class assigned
    """
    if pd.isna(value):
        return False
    value_str = str(value).strip()
    if value_str == "":
        return False
    if is_service_row(value):
        return False
    if detect_abc_class(value) is not None:
        return False
    if current_class is None:
        return False
    # Product name should have some content
    if len(value_str) < 2:
        return False
    return True

def safe_string_value(value) -> str:
    """
    Safely convert value to string, returning empty string if invalid.
    """
    if pd.isna(value):
        return ""
    return str(value).strip()

def find_text_column(df: pd.DataFrame, file_name: str) -> int:
    """
    Find the main text column dynamically.
    Choose the first column with substantial text content.
    """
    if len(df.columns) == 0:
        logger.error(f"[{file_name}] No columns in dataframe")
        return -1
    
    for col_idx in range(len(df.columns)):
        col_name = df.columns[col_idx]
        # Check if column has text content
        non_null_count = df.iloc[:, col_idx].notna().sum()
        if non_null_count > 0:
            # Sample some values to check if they're text-like
            sample_values = df.iloc[:, col_idx].dropna().head(10)
            text_like_count = 0
            for val in sample_values:
                if isinstance(val, str) and len(val.strip()) > 0:
                    text_like_count += 1
            if text_like_count > 0:
                logger.debug(f"[{file_name}] Column {col_idx} ('{col_name}') has {non_null_count} non-null values, {text_like_count} text-like samples")
                return col_idx
    
    # Fallback: use first column
    logger.warning(f"[{file_name}] No clear text column found, using first column (index 0)")
    return 0

def log_dataframe_debug(df: pd.DataFrame, stage: str, file_name: str):
    """Log debug information about DataFrame structure."""
    logger.debug(f"[{file_name}] {stage} - Shape: {df.shape}")
    logger.debug(f"[{file_name}] {stage} - Columns: {df.columns.tolist()}")
    logger.debug(f"[{file_name}] {stage} - First 15 rows:\n{df.head(15).to_string()}")

def adapt_abc_report(file_path: Path) -> pd.DataFrame:
    """
    Adapts raw 1C ABC Analysis Excel report.
    Uses state machine to parse vertical class hierarchy.
    Works with 1 or 2 column layouts.
    """
    logger.info(f"Adapting ABC Report: {file_path.name}")
    
    radiator_mode = is_radiator_abc_file(file_path)
    output_abc_col = "radiator_abc_class" if radiator_mode else "abc_class"
    logger.info(
        f"[{file_path.name}] ABC mode: {'radiator-specific' if radiator_mode else 'generic'}, output column: {output_abc_col}"
    )
    
    try:
        # Read without header to capture all rows including service rows
        df = pd.read_excel(file_path, engine="openpyxl", header=None)
    except Exception as e:
        logger.error(f"Failed to read ABC file {file_path.name}: {e}")
        return pd.DataFrame()

    if df.empty:
        logger.error(f"[{file_path.name}] DataFrame is empty immediately after reading")
        return df

    # DEBUG: Log initial structure
    log_dataframe_debug(df, "After reading Excel", file_path.name)
    logger.debug(f"[{file_path.name}] Total columns detected: {len(df.columns)}")

    # Set column names based on first row
    if len(df) > 0:
        df.columns = df.iloc[0].tolist()
        df = df[1:].reset_index(drop=True)
    
    # DEBUG: Log structure after setting headers
    log_dataframe_debug(df, "After setting headers from row 0", file_path.name)

    # Find the main text column dynamically
    text_column_idx = find_text_column(df, file_path.name)
    if text_column_idx < 0:
        logger.error(f"[{file_path.name}] Could not find text column")
        return pd.DataFrame()
    
    logger.info(f"[{file_path.name}] Using text column index: {text_column_idx}")

    # State machine variables
    current_class = None
    
    # Collect product rows with ABC classification
    product_rows = []
    skipped_rows = 0
    class_markers_detected = {'A': 0, 'B': 0, 'C': 0}
    products_per_class = {'A': 0, 'B': 0, 'C': 0}
    
    # Iterate through rows using iloc for positional access
    for idx in range(len(df)):
        row = df.iloc[idx]
        
        # Get text value from detected text column
        try:
            text_value = row.iloc[text_column_idx] if text_column_idx < len(row) else None
        except (IndexError, KeyError):
            logger.debug(f"[{file_path.name}] Row {idx}: Cannot access text column at index {text_column_idx}")
            skipped_rows += 1
            continue
        
        # Skip service rows
        if is_service_row(text_value):
            logger.debug(f"[{file_path.name}] Row {idx}: Skipping service row: {text_value}")
            skipped_rows += 1
            continue
        
        # Check for ABC class marker
        detected_class = detect_abc_class(text_value)
        if detected_class:
            current_class = detected_class
            class_markers_detected[detected_class] += 1
            logger.debug(f"[{file_path.name}] Row {idx}: ABC class marker detected: '{current_class}'")
            continue
        
        # Check for valid product row
        if is_valid_product_row(text_value, current_class):
            product_name = safe_string_value(text_value)

            if radiator_mode and not is_target_radiator_product(product_name):
                logger.debug(f"[{file_path.name}] Row {idx}: Skipping non-target radiator row: {product_name}")
                skipped_rows += 1
                continue
            
            product_rows.append({
                "product_name": product_name,  # Preserve raw product text
                output_abc_col: current_class
            })
            
            # Track products per class
            products_per_class[current_class] += 1
            
            logger.debug(f"[{file_path.name}] Row {idx}: Product '{product_name[:50]}...', ABC: {current_class}")
        else:
            if current_class is None:
                logger.debug(f"[{file_path.name}] Row {idx}: Row before any class marker, skipping: {text_value}")
            else:
                logger.debug(f"[{file_path.name}] Row {idx}: Invalid product row, skipping: {text_value}")
            skipped_rows += 1
    
    logger.info(f"[{file_path.name}] State machine complete: {len(product_rows)} product rows collected")
    logger.info(f"[{file_path.name}] Skipped rows: {skipped_rows}")
    logger.info(f"[{file_path.name}] Class markers detected: {class_markers_detected}")
    logger.info(f"[{file_path.name}] Products per class: {products_per_class}")
    
    if not product_rows:
        logger.error(f"[{file_path.name}] No product rows collected with ABC classification")
        logger.error(f"[{file_path.name}] Expected text column index: {text_column_idx}")
        logger.error(f"[{file_path.name}] Class markers detected: {class_markers_detected}")
        logger.error(f"[{file_path.name}] First 15 rows of raw data:\n{df.head(15).to_string()}")
        return pd.DataFrame()
    
    # Create output DataFrame
    output_df = pd.DataFrame(product_rows)
    
    # DEBUG: Log first 10 parsed rows with ABC class
    logger.debug(f"[{file_path.name}] First 10 parsed rows (with ABC class):")
    for i, row in output_df.head(10).iterrows():
        logger.debug(f"  Row {i}: product='{row['product_name'][:50]}...', {output_abc_col}={row[output_abc_col]}")
    
    # Normalize product_name for later merging (create separate column)
    if radiator_mode:
        output_df["product_key"] = output_df["product_name"].apply(normalize_radiator_product_name)
    else:
        output_df["product_key"] = output_df["product_name"].apply(normalize_product_name)
    pump_debug_mask = output_df["product_name"].astype(str).str.contains("unipump", case=False, na=False)
    if pump_debug_mask.any():
        logger.info(
            f"[{file_path.name}][DEBUG] Unipump rows after normalization:\n"
            + output_df.loc[
                pump_debug_mask,
                ["product_name", "product_key", output_abc_col],
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
    
    # Log ABC statistics
    unique_products = output_df["product_key"].nunique()
    final_abc_dist = output_df[output_abc_col].value_counts().to_dict()
    logger.info(f"[{file_path.name}] ABC statistics: unique_products={unique_products}, distribution={final_abc_dist}")

    logger.success(f"ABC Report adapted: {len(output_df)} products with ABC classification.")
    return output_df