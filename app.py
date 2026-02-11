import os, json, hashlib, base64, secrets, tempfile, datetime
import math
import streamlit as st
import matplotlib.pyplot as plt

st.set_page_config(page_title="Step-by-step Compound Growth", page_icon="🧮", layout="centered")

# ========= Simple local "auth" storage (demo only) =========
DATA_DIR = ".data"
DATA_FILE = os.path.join(DATA_DIR, "users.json")

def _ensure_db_file():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)

_ensure_db_file()

def _load_db() -> dict:
    _ensure_db_file()
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def _save_db(db: dict) -> None:
    _ensure_db_file()
    # Atomic save to avoid corrupting JSON if Streamlit reloads mid-write
    fd, tmp_path = tempfile.mkstemp(dir=DATA_DIR, prefix="users_", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, DATA_FILE)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass

def _norm_email(email: str) -> str:
    return (email or "").strip().lower()[:254]

def _sha256_legacy(pw: str) -> str:
    return hashlib.sha256((pw or "").encode("utf-8")).hexdigest()

def _hash_pw(pw: str, salt_b64: str | None = None) -> tuple[str, str]:
    pw_bytes = (pw or "").encode("utf-8")
    if not salt_b64:
        salt = secrets.token_bytes(16)
        salt_b64 = base64.b64encode(salt).decode("ascii")
    else:
        salt = base64.b64decode(salt_b64.encode("ascii"))
    dk = hashlib.pbkdf2_hmac("sha256", pw_bytes, salt, 200_000)
    return base64.b64encode(dk).decode("ascii"), salt_b64

def _verify_pw(user_rec: dict, password: str) -> bool:
    # New scheme
    if user_rec.get("pw_hash") and user_rec.get("pw_salt"):
        calc, _ = _hash_pw(password, user_rec["pw_salt"])
        return secrets.compare_digest(calc, user_rec["pw_hash"])
    # Legacy scheme
    if user_rec.get("password_hash"):
        return secrets.compare_digest(_sha256_legacy(password), user_rec["password_hash"])
    return False

def _upgrade_pw_if_legacy(user_rec: dict, password: str) -> None:
    # Upgrade legacy SHA256 to PBKDF2 on successful verification
    if user_rec.get("pw_hash") and user_rec.get("pw_salt"):
        return
    if user_rec.get("password_hash") and secrets.compare_digest(user_rec["password_hash"], _sha256_legacy(password)):
        new_hash, new_salt = _hash_pw(password)
        user_rec["pw_hash"] = new_hash
        user_rec["pw_salt"] = new_salt
        user_rec.pop("password_hash", None)

def _append_goal_history(user_rec: dict, payload: dict) -> None:
    goals = user_rec.setdefault("goals", [])
    ts = datetime.datetime.now().isoformat(timespec="seconds")
    goals.append({"ts": ts, **payload})
    if len(goals) > 30:
        user_rec["goals"] = goals[-30:]

def signup_save(email: str, password: str, payload: dict):
    email = _norm_email(email)
    if not email or not password:
        return False, "Email and password required."
    db = _load_db()
    rec = db.get(email)

    if rec:
        if not _verify_pw(rec, password):
            return False, "Account already exists with a different password. Use Log in."
        _upgrade_pw_if_legacy(rec, password)
    else:
        pw_hash, pw_salt = _hash_pw(password)
        rec = {"pw_hash": pw_hash, "pw_salt": pw_salt, "goals": []}
        db[email] = rec

    rec["last_goal"] = payload
    _append_goal_history(rec, payload)
    _save_db(db)
    return True, "Signed up and saved ✅"

def login_save(email: str, password: str, payload: dict):
    email = _norm_email(email)
    if not email or not password:
        return False, "Email and password required."
    db = _load_db()
    rec = db.get(email)
    if not rec:
        return False, "No account found. Use Sign up."
    if not _verify_pw(rec, password):
        return False, "Wrong password."

    _upgrade_pw_if_legacy(rec, password)
    rec["last_goal"] = payload
    _append_goal_history(rec, payload)
    _save_db(db)
    return True, "Logged in and saved ✅"


# ========= Session State =========

def init_state():
    defaults = {
        "step": 0,
        "name": "",
        "currency": "EUR",    # EUR / IDR / CNY
        "amount": 0.0,
        "want_invest": False,
        "monthly_amt": 0.0,
        "return_choice": "Medium (bonds 6%)",
        "target_years": 15,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
init_state()

RATE_MAP = {
    "High (stocks 10%)": 0.10,
    "Medium (bonds 6%)": 0.06,
    "Low (savings 3%)": 0.03,
}

# ========= Currency helpers =========
CURRENCY_SYMBOL = {"EUR": "€", "IDR": "Rp", "CNY": "¥"}

def fmt_money(x: float, cur: str) -> str:
    sym = CURRENCY_SYMBOL.get(cur, "")
    if cur == "IDR":
        return f"{sym}{x:,.0f}".replace(",", ".")
    else:
        return f"{sym}{x:,.2f}"

def go(step:int): st.session_state.step = step

def reset():
    # Only clear keys created by this app, do not wipe Streamlit internals.
    APP_KEYS = {
        "step","name","currency","amount","want_invest","monthly_amt","return_choice","target_years",
        "su_email","su_pw","li_email","li_pw"
    }
    for k in list(st.session_state.keys()):
        if k in APP_KEYS:
            del st.session_state[k]
    init_state()

# ========= Math helpers =========
def monthly_rate_from_annual(r_annual: float) -> float:
    return (1 + r_annual) ** (1/12) - 1

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

# ========= Tier tables per currency (per-person, monthly) =========
# EUR (baseline Europe)
TIERS_EUR = [
    (0,     500,   "Hustler",      "Extra hobby money; keep your main income."),
    (500,   1200,  "Bill Buffer",  "Covers some recurring bills; job still needed for rent/saving."),
    (1200,  1800,  "Lean-FI",      "Frugal living in low-mid cost EU or house-share in pricier cities."),
    (1800,  2500,  "Base-FI",      "Modest one-bed in mid-cost cities; normal groceries and transit."),
    (2500,  3500,  "Comfort-FI",   "Comfortable EU city life; more dining, travel, and buffer."),
    (3500,  5000,  "Family-FI",    "Support a small family or nicer housing; stable savings and travel."),
    (5000,  7000,  "Upscale-FI",   "Premium housing, frequent travel, high flexibility."),
    (7000,  10000, "Freedom-Plus", "High freedom: business-class travel, premium lifestyle, big buffer."),
    (10000, 10**12,"The Millionaire","Very high financial freedom; you can fund ambitious dreams."),
]

# IDR (Indonesia, monthly)
TIERS_IDR = [
    (0,          2_000_000,  "Hustler",       "Small passive stream; daily life still depends on salary."),
    (2_000_000,  6_000_000,  "Bill Buffer",   "Covers some bills and small treats; rent and big goals still need work."),
    (6_000_000, 12_000_000,  "Lean-FI",       "Frugal living; modest housing, simple food, limited travel."),
    (12_000_000,20_000_000,  "Base-FI",       "Modest comfort in major cities; stable monthly baseline."),
    (20_000_000,35_000_000,  "Comfort-FI",    "Comfortable lifestyle; more dining, travel, and savings buffer."),
    (35_000_000,55_000_000,  "Family-FI",     "Support a family, nicer housing; stable savings."),
    (55_000_000,85_000_000,  "Upscale-FI",    "Premium lifestyle; frequent travel; strong buffer."),
    (85_000_000,130_000_000, "Freedom-Plus",  "High freedom; premium choices; large buffer."),
    (130_000_000,10**15,     "The Millionaire","Very high freedom; fund big ambitions and legacy."),
]

# CNY (China, monthly)
TIERS_CNY = [
    (0,      3000,   "Hustler",       "Small passive stream; salary still does the heavy lifting."),
    (3000,   8000,   "Bill Buffer",   "Covers recurring bills; rent and larger goals still need work."),
    (8000,   14000,  "Lean-FI",       "Frugal city living; basic rent, simple food, limited travel."),
    (14000,  22000,  "Base-FI",       "Modest comfort in tier-2 or cheaper tier-1 areas; stable baseline."),
    (22000,  35000,  "Comfort-FI",    "Comfortable city lifestyle; more dining, travel, and buffer."),
    (35000,  55000,  "Family-FI",     "Support family and better housing; stable savings."),
    (55000,  85000,  "Upscale-FI",    "Premium housing and lifestyle; frequent travel."),
    (85000,  130000, "Freedom-Plus",  "High freedom; premium choices and strong buffer."),
    (130000, 10**12, "The Millionaire","Very high freedom; fund big ambitions and legacy."),
]

TIER_TABLES = {"EUR": TIERS_EUR, "IDR": TIERS_IDR, "CNY": TIERS_CNY}

def classify_drawdown(monthly_amount: float, currency: str):
    tiers = TIER_TABLES.get(currency, TIERS_EUR)
    for lo, hi, name, desc in tiers:
        if lo <= monthly_amount < hi:
            return name, desc, lo, hi
    return "Unclassified", "Out of expected range.", 0.0, 1.0

# ========= Deep-dive lifestyle narratives (currency-agnostic) =========
TIER_LIFESTYLE = {
    "Hustler": """
**As a Hustler**, you've got a small stream of passive income, enough to treat yourself every month while your day job still pays the bills.
- **Day-to-day:** You can say yes to the things you love: a Michelin set lunch, a concert ticket, or collecting **Labubu**. Nice little rewards without guilt.
- **Housing:** Keep it efficient, shared living, a compact studio, or staying where fixed costs are low.
- **Travel:** Occasional short trips, mostly budget style.
- **Mindset:** This is the "proof it works" phase. Your system is alive, now scale it.
""",
    "Bill Buffer": """
**As a Bill Buffer**, your portfolio can cover a meaningful chunk of recurring expenses.
- **Day-to-day:** You feel less pressure because utilities, phone, subscriptions, and small bills can be handled by your investments.
- **Housing:** Still likely tied to salary, but you can upgrade slightly or save more.
- **Travel:** A couple of modest holidays a year, off-season and budget flights.
- **Mindset:** You have breathing room. Use it to increase contributions and reduce lifestyle creep.
""",
    "Lean-FI": """
**As Lean-FI**, you can survive on your portfolio with a frugal lifestyle.
- **Day-to-day:** You cook more, choose simple pleasures, and prioritize value.
- **Housing:** Smaller apartment, shared housing, or living in a cheaper city.
- **Travel:** Low-cost travel, slow travel, or fewer trips.
- **Mindset:** Freedom is real, but it requires discipline. You are buying time, not luxury.
""",
    "Base-FI": """
**As Base-FI**, you can live modestly without stressing about every euro.
- **Day-to-day:** Normal groceries, decent gym, occasional dining out.
- **Housing:** A modest one-bed (location dependent), stable monthly routine.
- **Travel:** A few trips a year, mixing budget and comfort.
- **Mindset:** You can step away from work if you want, but you still think in tradeoffs.
""",
    "Comfort-FI": """
**As Comfort-FI**, you can enjoy life with flexibility.
- **Day-to-day:** More dining out, better hobbies, less compromise on quality.
- **Housing:** Nicer apartment, better neighborhood, or more space.
- **Travel:** Regular travel with comfort, you can choose direct flights sometimes.
- **Mindset:** This is where life feels "normal-good" without a job, not just survival.
""",
    "Family-FI": """
**As Family-FI**, you can support a household and a fuller lifestyle.
- **Day-to-day:** Family expenses are manageable, childcare, insurance, bigger groceries.
- **Housing:** Better housing choices, more space, more stability.
- **Travel:** Family holidays are feasible without stressing the budget.
- **Mindset:** Stability becomes the main value. You protect the system and avoid major risks.
""",
    "Upscale-FI": """
**As Upscale-FI**, you can choose premium comfort and experiences.
- **Day-to-day:** High-quality food, services, and hobbies become normal.
- **Housing:** Premium location, larger home, or very high comfort.
- **Travel:** Frequent travel, sometimes business class, better hotels.
- **Mindset:** Freedom includes choice and time. Your goal is often legacy and impact, not survival.
""",
    "Freedom-Plus": """
**As Freedom-Plus**, your lifestyle options are wide open.
- **Day-to-day:** You can say yes to almost anything without guilt.
- **Housing:** You choose locations for joy, not cost.
- **Travel:** Premium travel becomes routine, business class and long stays.
- **Mindset:** Time becomes your main asset. You can build projects, help family, fund causes.
""",
    "The Millionaire": """
**As The Millionaire**, you have serious financial power.
- **Day-to-day:** Your passive income is higher than many full salaries.
- **Housing:** Multiple homes, premium city centers, or dream countryside living.
- **Travel:** You can travel whenever you want, with comfort.
- **Mindset:** The question shifts from "can I afford it?" to "what kind of life do I want to build?"
""",
    "Unclassified": """
We couldn't place your monthly draw into a tier. Try adjusting contributions, time horizon, or return choice to land inside a band.
""",
}

# ========= Donut chart helpers (robust) =========
def donut_progress(pct: float, center_text: str, sublabel: str = "", colors=("#3B82F6","#F59E0B"), ring_width=0.22):
    try: pct = float(pct)
    except: pct = 0.0
    if not math.isfinite(pct): pct = 0.0
    pct = max(0.0, min(1.0, pct))
    if pct == 0.0: fracs = [1e-9, 1-1e-9]
    elif pct == 1.0: fracs = [1-1e-9, 1e-9]
    else: fracs = [pct, 1-pct]
    fig, ax = plt.subplots(figsize=(3.6, 3.6))
    ax.pie(fracs, startangle=90, counterclock=False, colors=[colors[0], colors[1]],
           wedgeprops=dict(width=ring_width, edgecolor="white"))
    ax.text(0, 0.05, center_text, ha="center", va="center", fontsize=22, fontweight="bold")
    if sublabel:
        ax.text(0, -0.2, sublabel, ha="center", va="center", fontsize=10)
    ax.axis("equal")
    try:
        st.pyplot(fig, use_container_width=True)
    except TypeError:
        st.pyplot(fig)
    plt.close(fig)

def donut_split(values, labels, colors=("#3B82F6","#F59E0B"), ring_width=0.28, center_text=""):
    vals = []
    for v in values:
        try: v = float(v)
        except: v = 0.0
        if not math.isfinite(v): v = 0.0
        vals.append(max(v, 0.0))
    total = sum(vals)
    if total <= 0:
        fracs = [1e-9] * max(1, len(vals))
    else:
        fracs = [v/total for v in vals]
        if sum(fracs) == 0:
            fracs[0] = 1e-9
    if len(colors) < len(fracs):
        colors = list(colors) * ((len(fracs) + len(colors) - 1) // len(colors))
    fig, ax = plt.subplots(figsize=(3.6, 3.6))
    ax.pie(fracs, startangle=90, counterclock=False, labels=None,
           colors=colors[:len(fracs)], wedgeprops=dict(width=ring_width, edgecolor="white"))
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

# ========= Flow =========
step = st.session_state.step

# Step 0: Hi
if step == 0:
    st.title("Hi 👋")
    st.write("Click to begin.")
    st.button("Next ➜", on_click=go, args=(1,), type="primary")

# Step 1: Ask name
elif step == 1:
    st.title("What's your name?")
    name = st.text_input("Name", value=st.session_state.name, placeholder="Your name")
    c1, c2 = st.columns(2)
    with c1: st.button("Back", on_click=go, args=(0,))
    with c2: st.button("Continue ➜", on_click=go, args=(2,), type="primary", disabled=(not name.strip()))
    st.session_state.name = name.strip()

# Step 2: Currency + starting amount
elif step == 2:
    st.title(f"Nice to meet you, {st.session_state.name or 'friend'}!")
    st.subheader("Choose currency and enter your savings/investment")
    st.session_state.currency = st.selectbox(
        "Currency", ["EUR", "IDR", "CNY"],
        index=["EUR","IDR","CNY"].index(st.session_state.currency)
    )
    cur = st.session_state.currency

    default_step = 100.0 if cur != "IDR" else 500_000.0
    amount = st.number_input(
        f"Starting amount ({cur})", min_value=0.0,
        value=float(st.session_state.amount or 0.0), step=default_step
    )
    st.session_state.amount = float(amount)

    c1, c2 = st.columns(2)
    with c1: st.button("Back", on_click=go, args=(1,))
    with c2: st.button("Continue ➜", on_click=go, args=(3,), type="primary")

# Step 3: Monthly investing
elif step == 3:
    st.title("Do you invest monthly?")
    want = st.radio("Monthly investing", ["No", "Yes"], index=(1 if st.session_state.want_invest else 0))
    st.session_state.want_invest = (want == "Yes")

    cur = st.session_state.currency
    if st.session_state.want_invest:
        default_step = 50.0 if cur != "IDR" else 250_000.0
        pmt = st.number_input(
            f"Monthly amount ({cur})", min_value=0.0,
            value=float(st.session_state.monthly_amt or 0.0), step=default_step
        )
        st.session_state.monthly_amt = float(pmt)
    else:
        st.session_state.monthly_amt = 0.0

    c1, c2 = st.columns(2)
    with c1: st.button("Back", on_click=go, args=(2,))
    with c2: st.button("Continue ➜", on_click=go, args=(4,), type="primary")

# Step 4: Return profile + target years
elif step == 4:
    st.title("Choose your return profile")
    st.session_state.return_choice = st.selectbox(
        "Return profile", list(RATE_MAP.keys()),
        index=list(RATE_MAP.keys()).index(st.session_state.return_choice)
    )
    yrs = st.slider("Target years from now", min_value=1, max_value=60,
                    value=int(st.session_state.target_years or 15), step=1)
    st.session_state.target_years = int(yrs)
    c1, c2 = st.columns(2)
    with c1: st.button("Back", on_click=go, args=(3,))
    with c2: st.button("See results ➜", on_click=go, args=(5,), type="primary")

# Step 5: Results (+ save)
elif step == 5:
    name = st.session_state.name or "there"
    cur = st.session_state.currency
    pv = float(st.session_state.amount or 0.0)
    want_invest = bool(st.session_state.want_invest)
    pmt = float(st.session_state.monthly_amt or 0.0)
    r_annual = RATE_MAP[st.session_state.return_choice]
    r_monthly = monthly_rate_from_annual(r_annual)
    T = int(st.session_state.target_years or 15)

    st.title("Your compound growth plan")
    st.caption(f"Hi {name}! Currency: **{cur}** • Return: **{st.session_state.return_choice}** → **{r_annual*100:.2f}%/yr**")

    st.metric("Starting amount (today)", fmt_money(pv, cur))
    st.metric("Monthly contribution", fmt_money((pmt if want_invest else 0.0), cur))
    st.metric("Retirement target", f"{T} years")

    st.divider()

    horizons = sorted(set([T, T+5, T+10, T+20]))

    def compute_snapshot(years:int):
        n = years * 12
        fv_lump = future_value_lump(pv, r_monthly, n)
        pmt_eff = pmt if want_invest else 0.0
        fv_pmt  = future_value_annuity(pmt_eff, r_monthly, n)
        total_fv = fv_lump + fv_pmt
        total_contrib = pv + pmt_eff * n
        growth = total_fv - total_contrib
        annual_dd, monthly_dd = swr_drawdown(total_fv, 0.04)
        tier_name, tier_desc, tier_lo, tier_hi = classify_drawdown(monthly_dd, cur)
        return {
            "years": years, "fv": total_fv, "contrib": total_contrib, "growth": growth,
            "annual_dd": annual_dd, "monthly_dd": monthly_dd,
            "tier_name": tier_name, "tier_desc": tier_desc, "tier_lo": tier_lo, "tier_hi": tier_hi
        }

    results = [compute_snapshot(y) for y in horizons]
    target_res = next(r for r in results if r["years"] == T)

    st.success(
        f"🎯 **Target: {T} years**\n\n"
        f"- Projected pot: **{fmt_money(target_res['fv'], cur)}**\n"
        f"- **Your total contributions:** {fmt_money(target_res['contrib'], cur)}\n"
        f"- **Growth/interest:** {fmt_money(target_res['growth'], cur)}\n\n"
        f"**4% rule drawdown:** ~ **{fmt_money(target_res['annual_dd'], cur)} / year** "
        f"(≈ **{fmt_money(target_res['monthly_dd'], cur)} / month**)\n\n"
        f"**Tier:** {target_res['tier_name']} - {target_res['tier_desc']}"
    )

    st.subheader("If you keep investing beyond the target")
    for r in results:
        if r["years"] == T:
            continue
        st.markdown(
            f"**In {r['years']} years**  \n"
            f"- Pot: **{fmt_money(r['fv'], cur)}**  \n"
            f"- Contributions: {fmt_money(r['contrib'], cur)}  \n"
            f"- Growth/interest: {fmt_money(r['growth'], cur)}  \n"
            f"- 4% rule ≈ **{fmt_money(r['annual_dd'], cur)}/yr** (~**{fmt_money(r['monthly_dd'], cur)}/mo**)  \n"
            f"- **Tier:** {r['tier_name']} - {r['tier_desc']}"
        )

    st.divider()
    st.write(
        "Notes: Projections assume end-of-month contributions and a constant average return. "
        "Real markets vary; taxes and fees ignored. Tiers reflect local living costs for your selected currency."
    )

    # ======= Sign up / Log in to save your setup (local JSON) =======
    st.markdown("---")
    st.subheader("Keep tracking your goal? Sign up / Log in to save")
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
        su_email = st.text_input("Email", key="su_email")
        su_pw = st.text_input("Password", type="password", key="su_pw")
        if st.button("Sign up and Save"):
            ok, msg = signup_save(su_email, su_pw, payload)
            st.success(msg) if ok else st.error(msg)

    with tab2:
        li_email = st.text_input("Email ", key="li_email")
        li_pw = st.text_input("Password ", type="password", key="li_pw")
        if st.button("Log in and Save"):
            ok, msg = login_save(li_email, li_pw, payload)
            st.success(msg) if ok else st.error(msg)

    c1, c2, c3, c4 = st.columns(4)
    with c1: st.button("Edit retirement years", on_click=go, args=(4,))
    with c2: st.button("Edit preferences", on_click=go, args=(3,))
    with c3: st.button("Start over", on_click=reset, type="secondary")
    with c4: st.button("See charts ➜", on_click=go, args=(6,), type="primary")

# Step 6: Insights & Charts (+ Lifestyle deep-dive)
elif step == 6:
    st.title("Insights and Charts")

    cur = st.session_state.currency
    pv = float(st.session_state.amount or 0.0)
    pmt = float(st.session_state.monthly_amt or 0.0) if st.session_state.want_invest else 0.0
    r_annual = RATE_MAP[st.session_state.return_choice]
    r_monthly = monthly_rate_from_annual(r_annual)
    T = int(st.session_state.target_years or 15)
    n = T * 12

    fv_lump = future_value_lump(pv, r_monthly, n)
    fv_pmt  = future_value_annuity(pmt, r_monthly, n)
    pot = fv_lump + fv_pmt
    contrib_total = pv + pmt * n
    growth = pot - contrib_total
    annual_dd, monthly_dd = swr_drawdown(pot, 0.04)
    tier_name, tier_desc, tier_lo, tier_hi = classify_drawdown(monthly_dd, cur)

    st.caption(f"Currency: **{cur}** • Return: **{st.session_state.return_choice}** → **{r_annual*100:.2f}%/yr** • Target: **{T} years**")

    # Donut A: Progress to next tier
    span = max(tier_hi - tier_lo, 1.0)
    pct_within = (monthly_dd - tier_lo) / span
    pct_within = max(0.0, min(1.0, pct_within))

    st.subheader("4% monthly draw, progress inside your tier")
    donut_progress(
        pct_within,
        center_text=f"{fmt_money(monthly_dd, cur)}/mo",
        sublabel=f"{tier_name}  • next at {fmt_money(tier_hi, cur)}/mo"
    )
    st.markdown(f"**Tier:** {tier_name} - {tier_desc}")

    st.divider()

    # Donut B: Contributions vs Growth
    st.subheader("Where your pot comes from")
    donut_split(
        values=[contrib_total, max(growth, 0.0)],
        labels=["Your contributions", "Growth/interest"],
        center_text=f"{fmt_money(pot, cur)}"
    )
    st.markdown(
        f"- **Total pot at {T} years:** {fmt_money(pot, cur)}  \n"
        f"- **Your contributions:** {fmt_money(contrib_total, cur)}  \n"
        f"- **Growth/interest:** {fmt_money(growth, cur)}  \n"
        f"- **4% rule draw:** {fmt_money(annual_dd, cur)}/yr (≈ {fmt_money(monthly_dd, cur)}/mo)"
    )

    st.divider()

    # Suggested approach (kept)
    st.subheader("Suggested approach (simple)")
    profile = st.session_state.return_choice
    suggestions = {
        "High (stocks 10%)": "Stock-heavy (higher return/volatility). Diversify (global equity + some bonds), keep 3-6 months cash, DCA monthly, rebalance yearly.",
        "Medium (bonds 6%)": "Bond tilt (steadier, lower return). Core bond fund + some equities; mind duration vs horizon; rebalance yearly.",
        "Low (savings 3%)": "Capital preservation. High-interest savings/term deposits. Consider higher contributions to reach higher tiers.",
    }
    st.markdown(f"**Based on your selection:** {profile}  \n{suggestions.get(profile, '')}")

    # Lifestyle deep-dive
    st.subheader("Lifestyle deep-dive")
    st.markdown(TIER_LIFESTYLE.get(tier_name, TIER_LIFESTYLE["Unclassified"]))

    with st.expander("Compare all tiers (see what each lifestyle feels like)"):
        for key in ["Hustler","Bill Buffer","Lean-FI","Base-FI","Comfort-FI","Family-FI","Upscale-FI","Freedom-Plus","The Millionaire"]:
            st.markdown(f"### {key}")
            st.markdown(TIER_LIFESTYLE[key])

    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    with c1: st.button("Back to results", on_click=go, args=(5,))
    with c2: st.button("Edit preferences", on_click=go, args=(3,))
    with c3: st.button("Start over", on_click=reset, type="secondary")