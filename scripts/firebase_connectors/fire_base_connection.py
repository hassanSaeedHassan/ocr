import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import pandas as pd

# ─── FIRESTORE INIT ────────────────────────────────────────────────────

def init_db():
    # Copy secrets into a mutable dict
    fb_raw   = st.secrets["firebase"]
    fb_creds = fb_raw.to_dict()                           

    # Convert escaped "\n" into real newlines (PEM format)
    fb_creds["private_key"] = fb_creds["private_key"].replace("\\n", "\n")

    # Initialize Firebase
    cred = credentials.Certificate(fb_creds)
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

# @st.cache_data
def load_appointments(_db) -> pd.DataFrame:
    """
    Fetch only 'pending' appointments (excluding failed bookings), 
    return a DataFrame with Title-Cased column names, sorted by Create At,
    and with a 1-based index.
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

        # convert Firestore timestamp to Python datetime
        ts = d.get("createdAt")
        if hasattr(ts, "ToDatetime"):
            d["createdAt"] = ts.ToDatetime()

        rows.append(d)

    # ─── build DataFrame ─────────────────────────────
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # ─── drop any failed bookings ─────────────────────
    if "bookingStatus" in df.columns:
        df = df[df["bookingStatus"].str.lower() != "failed"]

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
        "countryCode":       "Country Code",
        "bookingStatus":     "Booking Status"
    })

    # ─── reset index, then shift to 1-based ──────────
    df = df.reset_index(drop=True)
    df.index = df.index + 1

    return df
