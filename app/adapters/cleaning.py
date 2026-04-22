import pandas as pd
from loguru import logger

# Keywords that indicate total/summary rows which should be removed
TOTAL_KEYWORDS = ["итог", "итого", "всего", "total", "grand total"]

def remove_empty_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Remove rows where all values are NaN/None."""
    initial_count = len(df)
    df = df.dropna(how="all")
    logger.debug(f"Removed {initial_count - len(df)} empty rows.")
    return df

def remove_total_rows(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove rows containing summary keywords like 'итог', 'всего'.
    Checks all object/string columns.
    """
    initial_count = len(df)
    mask = pd.Series(False, index=df.index)

    for col in df.select_dtypes(include=["object", "string"]).columns:
        for keyword in TOTAL_KEYWORDS:
            col_mask = df[col].astype(str).str.contains(keyword, case=False, na=False)
            mask = mask | col_mask

    df = df.loc[~mask].reset_index(drop=True)
    logger.debug(f"Removed {initial_count - len(df)} total/summary rows.")
    return df

def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Apply standard cleaning rules to any procurement DataFrame."""
    df = remove_empty_rows(df)
    df = remove_total_rows(df)
    return df

def fill_hierarchical_columns(df: pd.DataFrame, columns):
    df = df.copy()

    for col in columns:
        if isinstance(col, str) and col in df.columns:
            df[col] = df[col].ffill()

    return df