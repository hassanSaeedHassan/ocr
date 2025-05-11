import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import pandas as pd

# ─── FIRESTORE INIT ────────────────────────────────────────────────────
@st.cache_resource
def init_db():
    """
    Initialize Firebase Admin SDK and return a Firestore client.
    """
    cred = credentials.Certificate("injaz-ocr-firebase-adminsdk-fbsvc-4595d1dbfd.json")
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

def signup_user(db, email: str, pwd: str, username: str) -> tuple[bool,str|None]:
    """
    Create a new user in auth collection. Return (True, None) on success,
    or (False, message) if email exists.
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
import streamlit as st
import pandas as pd
from datetime import datetime

@st.cache_data
def load_appointments(_db) -> pd.DataFrame:
    """
    Fetch only 'pending' appointments and return a DataFrame
    with Title-Cased column names, sorted by Create At.
    """
    db = _db
    rows = []

    # ─── only pending ────────────────────────────────
    docs = db.collection("appointments") \
             .where("status", "==", "pending") \
             .stream()

    for doc in docs:
        d = doc.to_dict()
        d["id"] = doc.id

        # convert Firestore timestamp
        ts = d.get("createdAt")
        if hasattr(ts, "ToDatetime"):
            d["createdAt"] = ts.ToDatetime()

        rows.append(d)

    # ─── build dataframe ─────────────────────────────
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # ─── coerce datetime & sort ──────────────────────
    if "createdAt" in df.columns:
        df["createdAt"] = pd.to_datetime(df["createdAt"])
        df = df.sort_values("createdAt", ascending=True)

    # ─── rename columns to Title Case ────────────────
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

    # ─── reset index and return ──────────────────────
    return df.reset_index(drop=True)
