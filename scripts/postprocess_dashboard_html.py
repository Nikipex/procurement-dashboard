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

    HTML_PATH.write_text(html)


if __name__ == "__main__":
    main()
