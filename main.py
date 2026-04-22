import os
import sys
from pathlib import Path
from loguru import logger
import yaml
import pandas as pd

# Add app to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.mapping.file_mapping import identify_file_type
from app.adapters.sales_adapter import adapt_sales_report
from app.adapters.sales_pdf_adapter import adapt_sales_report_for_pdf
from app.adapters.inventory_adapter import adapt_inventory_report
from app.adapters.abc_adapter import adapt_abc_report
from app.adapters.planning_adapter import adapt_planning_report
from app.adapters.gross_profit_year_adapter import adapt_gross_profit_year_report
from app.adapters.gross_profit_adapter import adapt_gross_profit_report
from app.adapters.radiator_margin_adapter import adapt_radiator_margin_report

from app.services.merge_service import MergeService
from app.services.metrics_service import MetricsService
from app.dashboard.dashboard_builder import build_dashboard
from app.reports.pdf_report import build_pdf_report

def load_config(config_path: str) -> dict:
    """Load configuration from YAML file."""
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

def setup_logging(config: dict):
    """Configure loguru based on config."""
    logger.remove()
    log_cfg = config.get("logging", {})
    logger.add(
        sys.stdout,
        format=log_cfg.get("format", "{time:YYYY-MM-DD HH:mm:ss} | {level} | {module} | {message}"),
        level=log_cfg.get("level", "INFO")
    )

def dispatch_adapter(file_path: Path, file_type: str) -> pd.DataFrame:
    """
    Dispatch file to the correct adapter based on identified type.
    Returns a DataFrame or empty DataFrame if adapter fails.
    """
    try:
        if file_type == "sales":
            return adapt_sales_report(file_path)
        elif file_type == "inventory":
            return adapt_inventory_report(file_path)
        elif file_type == "abc":
            return adapt_abc_report(file_path)
        elif file_type == "planning":
            return adapt_planning_report(file_path)
        elif file_type == "gross_profit_year":
            return adapt_gross_profit_year_report(file_path)
        elif file_type == "gross_profit_period":
            return adapt_gross_profit_report(file_path)
        elif file_type in {"radiator_jan", "radiator_feb", "radiator_mar", "radiator_apr"}:
            return adapt_radiator_margin_report(file_path)
        elif file_type == "radiator_abc":
            return adapt_abc_report(file_path)
        else:
            logger.warning(f"No adapter defined for file type: {file_type}")
            return pd.DataFrame()
    except Exception as e:
        logger.exception(f"Adapter failed for {file_path.name}: {e}")
        return pd.DataFrame()

def main():
    # 1. Load Configuration
    BASE_DIR = Path(__file__).resolve().parent
    config_path = BASE_DIR / "config.yaml"
    if not config_path.exists():
        logger.error(f"config.yaml not found: {config_path}")
        return
    
    config = load_config(str(config_path))
    allowed_file_types = set(
        config.get(
            "pipeline",
            {},
        ).get(
            "allowed_file_types",
            ["sales", "planning", "inventory", "abc", "gross_profit_year", "gross_profit_period"],
        )
    )
    setup_logging(config)
    logger.info(f"Allowed file types: {sorted(allowed_file_types)}")
    
    logger.info(f"Starting {config['app']['name']} v{config['app']['version']}")
    
    # 2. Discover Files
    raw_dir = BASE_DIR / config["paths"]["raw_data"]
    if not raw_dir.exists():
        logger.error(f"Raw data directory not found: {raw_dir}")
        return

    excel_files = list(raw_dir.glob("*.xlsx")) + list(raw_dir.glob("*.xls"))
    
    if not excel_files:
        logger.warning("No Excel files found in raw data directory.")
        return

    logger.info(f"Found {len(excel_files)} Excel files in {raw_dir}")

    def find_fallback_file(candidates: list[str]) -> Path | None:
        """Find file by lowercase name fragments if normal type identification failed."""
        for path in excel_files:
            name = path.name.lower()
            if any(candidate in name for candidate in candidates):
                return path
        return None

    # 3. Process Pipeline - Separate DataFrames per type
    datasets = {
        "sales": pd.DataFrame(),
        "inventory": pd.DataFrame(),
        "abc": pd.DataFrame(),
        "planning": pd.DataFrame(),
        "gross_profit_year": pd.DataFrame(),
        "gross_profit_period": pd.DataFrame(),
        "radiator_abc": pd.DataFrame(),
        "radiator_jan": pd.DataFrame(),
        "radiator_feb": pd.DataFrame(),
        "radiator_mar": pd.DataFrame(),
        "radiator_apr": pd.DataFrame(),
    }
    pdf_sales_source_file = None
    pdf_sales_df = pd.DataFrame()
    
    for file_path in excel_files:
        if file_path.name.startswith("~$"):
            logger.info(f"Skipping temporary Excel lock file: {file_path.name}")
            continue

        file_type = identify_file_type(file_path.name)

        if not file_type:
            logger.warning(f"Could not identify type for {file_path.name}, skipping.")
            if "валовая прибыль 20.01-20.03" in file_path.name.lower():
                logger.warning(
                    f"Potential gross_profit_period source was not identified automatically: {file_path.name}"
                )
            continue

        if file_type not in allowed_file_types:
            logger.info(f"Skipping unsupported file type (not enabled in pipeline): {file_path.name} -> {file_type}")
            continue

        logger.info(f"Processing {file_path.name} as {file_type}")
        if file_type == "sales":
            pdf_sales_source_file = file_path
        df = dispatch_adapter(file_path, file_type)

        if file_type in {"radiator_abc", "radiator_jan", "radiator_feb", "radiator_mar", "radiator_apr"}:
            if not df.empty:
                datasets[file_type] = df.copy()
                logger.info(f"  -> {file_type} dataset loaded with {len(datasets[file_type])} rows")
            else:
                logger.warning(f"  -> {file_type} adapter returned empty DataFrame")
            continue

        if not df.empty:
            # Append to existing dataset if multiple files of same type exist
            if datasets[file_type].empty:
                datasets[file_type] = df
            else:
                datasets[file_type] = pd.concat([datasets[file_type], df], ignore_index=True)
            logger.info(f"  -> {file_type} dataset now has {len(datasets[file_type])} rows")
        else:
            logger.warning(f"  -> {file_type} adapter returned empty DataFrame")

    # Fallback: force-load gross profit period file if normal identification/loading failed
    if datasets["gross_profit_period"].empty:
        fallback_gp_file = find_fallback_file([
            "валовая прибыль 20.01-20.03",
            "валовая прибыль",
        ])
        if fallback_gp_file is not None:
            logger.warning(
                f"gross_profit_period dataset is empty after discovery; forcing fallback load from {fallback_gp_file.name}"
            )
            try:
                fallback_gp_df = adapt_gross_profit_report(fallback_gp_file)
                if not fallback_gp_df.empty and "product_key" in fallback_gp_df.columns:
                    datasets["gross_profit_period"] = fallback_gp_df.copy()
                    logger.success(
                        "Fallback gross_profit_period loaded successfully: "
                        f"rows={len(fallback_gp_df)}, columns={fallback_gp_df.columns.tolist()}"
                    )
                else:
                    logger.warning(
                        "Fallback gross_profit_period load returned empty dataframe "
                        "or missing product_key"
                    )
            except Exception as e:
                logger.exception(f"Fallback gross_profit_period load failed: {e}")

    # Log dataset summary
    for dtype, df in datasets.items():
        if not df.empty:
            logger.info(f"{dtype.upper()} dataset: {len(df)} rows, {len(df.columns)} columns")
            if dtype in {"radiator_abc", "radiator_jan", "radiator_feb", "radiator_mar", "radiator_apr"}:
                logger.info(
                    f"{dtype.upper()} columns: {df.columns.tolist()}"
                )
                logger.info(
                    f"{dtype.upper()} preview:\n" + df.head(20).to_string()
                )
        else:
            logger.warning(f"{dtype.upper()} dataset: EMPTY")

    # 4. Merge Services
    logger.info("Merging datasets...")
    merge_service = MergeService()
    merged_df = merge_service.merge_sources(datasets)
    
    if merged_df.empty:
        logger.error("Merge resulted in empty DataFrame. Exiting.")
        return

    logger.info(f"Merged dataset: {len(merged_df)} products, {len(merged_df.columns)} columns")

    # === Inject gross profit period quantities (real sold qty) ===
    gross_df = datasets.get("gross_profit_period", pd.DataFrame())

    if not gross_df.empty and "product_key" in gross_df.columns:
        logger.info(f"Merging gross_profit_period: rows={len(gross_df)}")

        gp_merge = gross_df[["product_key", "quantity"]].copy()
        gp_merge = gp_merge.rename(columns={"quantity": "gross_qty_period"})
        gp_merge = gp_merge.groupby("product_key", as_index=False, dropna=False)["gross_qty_period"].sum()

        logger.info(
            "gross_profit_period merge source preview:\n"
            + gp_merge.head(30).to_string()
        )

        merged_df = pd.merge(
            merged_df,
            gp_merge,
            on="product_key",
            how="left",
        )

        # DEBUG: check merge quality
        logger.info(
            "Gross profit merge preview:\n" +
            merged_df[["product_name", "gross_qty_period"]]
            .dropna()
            .head(30)
            .to_string()
        )

        # Override sales quantity with gross profit quantity where available
        if "gross_qty_period" in merged_df.columns:
            existing_sales_qty = merged_df["sales_qty_60d"] if "sales_qty_60d" in merged_df.columns else 0
            merged_df["sales_qty_60d"] = merged_df["gross_qty_period"].fillna(existing_sales_qty)

            logger.info(
                "Sales qty overridden from gross profit where available"
            )
            logger.info(
                "Post gross profit override preview:\n"
                + merged_df.loc[
                    merged_df["gross_qty_period"].notna(),
                    ["product_name", "product_key", "gross_qty_period", "sales_qty_60d"],
                ].head(30).to_string()
            )
    else:
        logger.warning("gross_profit_period dataset empty or missing product_key")

    # 4.1 Merge radiator-specific monthly and ABC data into main dataframe
    radiator_merge_sources = [
        "radiator_abc",
        "radiator_jan",
        "radiator_feb",
        "radiator_mar",
        "radiator_apr",
    ]

    for radiator_key in radiator_merge_sources:
        radiator_df = datasets.get(radiator_key, pd.DataFrame())
        if radiator_df.empty or "product_key" not in radiator_df.columns:
            logger.info(f"Skipping radiator merge for {radiator_key}: empty or missing product_key")
            continue

        merge_columns = [col for col in radiator_df.columns if col != "product_name"]
        radiator_merge_df = radiator_df[merge_columns].copy()

        merged_df = pd.merge(
            merged_df,
            radiator_merge_df,
            on="product_key",
            how="left",
        )
        logger.info(
            f"Merged radiator dataset '{radiator_key}' into main dataframe: "
            f"rows={len(radiator_df)}, columns={radiator_merge_df.columns.tolist()}"
        )

    radiator_debug_columns = [
        "product_key",
        "product_name",
        "abc_class",
        "radiator_abc_class",
        "radiator_qty_jan_2026",
        "radiator_qty_feb_2026",
        "radiator_qty_mar_2026",
        "radiator_qty_apr_2026",
    ]
    available_radiator_debug_columns = [col for col in radiator_debug_columns if col in merged_df.columns]
    if available_radiator_debug_columns:
        radiator_debug_mask = (
            merged_df["product_name"].astype(str).str.contains("радиатор", case=False, na=False)
            & merged_df["product_name"].astype(str).str.contains("стальн", case=False, na=False)
        )
        if radiator_debug_mask.any():
            logger.info(
                "Radiator rows after monthly + ABC merge:\n"
                + merged_df.loc[radiator_debug_mask, available_radiator_debug_columns].head(50).to_string()
            )

    radiator_metrics_debug_columns = [
        "product_key",
        "product_name",
        "radiator_abc_class",
        "radiator_qty_jan_2026",
        "radiator_qty_feb_2026",
        "radiator_qty_mar_2026",
        "radiator_qty_apr_2026",
        "free_stock_qty",
    ]
    available_radiator_metrics_debug_columns = [col for col in radiator_metrics_debug_columns if col in merged_df.columns]
    if available_radiator_metrics_debug_columns:
        radiator_metrics_debug_mask = (
            merged_df["product_name"].astype(str).str.contains("радиатор", case=False, na=False)
            & merged_df["product_name"].astype(str).str.contains("стальн", case=False, na=False)
        )
        if radiator_metrics_debug_mask.any():
            logger.info(
                "Steel radiator rows before metrics calculation:\n"
                + merged_df.loc[
                    radiator_metrics_debug_mask,
                    available_radiator_metrics_debug_columns,
                ].head(50).to_string()
            )

    # 5. Compute Metrics
    logger.info("Computing metrics...")
    metrics_service = MetricsService(analysis_period_days=60)
    final_df = metrics_service.compute_all_metrics(merged_df)

    logger.info(
        "Post-metrics qty preview:\n" +
        final_df[["product_name", "product_key", "sales_qty_60d"]]
        .sort_values(by="sales_qty_60d", ascending=False)
        .head(20)
        .to_string()
    )

    # 6. Output Results
    output_dir = BASE_DIR / config["paths"]["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_path = output_dir / "product_metrics.csv"
    final_df.to_csv(output_path, index=False)
    logger.success(f"Final metrics saved to {output_path}")

    # Generate HTML dashboard
    dashboard_path = output_dir / "dashboard.html"
    build_dashboard(final_df, str(dashboard_path))
    logger.success(f"Dashboard saved to {dashboard_path}")

    # Generate PDF report
    if pdf_sales_source_file is not None:
        try:
            logger.info(f"Building isolated PDF sales dataframe from: {pdf_sales_source_file.name}")
            pdf_sales_df = adapt_sales_report_for_pdf(pdf_sales_source_file)
            if not pdf_sales_df.empty:
                logger.info(
                    f"PDF sales dataframe ready: rows={len(pdf_sales_df)}, columns={len(pdf_sales_df.columns)}"
                )
            else:
                logger.warning("PDF sales adapter returned empty DataFrame; falling back to default sales dataset")
        except Exception as e:
            logger.exception(f"Failed to build PDF sales dataframe: {e}")
            pdf_sales_df = pd.DataFrame()
    else:
        logger.warning("No sales source file found for PDF adapter; falling back to default sales dataset")

    pdf_path = output_dir / "report.pdf"
    build_pdf_report(final_df, datasets["sales"], str(pdf_path), pdf_sales_df=pdf_sales_df)
    logger.success(f"PDF report saved to {pdf_path}")
    
    # 7. Print Summary
    print("\n" + "="*80)
    print("FINAL PRODUCT METRICS")
    print("="*80)
    print(f"\nColumns: {final_df.columns.tolist()}")
    print(f"\nFirst 10 rows:")
    print(final_df.head(10).to_string())
    
    summary = metrics_service.get_metrics_summary(final_df)
    print(f"\nMetrics Summary:")
    for key, value in summary.items():
        print(f"  {key}: {value}")
    print("="*80 + "\n")
    
    logger.success("Pipeline completed successfully.")

if __name__ == "__main__":
    main()