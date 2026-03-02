"""
core.py

UI-agnostic retirement calculation engine.

This module contains:
- return profile mapping (RATE_MAP)
- compound growth functions
- safe withdrawal / drawdown calculation
- tier classification + lifestyle markdown

It is intentionally free of Streamlit (no st.* calls), so it can be reused by:
- Streamlit UI (retirement.py)
- future web/mobile UI (Next.js/Flutter)
- API layer (FastAPI) if you add one later
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

# ========= Config =========
RATE_MAP: Dict[str, float] = {
    "High (stocks 10%)": 0.10,
    "Medium (bonds 6%)": 0.06,
    "Low (savings 3%)": 0.03,
}

# ========= Math helpers =========
def monthly_rate_from_annual(r_annual: float) -> float:
    return (1.0 + float(r_annual)) ** (1.0 / 12.0) - 1.0

def future_value_lump(pv: float, r_m: float, n_months: int) -> float:
    pv = float(pv)
    r_m = float(r_m)
    n_months = int(n_months)
    return pv * ((1.0 + r_m) ** n_months)

def future_value_annuity(pmt: float, r_m: float, n_months: int) -> float:
    pmt = float(pmt)
    r_m = float(r_m)
    n_months = int(n_months)
    if abs(r_m) < 1e-12:
        return pmt * n_months
    return pmt * (((1.0 + r_m) ** n_months - 1.0) / r_m)

def swr_drawdown(fv: float, swr: float = 0.04) -> Tuple[float, float]:
    fv = float(fv)
    swr = float(swr)
    annual = fv * swr
    monthly = annual / 12.0
    return annual, monthly


# ========= Tiers =========
TIERS_EUR = [
    (0, 500, "Hustler", "Extra hobby money; keep your main income."),
    (500, 1200, "Bill Buffer", "Covers some recurring bills; job still needed for rent/saving."),
    (1200, 1800, "Lean-FI", "Frugal living in low-mid cost EU or house-share in pricier cities."),
    (1800, 2500, "Base-FI", "Modest one-bed in mid-cost cities; normal groceries and transit."),
    (2500, 3500, "Comfort-FI", "Comfortable EU city life; more dining, travel, and buffer."),
    (3500, 5000, "Family-FI", "Support a small family or nicer housing; stable savings and travel."),
    (5000, 7000, "Upscale-FI", "Premium housing, frequent travel, high flexibility."),
    (7000, 10000, "Freedom-Plus", "High freedom: premium lifestyle and strong buffer."),
    (10000, 10**12, "The Millionaire", "Very high financial freedom; you can fund ambitious dreams."),
]

TIERS_IDR = [
    (0, 2_000_000, "Hustler", "Small passive stream; daily life still depends on salary."),
    (2_000_000, 6_000_000, "Bill Buffer", "Covers some bills and small treats; rent still needs work."),
    (6_000_000, 12_000_000, "Lean-FI", "Frugal living; modest housing, simple food, limited travel."),
    (12_000_000, 20_000_000, "Base-FI", "Modest comfort in major cities; stable baseline."),
    (20_000_000, 35_000_000, "Comfort-FI", "Comfortable lifestyle; more dining, travel, and buffer."),
    (35_000_000, 55_000_000, "Family-FI", "Support a family, nicer housing; stable savings."),
    (55_000_000, 85_000_000, "Upscale-FI", "Premium lifestyle; frequent travel; strong buffer."),
    (85_000_000, 130_000_000, "Freedom-Plus", "High freedom; premium choices and strong buffer."),
    (130_000_000, 10**15, "The Millionaire", "Very high freedom; fund big ambitions and legacy."),
]

TIERS_CNY = [
    (0, 3000, "Hustler", "Small passive stream; salary still does the heavy lifting."),
    (3000, 8000, "Bill Buffer", "Covers recurring bills; rent and goals still need work."),
    (8000, 14000, "Lean-FI", "Frugal city living; basic rent, simple food, limited travel."),
    (14000, 22000, "Base-FI", "Modest comfort in cheaper areas; stable baseline."),
    (22000, 35000, "Comfort-FI", "Comfortable city lifestyle; more dining, travel, and buffer."),
    (35000, 55000, "Family-FI", "Support family and better housing; stable savings."),
    (55000, 85000, "Upscale-FI", "Premium housing and lifestyle; frequent travel."),
    (85000, 130000, "Freedom-Plus", "High freedom; premium choices and strong buffer."),
    (130000, 10**12, "The Millionaire", "Very high freedom; fund big ambitions and legacy."),
]

TIER_TABLES = {"EUR": TIERS_EUR, "IDR": TIERS_IDR, "CNY": TIERS_CNY}

def classify_drawdown(monthly_amount: float, currency: str) -> Tuple[str, str, float, float]:
    monthly_amount = float(monthly_amount)
    tiers = TIER_TABLES.get(currency, TIERS_EUR)
    for lo, hi, name, desc in tiers:
        if lo <= monthly_amount < hi:
            return name, desc, float(lo), float(hi)
    return "Unclassified", "Out of expected range.", 0.0, 1.0


# ========= Lifestyle deep-dive =========
TIER_LIFESTYLE: Dict[str, str] = {
    "Hustler": """
**As a Hustler**, you’ve got a small stream of passive income, enough to treat yourself every month while your day job still pays the bills.
- **Day-to-day:** Say yes to the things you love: a Michelin set lunch, a concert ticket, or collecting **Labubu**.
- **Housing:** Keep it efficient: shared living, compact studio, or low fixed-cost area.
- **Mindset:** Proof-it-works phase. The system is alive, now scale it.
""",
    "Bill Buffer": """
**As a Bill Buffer**, your portfolio covers a meaningful chunk of recurring expenses.
- **Day-to-day:** Utilities, phone, subscriptions, small bills feel lighter.
- **Mindset:** Use the breathing room to increase contributions and avoid lifestyle creep.
""",
    "Lean-FI": """
**As Lean-FI**, your investments can cover a frugal baseline.
- **Day-to-day:** Cooking at home, intentional spending, public transport, cheaper neighborhoods.
- **Housing:** House-share or compact studio in pricey cities, or a decent place in cheaper regions.
- **Mindset:** Freedom is emerging, but discipline matters.
""",
    "Base-FI": """
**As Base-FI**, you can fund a modest, comfortable life without relying on a salary.
- **Day-to-day:** Normal groceries, occasional dining, steady routines.
- **Housing:** Modest one-bed in mid-cost cities, or a nicer place in cheaper areas.
- **Mindset:** Stability phase: protect downside, keep habits.
""",
    "Comfort-FI": """
**As Comfort-FI**, you can live comfortably with real flexibility.
- **Day-to-day:** More dining out, hobbies, and higher-quality choices.
- **Travel:** Regular trips, not only budget options.
- **Mindset:** Enjoy the compounding, keep risk sensible.
""",
    "Family-FI": """
**As Family-FI**, you can support more people and still keep a buffer.
- **Day-to-day:** Bigger housing, childcare support, and stable routines.
- **Mindset:** Plan for resilience: insurance, education, longer runway.
""",
    "Upscale-FI": """
**As Upscale-FI**, your lifestyle can be premium and still sustainable.
- **Day-to-day:** Premium housing, convenience services, frequent travel.
- **Mindset:** Focus on preservation and meaning, not just growth.
""",
    "Freedom-Plus": """
**As Freedom-Plus**, money stops being a constraint for most choices.
- **Day-to-day:** Strong buffer, high autonomy, freedom to say no.
- **Mindset:** You can build big projects and still sleep well.
""",
    "The Millionaire": """
**As The Millionaire**, you have very high financial freedom.
- **Day-to-day:** You can fund ambitious dreams, support others, and build legacy.
- **Mindset:** Optimization shifts to impact, purpose, and stewardship.
""",
}

def lifestyle_for_tier(tier_name: str) -> str:
    return TIER_LIFESTYLE.get(tier_name, "")


# ========= Public API =========
@dataclass(frozen=True)
class RetirementInputs:
    currency: str
    current_net_worth: float
    monthly_contribution: float
    years: int
    annual_return: float
    annual_inflation: float = 0.0225
    swr: float = 0.04

def retirement_snapshot(inputs: RetirementInputs) -> Dict[str, Any]:
    cur = inputs.currency
    n_months = int(inputs.years) * 12
    r_m = monthly_rate_from_annual(inputs.annual_return)

    fv = future_value_lump(inputs.current_net_worth, r_m, n_months) + future_value_annuity(
        inputs.monthly_contribution, r_m, n_months
    )

    annual, monthly = swr_drawdown(fv, inputs.swr)

    inflation_factor = (1.0 + float(inputs.annual_inflation)) ** float(inputs.years)
    fv_real = float(fv) / inflation_factor if inflation_factor > 0 else float(fv)
    annual_real = float(annual) / inflation_factor if inflation_factor > 0 else float(annual)
    monthly_real = float(monthly) / inflation_factor if inflation_factor > 0 else float(monthly)

    tier_name, tier_desc, tier_lo, tier_hi = classify_drawdown(monthly, cur)

    # Yearly series for charts
    series: List[Dict[str, float]] = []
    for y in range(1, int(inputs.years) + 1):
        nm = y * 12
        v = future_value_lump(inputs.current_net_worth, r_m, nm) + future_value_annuity(
            inputs.monthly_contribution, r_m, nm
        )
        series.append({"year": float(y), "value": float(v)})

    return {
        "currency": cur,
        "fv": float(fv),
        "annual_drawdown": float(annual),
        "monthly_drawdown": float(monthly),
        "fv_real": float(fv_real),
        "annual_drawdown_real": float(annual_real),
        "monthly_drawdown_real": float(monthly_real),
        "annual_inflation": float(inputs.annual_inflation),
        "inflation_factor": float(inflation_factor),
        "tier_name": tier_name,
        "tier_desc": tier_desc,
        "tier_lo": float(tier_lo),
        "tier_hi": float(tier_hi),
        "lifestyle_md": lifestyle_for_tier(tier_name),
        "series": series,
        "assumptions": {
            "years": int(inputs.years),
            "annual_return": float(inputs.annual_return),
            "monthly_contribution": float(inputs.monthly_contribution),
            "swr": float(inputs.swr),
            "annual_inflation": float(inputs.annual_inflation),
        },
    }
