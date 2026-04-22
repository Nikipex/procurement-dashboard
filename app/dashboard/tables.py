import pandas as pd
from loguru import logger

from app.config.dashboard_rules import (
    GROUP_ORDER,
    GROUP_TITLES,
    VELOCITY_RU,
    COLUMN_NAMES_RU,
    NUMERIC_COLS_RU,
    PRIORITY_WHITELIST_ORDER,
    PRIORITY_WHITELIST_LABELS,
    CRITICAL_TABLE_COLUMNS,
    ORDERS_TABLE_COLUMNS,
    RADIATOR_TABLE_COLUMNS,
)
from app.config.product_rules import is_excluded_radiator_brand


def format_number(x):
    """Format numbers for display with thousand separators."""
    if pd.isna(x):
        return "N/A"
    try:
        if isinstance(x, float) and x == int(x):
            return f"{int(x):,}".replace(",", " ")
        return f"{x:,.2f}".replace(",", " ")
    except Exception:
        return str(x)


def _parse_display_number(value) -> float:
    try:
        return float(str(value).replace(" ", "").replace(",", "."))
    except Exception:
        return 0.0


def _badge(text: str, bg: str, fg: str = "#2b2b2b") -> str:
    return (
        f'<span style="display:inline-block; padding:4px 10px; border-radius:999px; '
        f'background:{bg}; color:{fg}; font-weight:600;">{text}</span>'
    )


def _apply_radiator_visuals(display_df: pd.DataFrame) -> pd.DataFrame:
    styled_df = display_df.copy()

    if "Коэф. покрытия" in styled_df.columns:
        def style_coverage(v):
            num = _parse_display_number(v)
            if num >= 1.0:
                return _badge(str(v), "#e7f6ec", "#067647")
            if num >= 0.7:
                return _badge(str(v), "#fff4e5", "#b54708")
            return _badge(str(v), "#fde8e8", "#b42318")
        styled_df["Коэф. покрытия"] = styled_df["Коэф. покрытия"].apply(style_coverage)

    if "К заказу, шт" in styled_df.columns:
        def style_order_qty(v):
            num = _parse_display_number(v)
            if num <= 0:
                return _badge(str(v), "#f2f4f7", "#667085")
            if num < 32:
                return _badge(str(v), "#fff4e5", "#b54708")
            return _badge(str(v), "#fde8e8", "#b42318")
        styled_df["К заказу, шт"] = styled_df["К заказу, шт"].apply(style_order_qty)

    return styled_df


def _get_dashboard_scope_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    scoped_df = df.copy()
    if "visible_in_dashboard" in scoped_df.columns:
        scoped_df = scoped_df[scoped_df["visible_in_dashboard"] == True].copy()

    return scoped_df


def _format_display_df(display_df: pd.DataFrame) -> pd.DataFrame:
    display_df = display_df.copy()

    rename_map = {k: v for k, v in COLUMN_NAMES_RU.items() if k in display_df.columns}
    display_df = display_df.rename(columns=rename_map)

    for col in display_df.columns:
        if col in NUMERIC_COLS_RU:
            display_df[col] = display_df[col].apply(format_number)

    if "Критично" in display_df.columns:
        display_df["Критично"] = display_df["Критично"].apply(
            lambda x: "Да" if x is True or x == "Да" else "Нет"
        )

    if "Whitelist" in display_df.columns:
        display_df["Whitelist"] = display_df["Whitelist"].apply(
            lambda x: "Да" if x is True or x == "Да" else "Нет"
        )

    if "Оборачиваемость" in display_df.columns:
        display_df["Оборачиваемость"] = display_df["Оборачиваемость"].map(VELOCITY_RU).fillna(display_df["Оборачиваемость"])

    return display_df


def _render_table(display_df: pd.DataFrame, css_class: str) -> str:
    if display_df.empty:
        return "<div>Нет данных</div>"

    return display_df.to_html(
        index=False,
        classes=f"data-table {css_class}",
        border=0,
        na_rep="N/A",
        escape=False,
    )


def _get_radiator_priority(product_name: str) -> tuple:
    """
    Priority for RENS radiators:
    1) 22 type, height 500
    2) 22 type, height 300
    3) 22 type, height 200
    4) 11 type, height 500 (side only)
    5) then same logic for lower connection
    """
    import re

    name = str(product_name or "").lower()

    # connection priority: side first, lower second
    is_lower = ("нижнее" in name) or (" vk " in f" {name} ") or ("vk" in name and "подкл" in name)
    connection_rank = 1 if is_lower else 0

    match = re.search(r"(200|300|500)//(11|22)\*(\d+)", name)
    if match:
        height = int(match.group(1))
        radiator_type = int(match.group(2))
        length = int(match.group(3))
    else:
        height = 999
        radiator_type = 999
        length = 9999

    # 11 type lower connection should sink to the end, because business sells 11 mostly side-connection
    if is_lower and radiator_type == 11:
        connection_rank = 99

    if radiator_type == 22 and height == 500:
        type_height_rank = 0
    elif radiator_type == 22 and height == 300:
        type_height_rank = 1
    elif radiator_type == 22 and height == 200:
        type_height_rank = 2
    elif radiator_type == 11 and height == 500:
        type_height_rank = 3
    elif radiator_type == 11 and height == 300:
        type_height_rank = 4
    elif radiator_type == 11 and height == 200:
        type_height_rank = 5
    else:
        type_height_rank = 99

    return (connection_rank, type_height_rank, length)


def _is_rens_radiator_position(product_name: str) -> bool:
    """
    Detect radiator positions by business naming pattern, not by explicit brand token.
    Examples:
    - Стальной радиатор 500//11*0800 (1,2)
    - Стальной радиатор 300//22*0500 VK (1,2) нижнее подкл.
    - Стальной Радиатор 200//22*1400 Vcu (Universal 1,2) Нижнее Подкл. Rens
    """
    import re

    name = str(product_name or "").lower().replace("﻿", "").strip()

    pattern = r"стальной\s+радиатор\s+(200|300|500)//(11|22)\*(\d{4})"
    has_core_pattern = re.search(pattern, name) is not None
    has_12_marker = "1,2" in name

    return has_core_pattern and has_12_marker


def _is_excluded_radiator_brand(product_name: str) -> bool:
    """
    Exclude substitute/secondary radiator variants from the main RENS radiator block,
    but allow Universal for 200 lower connection radiators.
    Delegates to the shared function in product_rules.
    """
    return is_excluded_radiator_brand(product_name)


def _build_group_blocks(df: pd.DataFrame, css_class: str, per_group_limit: int | None, mode: str) -> str:
    if df.empty:
        return "<div>Нет данных</div>"

    html_blocks = []

    abc_priority = {"A": 0, "B": 1, "C": 2}
    if "abc_class" in df.columns:
        df = df.copy()
        df["abc_priority"] = df["abc_class"].map(abc_priority).fillna(3)

    for group_name in GROUP_ORDER:
        if mode == "orders" and group_name == "радиаторы":
            continue
        if "product_group" not in df.columns:
            break

        group_df = df[df["product_group"] == group_name].copy()
        if group_df.empty:
            continue

        if mode == "critical":
            sort_columns = ["abc_priority", "days_of_cover", "recommended_order_qty_display"]
            ascending = [True, True, False]
            columns = CRITICAL_TABLE_COLUMNS
        elif mode == "orders":
            sort_columns = ["abc_priority", "recommended_order_qty_display"]
            ascending = [True, False]
            if "days_of_cover" in group_df.columns:
                sort_columns.append("days_of_cover")
                ascending.append(True)
            columns = ORDERS_TABLE_COLUMNS
        else:
            sort_columns = ["recommended_order_qty_display"]
            ascending = [False]
            columns = CRITICAL_TABLE_COLUMNS

        existing_sort_columns = [col for col in sort_columns if col in group_df.columns]
        existing_ascending = [ascending[i] for i, col in enumerate(sort_columns) if col in group_df.columns]
        if existing_sort_columns:
            group_df = group_df.sort_values(existing_sort_columns, ascending=existing_ascending)

        if per_group_limit is not None:
            group_df = group_df.head(per_group_limit)
        available_columns = [col for col in columns if col in group_df.columns]
        display_df = group_df[available_columns].copy()
        display_df = _format_display_df(display_df)

        group_title = GROUP_TITLES.get(group_name, group_name.title())
        table_html = _render_table(display_df, css_class)
        html_blocks.append(
            f'<div class="group-block">'
            f'<h3 class="group-title">{group_title}</h3>'
            f'{table_html}'
            f'</div>'
        )

    if not html_blocks:
        return "<div>Нет данных</div>"

    return "\n".join(html_blocks)


def build_critical_items_table(df: pd.DataFrame, top_n: int = 50) -> str:
    """
    Build critical items grouped by product categories.
    Only procurement-scope items are shown.
    """
    if df.empty:
        return "<div>Нет данных</div>"

    if "critical_flag" not in df.columns:
        return "<div>Колонка critical_flag не найдена</div>"

    scoped_df = _get_dashboard_scope_df(df)
    critical_df = scoped_df[scoped_df["critical_flag"] == True].copy()

    if critical_df.empty:
        return "<div>Критичные позиции не найдены</div>"

    per_group_limit = max(5, top_n // max(1, len(GROUP_ORDER)))
    html = _build_group_blocks(critical_df, css_class="critical-table", per_group_limit=per_group_limit, mode="critical")

    logger.info(f"Critical items grouped table rendered from {len(critical_df)} scoped rows")
    return html


def build_recommended_orders_table(df: pd.DataFrame, top_n: int = 50) -> str:
    """
    Build recommended orders grouped by product categories.
    Only procurement-scope items are shown.
    """
    if df.empty:
        return "<div>Нет данных</div>"

    if "recommended_order_qty_display" not in df.columns:
        return "<div>Колонка recommended_order_qty_display не найдена</div>"

    scoped_df = _get_dashboard_scope_df(df)

    # Show the full procurement assortment by groups,
    # not only rows with positive recommended qty.
    orders_df = scoped_df.copy()

    if orders_df.empty:
        return "<div>Нет данных для закупки</div>"

    html = _build_group_blocks(
        orders_df,
        css_class="orders-table",
        per_group_limit=None,
        mode="orders",
    )

    logger.info(f"Recommended orders grouped table rendered from {len(orders_df)} scoped rows")
    return html


def build_top_risk_table(df: pd.DataFrame, top_n: int = 10) -> str:
    """
    Legacy helper. Now mirrors grouped critical items for procurement scope.
    """
    return build_critical_items_table(df, top_n=top_n)


def build_radiator_table(df: pd.DataFrame, top_n: int = 20) -> str:
    """
    Build full prioritized table for all RENS radiators 1,2.
    Radiators are rendered from the full dataset, without dashboard scope cutoff,
    because they have their own monthly procurement logic.
    """
    if df.empty:
        return "<div>Нет данных по радиаторам</div>"

    radiator_df = df.copy()

    radiator_df = radiator_df[
        radiator_df["product_name"].apply(_is_rens_radiator_position)
    ].copy()

    radiator_df = radiator_df[
        ~radiator_df["product_name"].apply(_is_excluded_radiator_brand)
    ].copy()

    if radiator_df.empty:
        return "<div>Нет позиций радиаторов RENS 1,2</div>"

    if "recommended_order_qty_display" not in radiator_df.columns:
        radiator_df["recommended_order_qty_display"] = 0

    radiator_df["radiator_priority"] = radiator_df["product_name"].apply(_get_radiator_priority)

    radiator_df = radiator_df.sort_values(
        by=["radiator_priority", "recommended_order_qty_display"],
        ascending=[True, False]
    )

    columns = RADIATOR_TABLE_COLUMNS

    available_columns = [col for col in columns if col in radiator_df.columns]
    display_df = radiator_df[available_columns].copy()
    if "radiator_abc_class" in display_df.columns:
        display_df["radiator_abc_class"] = display_df["radiator_abc_class"].fillna("C")
    if "radiator_qty_jan_2026" in display_df.columns:
        display_df["radiator_qty_jan_2026"] = display_df["radiator_qty_jan_2026"].fillna(0)
    if "radiator_qty_feb_2026" in display_df.columns:
        display_df["radiator_qty_feb_2026"] = display_df["radiator_qty_feb_2026"].fillna(0)
    if "radiator_qty_mar_2026" in display_df.columns:
        display_df["radiator_qty_mar_2026"] = display_df["radiator_qty_mar_2026"].fillna(0)
    if "radiator_qty_apr_2026" in display_df.columns:
        display_df["radiator_qty_apr_2026"] = display_df["radiator_qty_apr_2026"].fillna(0)
    logger.info(
        "Radiator table preview before formatting:\n"
        + display_df.head(30).to_string()
    )
    display_df = _format_display_df(display_df)
    display_df = _apply_radiator_visuals(display_df)

    html = _render_table(display_df, css_class="orders-table")

    logger.info(f"Radiator table: {len(display_df)} rows")
    return html


def build_priority_whitelist_table(df: pd.DataFrame, top_n: int = 80) -> str:
    """
    Whitelist section is intentionally disabled in the dashboard.
    Categories should remain only in the recommended orders section.
    """
    logger.info("Priority whitelist section is disabled")
    return ""