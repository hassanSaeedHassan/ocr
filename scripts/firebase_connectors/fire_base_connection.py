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
def load_appointments(db) -> pd.DataFrame:
    """
    Fetch pending appointments. 
    - If st.session_state.selected_csr is set (a CSR), keep only those unassigned 
      or assigned to that CSR name.
    - Otherwise (admin), return all pending.
    Returns a DataFrame with Title-Cased columns plus raw 'id'.
    """
    # 1) Who’s the CSR?  (now stored as a name string)
    csr_name = st.session_state.get("selected_csr")  # e.g. "Ahmed Salah" or None

    # 2) Pull all pending docs
    rows = []
    for doc in db.collection("appointments") \
                 .where("status", "==", "pending") \
                 .stream():
        d = doc.to_dict()
        d["id"] = doc.id
        # ensure assigned_to exists (could be missing)
        d["assigned_to"] = d.get("assigned_to", None)
        # convert Firestore ts
        ts = d.get("createdAt")
        if hasattr(ts, "ToDatetime"):
            d["createdAt"] = ts.ToDatetime()
        rows.append(d)

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # 3) If CSR-mode, filter by assigned_to
    if csr_name:
        df = df[df["assigned_to"].isna() | (df["assigned_to"] == csr_name)]

    # 4) Drop any failed bookings
    if "bookingStatus" in df.columns:
        df = df[df["bookingStatus"].str.lower() != "failed"]

    # 5) Sort by creation time
    if "createdAt" in df.columns:
        df["createdAt"] = pd.to_datetime(df["createdAt"])
        df = df.sort_values("createdAt", ascending=True)

    # 6) Rename to Title Case
    df = df.rename(columns={
        "id":                "ID",
        "firstName":         "First Name",
        "lastName":          "Last Name",
        "clientType":        "Client Type",
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

    # 7) Reset index to 1-based
    df = df.reset_index(drop=True)
    df.index = df.index + 1

    return df
