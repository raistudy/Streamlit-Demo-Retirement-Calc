import streamlit as st
from networth import render_networth
from retirement import render_retirement

st.set_page_config(page_title="Finance Toolkit", page_icon="🧮", layout="centered")

def init_state():
    if "route" not in st.session_state:
        st.session_state.route = "home"
    if "currency" not in st.session_state:
        st.session_state.currency = "EUR"

def go(route: str):
    st.session_state.route = route

init_state()

route = st.session_state.route

if route == "home":
    st.title("Welcome 👋")
    st.write("Choose a tool to begin. They are independent for now.")

    st.session_state.currency = st.selectbox(
        "Currency",
        ["EUR", "IDR", "CNY"],
        index=["EUR", "IDR", "CNY"].index(st.session_state.currency),
    )

    c1, c2 = st.columns(2)
    with c1:
        st.button("Net Worth Tracker", type="primary", on_click=go, args=("networth",))
    with c2:
        st.button("Retirement Compound Calculator", type="primary", on_click=go, args=("retirement",))

    st.caption("Demo note: optional Sign up / Log in saves locally (JSON).")

elif route == "networth":
    render_networth(on_back=lambda: go("home"))

elif route == "retirement":
    render_retirement(on_back=lambda: go("home"))

else:
    st.session_state.route = "home"
    st.rerun()
