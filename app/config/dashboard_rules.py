"""
Dashboard rules: display/UI constants for the HTML dashboard —
group ordering, column labels, table column sets, etc.
"""

# ── Group display order ──────────────────────────────────────────
GROUP_ORDER = [
    "котлы",
    "радиаторы",
    "газовые колонки",
    "бойлеры",
    "коаксиалы",
    "насосы",
    "стабилизаторы",
]

GROUP_TITLES = {
    "котлы": "Котлы",
    "радиаторы": "Радиаторы",
    "газовые колонки": "Газовые колонки",
    "бойлеры": "Бойлеры",
    "коаксиалы": "Коаксиалы",
    "насосы": "Насосы",
    "стабилизаторы": "Стабилизаторы",
}


# ── Velocity labels (EN → RU) ───────────────────────────────────
VELOCITY_RU = {
    "FAST": "Быстрая",
    "MEDIUM": "Средняя",
    "SLOW": "Медленная",
}


# ── Column name translations ────────────────────────────────────
COLUMN_NAMES_RU = {
    "product_name": "Наименование",
    "product_group": "Группа",
    "abc_class": "ABC",
    "radiator_abc_class": "ABC",
    "free_stock_qty": "Остаток",
    "days_of_cover": "Дней покрытия",
    "velocity_segment": "Оборачиваемость",
    "recommended_order_qty_display": "К заказу, шт",
    "avg_daily_sales_1c": "Ср. продажа 1С",
    "avg_daily_sales_model": "Ср. продажа (модель)",
    "avg_weekly_sales": "Ср. продажа / неделя",
    "procurement_daily_sales": "Ср. продажа / день",
    "radiator_monthly_demand": "Спрос / месяц",
    "radiator_target_stock_qty": "Целевой запас",
    "radiator_coverage": "Коэф. покрытия",
    "radiator_qty_jan_2026": "Янв 2026",
    "radiator_qty_feb_2026": "Фев 2026",
    "radiator_qty_mar_2026": "Мар 2026",
    "radiator_qty_apr_2026": "Апр 2026",
    "priority_flag": "Whitelist",
    "critical_flag": "Критично",
}

NUMERIC_COLS_RU = {
    "Остаток",
    "Дней покрытия",
    "К заказу, шт",
    "Ср. продажа 1С",
    "Ср. продажа (модель)",
    "Ср. продажа / неделя",
    "Ср. продажа / день",
    "Спрос / месяц",
    "Целевой запас",
    "Коэф. покрытия",
    "Янв 2026",
    "Фев 2026",
    "Мар 2026",
    "Апр 2026",
}


# ── Priority whitelist section ───────────────────────────────────
PRIORITY_WHITELIST_ORDER = [
    "котлы",
    "газовые колонки",
    "бойлеры",
    "коаксиалы",
    "насосы",
    "стабилизаторы",
    "радиаторы",
]

PRIORITY_WHITELIST_LABELS = {
    "котлы": "Котлы / whitelist",
    "газовые колонки": "Газовые колонки / whitelist",
    "бойлеры": "Бойлеры / whitelist",
    "коаксиалы": "Коаксиалы / whitelist",
    "насосы": "Насосы / whitelist",
    "стабилизаторы": "Стабилизаторы / whitelist",
    "радиаторы": "Радиаторы / whitelist",
}


# ── Table column sets ────────────────────────────────────────────
CRITICAL_TABLE_COLUMNS = [
    "product_name",
    "abc_class",
    "free_stock_qty",
    "days_of_cover",
    "velocity_segment",
    "recommended_order_qty_display",
]

ORDERS_TABLE_COLUMNS = [
    "product_name",
    "abc_class",
    "free_stock_qty",
    "avg_weekly_sales",
    "recommended_order_qty_display",
]

RADIATOR_TABLE_COLUMNS = [
    "product_name",
    "radiator_abc_class",
    "radiator_qty_jan_2026",
    "radiator_qty_feb_2026",
    "radiator_qty_mar_2026",
    "radiator_qty_apr_2026",
    "radiator_monthly_demand",
    "radiator_coverage",
    "radiator_target_stock_qty",
    "free_stock_qty",
    "recommended_order_qty_display",
]
