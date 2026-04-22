import pandas as pd
from loguru import logger
from typing import Optional

# Valid suffix names for radiator margin data
VALID_SUFFIXES = ["prev_year", "current_year", "prev_month"]

def merge_radiator_margin_data(
    base_df: pd.DataFrame,
    radiator_margin_df: pd.DataFrame,
    suffix_name: str
) -> pd.DataFrame:
    """
    Merge radiator margin data into base metrics dataframe.
    
    Args:
        base_df: Base product metrics dataframe (from main pipeline)
        radiator_margin_df: Radiator margin dataframe from adapter
        suffix_name: One of 'prev_year', 'current_year', 'prev_month'
    
    Returns:
        base_df with additional radiator margin columns appended
    
    Added columns (example for suffix='prev_year'):
        - radiator_qty_prev_year
        - radiator_revenue_prev_year
        - radiator_gross_profit_prev_year
    """
    if suffix_name not in VALID_SUFFIXES:
        logger.error(f"Invalid suffix_name '{suffix_name}'. Must be one of {VALID_SUFFIXES}")
        return base_df
    
    if base_df.empty:
        logger.warning("Base dataframe is empty, cannot merge radiator margin data")
        return base_df
    
    if radiator_margin_df.empty:
        logger.info(f"No radiator margin data for suffix '{suffix_name}', skipping merge")
        # Still add zero columns for consistency
        base_df = base_df.copy()
        base_df[f"radiator_qty_{suffix_name}"] = 0
        base_df[f"radiator_revenue_{suffix_name}"] = 0.0
        base_df[f"radiator_gross_profit_{suffix_name}"] = 0.0
        return base_df
    
    logger.info(f"Merging radiator margin data (suffix: {suffix_name}) - {len(radiator_margin_df)} products")
    
    # Create a copy to avoid modifying original
    result_df = base_df.copy()
    
    # Ensure product_key exists in base_df for merging
    if "product_key" not in result_df.columns:
        logger.error("Base dataframe missing 'product_key' column for radiator margin merge")
        return base_df
    
    # Prepare radiator dataframe for merge
    radiator_df = radiator_margin_df[["product_key", "radiator_qty", "radiator_revenue", "radiator_gross_profit"]].copy()
    
    # Rename columns with suffix
    column_mapping = {
        "radiator_qty": f"radiator_qty_{suffix_name}",
        "radiator_revenue": f"radiator_revenue_{suffix_name}",
        "radiator_gross_profit": f"radiator_gross_profit_{suffix_name}"
    }
    radiator_df = radiator_df.rename(columns=column_mapping)
    
    # Merge on product_key (left join to keep all base products)
    result_df = pd.merge(
        result_df,
        radiator_df,
        on="product_key",
        how="left"
    )
    
    # Fill missing values with 0 for radiator-specific columns
    for col in column_mapping.values():
        if col in result_df.columns:
            result_df[col] = result_df[col].fillna(0)
    
    # Log merge statistics
    merged_count = result_df[f"radiator_qty_{suffix_name}"].gt(0).sum()
    logger.info(f"Radiator margin merge complete: {merged_count}/{len(result_df)} products have {suffix_name} data")
    
    return result_df


def merge_all_radiator_periods(
    base_df: pd.DataFrame,
    radiator_data: dict[str, pd.DataFrame]
) -> pd.DataFrame:
    """
    Merge radiator margin data for multiple periods.
    
    Args:
        base_df: Base product metrics dataframe
        radiator_data: Dict mapping suffix_name to radiator margin DataFrame
                      e.g., {"prev_year": df1, "current_year": df2, "prev_month": df3}
    
    Returns:
        base_df with all radiator margin columns merged
    """
    result_df = base_df.copy()
    
    for suffix_name, radiator_df in radiator_data.items():
        if suffix_name in VALID_SUFFIXES:
            result_df = merge_radiator_margin_data(result_df, radiator_df, suffix_name)
        else:
            logger.warning(f"Skipping unknown radiator period suffix: {suffix_name}")
    
    return result_df


def calculate_radiator_margin_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate derived radiator margin metrics.
    
    Adds columns:
        - radiator_margin_pct_prev_year: (gross_profit / revenue) * 100
        - radiator_margin_pct_current_year
        - radiator_margin_pct_prev_month
        - radiator_revenue_growth_yoy: (current_year - prev_year) / prev_year * 100
        - radiator_profit_growth_yoy
    """
    if df.empty:
        return df
    
    result_df = df.copy()
    
    # Calculate margin percentage for each period
    for suffix in VALID_SUFFIXES:
        revenue_col = f"radiator_revenue_{suffix}"
        profit_col = f"radiator_gross_profit_{suffix}"
        margin_col = f"radiator_margin_pct_{suffix}"
        
        if revenue_col in result_df.columns and profit_col in result_df.columns:
            # Avoid division by zero
            result_df[margin_col] = result_df.apply(
                lambda row: (row[profit_col] / row[revenue_col] * 100) 
                if row[revenue_col] > 0 else 0,
                axis=1
            )
            result_df[margin_col] = result_df[margin_col].round(2)
    
    # Calculate YoY growth (current_year vs prev_year)
    if "radiator_revenue_current_year" in result_df.columns and "radiator_revenue_prev_year" in result_df.columns:
        result_df["radiator_revenue_growth_yoy"] = result_df.apply(
            lambda row: ((row["radiator_revenue_current_year"] - row["radiator_revenue_prev_year"]) / 
                        row["radiator_revenue_prev_year"] * 100)
            if row["radiator_revenue_prev_year"] > 0 else None,
            axis=1
        )
        result_df["radiator_revenue_growth_yoy"] = result_df["radiator_revenue_growth_yoy"].round(2)
    
    if "radiator_gross_profit_current_year" in result_df.columns and "radiator_gross_profit_prev_year" in result_df.columns:
        result_df["radiator_profit_growth_yoy"] = result_df.apply(
            lambda row: ((row["radiator_gross_profit_current_year"] - row["radiator_gross_profit_prev_year"]) / 
                        row["radiator_gross_profit_prev_year"] * 100)
            if row["radiator_gross_profit_prev_year"] > 0 else None,
            axis=1
        )
        result_df["radiator_profit_growth_yoy"] = result_df["radiator_profit_growth_yoy"].round(2)
    
    logger.info("Radiator margin metrics calculated")
    
    return result_df