"""
Business rules: numeric constants, coefficients, and thresholds
used for procurement metrics calculations.
"""

# ── Analysis & Sales ─────────────────────────────────────────────
ANALYSIS_PERIOD_DAYS = 60
MAX_DAILY_SALES_CAP = 10          # Safety cap for daily sales
DISPLAY_CAP = 5000                # Cap for display purposes
HALF_YEAR_WEEKS = 26
DEFAULT_TARGET_STOCK_WEEKS = 4
NON_RADIATOR_BUFFER_RATIO = 0.20
WORKING_DAYS_PER_WEEK = 5
WORKING_DAYS_PER_MONTH = 20

# ── ABC target cover days ────────────────────────────────────────
ABC_TARGET_DAYS = {
    "A": 21,
    "B": 14,
    "C": 7,
}

# ── Radiator planning ───────────────────────────────────────────
RADIATOR_MIN_MONTHLY_ORDER_QTY = 2400
RADIATOR_PEAK_MONTHLY_ORDER_QTY = 3200
RADIATOR_MIN_COVERAGE_RATIO_TO_SKIP = 0.50
RADIATOR_TARGET_MONTH_COVERAGE_RATIO = 0.60
RADIATOR_DEMAND_PEAK_THRESHOLD = 2800

RADIATOR_ABC_COVERAGE = {
    "A": 1.0,
    "B": 0.7,
    "C": 0.5,
}

# ── Non-radiator order multipliers ───────────────────────────────
NON_RADIATOR_BASE_MULTIPLIER = 1.5

TARGET_NON_RADIATOR_ORDER_MULTIPLIERS = {
    "котел baxi eco 4s 24 f": 2.5,
    "navien deluxe c coaxial 24k 2х контур.": 2.5,
    "комплект коаксиальный l=1000мм, 60/100 универсальный антилед (хомут, стакан 60/50, фланец, 2 манжет)": 2.5,
}

# ── Critical item thresholds ────────────────────────────────────
CRITICAL_DAYS_OF_COVER = 14

CRITICAL_STOCK_THRESHOLDS = {
    "FAST": 5,
    "MEDIUM": 3,
    "SLOW": 1,
}

# ── Hard cap ────────────────────────────────────────────────────
HARD_CAP = 10_000
