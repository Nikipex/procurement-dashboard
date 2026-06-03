# app/reports/pdf_report.py

import os
import re
import logging


from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
)
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


def _register_cyrillic_fonts():
    regular_candidates = [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]

    bold_candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]

    regular_path = next((p for p in regular_candidates if os.path.exists(p)), None)
    bold_path = next((p for p in bold_candidates if os.path.exists(p)), None)

    if regular_path:
        pdfmetrics.registerFont(TTFont("ReportRegular", regular_path))
        pdfmetrics.registerFont(TTFont("ReportBold", bold_path or regular_path))
        return "ReportRegular", "ReportBold"

    return "Helvetica", "Helvetica-Bold"


FONT_REGULAR, FONT_BOLD = _register_cyrillic_fonts()

logger = logging.getLogger(__name__)


def _safe_number(value, default=0):
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _fmt_int(value) -> str:
    return f"{int(round(_safe_number(value, 0))):,}".replace(",", " ")


def _truncate(text: str, limit: int = 55) -> str:
    text = str(text or "")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _is_likely_client_row(customer_name: str, product_name: str = "", customer_order: str = "") -> bool:
    """
    Practical filter for client rows from hierarchical sales export.
    Rejects obvious product / order / technical rows, but keeps real client names.
    """
    name = str(customer_name or "").strip()
    product = str(product_name or "").strip()
    order = str(customer_order or "").strip()

    if not name:
        return False

    low = name.lower()
    product_low = product.lower()
    order_low = order.lower()

    if low in {"none", "nan"}:
        return False

    if product_low and low == product_low:
        return False

    if order_low and low == order_low:
        return False

    negative_patterns = [
        r"(котел|радиатор|колонка|бойлер|труба|муфта|отвод|кран|фильтр|колено|насос|удлинение|манжета|грибок|дюбель|прокладк)",
        r"(baxi|bosch|royal thermo|лемакс|viterm|navien|valfex|aquatec|eco nova|eco life|turbo|classic)",
        r"(комплект|коаксиальн|алюминиев|стальной|насадки|сварочн|арту|аогв|vpg|впг|сиберия)",
        r"(заказ покупателя|офн\d+|от \d{2}\.\d{2}\.\d{4})",
        r"^\d{3,}([\-\/\s]\d+)*$",
        r"\d+//\d+\*\d+",
        r"\(\d+,\d+\)\s*$",
    ]

    for pattern in negative_patterns:
        if re.search(pattern, low):
            return False

    if len(name) < 6:
        return False

    return True


def _build_styles():
    styles = getSampleStyleSheet()

    styles.add(
        ParagraphStyle(
            name="ReportTitle",
            parent=styles["Title"],
            fontName=FONT_BOLD,
            fontSize=22,
            leading=26,
            textColor=colors.HexColor("#1E3A5F"),
            spaceAfter=4,
            alignment=TA_LEFT,
        )
    )

    styles.add(
        ParagraphStyle(
            name="ReportSubtitle",
            parent=styles["Normal"],
            fontName=FONT_REGULAR,
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#5F6B7A"),
            spaceAfter=12,
        )
    )

    styles.add(
        ParagraphStyle(
            name="SectionTitle",
            parent=styles["Heading2"],
            fontName=FONT_BOLD,
            fontSize=13,
            leading=16,
            textColor=colors.white,
            leftIndent=6,
            spaceAfter=8,
        )
    )

    styles.add(
        ParagraphStyle(
            name="CardLabel",
            parent=styles["Normal"],
            fontName=FONT_REGULAR,
            fontSize=9,
            leading=11,
            textColor=colors.HexColor("#5F6B7A"),
        )
    )

    styles.add(
        ParagraphStyle(
            name="CardValue",
            parent=styles["Normal"],
            fontName=FONT_BOLD,
            fontSize=16,
            leading=18,
            textColor=colors.HexColor("#1E3A5F"),
        )
    )

    styles.add(
        ParagraphStyle(
            name="BodyNote",
            parent=styles["Normal"],
            fontName=FONT_REGULAR,
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#334155"),
        )
    )

    return styles


def _section_header(title: str, bg_color: str, styles):
    tbl = Table([[Paragraph(title, styles["SectionTitle"])]], colWidths=[170 * mm])
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(bg_color)),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("BOX", (0, 0), (-1, -1), 0, colors.white),
            ]
        )
    )
    return tbl


def _styled_table(data, col_widths, header_color="#1976D2", zebra=True):
    table = Table(data, colWidths=col_widths, repeatRows=1)

    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(header_color)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
        ("FONTNAME", (0, 1), (-1, -1), FONT_REGULAR),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]

    if zebra and len(data) > 1:
        for row_idx in range(1, len(data)):
            bg = "#FFFFFF" if row_idx % 2 else "#F8FAFC"
            style_cmds.append(("BACKGROUND", (0, row_idx), (-1, row_idx), colors.HexColor(bg)))

    table.setStyle(TableStyle(style_cmds))
    return table


def _kpi_cards(total_products, total_revenue, active_clients, avg_revenue_per_client, styles):
    cards = [
        [
            Paragraph("Всего товарных позиций", styles["CardLabel"]),
            Paragraph("Общая выручка", styles["CardLabel"]),
        ],
        [
            Paragraph(_fmt_int(total_products), styles["CardValue"]),
            Paragraph(_fmt_int(total_revenue), styles["CardValue"]),
        ],
        [
            Paragraph("Активных клиентов", styles["CardLabel"]),
            Paragraph("Средняя выручка на клиента", styles["CardLabel"]),
        ],
        [
            Paragraph(_fmt_int(active_clients), styles["CardValue"]),
            Paragraph(_fmt_int(avg_revenue_per_client), styles["CardValue"]),
        ],
    ]

    table = Table(cards, colWidths=[85 * mm, 85 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#CBD5E1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#E2E8F0")),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F8FAFC")),
                ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#F8FAFC")),
            ]
        )
    )
    return table


# === Procurement PDF Report additions ===

def _procurement_kpi_cards(total_products, critical_count, out_of_stock_count, total_stock_qty, styles):
    cards = [
        [
            Paragraph("Целевых товарных позиций", styles["CardLabel"]),
            Paragraph("Остаток, шт", styles["CardLabel"]),
        ],
        [
            Paragraph(_fmt_int(total_products), styles["CardValue"]),
            Paragraph(_fmt_int(total_stock_qty), styles["CardValue"]),
        ],
        [
            Paragraph("Критичных позиций", styles["CardLabel"]),
            Paragraph("Out of stock", styles["CardLabel"]),
        ],
        [
            Paragraph(_fmt_int(critical_count), styles["CardValue"]),
            Paragraph(_fmt_int(out_of_stock_count), styles["CardValue"]),
        ],
    ]

    table = Table(cards, colWidths=[85 * mm, 85 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#CBD5E1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#E2E8F0")),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F8FAFC")),
                ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#F8FAFC")),
            ]
        )
    )
    return table


def _is_procurement_dataset(df) -> bool:
    if df is None or getattr(df, "empty", True):
        return False
    return {"product_group", "stock_status", "stock_qty", "sales_qty_60d"}.issubset(df.columns)


def _fmt_days(value) -> str:
    numeric = _safe_number(value, -1)
    if numeric < 0:
        return "—"
    return f"{numeric:.1f}"


def _build_procurement_pdf_report(final_df, output_path: str, period_label: str):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )
    styles = _build_styles()
    elements = []

    df = final_df.copy()
    df = df[df["product_group"] != "прочее"].copy()

    elements.append(Paragraph("Закупочный отчёт: Южный склад", styles["ReportTitle"]))
    subtitle = f"Период продаж: {period_label}. Источник: 1С PostgreSQL / public.procurement_south_mvp"
    elements.append(Paragraph(subtitle, styles["ReportSubtitle"]))

    total_products = int(df["product_name"].nunique())
    critical_count = int((df["stock_status"] == "critical").sum())
    out_of_stock_count = int((df["stock_status"] == "out_of_stock").sum())
    total_stock_qty = _safe_number(df["stock_qty"].sum(), 0)

    elements.append(_section_header("Ключевые показатели закупки", "#334155", styles))
    elements.append(Spacer(1, 4))
    elements.append(_procurement_kpi_cards(total_products, critical_count, out_of_stock_count, total_stock_qty, styles))
    elements.append(Spacer(1, 12))

    critical_data = [["Группа", "Наименование", "Остаток", "Продажи 60д", "Дней"]]
    critical_df = df[df["stock_status"].isin(["out_of_stock", "critical"])].copy()
    if not critical_df.empty:
        critical_df = critical_df.sort_values(
            by=["stock_status", "days_of_cover", "sales_qty_60d"],
            ascending=[True, True, False],
        ).head(15)
        for _, row in critical_df.iterrows():
            critical_data.append(
                [
                    str(row.get("product_group", "")),
                    _truncate(row.get("product_name", ""), 46),
                    _fmt_int(row.get("stock_qty", 0)),
                    _fmt_int(row.get("sales_qty_60d", 0)),
                    _fmt_days(row.get("days_of_cover")),
                ]
            )
    critical_data = _ensure_table_has_rows(critical_data)

    elements.append(_section_header("Критичные позиции и отсутствующие товары", "#C62828", styles))
    elements.append(Spacer(1, 4))
    elements.append(_styled_table(critical_data, [28 * mm, 78 * mm, 22 * mm, 25 * mm, 17 * mm], header_color="#C62828"))
    elements.append(Spacer(1, 12))

    top_sales_data = [["Группа", "Наименование", "Остаток", "Продажи 60д", "Дней"]]
    top_sales = df.sort_values("sales_qty_60d", ascending=False).head(15)
    for _, row in top_sales.iterrows():
        top_sales_data.append(
            [
                str(row.get("product_group", "")),
                _truncate(row.get("product_name", ""), 46),
                _fmt_int(row.get("stock_qty", 0)),
                _fmt_int(row.get("sales_qty_60d", 0)),
                _fmt_days(row.get("days_of_cover")),
            ]
        )
    top_sales_data = _ensure_table_has_rows(top_sales_data)

    elements.append(_section_header("Топ продаж за 60 дней", "#2E7D32", styles))
    elements.append(Spacer(1, 4))
    elements.append(_styled_table(top_sales_data, [28 * mm, 78 * mm, 22 * mm, 25 * mm, 17 * mm], header_color="#2E7D32"))
    elements.append(Spacer(1, 12))

    group_data = [["Группа", "Позиций", "Остаток", "Продажи 60д", "Critical/OOS"]]
    group_summary = (
        df.assign(is_risk=df["stock_status"].isin(["out_of_stock", "critical"]))
        .groupby("product_group", dropna=True)
        .agg(
            products=("product_name", "nunique"),
            stock_qty=("stock_qty", "sum"),
            sales_qty_60d=("sales_qty_60d", "sum"),
            risk_count=("is_risk", "sum"),
        )
        .reset_index()
        .sort_values("sales_qty_60d", ascending=False)
    )
    for _, row in group_summary.iterrows():
        group_data.append(
            [
                str(row.get("product_group", "")),
                _fmt_int(row.get("products", 0)),
                _fmt_int(row.get("stock_qty", 0)),
                _fmt_int(row.get("sales_qty_60d", 0)),
                _fmt_int(row.get("risk_count", 0)),
            ]
        )
    group_data = _ensure_table_has_rows(group_data)

    elements.append(_section_header("Сводка по товарным группам", "#1976D2", styles))
    elements.append(Spacer(1, 4))
    elements.append(_styled_table(group_data, [45 * mm, 25 * mm, 35 * mm, 35 * mm, 30 * mm], header_color="#1976D2"))
    elements.append(Spacer(1, 12))

    note = (
        "Отчёт построен по прямой выгрузке из PostgreSQL 1С. "
        "Статусы считаются по остатку Южного склада, продажам за последние 60 дней, "
        "среднесуточной продаже и дням покрытия."
    )
    elements.append(
        KeepTogether(
            [
                _section_header("Краткий вывод", "#1E3A5F", styles),
                Spacer(1, 4),
                Paragraph(note, styles["BodyNote"]),
            ]
        )
    )

    doc.build(elements)
    logger.info("Procurement PDF report built: %s", output_path)


def _pick_quantity_column(df):
    candidates = [
        "quantity",
        "sale_qty",
        "sold_qty",
        "qty",
        "sales_qty_60d",
        "product_lines",
    ]
    for col in candidates:
        if col in df.columns:
            return col
    return None


def _empty_product_metrics_df(final_df):
    empty = None
    if final_df is not None:
        try:
            empty = final_df.iloc[0:0].copy()
        except Exception:
            empty = None

    if empty is None:
        try:
            import pandas as pd

            empty = pd.DataFrame()
        except Exception:
            return None

    empty = empty.copy()
    for col in ["product_name", "revenue", "qty", "recommended_order_qty"]:
        if col not in empty.columns:
            empty[col] = []
    return empty[["product_name", "revenue", "qty", "recommended_order_qty"]]


def _normalize_match_key(text: str) -> str:
    value = str(text or "").lower()

    # unify russian/latin specifics
    value = value.replace("ё", "е")
    value = value.replace("х", "x")

    # remove EVERYTHING except letters and digits
    value = re.sub(r"[^a-zа-я0-9]", "", value)

    return value


def _is_valid_product_name_for_pdf(name: str) -> bool:
    value = str(name or "").strip()
    if not value:
        return False

    low = value.lower()

    if low in {"none", "nan"}:
        return False

    if "заказ покупателя" in low:
        return False

    if _is_likely_client_row(value):
        return False

    service_like_patterns = [
        r"^период",
        r"^показатели",
        r"^группировки",
        r"^отборы",
        r"^номенклатура$",
        r"^покупатель$",
        r"^итог$",
        r"^итого$",
        r"^всего$",
    ]
    for pattern in service_like_patterns:
        if re.search(pattern, low):
            return False

    positive_patterns = [
        r"(котел|радиатор|колонка|бойлер|труба|муфта|отвод|кран|фильтр|колено|насос|удлинение|манжета|грибок|дюбель|прокладк)",
        r"(baxi|bosch|royal thermo|лемакс|viterm|navien|valfex|aquatec|eco nova|eco life|turbo|classic|сиберия|kermi|koer|rens|unipump)",
        r"\d+//\d+\*\d+",
        r"\d+\s*[xх*]\s*\d+",
        r"\(\d+,\d+\)\s*$",
        r"\b(vc|vcu|vk|c11|c22|c33)\b",
    ]
    return any(re.search(pattern, low) for pattern in positive_patterns)


def _detect_product_category(name: str) -> str:
    value = str(name or "").strip().lower()
    if not value:
        return "other"

    if re.search(r"(радиатор|стальн)", value):
        return "radiators"
    if re.search(r"(колонка|впг|gwh)", value):
        return "columns"
    if re.search(r"(котел|aogv|аогв|eco 4s|eco nova|navien|varme)", value):
        return "boilers"
    if re.search(r"(стабилизатор)", value):
        return "stabilizers"

    return "other"


def _find_profit_report_path():
    from pathlib import Path

    project_root = Path(__file__).resolve().parents[2]
    data_root = project_root / "data"

    direct_candidates = [
        data_root / "Валовая прибыль 20.01-20.03.xlsx",
        data_root / "raw" / "Валовая прибыль 20.01-20.03.xlsx",
        data_root / "input" / "Валовая прибыль 20.01-20.03.xlsx",
        data_root / "source" / "Валовая прибыль 20.01-20.03.xlsx",
    ]

    for path in direct_candidates:
        if path.exists():
            logger.info("Using profit report for qty enrichment: %s", path)
            return path

    if data_root.exists():
        recursive_candidates = []
        for path in data_root.rglob("*.xlsx"):
            name = path.name.lower()
            if "валовая" in name and "прибыль" in name:
                recursive_candidates.append(path)

        if recursive_candidates:
            recursive_candidates = sorted(recursive_candidates)
            logger.info("Using profit report for qty enrichment (recursive search): %s", recursive_candidates[0])
            return recursive_candidates[0]

    return None


def _build_qty_from_profit_report():
    """
    Use dedicated net_profit_adapter instead of manual parsing.
    Returns qty map: normalized product_name -> sold qty
    """
    file_path = _find_profit_report_path()
    if file_path is None:
        logger.warning("Profit report file not found for qty enrichment")
        return {}

    try:
        df = adapt_net_profit_report(file_path)
    except Exception as e:
        logger.warning("Failed to parse profit report via adapter: %s", e)
        return {}

    if df is None or df.empty:
        return {}

    qty_map = {}

    for _, row in df.iterrows():
        name = row.get("product_name")
        qty = _safe_number(row.get("quantity"), 0)

        if not name or qty <= 0:
            continue

        match_key = _normalize_match_key(name)
        if not match_key:
            continue

        qty_map[match_key] = qty_map.get(match_key, 0.0) + qty

    logger.info("Profit report qty map built via adapter: %s items", len(qty_map))
    logger.info("=== DEBUG PROFIT REPORT QTY MAP ===")
    logger.info("qty_map size: %s", len(qty_map))
    logger.info("Profit report qty sample: %s", list(qty_map.items())[:20])

    sample_items = list(qty_map.items())[:50]
    for key, qty in sample_items:
        logger.info("qty_map item: key='%s' qty=%s", key, qty)

    return qty_map


def _fill_qty_from_sales(final_df, sales_df, result_df):
    """
    Fill qty from trustworthy sources:
    1. existing qty in result_df
    2. dedicated gross profit report for the selected period
    3. radiator monthly qty columns from final_df for radiator rows
    4. real quantity-like column from sales_df product rows, if such column exists
    """
    if result_df is None or result_df.empty:
        return result_df

    result_df = result_df.copy()
    if "qty" not in result_df.columns:
        result_df["qty"] = 0.0

    result_df["match_key"] = result_df["product_name"].apply(_normalize_match_key)

    # 1) qty from dedicated profit report
    profit_report_qty_map = _build_qty_from_profit_report()
    logger.info("Profit report qty keys sample: %s", list(profit_report_qty_map.keys())[:20])

    logger.info("=== DEBUG PDF MATCH KEYS ===")
    logger.info("result_df rows before qty resolve: %s", len(result_df))
    for _, dbg_row in result_df.head(50).iterrows():
        logger.info(
            "result row: product='%s' | category='%s' | match_key='%s'",
            dbg_row.get("product_name"),
            dbg_row.get("category"),
            dbg_row.get("match_key"),
        )

    logger.info("=== DEBUG PROFIT REPORT LOOKUP SAMPLE ===")
    for dbg_key in list(profit_report_qty_map.keys())[:50]:
        logger.info("profit key: '%s' -> %s", dbg_key, profit_report_qty_map[dbg_key])

    # 2) radiator qty from final_df
    radiator_qty_map = {}
    if final_df is not None and not getattr(final_df, "empty", True) and "product_name" in final_df.columns:
        tmp_final = final_df.copy()
        tmp_final["product_name"] = tmp_final["product_name"].astype(str).str.strip()
        tmp_final = tmp_final[tmp_final["product_name"] != ""].copy()
        tmp_final["match_key"] = tmp_final["product_name"].apply(_normalize_match_key)

        radiator_qty_cols = [c for c in tmp_final.columns if c.startswith("radiator_qty_")]
        if radiator_qty_cols:
            for col in radiator_qty_cols:
                tmp_final[col] = tmp_final[col].apply(_safe_number).clip(lower=0)
            tmp_final["radiator_qty_sum"] = tmp_final[radiator_qty_cols].sum(axis=1)
            radiator_qty_map = (
                tmp_final.groupby("match_key", dropna=True)["radiator_qty_sum"]
                .max()
                .to_dict()
            )

    # 3) qty from sales_df if there is a real qty column
    sales_qty_map = {}
    if sales_df is not None and not getattr(sales_df, "empty", True) and "product_name" in sales_df.columns:
        tmp_sales = sales_df.copy()

        if "row_type" in tmp_sales.columns:
            tmp_sales = tmp_sales[tmp_sales["row_type"] == "product"].copy()

        if not tmp_sales.empty:
            tmp_sales["product_name"] = tmp_sales["product_name"].astype(str).str.strip()
            tmp_sales = tmp_sales[tmp_sales["product_name"] != ""].copy()
            tmp_sales = tmp_sales[tmp_sales["product_name"].apply(_is_valid_product_name_for_pdf)].copy()

            qty_col = _pick_quantity_column(tmp_sales)
            if qty_col:
                tmp_sales[qty_col] = tmp_sales[qty_col].apply(_safe_number)
                tmp_sales["match_key"] = tmp_sales["product_name"].apply(_normalize_match_key)
                sales_qty_map = (
                    tmp_sales.groupby("match_key", dropna=True)[qty_col]
                    .sum()
                    .to_dict()
                )

    def _resolve_qty(row):
        current_qty = _safe_number(row.get("qty", 0))
        if current_qty > 0:
            return current_qty

        match_key = row["match_key"]
        category = row.get("category", "other")

        if row.get("product_name") in [
            "Котел Baxi Eco 4S 24 F",
            "Navien Deluxe E Coaxial 24K 2X Контур.",
            "Колонка Газовая Royal Thermo Gwh 10 Inflame",
        ]:
            logger.info(
                "RESOLVE_QTY DEBUG: product='%s' | category='%s' | match_key='%s' | current_qty=%s | profit_qty=%s | radiator_qty=%s | sales_qty=%s",
                row.get("product_name"),
                row.get("category"),
                row.get("match_key"),
                _safe_number(row.get("qty", 0)),
                _safe_number(profit_report_qty_map.get(row["match_key"], 0)),
                _safe_number(radiator_qty_map.get(row["match_key"], 0)),
                _safe_number(sales_qty_map.get(row["match_key"], 0)),
            )

        # priority 1: dedicated period report
        profit_qty = _safe_number(profit_report_qty_map.get(match_key, 0))
        if profit_qty > 0:
            return profit_qty

        # priority 2: radiator monthly metrics from adapted radiator files
        if category == "radiators":
            radiator_qty = _safe_number(radiator_qty_map.get(match_key, 0))
            if radiator_qty > 0:
                return radiator_qty

        # priority 3: qty from sales_df only if it looks like a real quantity column
        sales_qty = _safe_number(sales_qty_map.get(match_key, 0))
        if sales_qty > 0 and sales_qty < 100000:
            return sales_qty

        return 0.0

    logger.info(
        "PDF result match keys sample before qty resolve: %s",
        result_df["match_key"].head(20).tolist()
    )
    logger.info(
        "PDF profit-report qty keys sample: %s",
        list(profit_report_qty_map.keys())[:20]
    )
    result_df["qty"] = result_df.apply(_resolve_qty, axis=1)
    result_df = result_df.drop(columns=["match_key"])
    return result_df


def _build_product_metrics(final_df, sales_df):
    """
    Build safe product metrics for PDF.

    Priority:
    - revenue: prefer final_df.revenue_60d, fallback to aggregated product sale_amount from sales_df
    - qty: prefer final_df.sales_qty_60d, then enrich via _fill_qty_from_sales

    We group by normalized product name so identical products with formatting differences
    are merged before rendering the PDF.
    """
    if final_df is None or getattr(final_df, "empty", True):
        if sales_df is not None and not getattr(sales_df, "empty", True) and {"product_name", "sale_amount"}.issubset(sales_df.columns):
            logger.info("PDF product metrics source=sales_df only")
            tmp_sales = sales_df.copy()

            if "row_type" in tmp_sales.columns:
                tmp_sales = tmp_sales[tmp_sales["row_type"].isin(["product", "", None])].copy()

            tmp_sales["product_name"] = tmp_sales["product_name"].astype(str).str.strip()
            tmp_sales = tmp_sales[tmp_sales["product_name"] != ""].copy()
            tmp_sales = tmp_sales[tmp_sales["product_name"].apply(_is_valid_product_name_for_pdf)].copy()

            tmp_sales["sale_amount"] = tmp_sales["sale_amount"].apply(_safe_number)
            qty_col = _pick_quantity_column(tmp_sales)
            if qty_col:
                tmp_sales[qty_col] = tmp_sales[qty_col].apply(_safe_number)
            else:
                tmp_sales["__qty"] = 0.0
                qty_col = "__qty"

            tmp_sales["category"] = tmp_sales["product_name"].apply(_detect_product_category)
            tmp_sales["match_key"] = tmp_sales["product_name"].apply(_normalize_match_key)

            result = (
                tmp_sales.groupby(["match_key", "category"], dropna=True)
                .agg(
                    product_name=("product_name", "first"),
                    revenue=("sale_amount", "sum"),
                    qty=(qty_col, "sum"),
                )
                .reset_index()
            )

            logger.info(
                "PDF product metrics source=sales_df rows=%s revenue_sum=%s qty_sum=%s",
                len(result),
                _safe_number(result["revenue"].sum(), 0),
                _safe_number(result["qty"].sum(), 0),
            )
            return result[["product_name", "revenue", "qty", "category"]]

        logger.warning("PDF product metrics source=empty final_df")
        empty = _empty_product_metrics_df(final_df)
        if empty is None:
            return empty
        empty["category"] = []
        return empty[["product_name", "revenue", "qty", "category"]]

    if "product_name" not in final_df.columns:
        logger.warning("PDF product metrics: no product_name in final_df")
        empty = _empty_product_metrics_df(final_df)
        if empty is None:
            return empty
        empty["category"] = []
        return empty[["product_name", "revenue", "qty", "category"]]

    tmp = final_df.copy()
    tmp["product_name"] = tmp["product_name"].astype(str).str.strip()
    tmp = tmp[tmp["product_name"] != ""].copy()
    tmp = tmp[tmp["product_name"].apply(_is_valid_product_name_for_pdf)].copy()

    if "revenue_60d" in tmp.columns:
        tmp["revenue"] = tmp["revenue_60d"].apply(_safe_number)
    else:
        tmp["revenue"] = 0.0

    # Для PDF не доверяем sales_qty_60d.
    # Реальное количество подтянем позже из отдельного отчета валовой прибыли
    # и из radiator_qty_* колонок.
    tmp["qty"] = 0.0

    tmp["category"] = tmp["product_name"].apply(_detect_product_category)
    tmp["match_key"] = tmp["product_name"].apply(_normalize_match_key)

    result = (
        tmp.groupby(["match_key", "category"], dropna=True)
        .agg(
            product_name=("product_name", "first"),
            revenue=("revenue", "sum"),
            qty=("qty", "sum"),
        )
        .reset_index()
    )

    # Fallback revenue from sales_df product rows only when revenue is missing/zero.
    sales_revenue_map = {}
    if sales_df is not None and not getattr(sales_df, "empty", True) and "product_name" in sales_df.columns:
        tmp_sales = sales_df.copy()

        if "row_type" in tmp_sales.columns:
            tmp_sales = tmp_sales[tmp_sales["row_type"] == "product"].copy()

        if not tmp_sales.empty and "sale_amount" in tmp_sales.columns:
            tmp_sales["product_name"] = tmp_sales["product_name"].astype(str).str.strip()
            tmp_sales = tmp_sales[tmp_sales["product_name"] != ""].copy()
            tmp_sales = tmp_sales[tmp_sales["product_name"].apply(_is_valid_product_name_for_pdf)].copy()
            tmp_sales["sale_amount"] = tmp_sales["sale_amount"].apply(_safe_number)
            tmp_sales["match_key"] = tmp_sales["product_name"].apply(_normalize_match_key)
            sales_revenue_map = (
                tmp_sales.groupby("match_key", dropna=True)["sale_amount"]
                .sum()
                .to_dict()
            )

    def _resolve_revenue(row):
        current_revenue = _safe_number(row.get("revenue", 0))
        if current_revenue > 0:
            return current_revenue
        return _safe_number(sales_revenue_map.get(row["match_key"], 0))

    result["revenue"] = result.apply(_resolve_revenue, axis=1)

    # Enrich qty only after safe aggregation.
    result = _fill_qty_from_sales(final_df, sales_df, result)

    logger.info(
        "PDF product metrics source=final_df rows=%s revenue_sum=%s qty_sum=%s",
        len(result),
        _safe_number(result["revenue"].sum(), 0),
        _safe_number(result["qty"].sum(), 0),
    )

    return result[["product_name", "revenue", "qty", "category"]]


def _build_radiator_metrics(final_df, sales_df):
    """
    Returns columns: product_name, revenue, qty_sold, profit.
    Prefer sales_df because it contains real gross profit from PostgreSQL sales rows.
    """
    if sales_df is not None and not sales_df.empty and "product_name" in sales_df.columns:
        tmp = sales_df.copy()

        if "row_type" in tmp.columns:
            tmp = tmp[tmp["row_type"] == "product"].copy()

        tmp["product_name"] = tmp["product_name"].astype(str).str.strip()
        tmp = tmp[tmp["product_name"].apply(_is_radiator_row)].copy()

        if not tmp.empty:
            revenue_col = "sale_amount" if "sale_amount" in tmp.columns else "revenue"
            qty_col = _pick_quantity_column(tmp)
            profit_col = "gross_profit_calc" if "gross_profit_calc" in tmp.columns else ("profit" if "profit" in tmp.columns else None)

            tmp[revenue_col] = tmp[revenue_col].apply(_safe_number)

            if qty_col:
                tmp[qty_col] = tmp[qty_col].apply(_safe_number)
            else:
                tmp["_qty_sold"] = 0.0
                qty_col = "_qty_sold"

            if profit_col:
                tmp[profit_col] = tmp[profit_col].apply(_safe_number)
            else:
                tmp["_profit"] = 0.0
                profit_col = "_profit"

            result = (
                tmp.groupby("product_name", dropna=True)
                .agg(
                    revenue=(revenue_col, "sum"),
                    qty_sold=(qty_col, "sum"),
                    profit=(profit_col, "sum"),
                )
                .reset_index()
            )

            result = result[(result["revenue"] > 0) | (result["qty_sold"] > 0)].copy()
            if not result.empty:
                logger.info("PDF radiator metrics source=sales_df rows=%s", len(result))
                return result

    if final_df is not None and not final_df.empty and "product_name" in final_df.columns:
        tmp = final_df.copy()
        tmp["product_name"] = tmp["product_name"].astype(str).str.strip()
        tmp = tmp[tmp["product_name"].apply(_is_radiator_row)].copy()

        if not tmp.empty:
            radiator_revenue_cols = [c for c in tmp.columns if c.startswith("radiator_revenue_")]
            radiator_qty_cols = [c for c in tmp.columns if c.startswith("radiator_qty_")]

            if radiator_revenue_cols:
                for col in radiator_revenue_cols:
                    tmp[col] = tmp[col].apply(_safe_number)
                tmp["revenue"] = tmp[radiator_revenue_cols].sum(axis=1)
            elif "revenue_60d" in tmp.columns:
                tmp["revenue"] = tmp["revenue_60d"].apply(_safe_number)
            else:
                tmp["revenue"] = 0.0

            if radiator_qty_cols:
                for col in radiator_qty_cols:
                    tmp[col] = tmp[col].apply(_safe_number).clip(lower=0)
                tmp["qty_sold"] = tmp[radiator_qty_cols].sum(axis=1)
            elif "sales_qty_60d" in tmp.columns:
                tmp["qty_sold"] = tmp["sales_qty_60d"].apply(_safe_number)
            else:
                tmp["qty_sold"] = 0.0

            tmp["profit"] = 0.0
            result = tmp[["product_name", "revenue", "qty_sold", "profit"]].copy()
            result = result[(result["revenue"] > 0) | (result["qty_sold"] > 0)].copy()

            if not result.empty:
                logger.info("PDF radiator metrics source=final_df rows=%s", len(result))
                return result

    logger.warning("PDF radiator metrics source=empty")
    return None


def _is_radiator_row(name: str) -> bool:
    value = str(name or "").strip().lower().replace("ё", "е")
    if not value:
        return False

    # PDF needs only core steel radiators (1,2), not valves/brackets/aluminum/bimetal/accessories.
    if "стальной радиатор" not in value:
        return False
    if not re.search(r"\(\s*1,2\s*\)", value):
        return False
    if not re.search(r"(200|300|500)//(11|22)\*\d{4}", value):
        return False
    if re.search(r"ruterm|orso|sanline|proexpert|\bvcr\b|\bvcu\b|кран|кронштейн|алюмин|биметалл", value):
        return False

    return True


def _ensure_table_has_rows(table_data, empty_label="Нет данных"):
    if len(table_data) == 1:
        width = len(table_data[0])
        filler = [empty_label] + ["0"] * (width - 1)
        table_data.append(filler)
    return table_data


def build_pdf_report(final_df, sales_df, output_path: str, period_label: str = "20.01.2026 – 20.03.2026", pdf_sales_df=None):
    has_sales_pdf_source = pdf_sales_df is not None and not getattr(pdf_sales_df, "empty", True)
    if _is_procurement_dataset(final_df) and not has_sales_pdf_source:
        return _build_procurement_pdf_report(final_df, output_path, period_label)

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )
    styles = _build_styles()
    elements = []

    elements.append(Paragraph("Отчёт по продажам", styles["ReportTitle"]))
    subtitle = f"Период: {period_label}" if period_label else "Период: не указан"
    elements.append(Paragraph(subtitle, styles["ReportSubtitle"]))

    report_sales_df = pdf_sales_df if pdf_sales_df is not None and not getattr(pdf_sales_df, "empty", True) else sales_df

    logger.info(
        "Building PDF report final_df_rows=%s sales_df_rows=%s",
        len(final_df) if final_df is not None else None,
        len(report_sales_df) if report_sales_df is not None else None,
    )
    logger.info("final_df columns=%s", list(final_df.columns) if final_df is not None else [])
    logger.info("sales_df columns=%s", list(report_sales_df.columns) if report_sales_df is not None else [])

    product_metrics_source_df = None if has_sales_pdf_source else final_df
    product_metrics_df = _build_product_metrics(product_metrics_source_df, report_sales_df)
    total_products = int(product_metrics_df["product_name"].nunique()) if product_metrics_df is not None and not product_metrics_df.empty else len(final_df)
    if report_sales_df is not None and not getattr(report_sales_df, "empty", True) and "sale_amount" in report_sales_df.columns:
        total_revenue = _safe_number(report_sales_df["sale_amount"].sum(), 0)
    else:
        total_revenue = _safe_number(product_metrics_df["revenue"].sum(), 0) if product_metrics_df is not None and not product_metrics_df.empty else 0

    active_clients = 0
    if report_sales_df is not None and not report_sales_df.empty and "customer_name" in report_sales_df.columns:
        tmp = report_sales_df.copy()

        if "row_type" in tmp.columns:
            tmp = tmp[tmp["row_type"] == "customer"].copy()

        tmp["customer_name"] = tmp["customer_name"].astype(str).str.strip()
        tmp["product_name"] = tmp.get("product_name", "").astype(str).str.strip()
        tmp["customer_order"] = tmp.get("customer_order", "").astype(str).str.strip()

        tmp = tmp[
            tmp.apply(
                lambda r: _is_likely_client_row(r["customer_name"], r["product_name"], r["customer_order"]),
                axis=1,
            )
        ]

        active_clients = int(tmp["customer_name"].nunique())

    avg_revenue_per_client = int(total_revenue / active_clients) if active_clients > 0 else 0

    elements.append(_section_header("Ключевые показатели", "#334155", styles))
    elements.append(Spacer(1, 4))
    elements.append(_kpi_cards(total_products, total_revenue, active_clients, avg_revenue_per_client, styles))
    elements.append(Spacer(1, 12))

    # Top sold products (strictly only requested categories, without radiators)
    top_allowed_categories = {"boilers", "columns", "stabilizers"}

    top_sold_data = [["Наименование", "Выручка", "Продано, шт"]]
    if product_metrics_df is not None and not product_metrics_df.empty:
        top_sold = product_metrics_df.copy()
        top_sold = top_sold[top_sold["category"].isin(top_allowed_categories)].copy()
        top_sold = top_sold[top_sold["revenue"] >= 1000].copy()
        top_sold = top_sold.sort_values(by=["revenue", "qty"], ascending=[False, False]).head(10)

        for _, row in top_sold.iterrows():
            top_sold_data.append(
                [
                    _truncate(row.get("product_name", ""), 58),
                    _fmt_int(row.get("revenue", 0)),
                    _fmt_int(row.get("qty", 0)),
                ]
            )

    top_sold_data = _ensure_table_has_rows(top_sold_data)

    elements.append(_section_header("Топ-10 продаваемых позиций", "#2E7D32", styles))
    elements.append(Spacer(1, 4))
    elements.append(_styled_table(top_sold_data, [105 * mm, 35 * mm, 30 * mm], header_color="#2E7D32"))
    elements.append(Spacer(1, 12))

    # Top radiator sales
    radiator_sales_data = [["Радиатор", "Выручка", "Продано", "Маржа/шт"]]
    radiator_metrics_df = _build_radiator_metrics(product_metrics_source_df, report_sales_df)
    if product_metrics_df is not None and not product_metrics_df.empty:
        logger.info(
            "PDF product metrics preview: %s",
            product_metrics_df[["product_name", "revenue", "qty", "category"]].head(20).to_dict("records")
        )
        logger.info(
            "PDF product metrics qty summary: total_qty=%s nonzero_rows=%s",
            _safe_number(product_metrics_df["qty"].sum(), 0),
            int((product_metrics_df["qty"] > 0).sum()),
        )

    if radiator_metrics_df is not None and not radiator_metrics_df.empty:
        logger.info(
            "PDF radiator metrics columns=%s profit_sum=%s preview=%s",
            list(radiator_metrics_df.columns),
            _safe_number(radiator_metrics_df["profit"].sum(), 0) if "profit" in radiator_metrics_df.columns else None,
            radiator_metrics_df.head(5).to_dict("records"),
        )
        top_radiators = radiator_metrics_df.copy()
        top_radiators["has_12"] = top_radiators["product_name"].astype(str).str.contains(
            r"\(\s*1,2\s*\)", case=False, regex=True, na=False
        )
        top_radiators = top_radiators.sort_values(by=["has_12", "revenue"], ascending=[False, False]).head(10)

        for _, row in top_radiators.iterrows():
            qty_sold = _safe_number(row.get("qty_sold", 0))
            avg_margin_per_unit = _safe_number(row.get("profit", 0)) / max(qty_sold, 1)

            radiator_sales_data.append(
                [
                    _truncate(row.get("product_name", ""), 44),
                    _fmt_int(row.get("revenue", 0)),
                    _fmt_int(qty_sold),
                    _fmt_int(avg_margin_per_unit),
                ]
            )

    radiator_sales_data = _ensure_table_has_rows(radiator_sales_data)

    elements.append(_section_header("Топ-10 стальных радиаторов (1,2) по выручке", "#C62828", styles))
    elements.append(Spacer(1, 4))
    elements.append(_styled_table(radiator_sales_data, [98 * mm, 30 * mm, 24 * mm, 30 * mm], header_color="#C62828"))
    elements.append(Spacer(1, 12))

    # Top clients by sales amount and gross profit from PostgreSQL sales rows
    top_clients_data = [["Клиент", "Сумма продажи", "Валовая прибыль"]]
    if report_sales_df is not None and not report_sales_df.empty and {"customer_name", "sale_amount"}.issubset(report_sales_df.columns):
        clients_df = report_sales_df.copy()

        clients_df["customer_name"] = clients_df["customer_name"].astype(str).str.strip()
        clients_df["customer_name"] = clients_df["customer_name"].str.replace(r"\s+", " ", regex=True)
        clients_df["sale_amount"] = clients_df["sale_amount"].apply(_safe_number)

        if "gross_profit_calc" in clients_df.columns:
            clients_df["gross_profit"] = clients_df["gross_profit_calc"].apply(_safe_number)
        elif "profit" in clients_df.columns:
            clients_df["gross_profit"] = clients_df["profit"].apply(_safe_number)
        elif "net_profit" in clients_df.columns:
            clients_df["gross_profit"] = clients_df["net_profit"].apply(_safe_number)
        else:
            clients_df["gross_profit"] = 0.0

        clients_df = clients_df[
            (clients_df["customer_name"] != "")
            & (~clients_df["customer_name"].str.lower().isin(["none", "nan"]))
            & (clients_df["sale_amount"] > 0)
        ].copy()

        top_clients = (
            clients_df.groupby("customer_name", dropna=True)
            .agg(
                total_sales_amount=("sale_amount", "sum"),
                total_gross_profit=("gross_profit", "sum"),
            )
            .reset_index()
            .sort_values(by=["total_sales_amount", "total_gross_profit"], ascending=[False, False])
            .head(10)
        )

        for _, row in top_clients.iterrows():
            top_clients_data.append(
                [
                    _truncate(row.get("customer_name", ""), 45),
                    _fmt_int(row.get("total_sales_amount", 0)),
                    _fmt_int(row.get("total_gross_profit", 0)),
                ]
            )
    top_clients_data = _ensure_table_has_rows(top_clients_data)

    elements.append(_section_header("Топ-10 клиентов по сумме продаж", "#6A1B9A", styles))
    elements.append(Spacer(1, 4))
    elements.append(_styled_table(top_clients_data, [104 * mm, 38 * mm, 40 * mm], header_color="#6A1B9A"))
    elements.append(Spacer(1, 12))

    note = (
        "Отчёт сфокусирован на лидерах продаж, слабопродаваемых позициях, "
        "стальных радиаторах и клиентах с наибольшим объёмом продаж и валовой прибылью за период."
    )
    elements.append(
        KeepTogether(
            [
                _section_header("Краткий вывод", "#1E3A5F", styles),
                Spacer(1, 4),
                Paragraph(note, styles["BodyNote"]),
            ]
        )
    )

    doc.build(elements)
    if radiator_metrics_df is not None and not radiator_metrics_df.empty:
        logger.info(
            "PDF radiator metrics preview: %s",
            radiator_metrics_df[["product_name", "revenue", "qty_sold"]].head(20).to_dict("records")
        )