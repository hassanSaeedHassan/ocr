import streamlit as st
from streamlit.runtime.secrets import StreamlitSecretNotFoundError

st.title("🔍 Verify Streamlit Cloud Secrets")

# Only run in deployed environment
try:
    keys = list(st.secrets.keys())
    st.write("✅ Secrets loaded:", keys)
    st.json(st.secrets)
except StreamlitSecretNotFoundError:
    st.error("❌ No secrets found. Make sure you've saved them in App Settings → Secrets.")
