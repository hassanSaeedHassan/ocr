import streamlit as st

st.title("🔍 Verify Streamlit Cloud Secrets")

if st.button("Show all secrets"):
    # Top-level sections, e.g. ["firebase"]
    st.write("Secret namespaces:", list(st.secrets.keys()))

    # Full contents of each section
    st.json(st.secrets)
