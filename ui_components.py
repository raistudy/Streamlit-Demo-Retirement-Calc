import streamlit as st

def card(title: str, body_md: str) -> None:
    """Render a simple reusable card."""
    st.markdown(
        f"""
        <div class="ui-card">
          <div class="ui-card-title">{title}</div>
          <div class="ui-card-body">{body_md}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def pill(text: str) -> None:
    st.markdown(f'<span class="ui-pill">{text}</span>', unsafe_allow_html=True)

def section(title: str, subtitle: str = "") -> None:
    st.markdown(
        f"""
        <div class="ui-section">
          <div class="ui-section-title">{title}</div>
          {f'<div class="ui-section-sub">{subtitle}</div>' if subtitle else ''}
        </div>
        """,
        unsafe_allow_html=True,
    )
