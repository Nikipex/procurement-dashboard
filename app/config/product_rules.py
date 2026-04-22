"""
Product rules: target product lists, exclusion lists, regex patterns,
and product classification helpers used across the pipeline.
"""
import re


# ── Unipump pumps ───────────────────────────────────────────────
TARGET_UNIPUMP_PUMP_KEYS = {
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

UNIPUMP_PUMP_SIZE_PATTERN = re.compile(r"\b(25|32)-(40|60|80)\s*(130|180)\b")


# ── Coaxial target names ────────────────────────────────────────
TARGET_COAXIAL_EXACT_NAMES = {
    "комплект коаксиальный l=1000мм, 60/100 универсальный антилед (хомут, стакан 60/50, фланец, 2 манжет)",
    "комплект коаксиальный l=1000мм, 60/100 антилед immergas",
    "комплект коаксиальный l=1000мм, 60/100 универсальный антилед(хомут,стакан60/50,фланец,2ма",
}


# ── Excluded boiler names ───────────────────────────────────────
EXCLUDED_BOILER_EXACT_NAMES = {
    "водонагреватель ariston abs vls pro r inox 50",
    "водонагреватель ariston abs vls pro r inox 80",
    "водонагреватель ariston abs vls pro r inox 100",
    "водонагреватель ariston nts 50 v 1.5k (fa)",
    "водонагреватель ariston nts 80 v 1.5k (fa)",
    "водонагреватель ariston nts superlux 100 v 1.5k (su)",
}


# ── Priority patterns (used in _is_priority_item) ───────────────
PRIORITY_PATTERNS = [
    # Стабилизаторы — exact whitelist
    r"^стабилизатор напряжения solpi-m tsd-500va$",
    r"^стабилизатор teplocom st-222/500$",
    r"^стабилизатор teplocom st-222/500-[иi]$",
    r"^стабилизатор teplocom st-555$",
    r"^стабилизатор teplocom st-555-[иi]$",

    # Газовые колонки
    r"ballu.*warmix.*gwh-10",
    r"genberg",
    r"inflame",

    # Котлы — exact whitelist
    r"^котел baxi eco\s*nova\s*10f$",
    r"^котел baxi eco\s*nova\s*14f$",
    r"^котел baxi eco\s*nova\s*18f$",
    r"^котел baxi eco\s*nova\s*24f$",
    r"^котел baxi eco\s*4s\s*10\s*f$",
    r"^котел baxi eco\s*4s\s*18\s*f$",
    r"^котел baxi eco\s*4s\s*24$",
    r"^котел baxi eco\s*4s\s*24\s*f$",
    r"^котел baxi eco\s*four\s*24\s*f$",
    r"^navien deluxe c coaxial 13k\s*2х контур\.?$",
    r"^navien deluxe c coaxial 16k\s*2х контур\.?$",
    r"^navien deluxe c coaxial 24k\s*2х контур\.?$",
    r"^navien deluxe c coaxial 30k\s*2х контур\.?$",
    r"^navien deluxe c coaxial 35k\s*2х контур\.?$",
    r"^navien deluxe c coaxial 40k\s*2х контур\.?$",
    r"^navien deluxe one 24k\s*1 контур\.?$",
    r"^navien deluxe one 30k\s*1 контур\.?$",
    r"^navien deluxe e coaxial 10k\s*2х контур\.?$",
    r"^navien deluxe e coaxial 13k\s*2х контур\.?$",
    r"^navien deluxe e coaxial 16k\s*2х контур\.?$",
    r"^navien deluxe e coaxial 24k\s*2х контур\.?$",
    r"^navien heatatmo ngb 150 24 a$",

    # Бойлеры — только нужные позиции, без Inox / FA / Superlux
    r"^водонагреватель ariston abs vls pro r 50$",
    r"^водонагреватель ariston abs vls pro r 80$",
    r"^водонагреватель ariston abs vls pro r 100$",
    r"^водонагреватель ariston abse vls pro pw 50$",
    r"^водонагреватель ariston abse vls pro pw 100$",
    r"^водонагреватель ariston nts 30 v 1\.5k \(su\) slim$",
    r"^водонагреватель ariston nts 50 v 1\.5k \(su\)$",
    r"^водонагреватель ariston nts 80 v 1\.5k \(su\)$",
    r"^водонагреватель ariston nts 100 v 1\.5k \(su\)$",
    r"^водонагреватель ariston nts fais v 1\.5k$",
    # Насосы обрабатываются отдельно через exact key.

    # Коаксиалы
    r"адаптер двублочн.*80/80.*immergas",
    r"адаптер моноблочн.*60/100.*80/80.*универс",
    r"декоративн.*манжета.*100",
    r"декоративн.*манжета.*80",
    r"изолятор кровли",
    r"коаксиальн.*удлинение.*60/100",
    r"колено алюминиевое.*80",
    r"колено коаксиальн.*60/100",
    r"колено стартовое коаксиальн.*60/100",
    r"комплект коаксиальн.*60/100",
    r"конденсатоотводчик.*60/100",
    r"конденсатоотводчик.*71\.ме7\.00\.46",
    r"муфта 80/60",
    r"наконечник.*60/100",
    r"наконечник.*80",
    r"сетка наконечник.*80",
    r"т-образн.*80",
    r"т-образн.*60/100",
    r"труба алюминиевая.*d80",
    r"хомут.*100",
    r"хомут.*80",

    r"rens",
]


# ── Special-order patterns (used in _is_special_order_item) ──────
SPECIAL_ORDER_PATTERNS = [
    r"конденсац",
    r"80/125.*конденсац",
    r"нержав",
    r"ремонт",
    r"комплект",
    r"дымоход",
    r"переходн",
    r"форсунки",
    r"vivat",
    r"viessma",
    r"ariston,?vaillant",
    r"baxi \(кроме",
    r"для всех моделей",
]


# ── Excluded radiator brand patterns ─────────────────────────────
EXCLUDED_RADIATOR_BRAND_PATTERNS = [
    r"ruterm",
    r"orso",
    r"sanline",
    r"proexpert",
    r"\bvcr\b",
    r"\bvcu\b",
]


def is_excluded_radiator_brand(name: str) -> bool:
    """
    Single source of truth for radiator brand exclusion logic.

    Exclude substitute/secondary radiator variants,
    but allow Universal for 200 lower-connection radiators.
    """
    name = str(name or "").strip().lower()
    name = name.replace("ё", "е")
    name = re.sub(r"\s+", " ", name)

    if "universal" in name:
        if "200" in name and ("ниж" in name or "нижнее" in name):
            return False
        return True

    return any(re.search(p, name) for p in EXCLUDED_RADIATOR_BRAND_PATTERNS)
