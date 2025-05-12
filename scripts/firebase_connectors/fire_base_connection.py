import json
from datetime import datetime

import pandas as pd
import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import os

# ─── FIRESTORE INIT ────────────────────────────────────────────────────
@st.cache_resource
def init_db():
    # Grab the AttrDict from Secrets
    st.write(os.environ)
    firebase_config = st.secrets["firebase"]

    # Turn into a plain dict
    service_account_dict = {k: firebase_config[k] for k in firebase_config}

    # Initialize the credentials
    cred = credentials.Certificate(service_account_dict)

    # Only initialize once
    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app(cred)

    return firestore.client()
# ─── AUTH HELPERS ───────────────────────────────────────────────────────
def login_user(db, email: str, pwd: str) -> dict | None:
    """
    Return user dict if email/password match, otherwise None.
    """
    docs = (
        db.collection("auth")
          .where("email", "==", email)
          .where("password", "==", pwd)
          .stream()
    )
    for doc in docs:
        return doc.to_dict()
    return None


def signup_user(db, email: str, pwd: str, username: str) -> tuple[bool, str | None]:
    """
    Create a new user in auth collection.
    Return (True, None) on success, or (False, message) if email exists.
    """
    existing = db.collection("auth").where("email", "==", email).get()
    if existing:
        return False, "Email already registered"

    db.collection("auth").add({
        "email": email,
        "password": pwd,
        "username": username,
        "createdAt": datetime.utcnow()
    })
    return True, None


# ─── APPOINTMENT LOADER ─────────────────────────────────────────────────
@st.cache_data
def load_appointments(_db) -> pd.DataFrame:
    """
    Fetch only 'pending' appointments and return a DataFrame
    with Title-Cased column names, sorted by Create At.
    """
    rows = []
    docs = _db.collection("appointments") \
              .where("status", "==", "pending") \
              .stream()

    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id

        # convert Firestore timestamp to Python datetime
        ts = data.get("createdAt")
        if hasattr(ts, "to_datetime"):
            data["createdAt"] = ts.to_datetime()

        rows.append(data)

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # Coerce and sort
    df["createdAt"] = pd.to_datetime(df["createdAt"])
    df = df.sort_values("createdAt", ascending=True)

    # Rename for display
    df = df.rename(columns={
        "id":                "ID",
        "clientType":        "Client Type",
        "lastName":          "Last Name",
        "firstName":         "First Name",
        "appointmentType":   "Appointment Type",
        "status":            "Status",
        "appointmentDate":   "Appointment Date",
        "marketingConsent":  "Marketing Consent",
        "phone":             "Phone",
        "certifyInfo":       "Certify Info",
        "documentUrls":      "Document URLs",
        "createdAt":         "Create At",
        "email":             "Email",
        "contractPassword":  "Contract Password",
        "timeSlot":          "Time Slot",
        "countryCode":       "Country Code"
    })

    return df.reset_index(drop=True)
