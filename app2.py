import streamlit as st

st.title("🔑 Secrets Debugger")

if st.button("Show all secrets"):
    # List all top‑level keys
    st.write("**Secret keys:**", list(st.secrets.keys()))

    # Pretty‑print the entire secrets object (including nested tables)
    st.json(st.secrets)
