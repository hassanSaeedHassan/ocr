# test_secrets_app.py
import os, streamlit as st

st.title("🔒 Secrets Test")

# List available secret sections
try:
    sections = list(st.secrets.keys())
    st.write("st.secrets sections:", sections)
except Exception as e:
    st.error(f"No st.secrets: {e}")

# Try a known secret
for section, key in [("api","test_key")]:
    try:
        val = st.secrets[section][key]
        st.success(f"Loaded st.secrets['{section}']['{key}'] = {val!r}")
    except Exception:
        # fallback
        env = os.getenv(f"{section.upper()}__{key.upper()}")
        if env:
            st.success(f"Loaded env var {section.upper()}__{key.upper()} = {env!r}")
        else:
            st.error(f"Secret {section}.{key} not found")
