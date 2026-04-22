import pandas as pd
from loguru import logger
from typing import Dict

CANONICAL_PUMP_DISPLAY_NAMES = {
    "unipump upc 25-40 130": "Unipump насос циркуляц. (отопл.) UPС 25-40 130",
    "unipump upc 25-40 180": "Unipump насос циркуляц. (отопл.) UPС 25-40 180",
    "unipump upc 25-60 130": "Unipump насос циркуляц. (отопл.) UPС 25-60 130",
    "unipump upc 25-60 180": "Unipump насос циркуляц. (отопл.) UPС 25-60 180",
    "unipump upc 25-80 180": "Unipump насос циркуляц. (отопл.) UPС 25-80 180",
    "unipump upc 32-60 180": "Unipump насос циркуляц. (отопл.) UPС 32-60 180",
    "unipump upc 32-80 180": "Unipump насос циркуляц. (отопл.) UPС 32-80 180",
    "unipump cp 25-40 180": "Unipump насос циркуляц. (отопл.) CP 25-40 180",
    "unipump cp 25-60 130": "Unipump насос циркуляц. (отопл.) CP 25-60 130",
    "unipump cp 25-60 180": "Unipump насос циркуляц. (отопл.) CP 25-60 180",
}


class MergeService:
    """
    Service for merging procurement datasets into unified schema.
    Uses normalized product_name as product_key.
    """
    
    def __init__(self):
        self.logger = logger
    
    def merge_sources(self, datasets: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        Merge sales, inventory, abc, planning into unified schema.
        
        Output Schema:
        - product_key
        - product_name
        - abc_class
        - sales_qty_60d
        - revenue_60d
        - gross_profit_year_qty
        - avg_weekly_sales_gpy
        - avg_daily_sales_1c
        - free_stock_qty
        - required_purchase_qty_1c
        - planned_sales_qty
        """
        self.logger.info("Starting data merge process...")
        
        sales_df = datasets.get("sales", pd.DataFrame())
        inventory_df = datasets.get("inventory", pd.DataFrame())
        abc_df = datasets.get("abc", pd.DataFrame())
        planning_df = datasets.get("planning", pd.DataFrame())
        gross_profit_year_df = datasets.get("gross_profit_year", pd.DataFrame())
        
        # Log source statistics
        self.logger.info("Source dataset statistics:")
        if not sales_df.empty and "product_key" in sales_df.columns:
            self.logger.info(f"  Sales: {len(sales_df)} rows, {sales_df['product_key'].nunique()} unique product_keys")
        else:
            self.logger.info("  Sales: EMPTY or missing product_key")
        
        if not inventory_df.empty and "product_key" in inventory_df.columns:
            self.logger.info(f"  Inventory: {len(inventory_df)} rows, {inventory_df['product_key'].nunique()} unique product_keys")
        else:
            self.logger.info("  Inventory: EMPTY or missing product_key")
        
        if not abc_df.empty and "product_key" in abc_df.columns:
            self.logger.info(f"  ABC: {len(abc_df)} rows, {abc_df['product_key'].nunique()} unique product_keys")
            self.logger.info(f"  ABC distribution: {abc_df['abc_class'].value_counts().to_dict() if 'abc_class' in abc_df.columns else 'N/A'}")
        else:
            self.logger.info("  ABC: EMPTY or missing product_key")
        
        if not planning_df.empty and "product_key" in planning_df.columns:
            self.logger.info(f"  Planning: {len(planning_df)} rows, {planning_df['product_key'].nunique()} unique product_keys")
        else:
            self.logger.info("  Planning: EMPTY or missing product_key")

        if not gross_profit_year_df.empty and "product_key" in gross_profit_year_df.columns:
            self.logger.info(
                f"  Gross Profit Year: {len(gross_profit_year_df)} rows, "
                f"{gross_profit_year_df['product_key'].nunique()} unique product_keys"
            )
        else:
            self.logger.info("  Gross Profit Year: EMPTY or missing product_key")
        
        # 1. Aggregate Sales by product_key
        sales_agg = pd.DataFrame()
        if not sales_df.empty and "product_key" in sales_df.columns:
            sales_agg = sales_df.groupby("product_key").agg(
                product_name=("product_name", "first"),
                sales_qty_60d=("quantity", "sum"),
                revenue_60d=("sale_amount", "sum")
            ).reset_index()
            self.logger.info(f"Sales aggregated: {len(sales_agg)} unique products")
        
        # 2. Aggregate Inventory by product_key
        inv_agg = pd.DataFrame()
        if not inventory_df.empty and "product_key" in inventory_df.columns:
            inv_agg = inventory_df.groupby("product_key").agg(
                free_stock_qty=("free_stock_qty", "sum")
            ).reset_index()
            self.logger.info(f"Inventory aggregated: {len(inv_agg)} unique products")
        
        # 3. Aggregate ABC by product_key
        abc_agg = pd.DataFrame()
        if not abc_df.empty and "product_key" in abc_df.columns:
            abc_agg = abc_df.groupby("product_key").agg(
                abc_class=("abc_class", "first")
            ).reset_index()
            self.logger.info(f"ABC aggregated: {len(abc_agg)} unique products")
        
        # 4. Aggregate Planning by product_key
        plan_agg = pd.DataFrame()
        if not planning_df.empty and "product_key" in planning_df.columns:
            plan_agg = planning_df.groupby("product_key").agg(
                avg_daily_sales_1c=("avg_daily_sales_1c", "first"),
                required_purchase_qty_1c=("required_purchase_qty_1c", "sum"),
                planned_sales_qty=("planned_sales_qty", "sum")
            ).reset_index()
            self.logger.info(f"Planning aggregated: {len(plan_agg)} unique products")

        # 5. Aggregate Gross Profit Year by product_key
        gpy_agg = pd.DataFrame()
        if not gross_profit_year_df.empty and "product_key" in gross_profit_year_df.columns:
            gpy_agg = gross_profit_year_df.groupby("product_key").agg(
                gross_profit_year_qty=("gross_profit_year_qty", "sum")
            ).reset_index()
            gpy_agg["avg_weekly_sales_gpy"] = gpy_agg["gross_profit_year_qty"] / 52.0
            self.logger.info(f"Gross Profit Year aggregated: {len(gpy_agg)} unique products")
        
        # Merge all on product_key (Outer Join to capture all products)
        merged = pd.DataFrame()
        
        dataframes_to_merge = [df for df in [sales_agg, inv_agg, abc_agg, plan_agg, gpy_agg] if not df.empty]
        
        if not dataframes_to_merge:
            self.logger.warning("No data to merge")
            return pd.DataFrame()
        
        merged = dataframes_to_merge[0].copy()
        for df in dataframes_to_merge[1:]:
            if "product_name" in df.columns:
                df = df.drop(columns=["product_name"], errors="ignore")
            merged = pd.merge(merged, df, on="product_key", how="outer")
        
        # Final Cleanup & Schema Enforcement
        if not merged.empty:
            # Ensure product_name exists
            if "product_name" not in merged.columns:
                merged["product_name"] = ""
            else:
                merged["product_name"] = merged["product_name"].fillna("")
                merged["product_name"] = merged["product_name"].astype(str).str.strip()

            # Canonical human-readable names for agreed pump keys
            pump_display_mask = merged["product_key"].isin(CANONICAL_PUMP_DISPLAY_NAMES.keys())
            merged.loc[pump_display_mask, "product_name"] = merged.loc[
                pump_display_mask, "product_key"
            ].map(CANONICAL_PUMP_DISPLAY_NAMES)

            # Fallback for everything else
            merged["product_name"] = merged["product_name"].replace("", pd.NA)
            merged["product_name"] = merged["product_name"].fillna(merged["product_key"].str.title())
            
            # Fill numeric zeros
            numeric_cols = [
                "sales_qty_60d",
                "revenue_60d",
                "gross_profit_year_qty",
                "avg_weekly_sales_gpy",
                "avg_daily_sales_1c",
                "free_stock_qty",
                "required_purchase_qty_1c",
                "planned_sales_qty",
            ]
            for col in numeric_cols:
                if col not in merged.columns:
                    merged[col] = 0
                else:
                    merged[col] = merged[col].fillna(0)
            
            # DEBUG: Log ABC matching statistics before filling default
            if "abc_class" in merged.columns:
                abc_null_count = merged["abc_class"].isna().sum()
                abc_total = len(merged)
                abc_matched = abc_total - abc_null_count
                self.logger.info("ABC matching statistics:")
                self.logger.info(f"  Total rows: {abc_total}")
                self.logger.info(f"  Rows with ABC class matched: {abc_matched} ({abc_matched/abc_total*100:.1f}%)")
                self.logger.info(f"  Rows without ABC class (null before fill): {abc_null_count} ({abc_null_count/abc_total*100:.1f}%)")
                
                abc_dist_before = merged["abc_class"].value_counts(dropna=True).to_dict()
                self.logger.info(f"  ABC distribution before fill: {abc_dist_before}")
            else:
                self.logger.warning("abc_class column not found in merged DataFrame")
            
            # Fill ABC class
            if "abc_class" not in merged.columns:
                merged["abc_class"] = "C"
            else:
                merged["abc_class"] = merged["abc_class"].fillna("C")
            
            abc_dist_after = merged["abc_class"].value_counts().to_dict()
            self.logger.info(f"ABC distribution after fill: {abc_dist_after}")
            
            final_columns = [
                "product_key",
                "product_name",
                "abc_class",
                "sales_qty_60d",
                "revenue_60d",
                "gross_profit_year_qty",
                "avg_weekly_sales_gpy",
                "avg_daily_sales_1c",
                "free_stock_qty",
                "required_purchase_qty_1c",
                "planned_sales_qty",
            ]
            
            for col in final_columns:
                if col not in merged.columns:
                    if col == "product_name":
                        merged[col] = ""
                    elif col == "abc_class":
                        merged[col] = "C"
                    else:
                        merged[col] = 0
            
            merged = merged[final_columns]
            merged = merged[merged["product_key"] != ""]
            merged = merged.drop_duplicates(subset=["product_key"], keep="first")

            # DEBUG: canonical pump rows after merge
            pump_debug_mask = merged["product_key"].isin(CANONICAL_PUMP_DISPLAY_NAMES.keys())
            if pump_debug_mask.any():
                self.logger.info(
                    "Canonical pump rows after merge:\n"
                    + merged.loc[
                        pump_debug_mask,
                        [
                            "product_key",
                            "product_name",
                            "abc_class",
                            "gross_profit_year_qty",
                            "avg_weekly_sales_gpy",
                            "avg_daily_sales_1c",
                            "free_stock_qty",
                            "required_purchase_qty_1c",
                        ],
                    ].to_string()
                )
            
            self.logger.info("First 10 merged rows (product_name + abc_class):")
            for i, row in merged.head(10).iterrows():
                self.logger.info(
                    f"  Row {i}: product_key='{row['product_key'][:50]}...', "
                    f"product_name='{row['product_name'][:50]}...', abc_class={row['abc_class']}"
                )

        self.logger.success(f"Merge complete. Total products: {len(merged)}")
        return merged