import math
import streamlit as st
import matplotlib.pyplot as plt
from storage import signup_save, login_save

# ========= Config =========
RATE_MAP = {
    "High (stocks 10%)": 0.10,
    "Medium (bonds 6%)": 0.06,
    "Low (savings 3%)": 0.03,
}

CURRENCY_SYMBOL = {"EUR": "€", "IDR": "Rp", "CNY": "¥"}

# Match Net Worth tool palette
PALETTE = {
    "cream": "#FAF2DE",
    "paper": "#FFF9EA",
    "teal": "#1F8A86",
    "mustard": "#E0B12E",
    "ink": "#1B1B1B",
}

# ========= Styling helpers =========
def _inject_retro_css() -> None:
    css = f"""
    <style>
      :root {{
        --cream: {PALETTE['cream']};
        --paper: {PALETTE['paper']};
        --teal: {PALETTE['teal']};
        --mustard: {PALETTE['mustard']};
        --ink: {PALETTE['ink']};
      }}

      .stApp {{
        background: var(--paper);
        color: var(--ink);
      }}

      /* Buttons */
      .stButton > button {{
        border-radius: 14px;
        border: 2px solid var(--ink);
        box-shadow: 2px 2px 0 var(--ink);
        white-space: pre-line;   /* allow \n line breaks */
        text-align: left;
        padding: 18px 16px;
      }}

      .stButton > button[kind="primary"] {{
        background: var(--teal);
        color: white;
      }}

      /* Tabs */
      button[role="tab"] {{
        border-radius: 14px;
        border: 2px solid var(--ink);
        margin-right: 6px;
      }}

      /* Metric style (kept for anywhere else you use st.metric) */
      [data-testid="stMetric"] {{
        background: var(--cream);
        border: 2px solid var(--ink);
        border-radius: 16px;
        padding: 12px 14px;
        box-shadow: 3px 3px 0 var(--ink);
      }}

      /* Inputs */
      [data-baseweb="input"] > div {{
        border-radius: 14px;
      }}
      [data-baseweb="textarea"] > div {{
        border-radius: 14px;
      }}
      [data-baseweb="select"] > div {{
        border-radius: 14px;
      }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def _card(title: str, body_html: str, bg: str = None) -> None:
    bgc = bg or PALETTE["cream"]
    st.markdown(
        f"""
        <div style="background:{bgc}; border:2px solid {PALETTE['ink']}; border-radius:18px;
                    padding:14px 16px; box-shadow:3px 3px 0 {PALETTE['ink']}; margin-bottom:10px;">
          <div style="font-weight:800; font-size:18px; margin-bottom:6px;">{title}</div>
          <div style="font-size:14px; line-height:1.4;">{body_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def click_metric_card(title: str, value: str, go_step: int, key: str) -> None:
    """
    Streamlit st.metric is not clickable, so we render a button that looks like a card.
    Clicking it jumps to the step that edits the corresponding input.
    """
    if st.button(f"{title}\n{value}", key=key, use_container_width=True):
        st.session_state.ret_step = go_step
        st.rerun()


# ========= Formatting helpers =========
def fmt_money(x: float, cur: str) -> str:
    sym = CURRENCY_SYMBOL.get(cur, "")
    if cur == "IDR":
        return f"{sym}{x:,.0f}".replace(",", ".")
    return f"{sym}{x:,.2f}"


def number_step_for_currency(cur: str) -> float:
    return 500_000.0 if cur == "IDR" else 100.0


# ========= State =========
def init_ret_state():
    st.session_state.setdefault("ret_step", 1)
    st.session_state.setdefault("name", "")
    st.session_state.setdefault("amount", 0.0)
    st.session_state.setdefault("want_invest", False)
    st.session_state.setdefault("monthly_amt", 0.0)
    st.session_state.setdefault("return_choice", "Medium (bonds 6%)")
    st.session_state.setdefault("target_years", 15)
    st.session_state.setdefault("currency", "EUR")


# ========= Math helpers =========
def monthly_rate_from_annual(r_annual: float) -> float:
    return (1 + r_annual) ** (1 / 12) - 1


def future_value_lump(pv: float, r_m: float, n_months: int) -> float:
    return pv * ((1 + r_m) ** n_months)


def future_value_annuity(pmt: float, r_m: float, n_months: int) -> float:
    if abs(r_m) < 1e-12:
        return pmt * n_months
    return pmt * (((1 + r_m) ** n_months - 1) / r_m)


def swr_drawdown(fv: float, swr: float = 0.04):
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


def classify_drawdown(monthly_amount: float, currency: str):
    tiers = TIER_TABLES.get(currency, TIERS_EUR)
    for lo, hi, name, desc in tiers:
        if lo <= monthly_amount < hi:
            return name, desc, lo, hi
    return "Unclassified", "Out of expected range.", 0.0, 1.0


# ========= Lifestyle deep-dive =========
TIER_LIFESTYLE = {
    "Hustler": """
**As a Hustler**, you’ve got a small stream of passive income, enough to treat yourself every month while your day job still pays the bills.
- **Day-to-day:** Say yes to the things you love: a Michelin set lunch, a concert ticket, or collecting **Labubu**.
- **Housing:** Keep it efficient, shared living, compact studio, or low fixed-cost area.
- **Mindset:** Proof it works phase. System is alive, now scale it.
""",
    "Bill Buffer": """
**As a Bill Buffer**, your portfolio covers a meaningful chunk of recurring expenses.
- **Day-to-day:** Utilities, phone, subscriptions, small bills feel lighter.
- **Mindset:** Use the breathing room to increase contributions and avoid lifestyle creep.
""",
    "Lean-FI": """
**As Lean-FI**, you can survive on your portfolio with a frugal lifestyle.
- **Day-to-day:** Value-focused living, cooking more, simple pleasures.
- **Mindset:** Real freedom, still discipline-heavy.
""",
    "Base-FI": """
**As Base-FI**, you can live modestly without stressing about every euro.
- **Day-to-day:** Normal groceries, decent gym, occasional dining out.
- **Mindset:** Tradeoffs remain, but anxiety drops.
""",
    "Comfort-FI": """
**As Comfort-FI**, you can enjoy life with flexibility.
- **Day-to-day:** Better hobbies, less compromise on quality.
- **Mindset:** “Normal-good” life without a job.
""",
    "Family-FI": """
**As Family-FI**, you can support a household and a fuller lifestyle.
- **Day-to-day:** Childcare, insurance, bigger groceries are manageable.
- **Mindset:** Protect stability, avoid large shocks.
""",
    "Upscale-FI": """
**As Upscale-FI**, you can choose premium comfort and experiences.
- **Day-to-day:** Higher quality services, frequent travel, premium choices.
- **Mindset:** Legacy and impact start to matter more.
""",
    "Freedom-Plus": """
**As Freedom-Plus**, your lifestyle options are wide open.
- **Day-to-day:** You can say yes to almost anything with minimal guilt.
- **Mindset:** Time becomes the main asset.
""",
    "The Millionaire": """
**As The Millionaire**, you have serious financial power.
- **Day-to-day:** Passive income can exceed many full salaries.
- **Mindset:** The question becomes “what kind of life do I want to build?”
""",
    "Unclassified": """
We couldn't place your monthly draw into a tier. Adjust contributions, horizon, or return profile.
""",
}


# ========= Charts =========
def donut_progress(
    pct: float,
    center_text: str,
    sublabel: str = "",
    colors=(PALETTE["teal"], PALETTE["mustard"]),
    ring_width: float = 0.22,
):
    try:
        pct = float(pct)
    except Exception:
        pct = 0.0
    if not math.isfinite(pct):
        pct = 0.0
    pct = max(0.0, min(1.0, pct))

    if pct == 0.0:
        fracs = [1e-9, 1 - 1e-9]
    elif pct == 1.0:
        fracs = [1 - 1e-9, 1e-9]
    else:
        fracs = [pct, 1 - pct]

    fig, ax = plt.subplots(figsize=(3.6, 3.6))
    ax.pie(
        fracs,
        startangle=90,
        counterclock=False,
        colors=[colors[0], colors[1]],
        wedgeprops=dict(width=ring_width, edgecolor="white"),
    )
    ax.text(0, 0.05, center_text, ha="center", va="center", fontsize=22, fontweight="bold")
    if sublabel:
        ax.text(0, -0.2, sublabel, ha="center", va="center", fontsize=10)
    ax.axis("equal")
    try:
        st.pyplot(fig, use_container_width=True)
    except TypeError:
        st.pyplot(fig)
    plt.close(fig)


def donut_split(
    values,
    labels,
    colors=(PALETTE["teal"], PALETTE["mustard"]),
    ring_width: float = 0.28,
    center_text: str = "",
):
    vals = []
    for v in values:
        try:
            v = float(v)
        except Exception:
            v = 0.0
        if not math.isfinite(v):
            v = 0.0
        vals.append(max(v, 0.0))

    total = sum(vals)
    if total <= 0:
        fracs = [1e-9] * max(1, len(vals))
    else:
        fracs = [v / total for v in vals]
        if sum(fracs) == 0:
            fracs[0] = 1e-9

    cols = list(colors)
    if len(cols) < len(fracs):
        cols = cols * ((len(fracs) + len(cols) - 1) // len(cols))

    fig, ax = plt.subplots(figsize=(3.6, 3.6))
    ax.pie(
        fracs,
        startangle=90,
        counterclock=False,
        labels=None,
        colors=cols[: len(fracs)],
        wedgeprops=dict(width=ring_width, edgecolor="white"),
    )
    if center_text:
        ax.text(0, 0, center_text, ha="center", va="center", fontsize=16, fontweight="bold")
    ax.axis("equal")
    try:
        st.pyplot(fig, use_container_width=True)
    except TypeError:
        st.pyplot(fig)
    plt.close(fig)

    for lab, val in zip(labels, vals):
        st.write(f"- **{lab}**: {fmt_money(val, st.session_state.currency)}")


# ========= Main render =========
def render_retirement(on_back):
    init_ret_state()
    _inject_retro_css()

    rs = st.session_state.ret_step

    def rgo(step_num: int):
        st.session_state.ret_step = step_num

    st.caption("Retirement Compound Calculator, styled to match Net Worth Tracker.")

    # Step 1
    if rs == 1:
        st.title("Retirement compound calculator")
        _card(
            "Step 1: Who are we planning for?",
            "Tell me your name, we’ll keep the flow simple and mobile-first.",
        )
        name = st.text_input("Name", value=st.session_state.name, placeholder="Your name")

        c1, c2 = st.columns(2)
        with c1:
            st.button("Back to home", on_click=on_back, key="ret_btn_back_home_s1")
        with c2:
            st.button(
                "Continue ➜",
                on_click=rgo,
                args=(2,),
                type="primary",
                disabled=(not name.strip()),
                key="ret_btn_continue_s1",
            )

        st.session_state.name = name.strip()

    # Step 2
    elif rs == 2:
        st.title(f"Nice to meet you, {st.session_state.name or 'friend'}!")
        _card(
            "Step 2: Starting point",
            "Pick a currency and enter your current savings or investment balance.",
        )

        st.session_state.currency = st.selectbox(
            "Currency",
            ["EUR", "IDR", "CNY"],
            index=["EUR", "IDR", "CNY"].index(st.session_state.get("currency", "EUR")),
            key="ret_currency",
        )
        cur = st.session_state.currency

        amount = st.number_input(
            f"Starting amount ({cur})",
            min_value=0.0,
            value=float(st.session_state.amount or 0.0),
            step=number_step_for_currency(cur),
            key="ret_amount",
        )
        st.session_state.amount = float(amount)

        c1, c2 = st.columns(2)
        with c1:
            st.button("Back", on_click=rgo, args=(1,), key="ret_btn_back_s2")
        with c2:
            st.button("Continue ➜", on_click=rgo, args=(3,), type="primary", key="ret_btn_continue_s2")

    # Step 3
    elif rs == 3:
        st.title("Monthly investing")
        _card(
            "Step 3: Add monthly contributions?",
            "Monthly investing (DCA) usually matters more than tiny return differences. Keep it realistic and consistent.",
        )

        want = st.radio(
            "Do you invest monthly?",
            ["No", "Yes"],
            index=(1 if st.session_state.want_invest else 0),
            horizontal=True,
            key="ret_want_invest_radio",
        )
        st.session_state.want_invest = (want == "Yes")

        cur = st.session_state.currency
        if st.session_state.want_invest:
            default_step = 250_000.0 if cur == "IDR" else 50.0
            pmt = st.number_input(
                f"Monthly amount ({cur})",
                min_value=0.0,
                value=float(st.session_state.monthly_amt or 0.0),
                step=default_step,
                key="ret_monthly_amt",
            )
            st.session_state.monthly_amt = float(pmt)
        else:
            st.session_state.monthly_amt = 0.0

        c1, c2 = st.columns(2)
        with c1:
            st.button("Back", on_click=rgo, args=(2,), key="ret_btn_back_s3")
        with c2:
            st.button("Continue ➜", on_click=rgo, args=(4,), type="primary", key="ret_btn_continue_s3")

    # Step 4
    elif rs == 4:
        st.title("Return profile and timeline")
        _card(
            "Step 4: Assumptions",
            "Choose a simple return profile and your target years. These are averages, reality varies.",
        )

        st.session_state.return_choice = st.selectbox(
            "Return profile",
            list(RATE_MAP.keys()),
            index=list(RATE_MAP.keys()).index(st.session_state.return_choice),
            key="ret_return_choice",
        )

        yrs = st.slider(
            "Target years from now",
            min_value=1,
            max_value=60,
            value=int(st.session_state.target_years or 15),
            step=1,
            key="ret_target_years",
        )
        st.session_state.target_years = int(yrs)

        c1, c2 = st.columns(2)
        with c1:
            st.button("Back", on_click=rgo, args=(3,), key="ret_btn_back_s4")
        with c2:
            st.button("See results ➜", on_click=rgo, args=(5,), type="primary", key="ret_btn_results_s4")

    # Step 5
    elif rs == 5:
        name = st.session_state.name or "there"
        cur = st.session_state.currency
        pv = float(st.session_state.amount or 0.0)
        want_invest = bool(st.session_state.want_invest)
        pmt = float(st.session_state.monthly_amt or 0.0)
        r_annual = RATE_MAP[st.session_state.return_choice]
        r_monthly = monthly_rate_from_annual(r_annual)
        T = int(st.session_state.target_years or 15)

        st.title("Your compound growth plan")
        st.caption(
            f"Hi {name}! Currency: **{cur}** • Return: **{st.session_state.return_choice}** → **{r_annual*100:.2f}%/yr**"
        )

        # Clickable summary cards (tap to edit)
        m1, m2, m3 = st.columns(3)
        with m1:
            click_metric_card("Starting amount", fmt_money(pv, cur), go_step=2, key="ret_card_start")
        with m2:
            click_metric_card(
                "Monthly contribution",
                fmt_money((pmt if want_invest else 0.0), cur),
                go_step=3,
                key="ret_card_monthly",
            )
        with m3:
            click_metric_card("Target", f"{T} years", go_step=4, key="ret_card_target")

        st.divider()

        horizons = sorted(set([T, T + 5, T + 10, T + 20]))

        def compute_snapshot(years: int):
            n = years * 12
            pmt_eff = pmt if want_invest else 0.0

            fv_lump = future_value_lump(pv, r_monthly, n)
            fv_pmt = future_value_annuity(pmt_eff, r_monthly, n)
            total_fv = fv_lump + fv_pmt

            total_contrib = pv + pmt_eff * n
            growth = total_fv - total_contrib

            annual_dd, monthly_dd = swr_drawdown(total_fv, 0.04)
            tier_name, tier_desc, tier_lo, tier_hi = classify_drawdown(monthly_dd, cur)

            return {
                "years": years,
                "fv": total_fv,
                "contrib": total_contrib,
                "growth": growth,
                "annual_dd": annual_dd,
                "monthly_dd": monthly_dd,
                "tier_name": tier_name,
                "tier_desc": tier_desc,
                "tier_lo": tier_lo,
                "tier_hi": tier_hi,
            }

        results = [compute_snapshot(y) for y in horizons]
        target_res = next(r for r in results if r["years"] == T)

        _card(
            f"Target outcome in {T} years",
            f"""
            <b>Projected pot:</b> {fmt_money(target_res['fv'], cur)}<br>
            <b>Total contributions:</b> {fmt_money(target_res['contrib'], cur)}<br>
            <b>Growth / interest:</b> {fmt_money(target_res['growth'], cur)}<br><br>
            <b>4% rule draw:</b> {fmt_money(target_res['annual_dd'], cur)}/yr
            (≈ {fmt_money(target_res['monthly_dd'], cur)}/mo)<br>
            <b>Tier:</b> {target_res['tier_name']}<br>
            <span style="opacity:0.9;">{target_res['tier_desc']}</span>
            """,
            bg=PALETTE["cream"],
        )

        st.subheader("If you keep investing beyond the target")
        for r in results:
            if r["years"] == T:
                continue
            _card(
                f"In {r['years']} years",
                f"""
                Pot: <b>{fmt_money(r['fv'], cur)}</b><br>
                Contributions: {fmt_money(r['contrib'], cur)}<br>
                Growth: {fmt_money(r['growth'], cur)}<br>
                4% rule: <b>{fmt_money(r['monthly_dd'], cur)}/mo</b><br>
                Tier: <b>{r['tier_name']}</b>, {r['tier_desc']}
                """,
            )

        st.divider()
        st.write(
            "Notes: Projections assume end-of-month contributions and a constant average return. "
            "Taxes and fees are ignored."
        )

        st.markdown("---")
        st.subheader("Save this retirement goal (optional)")
        tab1, tab2 = st.tabs(["Sign up and Save", "Log in and Save"])

        payload = {
            "name": st.session_state.name,
            "currency": cur,
            "amount": float(st.session_state.amount or 0.0),
            "want_invest": bool(st.session_state.want_invest),
            "monthly_amt": float(st.session_state.monthly_amt or 0.0),
            "return_choice": st.session_state.return_choice,
            "target_years": int(st.session_state.target_years or 0),
            "last_pot": float(target_res["fv"]),
            "last_monthly_draw": float(target_res["monthly_dd"]),
            "last_tier": target_res["tier_name"],
        }

        with tab1:
            su_email = st.text_input("Email", key="ret_su_email")
            su_pw = st.text_input("Password", type="password", key="ret_su_pw")
            if st.button("Sign up and Save", key="ret_su_btn", type="primary"):
                ok, msg = signup_save(su_email, su_pw, payload, record_type="retirement")
                st.success(msg) if ok else st.error(msg)

        with tab2:
            li_email = st.text_input("Email ", key="ret_li_email")
            li_pw = st.text_input("Password ", type="password", key="ret_li_pw")
            if st.button("Log in and Save", key="ret_li_btn", type="primary"):
                ok, msg = login_save(li_email, li_pw, payload, record_type="retirement")
                st.success(msg) if ok else st.error(msg)

        # Removed "Edit years" and "Edit inputs" buttons
        c1, c2 = st.columns(2)
        with c1:
            st.button("See charts ➜", on_click=rgo, args=(6,), type="primary", key="ret_btn_to_charts")
        with c2:
            st.button("Back to home", on_click=on_back, key="ret_btn_back_home_s5")

    # Step 6
    elif rs == 6:
        st.title("Insights and Charts")

        cur = st.session_state.currency
        pv = float(st.session_state.amount or 0.0)
        pmt = float(st.session_state.monthly_amt or 0.0) if st.session_state.want_invest else 0.0
        r_annual = RATE_MAP[st.session_state.return_choice]
        r_monthly = monthly_rate_from_annual(r_annual)
        T = int(st.session_state.target_years or 15)
        n = T * 12

        fv_lump = future_value_lump(pv, r_monthly, n)
        fv_pmt = future_value_annuity(pmt, r_monthly, n)
        pot = fv_lump + fv_pmt
        contrib_total = pv + pmt * n
        growth = pot - contrib_total
        annual_dd, monthly_dd = swr_drawdown(pot, 0.04)
        tier_name, tier_desc, tier_lo, tier_hi = classify_drawdown(monthly_dd, cur)

        _card(
            "Snapshot",
            f"""
            Currency: <b>{cur}</b><br>
            Return: <b>{st.session_state.return_choice}</b> ({r_annual*100:.2f}%/yr)<br>
            Target: <b>{T} years</b><br>
            4% rule draw: <b>{fmt_money(monthly_dd, cur)}/mo</b><br>
            Tier: <b>{tier_name}</b><br>
            <span style="opacity:0.9;">{tier_desc}</span>
            """,
        )

        # Donut A: progress inside tier
        span = max(tier_hi - tier_lo, 1.0)
        pct_within = (monthly_dd - tier_lo) / span
        pct_within = max(0.0, min(1.0, pct_within))

        st.subheader("4% monthly draw, progress inside your tier")
        donut_progress(
            pct_within,
            center_text=f"{fmt_money(monthly_dd, cur)}/mo",
            sublabel=f"{tier_name}  • next at {fmt_money(tier_hi, cur)}/mo",
        )

        st.divider()

        # Donut B: contributions vs growth
        st.subheader("Where your pot comes from")
        donut_split(
            values=[contrib_total, max(growth, 0.0)],
            labels=["Your contributions", "Growth/interest"],
            center_text=f"{fmt_money(pot, cur)}",
        )

        st.divider()

        # Suggested approach
        st.subheader("Suggested approach (simple)")
        profile = st.session_state.return_choice
        suggestions = {
            "High (stocks 10%)": "Stock-heavy (higher return and volatility). Diversify (global equity + some bonds), keep 3 to 6 months cash, DCA monthly, rebalance yearly.",
            "Medium (bonds 6%)": "Bond tilt (steadier, lower return). Core bond fund + some equities; rebalance yearly.",
            "Low (savings 3%)": "Capital preservation. High-interest savings or term deposits. Consider higher contributions to reach higher tiers.",
        }
        _card("Plan", suggestions.get(profile, ""), bg=PALETTE["cream"])

        # Lifestyle deep-dive
        st.subheader("Lifestyle deep-dive")
        st.markdown(TIER_LIFESTYLE.get(tier_name, TIER_LIFESTYLE["Unclassified"]))

        with st.expander("Compare all tiers (see what each lifestyle feels like)"):
            for key in [
                "Hustler",
                "Bill Buffer",
                "Lean-FI",
                "Base-FI",
                "Comfort-FI",
                "Family-FI",
                "Upscale-FI",
                "Freedom-Plus",
                "The Millionaire",
            ]:
                st.markdown(f"### {key}")
                st.markdown(TIER_LIFESTYLE[key])

        st.markdown("---")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.button("Back to results", on_click=rgo, args=(5,), key="ret_btn_back_results")
        with c2:
            st.button("Edit inputs", on_click=rgo, args=(3,), key="ret_btn_edit_inputs_2")
        with c3:
            st.button("Back to home", on_click=on_back, key="ret_btn_back_home_s6")

    else:
        st.session_state.ret_step = 1
        st.rerun()