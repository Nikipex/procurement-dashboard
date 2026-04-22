

import re
from pathlib import Path
from typing import List

import pandas as pd
from loguru import logger


# =========================
# Utils
# =========================

def normalize_text(value) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip().lower().replace("ё", "е")
    text = re.sub(r"\s+", " ", text)
    return text


def safe_numeric(value) -> float:
    if pd.isna(value):
        return 0.0
    try:
        return float(str(value).replace(" ", "").replace(",", "."))
    except Exception:
        return 0.0


def normalize_product_name(name: str) -> str:
    return normalize_text(name)


def is_service_row(value: str) -> bool:
    text = normalize_text(value)
    if not text:
        return True

    service_patterns = [
        r"^период",
        r"^показател",
        r"^группиров",
        r"^отбор",
        r"^номенклатура$",
        r"^покупатель$",
        r"^заказ покупателя",
        r"^итог$",
        r"^итого$",
        r"^всего$",
        r"^остаток",
        r"^склад",
    ]
    return any(re.search(pattern, text) for pattern in service_patterns)



def is_customer_row(value: str) -> bool:
    text = normalize_text(value)
    if not text:
        return False

    if is_service_row(text):
        return False

    customer_markers = ["ооо", "ип", "ао", "зао", "пао"]
    if any(marker in text for marker in customer_markers):
        return True

    if "заказ покупателя" in text:
        return False

    product_markers = [
        "радиатор",
        "котел",
        "колонка",
        "стабилизатор",
        "бойлер",
        "насос",
        "коаксиал",
    ]
    if any(marker in text for marker in product_markers):
        return False

    return False



def is_product_row(value: str, qty: float) -> bool:
    text = normalize_text(value)
    if not text:
        return False

    if is_service_row(text):
        return False

    if is_customer_row(text):
        return False

    if "заказ покупателя" in text:
        return False

    return qty > 0


# =========================
# Core adapter
# =========================

def adapt_gross_profit_report(file_path: Path) -> pd.DataFrame:
    """
    Парсит отчет 1С "Валовая прибыль"

    Возвращает:
        DataFrame с колонками:
            - product_name
            - product_key
            - quantity
    """

    logger.info(f"[gross_profit] Loading file: {file_path}")

    df = pd.read_excel(file_path, header=None)

    logger.info(f"[gross_profit] Raw shape: {df.shape}")

    # =========================
    # Найти колонку номенклатуры и количества
    # =========================

    nomenclature_col = None
    quantity_col = None

    search_rows = min(len(df), 20)

    for i in range(search_rows):
        row = df.iloc[i]

        for j in range(len(row)):
            cell = normalize_text(row.iloc[j])

            if nomenclature_col is None and "номенклатура" in cell:
                nomenclature_col = j

            if quantity_col is None and ("ед. хранения" in cell or "ед хранения" in cell or cell == "количество"):
                quantity_col = j

        if nomenclature_col is not None and quantity_col is not None:
            break

    if nomenclature_col is None:
        nomenclature_col = 1 if len(df.columns) > 1 else 0

    if quantity_col is None or quantity_col == nomenclature_col:
        quantity_candidates = []
        for col_idx in range(len(df.columns)):
            if col_idx == nomenclature_col:
                continue

            numeric_count = 0
            positive_count = 0
            sample_limit = min(len(df), 80)
            for row_idx in range(sample_limit):
                value = safe_numeric(df.iloc[row_idx, col_idx])
                if value != 0:
                    numeric_count += 1
                    if value > 0:
                        positive_count += 1

            quantity_candidates.append((col_idx, numeric_count, positive_count))

        quantity_candidates.sort(key=lambda item: (item[2], item[1]), reverse=True)
        if quantity_candidates:
            quantity_col = quantity_candidates[0][0]

    logger.info(f"[gross_profit] Detected columns: nomenclature={nomenclature_col}, quantity={quantity_col}")

    if nomenclature_col is None or quantity_col is None or quantity_col == nomenclature_col:
        raise ValueError("Не удалось определить разные колонки номенклатуры и количества")

    # =========================
    # Парсинг строк
    # =========================

    records: List[dict] = []

    current_customer = None
    skipped_rows = 0
    service_rows = 0
    customer_rows = 0
    product_rows = 0

    for idx in range(len(df)):
        row = df.iloc[idx]

        name_raw = row.iloc[nomenclature_col]
        qty_raw = row.iloc[quantity_col]

        name = str(name_raw).strip() if not pd.isna(name_raw) else ""
        qty = safe_numeric(qty_raw)

        if not name:
            skipped_rows += 1
            continue

        if is_service_row(name):
            service_rows += 1
            continue

        if is_customer_row(name):
            current_customer = name
            customer_rows += 1
            continue

        if is_product_row(name, qty):
            records.append({
                "product_name": name,
                "product_key": normalize_product_name(name),
                "quantity": qty,
                "customer": current_customer,
            })
            product_rows += 1
            continue

        skipped_rows += 1

    if not records:
        raise ValueError("Не удалось распарсить ни одной товарной строки")

    logger.info(
        f"[gross_profit] Parsing stats: service_rows={service_rows}, customer_rows={customer_rows}, product_rows={product_rows}, skipped_rows={skipped_rows}"
    )

    result_df = pd.DataFrame(records)

    logger.info(f"[gross_profit] Parsed rows: {len(result_df)}")
    logger.info(
        "[gross_profit] Preview before grouping:\n{}".format(
            result_df[["product_name", "product_key", "quantity"]].head(30).to_string(index=False)
        )
    )

    # =========================
    # Группировка
    # =========================

    grouped = (
        result_df
        .groupby("product_key", as_index=False)
        .agg({
            "product_name": "first",
            "quantity": "sum",
        })
    )

    logger.info(
        "[gross_profit] Grouped preview:\n{}".format(
            grouped.head(30).to_string(index=False)
        )
    )
    logger.info(f"[gross_profit] Unique products: {len(grouped)}")

    return grouped