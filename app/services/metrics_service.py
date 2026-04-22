import pandas as pd
import numpy as np
from loguru import logger
from typing import Dict
from datetime import datetime
import math
import re

from app.config.business_rules import (
    ANALYSIS_PERIOD_DAYS,
    MAX_DAILY_SALES_CAP,
    DISPLAY_CAP,
    HALF_YEAR_WEEKS,
    DEFAULT_TARGET_STOCK_WEEKS,
    NON_RADIATOR_BUFFER_RATIO,
    WORKING_DAYS_PER_WEEK,
    WORKING_DAYS_PER_MONTH,
    RADIATOR_MIN_MONTHLY_ORDER_QTY,
    RADIATOR_PEAK_MONTHLY_ORDER_QTY,
    RADIATOR_MIN_COVERAGE_RATIO_TO_SKIP,
    RADIATOR_TARGET_MONTH_COVERAGE_RATIO,
    RADIATOR_DEMAND_PEAK_THRESHOLD,
    ABC_TARGET_DAYS,
    RADIATOR_ABC_COVERAGE,
    NON_RADIATOR_BASE_MULTIPLIER,
    TARGET_NON_RADIATOR_ORDER_MULTIPLIERS,
    CRITICAL_DAYS_OF_COVER,
    CRITICAL_STOCK_THRESHOLDS,
    HARD_CAP,
)
from app.config.product_rules import (
    TARGET_UNIPUMP_PUMP_KEYS,
    UNIPUMP_PUMP_SIZE_PATTERN,
    TARGET_COAXIAL_EXACT_NAMES,
    EXCLUDED_BOILER_EXACT_NAMES,
    PRIORITY_PATTERNS,
    SPECIAL_ORDER_PATTERNS,
    is_excluded_radiator_brand,
)


class MetricsService:
    """
    Service for computing procurement metrics and KPIs.
    
    Business Rules:
    - analysis_period_days = 60
    - avg_daily_sales_model = sales_qty_60d / 60
    - days_of_cover = free_stock_qty / avg_daily_sales_model
    - Velocity: quantile-based FAST/MEDIUM/SLOW
    - Critical thresholds (by free_stock_qty):
      * FAST -> free_stock_qty <= 5
      * MEDIUM -> free_stock_qty <= 3
      * SLOW -> free_stock_qty <= 1
      * OR days_of_cover < 14 (global rule)
    - recommended_order_qty uses business-safe caps, ABC-based target cover days, and product-type limits
    - preferred_daily_sales = avg_daily_sales_1c if > 0 else avg_daily_sales_model, then clamped for sanity
    """
    
    def __init__(self, analysis_period_days: int = ANALYSIS_PERIOD_DAYS):
        self.analysis_period_days = analysis_period_days
        self.logger = logger
        self.display_cap = DISPLAY_CAP
        self.max_daily_sales_cap = MAX_DAILY_SALES_CAP
        self.half_year_weeks = HALF_YEAR_WEEKS
        self.default_target_stock_weeks = DEFAULT_TARGET_STOCK_WEEKS
        self.non_radiator_buffer_ratio = NON_RADIATOR_BUFFER_RATIO
        self.working_days_per_week = WORKING_DAYS_PER_WEEK
        self.working_days_per_month = WORKING_DAYS_PER_MONTH
        self.radiator_min_monthly_order_qty = RADIATOR_MIN_MONTHLY_ORDER_QTY
        self.radiator_peak_monthly_order_qty = RADIATOR_PEAK_MONTHLY_ORDER_QTY
        self.radiator_min_coverage_ratio_to_skip = RADIATOR_MIN_COVERAGE_RATIO_TO_SKIP
        self.radiator_target_month_coverage_ratio = RADIATOR_TARGET_MONTH_COVERAGE_RATIO

    def _normalize_name(self, value: str) -> str:
        value = str(value or "").strip().lower()
        value = value.replace("ё", "е")
        value = re.sub(r"\s+", " ", value)
        return value

    def _extract_unipump_pump_key(self, value: str) -> str:
        """
        Extract canonical Unipump pump key, keeping UPC and CP as different models.
        Supports both raw Russian names and canonical fallback names.
        """
        text = self._normalize_name(value)
        if "unipump" not in text:
            return ""

        if "насос" not in text and "upc" not in text and "cp" not in text:
            return ""

        text = text.replace("upс", "upc")
        text = text.replace("ср", "cp")
        text = text.replace("циркуляц.", "циркуляц")
        text = text.replace("(отопл.)", "")
        text = text.replace("(отопл)", "")
        text = text.replace("отопл.", "")
        text = text.replace("отопл", "")
        text = re.sub(r"\s+", " ", text).strip()

        if re.search(r"\bupc\b", text):
            model = "upc"
        elif re.search(r"\bcp\b", text):
            model = "cp"
        else:
            return ""

        match = UNIPUMP_PUMP_SIZE_PATTERN.search(text)
        if not match:
            return ""

        diameter, head, mount = match.groups()
        return f"unipump {model} {diameter}-{head} {mount}"

    def _infer_product_group(self, name: str) -> str:
        name = self._normalize_name(name)

        if "rens" in name or "радиатор" in name:
            return "радиаторы"
        if "котел" in name or "baxi" in name or "navien" in name:
            return "котлы"
        if "колонка" in name or "gwh" in name or "inflame" in name or "genberg" in name:
            return "газовые колонки"
        if "бойлер" in name or "ariston" in name or "vls" in name or "nts" in name:
            return "бойлеры"
        if (
            "coax" in name
            or "коакси" in name
            or "camino" in name
            or "immergas" in name
            or "манжета" in name
            or "изолятор кровли" in name
            or "конденсатоотводчик" in name
            or "наконечник" in name
            or "муфта 80/60" in name
            or "труба алюминиевая d80" in name
            or "колено алюминиевое" in name
            or "хомут 100" in name
            or "хомут крепления к стене д 80" in name
        ):
            return "коаксиалы"
        if "насос" in name or "unipump" in name or "upc" in name or re.search(r"\bcp\b", name):
            return "насосы"
        if (
            "stabil" in name
            or "стаб" in name
            or "teplocom" in name
            or "теплоком" in name
            or "solpi" in name
            or "tsd-500va" in name
            or "tsd 500va" in name
        ):
            return "стабилизаторы"
        return "прочее"

    def _is_priority_item(self, name: str) -> bool:
        name = self._normalize_name(name)

        if name in EXCLUDED_BOILER_EXACT_NAMES:
            return False

        if name in TARGET_COAXIAL_EXACT_NAMES:
            return True

        pump_key = self._extract_unipump_pump_key(name)
        if pump_key:
            return pump_key in TARGET_UNIPUMP_PUMP_KEYS

        return any(re.search(pattern, name) for pattern in PRIORITY_PATTERNS)

    def _is_special_order_item(self, name: str) -> bool:
        name = self._normalize_name(name)
        if name in TARGET_COAXIAL_EXACT_NAMES:
            return False
        return any(re.search(pattern, name) for pattern in SPECIAL_ORDER_PATTERNS)

    def _is_excluded_radiator_brand(self, name: str) -> bool:
        return is_excluded_radiator_brand(name)

    def _is_procurement_scope_item(self, row: pd.Series) -> bool:
        """
        Hard procurement scope:
        - only priority whitelist
        - no special-order items
        - no 'прочее'
        - exclude substitute radiator brands (Ruterm / Orso)
        """
        group_name = self._normalize_name(row.get("product_group", ""))
        product_name = self._normalize_name(row.get("product_name", ""))
        priority_flag = bool(row.get("priority_flag", False))
        special_order_flag = bool(row.get("special_order_flag", False))

        if not priority_flag:
            return False
        if special_order_flag:
            return False
        if group_name == "прочее":
            return False
        if group_name == "радиаторы" and self._is_excluded_radiator_brand(product_name):
            return False

        return True

    def _round_half_up(self, value: float) -> int:
        if pd.isna(value):
            return 0
        if value < 1:
            return 0
        return int(math.floor(float(value) + 0.5))

    def _sanitize_non_negative_number(self, value) -> float:
        value = pd.to_numeric(value, errors="coerce")
        if pd.isna(value) or value < 0:
            return 0.0
        return float(value)

    def _get_radiator_month_qty_columns(self, df: pd.DataFrame) -> list[str]:
        return [
            col for col in df.columns
            if col.startswith("radiator_qty_") and re.search(r"_\d{4}$", col)
        ]

    def _sanitize_radiator_month_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        month_qty_cols = self._get_radiator_month_qty_columns(df)
        for col in month_qty_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
            negative_count = int((df[col] < 0).sum())
            if negative_count > 0:
                self.logger.warning(
                    f"Radiator month column '{col}' contains {negative_count} negative values; clamping them to 0"
                )
            df[col] = df[col].clip(lower=0)
        return df

    def _get_completed_ytd_months(self) -> int:
        today = datetime.now()
        return max(1, today.month - 1)

    def _get_radiator_monthly_demand(self, row: pd.Series) -> float:
        """
        Monthly demand based on recent monthly radiator reports.
        Uses up to last 3 months with non-negative sales only.
        Works dynamically with monthly columns like radiator_qty_jan_2026.
        """
        month_cols = []
        for col in row.index:
            if isinstance(col, str) and col.startswith("radiator_qty_") and re.search(r"_\d{4}$", col):
                month_cols.append(col)

        month_cols = sorted(month_cols, reverse=True)

        values = []
        for col in month_cols:
            v = self._sanitize_non_negative_number(row.get(col, np.nan))
            if v > 0:
                values.append(v)
            if len(values) == 3:
                break

        if values:
            return float(np.mean(values))

        fallback_month = pd.to_numeric(row.get("preferred_daily_sales", 0), errors="coerce") * self.working_days_per_month
        return float(fallback_month if pd.notna(fallback_month) and fallback_month > 0 else 0.0)

    def _get_radiator_procurement_daily_sales(self, row: pd.Series) -> int:
        monthly_demand = self._get_radiator_monthly_demand(row)
        daily_demand = monthly_demand / self.working_days_per_month
        return self._round_half_up(daily_demand)

    def _get_radiator_coverage_by_abc(self, abc_class: str) -> float:
        return RADIATOR_ABC_COVERAGE.get(abc_class, RADIATOR_ABC_COVERAGE["C"])

    def _get_radiator_order_pool_qty(self, radiator_df: pd.DataFrame) -> int:
        if radiator_df.empty:
            return 0

        total_monthly_demand = float(pd.to_numeric(radiator_df.get("radiator_monthly_demand", 0), errors="coerce").fillna(0).sum())

        prev_month_total = 0.0
        if "radiator_qty_prev_month" in radiator_df.columns:
            prev_month_total = float(pd.to_numeric(radiator_df["radiator_qty_prev_month"], errors="coerce").fillna(0).sum())

        current_year_total = 0.0
        if "radiator_qty_current_year" in radiator_df.columns:
            current_year_total = float(pd.to_numeric(radiator_df["radiator_qty_current_year"], errors="coerce").fillna(0).sum())

        current_year_monthly = current_year_total / self._get_completed_ytd_months() if current_year_total > 0 else 0.0
        demand_signal = max(total_monthly_demand, prev_month_total, current_year_monthly)

        if demand_signal >= RADIATOR_DEMAND_PEAK_THRESHOLD:
            return self.radiator_peak_monthly_order_qty
        return self.radiator_min_monthly_order_qty

    def _get_hard_cap(self, group_name: str, product_name: str) -> int:
        return HARD_CAP
    
    def _get_avg_weekly_sales(self, row: pd.Series) -> float:
        gpy_weekly = pd.to_numeric(row.get("avg_weekly_sales_gpy", np.nan), errors="coerce")
        if pd.notna(gpy_weekly) and gpy_weekly > 0:
            return float(gpy_weekly)

        fallback_weekly = pd.to_numeric(row.get("avg_weekly_sales_fallback", np.nan), errors="coerce")
        if pd.notna(fallback_weekly) and fallback_weekly > 0:
            return float(fallback_weekly)

        preferred_daily_sales = pd.to_numeric(row.get("preferred_daily_sales", np.nan), errors="coerce")
        if pd.notna(preferred_daily_sales) and preferred_daily_sales > 0:
            return float(preferred_daily_sales * 7)

        return 0.0

    def _get_procurement_daily_sales(self, row: pd.Series) -> int:
        weekly_sales = self._get_avg_weekly_sales(row)
        daily_sales = weekly_sales / 7.0

        if daily_sales < 1:
            return 0

        base = int(daily_sales)
        fractional = daily_sales - base

        if fractional > 0.5:
            return base + 1
        return base

    def _get_non_radiator_target_multiplier(self, product_name: str) -> float:
        normalized_name = self._normalize_name(product_name)
        return TARGET_NON_RADIATOR_ORDER_MULTIPLIERS.get(normalized_name, NON_RADIATOR_BASE_MULTIPLIER)
    
    def calculate_avg_daily_sales_model(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        if "sales_qty_60d" not in df.columns:
            self.logger.warning("sales_qty_60d column not found")
            df["avg_daily_sales_model"] = 0
            return df
        
        df["avg_daily_sales_model"] = df["sales_qty_60d"] / self.analysis_period_days
        df["avg_daily_sales_model"] = df["avg_daily_sales_model"].fillna(0)
        df["avg_daily_sales_model"] = df["avg_daily_sales_model"].clip(lower=0)
        
        if "avg_daily_sales_1c" not in df.columns:
            df["avg_daily_sales_1c"] = df["avg_daily_sales_model"]
        
        product_name_series = df.get("product_name", pd.Series("", index=df.index)).astype(str)
        df["product_group"] = product_name_series.apply(self._infer_product_group)
        df["priority_flag"] = product_name_series.apply(self._is_priority_item)
        df["special_order_flag"] = product_name_series.apply(self._is_special_order_item)
        df["procurement_scope_flag"] = df.apply(self._is_procurement_scope_item, axis=1)
        
        if "sales_qty_180d" in df.columns:
            df["avg_weekly_sales_fallback"] = pd.to_numeric(df["sales_qty_180d"], errors="coerce").fillna(0) / self.half_year_weeks
        else:
            df["avg_weekly_sales_fallback"] = pd.to_numeric(df["avg_daily_sales_model"], errors="coerce").fillna(0) * 7

        df["avg_weekly_sales_fallback"] = df["avg_weekly_sales_fallback"].clip(lower=0)
        df["procurement_daily_sales"] = df.apply(self._get_procurement_daily_sales, axis=1)
        
        return df
    
    def calculate_days_of_cover(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        if "free_stock_qty" not in df.columns or "avg_daily_sales_model" not in df.columns:
            self.logger.warning("Required columns for days_of_cover not found")
            df["days_of_cover"] = 0
            return df
        
        df["days_of_cover"] = np.where(
            df["avg_daily_sales_model"] > 0,
            df["free_stock_qty"] / df["avg_daily_sales_model"],
            np.inf
        )
        
        df["days_of_cover"] = df["days_of_cover"].clip(upper=365)
        df["days_of_cover"] = df["days_of_cover"].fillna(0)
        
        return df
    
    def segment_by_velocity(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        if "avg_daily_sales_model" not in df.columns:
            df["velocity_segment"] = "UNKNOWN"
            return df
        
        valid_sales = df[df["avg_daily_sales_model"] > 0]["avg_daily_sales_model"]
        
        if len(valid_sales) < 3:
            df["velocity_segment"] = "MEDIUM"
            return df
        
        p33 = valid_sales.quantile(0.33)
        p66 = valid_sales.quantile(0.66)
        
        def assign_velocity(sales):
            if sales == 0:
                return "SLOW"
            if sales >= p66:
                return "FAST"
            elif sales >= p33:
                return "MEDIUM"
            else:
                return "SLOW"
        
        df["velocity_segment"] = df["avg_daily_sales_model"].apply(assign_velocity)
        
        velocity_dist = df["velocity_segment"].value_counts().to_dict()
        self.logger.info(f"Velocity distribution: {velocity_dist}")
        
        return df
    
    def flag_critical_items(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["critical_flag"] = False
        
        if "days_of_cover" not in df.columns or "velocity_segment" not in df.columns or "free_stock_qty" not in df.columns:
            self.logger.warning("Required columns for critical flag not found")
            return df
        
        doc = df["days_of_cover"]
        vel = df["velocity_segment"]
        stock = df["free_stock_qty"]
        
        cond_global = doc < CRITICAL_DAYS_OF_COVER
        cond_fast = (vel == "FAST") & (stock <= CRITICAL_STOCK_THRESHOLDS["FAST"])
        cond_med = (vel == "MEDIUM") & (stock <= CRITICAL_STOCK_THRESHOLDS["MEDIUM"])
        cond_slow = (vel == "SLOW") & (stock <= CRITICAL_STOCK_THRESHOLDS["SLOW"])
        
        df["critical_flag"] = cond_global | cond_fast | cond_med | cond_slow

        if "procurement_scope_flag" in df.columns:
            df.loc[~df["procurement_scope_flag"], "critical_flag"] = False

        critical_count = df["critical_flag"].sum()
        total_count = len(df)
        pct = (critical_count / total_count * 100) if total_count > 0 else 0
        self.logger.warning(f"Critical items flagged: {critical_count} ({pct:.1f}%)")

        return df
    
    def calculate_recommended_order_qty(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        if "avg_daily_sales_model" not in df.columns or "free_stock_qty" not in df.columns:
            self.logger.warning("Required columns for order qty calculation not found")
            df["recommended_order_qty"] = 0
            df["recommended_order_qty_display"] = 0
            return df

        if "avg_daily_sales_1c" in df.columns:
            df["preferred_daily_sales"] = np.where(
                pd.to_numeric(df["avg_daily_sales_1c"], errors="coerce").fillna(0) > 0,
                pd.to_numeric(df["avg_daily_sales_1c"], errors="coerce").fillna(0),
                pd.to_numeric(df["avg_daily_sales_model"], errors="coerce").fillna(0),
            )
        else:
            df["preferred_daily_sales"] = pd.to_numeric(df["avg_daily_sales_model"], errors="coerce").fillna(0)

        df["preferred_daily_sales"] = pd.to_numeric(df["preferred_daily_sales"], errors="coerce").fillna(0)
        df["preferred_daily_sales"] = df["preferred_daily_sales"].clip(lower=0, upper=self.max_daily_sales_cap)

        def get_target_days(abc_class: str) -> int:
            return ABC_TARGET_DAYS.get(abc_class, ABC_TARGET_DAYS["C"])

        if "abc_class" not in df.columns:
            df["abc_class"] = "C"
        df["target_cover_days"] = df["abc_class"].fillna("C").apply(get_target_days)

        free_stock = pd.to_numeric(df["free_stock_qty"], errors="coerce").fillna(0)
        df["base_need"] = (df["preferred_daily_sales"] * df["target_cover_days"] - free_stock).clip(lower=0)

        if "required_purchase_qty_1c" in df.columns:
            planning_limit = pd.to_numeric(df["required_purchase_qty_1c"], errors="coerce").fillna(0)
        else:
            planning_limit = pd.Series(0, index=df.index)

        df["recommended_order_qty"] = np.where(
            planning_limit > 0,
            np.minimum(df["base_need"], planning_limit),
            df["base_need"]
        )

        product_name_series = df.get("product_name", pd.Series("", index=df.index)).astype(str)
        df["product_group"] = product_name_series.apply(self._infer_product_group)
        df["priority_flag"] = product_name_series.apply(self._is_priority_item)
        df["special_order_flag"] = product_name_series.apply(self._is_special_order_item)
        df["procurement_scope_flag"] = df.apply(self._is_procurement_scope_item, axis=1)

        df.loc[~df["procurement_scope_flag"], "recommended_order_qty"] = 0

        radiator_mask = df["product_group"] == "радиаторы"
        non_radiator_mask = ~radiator_mask

        df["avg_weekly_sales"] = df.apply(self._get_avg_weekly_sales, axis=1)
        df["procurement_daily_sales"] = df.apply(self._get_procurement_daily_sales, axis=1)

        avg_weekly = pd.to_numeric(df["avg_weekly_sales"], errors="coerce").fillna(0)
        df["non_radiator_target_multiplier"] = product_name_series.apply(
            self._get_non_radiator_target_multiplier
        )
        raw_target = avg_weekly * df["non_radiator_target_multiplier"]

        def round_target(x):
            if x < 0.2:
                return 0
            elif x < 1:
                return 1
            else:
                return int(math.ceil(x))

        df["target_stock_qty"] = raw_target.apply(round_target)

        free_stock = pd.to_numeric(df["free_stock_qty"], errors="coerce").fillna(0)

        df.loc[non_radiator_mask, "recommended_order_qty"] = (
            df.loc[non_radiator_mask, "target_stock_qty"] - free_stock.loc[non_radiator_mask]
        ).clip(lower=0)

        if radiator_mask.any():
            radiator_df = df.loc[radiator_mask].copy()
            radiator_df = self._sanitize_radiator_month_columns(radiator_df)

            radiator_df["radiator_monthly_demand"] = radiator_df.apply(self._get_radiator_monthly_demand, axis=1)

            radiator_abc_series = radiator_df.get("radiator_abc_class")
            if radiator_abc_series is None:
                radiator_abc_series = radiator_df.get("abc_class", pd.Series("C", index=radiator_df.index))

            radiator_df["radiator_abc_class"] = radiator_abc_series.fillna(radiator_df.get("abc_class", "C")).fillna("C")
            radiator_df["radiator_coverage"] = radiator_df["radiator_abc_class"].apply(self._get_radiator_coverage_by_abc)

            radiator_df["radiator_target_stock_qty"] = (
                radiator_df["radiator_monthly_demand"] * radiator_df["radiator_coverage"]
            )

            radiator_df["radiator_to_order_qty"] = (
                radiator_df["radiator_target_stock_qty"]
                - pd.to_numeric(radiator_df["free_stock_qty"], errors="coerce").fillna(0).clip(lower=0)
            ).clip(lower=0)

            for col in self._get_radiator_month_qty_columns(radiator_df):
                df.loc[radiator_mask, col] = radiator_df[col]

            radiator_df["recommended_order_qty"] = radiator_df["radiator_to_order_qty"].apply(
                lambda x: int(math.ceil(x)) if x > 0 else 0
            )
            radiator_df["recommended_order_qty"] = radiator_df["recommended_order_qty"].clip(lower=0)

            df.loc[radiator_mask, "recommended_order_qty"] = radiator_df["recommended_order_qty"]
            df.loc[radiator_mask, "radiator_monthly_demand"] = radiator_df["radiator_monthly_demand"]
            df.loc[radiator_mask, "radiator_abc_class"] = radiator_df["radiator_abc_class"]
            df.loc[radiator_mask, "radiator_to_order_qty"] = radiator_df["radiator_to_order_qty"]
            df.loc[radiator_mask, "radiator_target_stock_qty"] = radiator_df["radiator_target_stock_qty"]
            df.loc[radiator_mask, "radiator_coverage"] = radiator_df["radiator_coverage"]

        df["hard_cap"] = [
            self._get_hard_cap(group_name, product_name)
            for group_name, product_name in zip(df["product_group"], product_name_series)
        ]
        df["recommended_order_qty"] = np.minimum(df["recommended_order_qty"], df["hard_cap"])

        non_radiator_no_demand_mask = (
            non_radiator_mask
            & (~df["priority_flag"])
            & (pd.to_numeric(df["avg_weekly_sales"], errors="coerce").fillna(0) < 1)
        )
        df.loc[non_radiator_no_demand_mask, "recommended_order_qty"] = 0

        priority_pump_min_order_mask = (
            non_radiator_mask
            & (df["product_group"] == "насосы")
            & (df["priority_flag"])
            & (pd.to_numeric(df["avg_weekly_sales"], errors="coerce").fillna(0) > 0)
            & (pd.to_numeric(df["free_stock_qty"], errors="coerce").fillna(0) <= 0)
        )
        df.loc[priority_pump_min_order_mask, "recommended_order_qty"] = np.maximum(
            df.loc[priority_pump_min_order_mask, "recommended_order_qty"],
            1,
        )

        pump_debug_mask = (
            df["product_name"].astype(str).str.contains("unipump", case=False, na=False)
            & (
                df["product_name"].astype(str).str.contains("насос", case=False, na=False)
                | df["product_name"].astype(str).str.contains("upc", case=False, na=False)
                | df["product_name"].astype(str).str.contains(r"\bcp\b", case=False, na=False, regex=True)
            )
        )
        if pump_debug_mask.any():
            canonical_pump_mask = (
                df["product_group"].eq("насосы")
                & df["priority_flag"].fillna(False)
                & df["product_name"].astype(str).apply(
                    lambda x: self._extract_unipump_pump_key(x) in TARGET_UNIPUMP_PUMP_KEYS
                )
            )
            pump_debug_df = df.loc[
                canonical_pump_mask | pump_debug_mask,
                [
                    "product_name",
                    "product_group",
                    "priority_flag",
                    "procurement_scope_flag",
                    "gross_profit_year_qty",
                    "avg_weekly_sales_gpy",
                    "avg_weekly_sales_fallback",
                    "avg_weekly_sales",
                    "free_stock_qty",
                    "target_stock_qty",
                    "recommended_order_qty",
                ],
            ].copy()
            pump_debug_df["pump_model_key"] = pump_debug_df["product_name"].apply(self._extract_unipump_pump_key)
            self.logger.info(
                "Pump debug before final cleanup:\n"
                + pump_debug_df.to_string()
            )

        priority_count = int(df["priority_flag"].sum()) if "priority_flag" in df.columns else 0
        group_distribution = df["product_group"].value_counts().to_dict() if "product_group" in df.columns else {}
        self.logger.info(f"Priority items in scope: {priority_count}")
        self.logger.info(f"Product group distribution: {group_distribution}")
        if radiator_mask.any():
            radiator_rows = int(radiator_mask.sum())
            radiator_active = int((df.loc[radiator_mask, "recommended_order_qty"] > 0).sum())
            radiator_total_order = int(pd.to_numeric(df.loc[radiator_mask, "recommended_order_qty"], errors="coerce").fillna(0).sum())
            self.logger.info(
                f"Radiator planning: rows={radiator_rows}, active_positions={radiator_active}, total_order_qty={radiator_total_order}"
            )

        df["recommended_order_qty"] = pd.to_numeric(df["recommended_order_qty"], errors="coerce").fillna(0)
        df["recommended_order_qty"] = df["recommended_order_qty"].round(0).astype(int)

        df = df.drop(columns=["non_radiator_target_multiplier"], errors="ignore")
        df["recommended_order_qty_display"] = df["recommended_order_qty"]

        if "procurement_scope_flag" in df.columns:
            df["visible_in_dashboard"] = df["procurement_scope_flag"]
        else:
            df["visible_in_dashboard"] = True

        order_count = int((df["recommended_order_qty"] > 0).sum())
        total_qty = int(df["recommended_order_qty"].sum())

        avg_weekly_summary = {
            "min": float(df["avg_weekly_sales"].min()) if "avg_weekly_sales" in df.columns and len(df) > 0 else 0.0,
            "max": float(df["avg_weekly_sales"].max()) if "avg_weekly_sales" in df.columns and len(df) > 0 else 0.0,
            "mean": float(df["avg_weekly_sales"].mean()) if "avg_weekly_sales" in df.columns and len(df) > 0 else 0.0,
        }
        procurement_daily_summary = {
            "min": int(df["procurement_daily_sales"].min()) if "procurement_daily_sales" in df.columns and len(df) > 0 else 0,
            "max": int(df["procurement_daily_sales"].max()) if "procurement_daily_sales" in df.columns and len(df) > 0 else 0,
            "mean": float(df["procurement_daily_sales"].mean()) if "procurement_daily_sales" in df.columns and len(df) > 0 else 0.0,
        }
        self.logger.info(f"Average weekly sales summary: {avg_weekly_summary}")
        self.logger.info(f"Procurement daily sales summary: {procurement_daily_summary}")
        self.logger.info(
            f"Recommended orders: {order_count} products, total qty: {total_qty}, "
            f"target stock weeks: {self.default_target_stock_weeks}"
        )

        return df
    
    def compute_all_metrics(self, df: pd.DataFrame) -> pd.DataFrame:
        self.logger.info("Computing all procurement metrics...")
        
        df = self.calculate_avg_daily_sales_model(df)
        df = self.calculate_days_of_cover(df)
        df = self.segment_by_velocity(df)
        df = self.flag_critical_items(df)
        df = self.calculate_recommended_order_qty(df)
        
        df["metrics_calculated_at"] = datetime.now()
        df["analysis_period_days"] = self.analysis_period_days
        
        self.logger.success("All metrics computed successfully")
        return df
    
    def get_metrics_summary(self, df: pd.DataFrame) -> Dict:
        if "procurement_scope_flag" in df.columns:
            scoped_df = df[df["procurement_scope_flag"]].copy()
        else:
            scoped_df = df.copy()

        summary = {
            "total_products": len(scoped_df),
            "critical_items": int(scoped_df["critical_flag"].sum()) if "critical_flag" in scoped_df.columns else 0,
            "products_to_order": int((scoped_df["recommended_order_qty"] > 0).sum()) if "recommended_order_qty" in scoped_df.columns else 0,
            "total_recommended_qty": int(scoped_df["recommended_order_qty_display"].sum()) if "recommended_order_qty_display" in scoped_df.columns else 0,
            "avg_days_of_cover": float(scoped_df["days_of_cover"].mean()) if "days_of_cover" in scoped_df.columns and len(scoped_df) > 0 else 0,
            "velocity_distribution": scoped_df["velocity_segment"].value_counts().to_dict() if "velocity_segment" in scoped_df.columns else {},
            "abc_distribution": scoped_df["abc_class"].value_counts().to_dict() if "abc_class" in scoped_df.columns else {},
            "group_distribution": scoped_df["product_group"].value_counts().to_dict() if "product_group" in scoped_df.columns else {},
            "priority_items": int(scoped_df["priority_flag"].sum()) if "priority_flag" in scoped_df.columns else 0,
        }
        return summary