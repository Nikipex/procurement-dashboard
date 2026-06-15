from __future__ import annotations

import re
from pathlib import Path

HTML_PATH = Path("data/output/dashboard_postgres.html")


def fmt_number(value: str) -> str:
    # Не трогаем ячейки с HTML-разметкой: цветные badge/span должны сохраниться.
    if "<" in value and ">" in value:
        return value

    raw = value.replace("&nbsp;", " ").strip()

    if not re.fullmatch(r"-?\d+(?:\.\d+)?", raw):
        return value

    number = float(raw)
    if number.is_integer():
        return str(int(number))

    return f"{number:.1f}".replace(".", ",")


def normalize_numbers(html: str) -> str:
    def repl(match: re.Match[str]) -> str:
        inner = match.group(1)
        return f"<td>{fmt_number(inner)}</td>"

    return re.sub(r"<td>(.*?)</td>", repl, html, flags=re.S)


def add_css(html: str) -> str:
    if ".stock-risk-icon" in html:
        return html

    css = """
<style>
.stock-risk-icon {
    display: inline-block;
    margin-left: 6px;
    color: #f59e0b;
    cursor: help;
    font-size: 0.95em;
    vertical-align: middle;
}
</style>
"""
    if "</head>" in html:
        return html.replace("</head>", css + "\n</head>", 1)
    return css + html



def force_radiator_low_stock_warning(html: str) -> str:
    """Add warning icon to radiator rows with positive but risky low stock.

    Radiator table columns after formatting:
    0 name
    1 ABC
    2 stock
    3 Jan
    4 Feb
    5 Mar
    6 Apr
    7 May
    8 Jun
    9 monthly demand
    10 coverage badge
    11 order qty badge
    """

    def parse_num(value: str) -> float:
        clean = re.sub(r"<.*?>", "", value, flags=re.S)
        clean = clean.replace("&nbsp;", " ").replace(" ", "").replace(",", ".").strip()
        try:
            return float(clean)
        except Exception:
            return 0.0

    def patch_row(match: re.Match[str]) -> str:
        row = match.group(0)

        if "radiator-low-stock-icon" in row:
            return row

        # Only radiator rows.
        if "радиатор" not in row.lower():
            return row

        # Do not touch non-core/vendor rows if they still appear.
        lowered = row.lower()
        if any(x in lowered for x in ["ruterm", "orso", "sanline", "proexpert", "vcr", "vcu"]):
            return row

        tds = list(re.finditer(r"<td>(.*?)</td>", row, flags=re.S))
        if len(tds) < 12:
            return row

        stock_cell = tds[2]
        stock = parse_num(stock_cell.group(1))
        monthly_demand = parse_num(tds[9].group(1))
        order_qty = parse_num(tds[11].group(1))

        # Warning rule:
        # positive stock exists, but there is real demand and dashboard recommends ordering.
        # This catches technical/near-empty leftovers like 300//22*1800: stock=3, demand=11.2, order=16.
        if not (0 < stock <= 5 and monthly_demand > 0 and order_qty > 0):
            return row

        inner = stock_cell.group(1)
        new_cell = (
            f"<td>{inner}"
            '<span class="stock-risk-icon radiator-low-stock-icon" '
            'title="Критически малый остаток по радиатору. Есть спрос и рекомендация к заказу — проверьте остаток в 1С.">⚠️</span>'
            "</td>"
        )

        return row[:stock_cell.start()] + new_cell + row[stock_cell.end():]

    return re.sub(
        r"<tr>\s*<td>.*?радиатор.*?</tr>",
        patch_row,
        html,
        flags=re.S | re.I,
    )


def force_baxi_warning(html: str) -> str:
    def patch_row(match: re.Match[str]) -> str:
        row = match.group(0)
        if "stock-risk-icon" in row:
            return row

        tds = list(re.finditer(r"<td>(.*?)</td>", row, flags=re.S))
        if len(tds) < 3:
            return row

        stock_cell = tds[2]
        inner = stock_cell.group(1)

        new_cell = (
            f"<td>{inner}"
            '<span class="stock-risk-icon" title="Остаток требует проверки в 1С. Возможен технический остаток в регистре.">⚠️</span>'
            "</td>"
        )

        return row[:stock_cell.start()] + new_cell + row[stock_cell.end():]

    return re.sub(
        r"<tr>\s*<td>Котел BAXI ECO 4S 24(?: F)?</td>.*?</tr>",
        patch_row,
        html,
        flags=re.S,
    )


def main() -> None:
    html = HTML_PATH.read_text()

    html = add_css(html)

    html = html.replace("stock_qty", "Остаток")
    html = html.replace("free_stock_qty", "Свободный остаток")

    html = normalize_numbers(html)
    html = force_baxi_warning(html)
    html = force_radiator_low_stock_warning(html)

    HTML_PATH.write_text(html)


if __name__ == "__main__":
    main()
