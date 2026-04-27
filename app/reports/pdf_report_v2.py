from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

FONT_REGULAR = "ReportRegular"
FONT_BOLD = "ReportBold"

def register_fonts() -> None:
    font_paths = [
        (
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        ),
        (
            "/Library/Fonts/Arial.ttf",
            "/Library/Fonts/Arial Bold.ttf",
        ),
        (
            "/System/Library/Fonts/Supplemental/DejaVuSans.ttf",
            "/System/Library/Fonts/Supplemental/DejaVuSans-Bold.ttf",
        ),
        (
            "/Library/Fonts/DejaVuSans.ttf",
            "/Library/Fonts/DejaVuSans-Bold.ttf",
        ),
    ]

    for regular_path, bold_path in font_paths:
        if Path(regular_path).exists() and Path(bold_path).exists():
            pdfmetrics.registerFont(TTFont(FONT_REGULAR, regular_path))
            pdfmetrics.registerFont(TTFont(FONT_BOLD, bold_path))
            return

    raise FileNotFoundError("No Cyrillic TTF font found for PDF report")


def fmt_money(value: float) -> str:
    return f"{value:,.0f}".replace(",", " ")


def fmt_qty(value: float) -> str:
    return f"{value:,.0f}".replace(",", " ")


def make_table(data, header_bg=colors.HexColor("#26364d")):
    table = Table(data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), header_bg),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
                ("FONTNAME", (0, 1), (-1, -1), FONT_REGULAR),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d7dde8")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f7fb")]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def build_pdf_report(df: pd.DataFrame, output_path: Path) -> None:
    register_fonts()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    styles = getSampleStyleSheet()
    styles["Normal"].fontName = FONT_REGULAR
    title_style = ParagraphStyle(
        "TitleCustom",
        parent=styles["Title"],
        fontName=FONT_BOLD,
        fontSize=24,
        textColor=colors.HexColor("#26364d"),
        spaceAfter=12,
    )
    h2_style = ParagraphStyle(
        "H2Custom",
        parent=styles["Heading2"],
        fontName=FONT_BOLD,
        fontSize=15,
        textColor=colors.white,
        backColor=colors.HexColor("#26364d"),
        leftIndent=0,
        spaceBefore=14,
        spaceAfter=8,
        leading=18,
    )

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )

    story = []

    period_start = df["invoice_created_at"].min().strftime("%d.%m.%Y")
    period_end = df["invoice_created_at"].max().strftime("%d.%m.%Y")

    revenue = df["line_amount"].sum()
    qty = df["qty"].sum()
    invoice_count = df["invoice_number"].nunique()
    sku_count = df["product_code"].nunique()
    avg_invoice = revenue / invoice_count if invoice_count else 0

    story.append(Paragraph("Отчет по продажам v2", title_style))
    story.append(Paragraph(f"Период: {period_start} - {period_end}", styles["Normal"]))
    story.append(Spacer(1, 8))

    kpi_data = [
        ["Показатель", "Значение"],
        ["Выручка", fmt_money(revenue)],
        ["Количество счетов", fmt_qty(invoice_count)],
        ["Средний счет", fmt_money(avg_invoice)],
        ["Продано, шт", fmt_qty(qty)],
        ["Уникальных SKU", fmt_qty(sku_count)],
        ["Строк данных", fmt_qty(len(df))],
    ]
    story.append(Paragraph("Ключевые показатели", h2_style))
    story.append(make_table(kpi_data))
    story.append(Spacer(1, 12))

    top_products = (
        df.groupby("product_name", as_index=False)
        .agg(revenue=("line_amount", "sum"), qty=("qty", "sum"))
        .sort_values("revenue", ascending=False)
        .head(15)
    )

    top_data = [["Товар", "Выручка", "Продано, шт"]]
    for _, row in top_products.iterrows():
        top_data.append([
            str(row["product_name"])[:55],
            fmt_money(row["revenue"]),
            fmt_qty(row["qty"]),
        ])

    story.append(Paragraph("Топ-15 товаров по выручке", h2_style))
    story.append(make_table(top_data, colors.HexColor("#3f7f35")))
    story.append(Spacer(1, 12))

    df = df.copy()
    df["invoice_date"] = df["invoice_created_at"].dt.date

    daily = (
        df.groupby("invoice_date", as_index=False)
        .agg(revenue=("line_amount", "sum"), qty=("qty", "sum"))
        .sort_values("invoice_date", ascending=False)
        .head(15)
    )

    daily_data = [["Дата", "Выручка", "Продано, шт"]]
    for _, row in daily.iterrows():
        daily_data.append([
            row["invoice_date"].strftime("%d.%m.%Y"),
            fmt_money(row["revenue"]),
            fmt_qty(row["qty"]),
        ])

    story.append(Paragraph("Последние 15 дней продаж", h2_style))
    story.append(make_table(daily_data, colors.HexColor("#b83232")))

    story.append(Spacer(1, 16))
    story.append(
        Paragraph(
            "Краткий вывод: отчет построен напрямую из PostgreSQL-базы 1C. "
            "Источник данных: счета, строки счетов и справочник номенклатуры.",
            styles["Normal"],
        )
    )

    doc.build(story)