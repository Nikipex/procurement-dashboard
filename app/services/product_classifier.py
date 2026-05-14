from app.config.procurement_rules import PRODUCT_GROUPS


# Жесткий классификатор для procurement dashboard.
# Принцип: сначала отсекаем мусор/нецелевой ассортимент, потом ищем тип товара,
# и только потом используем брендовые fallback-правила из PRODUCT_GROUPS.

EXCLUDE_PATTERNS = [
    "не использовать",
    "неиспользовать",
    "не исп",
    "архив",
    "уценка",
    "брак",

    # Кондиционеры / сплит-системы. Ballu может быть колонкой, а может быть климатом.
    "кондиционер",
    "сплит",
    "split",
    "сплит-систем",
    "сплит систем",
    "наружный блок",
    "внутренний блок",
    "блок внешний",
    "блок внутренний",
    "bso/out",
    "bso/in",
    "out-",
    "in-",

    # Явно не закупочные целевые группы для текущего MVP.
    "крепление",
    "крепления",
    "дюбель",
    "саморез",
    "шуруп",
    "труба",
    "тройник",
    "муфта",
    "уголок",
    "переходник",
    "фум",
    "лента",
    "пена",
    "пеноплекс",
    "кварц",
]


# Сначала тип товара, потом бренд.
# Это защищает от ошибок типа:
# - "Инверторный стабилизатор BAXI ENERGY" -> стабилизаторы, а не котлы
# - "Ballu BSO/out" -> прочее, а не газовые колонки
TYPE_KEYWORDS = {
    "стабилизаторы": [
        "стабилизатор",
        "teplocom",
        "теплоком",
        "solpi",
        "energy 400",
        "baxi energy",
        "инверторный стабилизатор",
    ],
    "насосы": [
        "насос",
        "unipump",
        "upс",
        "upc",
        "циркуляц",
        "циркул",
    ],
    "бойлеры": [
        "водонагреватель",
        "бойлер",
        "abs vls",
        "nts",
        "andris",
    ],
    "газовые колонки": [
        "газовая колонка",
        "газ колонка",
        "колонка газ",
        "колонка газовая",
        "впг",
        "gwh",
        "warmix",
        "inflame",
    ],
    "радиаторы": [
        "радиатор",
        "rens",
        "sti 500",
        "sti 350",
    ],
    "коаксиалы": [
        "коаксиал",
        "коаксиальный",
        "60/100",
        "80/125",
        "дымоход",
        "комплект дымохода",
    ],
    "котлы": [
        "котел",
        "котёл",
        "газ.котел",
        "газ. котел",
        "газовый котел",
        "газовый котёл",
        "navien deluxe",
        "navien heatluxe",
        "baxi eco",
        "baxi luna",
        "baxi slim",
    ],
}


# Брендовые fallback-правила. Используются только если TYPE_KEYWORDS не сработали.
# Здесь нельзя ставить слишком широкие ключи без проверки exclusions.
GROUP_PRIORITY = [
    "стабилизаторы",
    "насосы",
    "бойлеры",
    "газовые колонки",
    "радиаторы",
    "коаксиалы",
    "котлы",
]


def normalize_name(name: str) -> str:
    return " ".join(str(name).lower().replace("ё", "е").split())


def has_exclude_pattern(name: str) -> bool:
    normalized_name = normalize_name(name)
    return any(pattern in normalized_name for pattern in EXCLUDE_PATTERNS)


def keyword_matches(name: str, keywords: list[str]) -> bool:
    for keyword in keywords:
        normalized_keyword = normalize_name(keyword)
        if normalized_keyword and normalized_keyword in name:
            return True
    return False


def classify_product_group(product_name: str) -> str:
    name = normalize_name(product_name)

    if not name or has_exclude_pattern(name):
        return "прочее"

    for group_name, keywords in TYPE_KEYWORDS.items():
        if keyword_matches(name, keywords):
            return group_name

    for group_name in GROUP_PRIORITY:
        keywords = PRODUCT_GROUPS.get(group_name, [])
        if keyword_matches(name, keywords):
            return group_name

    # fallback для групп, которые есть в PRODUCT_GROUPS, но не добавлены в GROUP_PRIORITY
    for group_name, keywords in PRODUCT_GROUPS.items():
        if group_name in GROUP_PRIORITY:
            continue
        if keyword_matches(name, keywords):
            return group_name

    return "прочее"


def is_target_product(product_name: str) -> bool:
    return classify_product_group(product_name) != "прочее"