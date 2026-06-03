import pandas as pd
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from loguru import logger
from datetime import datetime

# --- DataFrame normalization for dashboard ---
def prepare_dashboard_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize dataframe columns for the dashboard.

    Supports both legacy Excel metrics and the new PostgreSQL procurement mart.
    """
    result = df.copy()

    if result.empty:
        return result

    if "visible_in_dashboard" not in result.columns:
        result["visible_in_dashboard"] = True

    if "critical_flag" not in result.columns:
        if "is_critical" in result.columns:
            result["critical_flag"] = result["is_critical"].fillna(False).astype(bool)
        elif "stock_status" in result.columns:
            result["critical_flag"] = result["stock_status"].isin(["out_of_stock", "critical"])
        else:
            result["critical_flag"] = False

    if "free_stock_qty" not in result.columns and "stock_qty" in result.columns:
        result["free_stock_qty"] = result["stock_qty"]

    if "recommended_order_qty" not in result.columns:
        if {"avg_daily_sales", "stock_qty"}.issubset(result.columns):
            target_days = 30
            result["recommended_order_qty"] = (
                result["avg_daily_sales"].fillna(0) * target_days - result["stock_qty"].fillna(0)
            ).clip(lower=0).round()
        else:
            result["recommended_order_qty"] = 0

    if "recommended_order_qty_display" not in result.columns:
        result["recommended_order_qty_display"] = result["recommended_order_qty"]

    if "metrics_calculated_at" not in result.columns:
        result["metrics_calculated_at"] = datetime.now()

    if "days_of_cover" not in result.columns and {"free_stock_qty", "avg_daily_sales"}.issubset(result.columns):
        avg_daily_sales = result["avg_daily_sales"].replace(0, pd.NA)
        result["days_of_cover"] = (result["free_stock_qty"] / avg_daily_sales).round(1)

    return result


from app.dashboard.tables import (
    build_critical_items_table,
    build_recommended_orders_table,
    build_radiator_table,
)

def calculate_kpi_summary(df: pd.DataFrame) -> dict:
    """
    Calculate KPI summary values from the metrics dataframe.
    """
    kpi = {
        "total_products": len(df),
        "critical_items": 0,
        "products_to_order": 0,
        "total_recommended_qty": 0,
        "total_free_stock": 0
    }
    
    if df.empty:
        return kpi

    df = prepare_dashboard_dataframe(df)

    scoped_df = df.copy()
    if "visible_in_dashboard" in scoped_df.columns:
        scoped_df = scoped_df[scoped_df["visible_in_dashboard"] == True].copy()

    if scoped_df.empty:
        return kpi
    
    # Critical items
    if "critical_flag" in scoped_df.columns:
        kpi["critical_items"] = int(scoped_df["critical_flag"].sum())
    
    # Products to order
    if "recommended_order_qty_display" in scoped_df.columns:
        kpi["products_to_order"] = int((scoped_df["recommended_order_qty_display"] > 0).sum())
        kpi["total_recommended_qty"] = int(scoped_df["recommended_order_qty_display"].sum())
    elif "recommended_order_qty" in scoped_df.columns:
        kpi["products_to_order"] = int((scoped_df["recommended_order_qty"] > 0).sum())
        kpi["total_recommended_qty"] = int(scoped_df["recommended_order_qty"].sum())
    
    # Total free stock
    if "free_stock_qty" in scoped_df.columns:
        kpi["total_free_stock"] = int(scoped_df["free_stock_qty"].sum())
    
    # Metrics calculated at
    if "metrics_calculated_at" in scoped_df.columns:
        kpi["metrics_calculated_at"] = scoped_df["metrics_calculated_at"].iloc[0]
    else:
        kpi["metrics_calculated_at"] = datetime.now()
    
    return kpi

def build_dashboard(df: pd.DataFrame, output_path: str) -> None:
    df = df.copy()

    if "stock_status" not in df.columns:
        if "recommended_order_qty" in df.columns:
            df["stock_status"] = df["recommended_order_qty"].apply(
                lambda x: "critical" if float(x or 0) > 0 else "ok"
            )
        elif "recommended_order_qty_display" in df.columns:
            df["stock_status"] = df["recommended_order_qty_display"].apply(
                lambda x: "critical" if float(x or 0) > 0 else "ok"
            )
        else:
            df["stock_status"] = "ok"

    """
    Build HTML dashboard from metrics dataframe.
    
    Args:
        df: Metrics dataframe with all computed columns
        output_path: Path to save the HTML dashboard
    """
    logger.info(f"Building dashboard with {len(df)} products...")

    df = prepare_dashboard_dataframe(df)
    
    # Calculate KPI summary
    kpi = calculate_kpi_summary(df)
    
    
    
    # Generate grouped table HTML snippets
    tables = {
        "critical_items": build_critical_items_table(df, top_n=50),
        "recommended_orders": build_recommended_orders_table(df, top_n=99999),
        "radiators": build_radiator_table(df, top_n=99999),
    }

    if "product_group" in df.columns:
        tables["postgres_critical"] = (
            df[df["stock_status"].isin(["out_of_stock", "critical"])]
            .sort_values(["stock_status", "days_of_cover", "sales_qty_60d"], ascending=[True, True, False])
            .head(100)
            .to_html(index=False, classes="data-table", border=0)
        )
        tables["postgres_top_sales"] = (
            df.sort_values("sales_qty_60d", ascending=False)
            .head(100)
            .to_html(index=False, classes="data-table", border=0)
        )
    
    # Setup Jinja2 environment
    template_dir = Path(__file__).parent / "templates"
    env = Environment(loader=FileSystemLoader(template_dir))
    
    try:
        template = env.get_template("dashboard.html")
    except Exception as e:
        logger.error(f"Failed to load dashboard template: {e}")
        raise
    
    # Format metrics_calculated_at for display
    metrics_time = kpi["metrics_calculated_at"]
    if isinstance(metrics_time, pd.Timestamp):
        metrics_time_str = metrics_time.strftime("%Y-%m-%d %H:%M:%S")
    elif isinstance(metrics_time, datetime):
        metrics_time_str = metrics_time.strftime("%Y-%m-%d %H:%M:%S")
    else:
        metrics_time_str = str(metrics_time)
    
    # Render template
    html_content = template.render(
        kpi=kpi,
        tables=tables,
        metrics_calculated_at=metrics_time_str,
        total_products=kpi["total_products"],
        critical_items=kpi["critical_items"],
        products_to_order=kpi["products_to_order"],
        total_recommended_qty=kpi["total_recommended_qty"]
    )
    
    # Save to file
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    logger.success(f"Dashboard saved to {output_path}")