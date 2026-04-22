from loguru import logger

FILE_MAPPING = {
    "продажи": "sales",
    "abc": "abc",
    "планирование": "planning",
    "анализ доступности": "inventory",
    "план-факт": "sales_plan_fact",
    "валовая прибыль за год": "gross_profit_year",
    "валовая прибыль 20.01-20.03": "gross_profit_period",
    "валовая прибыль 20.01-20.03.xlsx": "gross_profit_period",
    "валовая прибыль ": "gross_profit_period",
    # 🔥 Радиаторы (ABC + помесячная валовая)
    "abc-анализ продаж текущий год радиаторы": "radiator_abc",
    "валовая радиаторы январь": "radiator_jan",
    "валовая радиаторы февраль": "radiator_feb",
    "валовая радиаторы март": "radiator_mar",
    "валовая радиаторы апрель": "radiator_apr",
}

def identify_file_type(filename: str) -> str | None:
    filename_lower = filename.lower()

    # 🔥 Сначала обрабатываем специфичные файлы радиаторов (чтобы не пересекались с общими)
    if "abc-анализ продаж текущий год радиаторы" in filename_lower:
        return "radiator_abc"

    if "валовая радиаторы январь" in filename_lower:
        return "radiator_jan"
    if "валовая радиаторы февраль" in filename_lower:
        return "radiator_feb"
    if "валовая радиаторы март" in filename_lower:
        return "radiator_mar"
    if "валовая радиаторы апрель" in filename_lower:
        return "radiator_apr"

    if (
        "валовая прибыль 20.01-20.03" in filename_lower
        or (
            "валовая прибыль" in filename_lower
            and "за год" not in filename_lower
            and "радиаторы" not in filename_lower
        )
    ):
        return "gross_profit_period"

    for keyword, file_type in FILE_MAPPING.items():
        if keyword in filename_lower:
            logger.debug(f"Identified {filename} as {file_type}")
            return file_type

    logger.warning(f"Could not identify file type for: {filename}")
    return None