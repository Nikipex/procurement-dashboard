from datetime import date

MONTHS = [
    ("jan", "Янв"),
    ("feb", "Фев"),
    ("mar", "Мар"),
    ("apr", "Апр"),
    ("may", "Май"),
    ("jun", "Июн"),
    ("jul", "Июл"),
    ("aug", "Авг"),
    ("sep", "Сен"),
    ("oct", "Окт"),
    ("nov", "Ноя"),
    ("dec", "Дек"),
]


def get_radiator_month_columns(
    year: int | None = None,
    include_current_month: bool = True,
    today: date | None = None,
) -> list[str]:
    today = today or date.today()
    year = year or today.year

    max_month = today.month if include_current_month else today.month - 1
    max_month = max(0, min(max_month, 12))

    return [
        f"radiator_qty_{month_key}_{year}"
        for month_key, _ in MONTHS[:max_month]
    ]


def get_radiator_month_labels(
    year: int | None = None,
    include_current_month: bool = True,
    today: date | None = None,
) -> dict[str, str]:
    today = today or date.today()
    year = year or today.year

    max_month = today.month if include_current_month else today.month - 1
    max_month = max(0, min(max_month, 12))

    return {
        f"radiator_qty_{month_key}_{year}": f"{label} {year}"
        for month_key, label in MONTHS[:max_month]
    }
