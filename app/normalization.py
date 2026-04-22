import re
import pandas as pd


def normalize_text(value) -> str:
    if pd.isna(value):
        return ""

    text = str(value).strip().lower()
    text = text.replace("\xa0", " ")
    text = text.replace("ё", "е")
    text = re.sub(r"\s+", " ", text)
    return text


ALLOWED_UNIPUMP_PUMP_KEYS = {
    "unipump upc 25-40 130",
    "unipump upc 25-40 180",
    "unipump upc 25-60 130",
    "unipump upc 25-60 180",
    "unipump upc 25-80 180",
    "unipump upc 32-60 180",
    "unipump upc 32-80 180",
    "unipump cp 25-40 180",
    "unipump cp 25-60 130",
    "unipump cp 25-60 180",
}

PUMP_SIZE_PATTERN = re.compile(r"\b(25|32)-(40|60|80)\s*(130|180)\b")


def _extract_unipump_pump_model_and_size(name: str) -> tuple[str, str]:
    text = normalize_text(name)

    if "unipump" not in text or "насос" not in text:
        return "", ""

    normalized = text
    normalized = normalized.replace("upс", "upc")   # кириллическая С
    normalized = normalized.replace("ср", "cp")
    normalized = normalized.replace("циркуляц.", "циркуляц")
    normalized = normalized.replace("(отопл.)", "")
    normalized = normalized.replace("(отопл)", "")
    normalized = normalized.replace("отопл.", "")
    normalized = normalized.replace("отопл", "")
    normalized = re.sub(r"\s+", " ", normalized).strip()

    if re.search(r"\bupc\b", normalized):
        model = "upc"
    elif re.search(r"\bcp\b", normalized):
        model = "cp"
    else:
        return "", ""

    match = PUMP_SIZE_PATTERN.search(normalized)
    if not match:
        return "", ""

    d, h, m = match.groups()
    return model, f"{d}-{h} {m}"


def normalize_product_name(name) -> str:
    text = normalize_text(name)
    if not text:
        return ""

    model, size = _extract_unipump_pump_model_and_size(text)
    if model and size:
        candidate = f"unipump {model} {size}"
        if candidate in ALLOWED_UNIPUMP_PUMP_KEYS:
            return candidate

    return text


def normalize_radiator_product_name(name) -> str:
    """
    Dedicated normalization for steel radiator SKUs.

    Goal:
    - keep only real radiator product names aligned between
      monthly radiator reports and radiator ABC report
    - avoid accessories / valves / kits / brackets noise
    - keep matching stable for radiator analytics
    """
    text = normalize_text(name)
    if not text:
        return ""

    # unify wording variants
    text = text.replace("cтальной", "стальной")
    text = text.replace("стальн.", "стальной")
    text = text.replace("радиатор стальной", "стальной радиатор")

    # unify separators / size notations
    text = text.replace(" x ", "x")
    text = re.sub(r"\s*/\s*", "/", text)
    text = re.sub(r"\s*-\s*", "-", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text