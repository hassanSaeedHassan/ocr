# test_secrets_app.py
import streamlit as st

st.title("🔥 Secrets Demo")

# Show all top-level sections
st.subheader("Secret sections available:")
st.write(list(st.secrets.keys()))

# Try reading a known secret
try:
    secret_val = st.secrets["api"]["test_key"]
    st.success(f"`test_key` loaded: {secret_val}")
except Exception as e:
    st.error(f"Could not load secret: {e}")
