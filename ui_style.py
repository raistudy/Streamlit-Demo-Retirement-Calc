import streamlit as st
from pathlib import Path

def load_css(path: str = "styles.css") -> None:
    """Inject a single global CSS file into Streamlit."""
    css = Path(path).read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
