"""
core_networth.py

UI-agnostic net worth computation helpers.

This module contains:
- safe number parsing
- sum helpers
- debt classification (good vs bad)
- overall status computation
- payload builder (JSON-serializable)

No Streamlit imports here.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple
import datetime as _dt

def today_iso() -> str:
    return _dt.date.today().isoformat()

def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return float(default)
        if isinstance(value, (int, float)):
            return float(value)
        s = str(value).strip().replace(",", "")
        if s == "":
            return float(default)
        return float(s)
    except Exception:
        return float(default)

def sum_items(items: List[Dict[str, Any]], key: str) -> float:
    total = 0.0
    for it in items or []:
        total += safe_float(it.get(key, 0.0), 0.0)
    return float(total)

def is_good_debt(debt: Dict[str, Any]) -> bool:
    """
    Rule:
    - Mortgage is considered good debt
    - Or interest < 4% annually
    """
    dtype = (debt.get("type") or "").strip().lower()
    if dtype == "mortgage":
        return True
    interest = safe_float(debt.get("interest", 0.0), 0.0)
    return interest < 0.04

def compute_status(
    assets_total: float,
    debts_total: float,
    bad_debt_total: float,
    cashflow: float,
    emergency_fund: float,
    essential_monthly: float,
) -> Tuple[str, str]:
    """
    Returns:
    - status label
    - short explanation
    """
    assets_total = float(assets_total)
    debts_total = float(debts_total)
    bad_debt_total = float(bad_debt_total)
    cashflow = float(cashflow)
    emergency_fund = float(emergency_fund)
    essential_monthly = float(essential_monthly)

    # Simple heuristics tuned for your UI:
    runway = (emergency_fund / essential_monthly) if essential_monthly > 0 else 0.0

    if cashflow < 0 and runway < 3:
        return "High Stress", "Negative cash flow and less than ~3 months runway."
    if bad_debt_total > 0 and runway < 6:
        return "Vulnerable", "Some bad debt and runway below ~6 months."
    if cashflow >= 0 and runway >= 6:
        return "Stable", "Positive/neutral cash flow and at least ~6 months runway."
    return "Vulnerable", "Build runway and reduce high-interest debt for stability."

def build_payload(
    month: str,
    currency: str,
    assets_items: List[Dict[str, Any]],
    debts_items: List[Dict[str, Any]],
    income_items: List[Dict[str, Any]],
    expense_items: List[Dict[str, Any]],
    emergency_fund: Any,
    note: str = "",
    date_iso: str | None = None,
) -> Dict[str, Any]:
    assets_total = sum_items(assets_items, "value")
    debts_total = sum_items(debts_items, "balance")
    net_worth = assets_total - debts_total

    income_total = sum_items(income_items, "value")
    expense_total = sum_items(expense_items, "value")
    cashflow = income_total - expense_total

    essential_total = sum_items([e for e in (expense_items or []) if e.get("essential")], "value")
    emergency_fund_f = safe_float(emergency_fund, 0.0)
    runway_months = (emergency_fund_f / essential_total) if essential_total > 0 else 0.0

    bad_debt_total = 0.0
    for d in debts_items or []:
        if not is_good_debt(d):
            bad_debt_total += safe_float(d.get("balance", 0.0), 0.0)

    status, status_msg = compute_status(
        assets_total=assets_total,
        debts_total=debts_total,
        bad_debt_total=bad_debt_total,
        cashflow=cashflow,
        emergency_fund=emergency_fund_f,
        essential_monthly=essential_total,
    )

    return {
        "date": (date_iso or today_iso()),
        "month": month,
        "currency": currency,
        "assets_items": assets_items,
        "debts_items": debts_items,
        "income_items": income_items,
        "expense_items": expense_items,
        "emergency_fund": float(emergency_fund_f),
        "assets_total": float(assets_total),
        "debts_total": float(debts_total),
        "net_worth": float(net_worth),
        "income_total": float(income_total),
        "expense_total": float(expense_total),
        "cashflow": float(cashflow),
        "essential_expense_total": float(essential_total),
        "runway_months": float(runway_months),
        "bad_debt_total": float(bad_debt_total),
        "status": status,
        "status_msg": status_msg,
        "note": note or "",
    }
