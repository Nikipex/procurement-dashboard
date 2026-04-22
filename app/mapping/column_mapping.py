import pandas as pd
from loguru import logger

# Standard internal schema for the dashboard
STANDARD_COLUMNS = {
    "date": "transaction_date",
    "amount": "total_amount",
    "vendor": "vendor_name",
    "item": "description",
    "id": "transaction_id"
}

# Mapping from source column names to standard columns per file type
COLUMN_MAPS = {
    "purchase_orders": {
        "PO Date": "transaction_date",
        "Total Value": "total_amount",
        "Supplier": "vendor_name",
        "Item Description": "description",
        "PO Number": "transaction_id"
    },
    "invoices": {
        "Invoice Date": "transaction_date",
        "Amount Due": "total_amount",
        "Vendor Name": "vendor_name",
        "Line Item": "description",
        "Invoice ID": "transaction_id"
    },
    "vendors": {
        "Reg Date": "transaction_date",
        "Credit Limit": "total_amount",
        "Company Name": "vendor_name",
        "Category": "description",
        "Vendor ID": "transaction_id"
    }
}

def normalize_columns(df: pd.DataFrame, file_type: str) -> pd.DataFrame:
    """
    Renames columns in the dataframe to match the standard internal schema.
    """
    if file_type not in COLUMN_MAPS:
        logger.warning(f"No column mapping defined for file type: {file_type}")
        return df

    mapping = COLUMN_MAPS[file_type]
    
    # Filter mapping to only include columns present in the dataframe
    valid_mapping = {k: v for k, v in mapping.items() if k in df.columns}
    
    if not valid_mapping:
        logger.warning(f"No matching columns found in {file_type} file for normalization.")
        return df

    df_normalized = df.rename(columns=valid_mapping)
    
    # Ensure standard columns exist even if missing in source (fill with None)
    for standard_name in mapping.values():
        if standard_name not in df_normalized.columns:
            df_normalized[standard_name] = None
            
    return df_normalized