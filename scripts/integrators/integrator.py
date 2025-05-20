# scripts/integrator.py
import requests
import json
from typing import Tuple, Dict
import streamlit as st
from datetime import datetime
import re
from scripts.unifiers import *
import time
import requests
from typing import Dict, Tuple

### 1) Unified retry decorator for HTTP calls ###
def retry_on_exception(fn, retries=3, backoff=2, allowed_exceptions=(requests.exceptions.RequestException,)):
    """
    Calls fn(); on allowed exceptions, sleeps and retries up to `retries` times.
    Returns fn()’s return value, or raises on final failure.
    """
    for attempt in range(1, retries + 1):
        try:
            return fn()
        except allowed_exceptions as e:
            if attempt == retries:
                raise
            wait = backoff ** (attempt - 1)
            print(f"[Retry] Attempt {attempt}/{retries} failed: {e!r}. Retrying in {wait}s…")
            time.sleep(wait)

### 2) Post a booking, retry on connection errors & 401 refresh ###
def post_booking(auth_token: str, booking_payload: Dict) -> bool:
    url     = "https://crm.zoho.com/crm/v2.2/Deals"
    headers = {'Content-Type': 'application/json'}

    def _call(token: str):
        return retry_on_exception(
            lambda: requests.post(
                url,
                headers={**headers, 'Authorization': f'Zoho-oauthtoken {token}'},
                json=booking_payload,
                timeout=10
            ),
            retries=3
        )

    # 1) First attempt
    resp = _call(auth_token)

    # 2) If unauthorized, refresh & retry once
    if resp.status_code == 401:
        auth_token = get_auth_token(auth_token)
        resp = _call(auth_token)

    # 3) Raise for anything but 2xx
    try:
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print(f"[Zoho POST /Deals] HTTP {resp.status_code}: {resp.text}")
        return False

    # 4) Check body for success
    return bool(resp.json().get('data'))

def create_contact(auth_token: str,
                   first_name: str,
                   last_name: str,
                   email: str,
                   phone: str,
                   billing_phone: str,
                   owner: dict,
                   created_by: dict,
                   lead_source: str = "Zoho Bookings"
                  ) -> dict:
    """
    Creates a Contact in Zoho CRM and returns the API response JSON.
    """
    # make sure your ENDPOINTS dict includes:
    ZOHO_API_BASE = "https://crm.zoho.com/crm/v2.2"
    ENDPOINTS = {
        # ... other modules ...
        "contacts": f"{ZOHO_API_BASE}/Contacts",
    }
    url = ENDPOINTS["contacts"]
    record = {
        "First_Name":     first_name,
        "Last_Name":      last_name,
        "Full_Name":      f"{first_name} {last_name}",
        "Email":          email,
        "Phone":          phone,
        "Billing_Phone":  billing_phone,
        "Owner":          owner,
        "Created_By":     created_by,
        "Lead_Source":    lead_source
    }
    payload = {"data": [record]}

    def _call(token: str):
        return retry_on_exception(
            lambda: requests.post(
                url,
                headers={
                    "Authorization": f"Zoho-oauthtoken {token}",
                    "Content-Type":  "application/json"
                },
                json=payload,
                timeout=10
            ),
            retries=3
        )

    # 1) initial attempt
    resp = _call(auth_token)

    # 2) 401→refresh
    if resp.status_code == 401:
        auth_token = get_auth_token(auth_token)
        resp = _call(auth_token)

    # 3) raise on error
    resp.raise_for_status()

    return resp.json()

### 3) Search for a deal by Booking_Id, with retries & 401 refresh ###
def get_deal_id_by_booking_id(auth_token: str, booking_id: str) -> str | None:
    search_url = "https://crm.zoho.com/crm/v2.2/Deals/search"
    params     = {"criteria": f"(Booking_Id:equals:{booking_id})"}

    def _call(token: str):
        return retry_on_exception(
            lambda: requests.get(
                search_url,
                headers={'Authorization': f'Zoho-oauthtoken {token}'},
                params=params,
                timeout=10
            ),
            retries=3
        )

    resp = _call(auth_token)
    if resp.status_code == 401:
        auth_token = get_auth_token(auth_token)
        resp = _call(auth_token)

    try:
        resp.raise_for_status()
    except requests.exceptions.HTTPError:
        print(f"[Zoho Search] HTTP {resp.status_code}: {resp.text}")
        return None

    try:
        payload = resp.json()
    except ValueError:
        print(f"[Zoho Search] Non-JSON response: {repr(resp.text)}")
        return None

    data = payload.get("data") or []
    return data[0].get("id") if data else None


### 4) Upload an attachment, with retries on connection errors & 401 refresh ###
def upload_attachment_to_deal(
    auth_token: str,
    deal_id: str,
    file_name: str,
    file_content: bytes,
    content_type: str = "application/pdf"
) -> Tuple[bool, str]:
    upload_url = f"https://crm.zoho.com/crm/v2.2/Deals/{deal_id}/Attachments"

    def _call(token: str):
        return retry_on_exception(
            lambda: requests.post(
                upload_url,
                headers={'Authorization': f'Zoho-oauthtoken {token}'},
                files={'file': (file_name, file_content, content_type)},
                timeout=10
            ),
            retries=3
        )

    # 1) First attempt
    try:
        resp = _call(auth_token)
    except Exception as e:
        return False, f"HTTP request failed after retries: {e}"

    # 2) Handle 401 by refreshing & retrying once
    if resp.status_code == 401:
        auth_token = get_auth_token(auth_token)
        try:
            resp = _call(auth_token)
        except Exception as e:
            return False, f"HTTP request failed after refresh: {e}"

    # 3) Final status check
    try:
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        return False, f"HTTP {resp.status_code}: {resp.text}"

    result = resp.json()
    if isinstance(result, dict) and result.get('data'):
        return True, result['data'][0].get('download_url', '')
    return False, "Unexpected response format from Zoho"



def get_auth_token(current_token: str = '1000.aa7f6633b0d4c235ef2c317f05695a4d.c9998667002c809f7772a82e082aab67') -> str:
    """
    Returns a valid Zoho OAuth token:
      1) If current_token works, return it.
      2) Otherwise, hit the refresh endpoint up to 3 times with backoff.
      3) If refresh still fails (network or 5xx), log a warning and return current_token.
    """
    refresh_url = "https://accounts.zoho.com/oauth/v2/token"
    refresh_payload = {
        'refresh_token': '1000.e5df7eae0ebc8950cb6909334050bf72.4be3953490faab658f39661c4dc64497',
        'client_id':     '1000.EMLDH1ZQIDJAUC3G46H1QR14127OSD',
        'client_secret': 'c074d1ccbdbbc4905bb2f78a325fe048668a7b446d',
        'grant_type':    'refresh_token'
    }
    refresh_headers = {'Content-Type': 'application/x-www-form-urlencoded'}

    # 1) If we already have a token, test it lightly
    if current_token:
        try:
            r = requests.get(
                "https://crm.zoho.com/crm/v2.2/Deals",
                headers={'Authorization': f'Zoho-oauthtoken {current_token}'},
                timeout=5
            )
            if 200 <= r.status_code < 300:
                return current_token
        except requests.exceptions.RequestException:
            pass  # fall through to refresh

    # 2) Try to refresh up to 3×
    backoff = 1
    for attempt in range(1, 4):
        try:
            resp = requests.post(
                refresh_url,
                data=refresh_payload,
                headers=refresh_headers,
                timeout=10
            )
            resp.raise_for_status()
            token = resp.json().get('access_token')
            if token:
                return token
            else:
                print("[Zoho Refresh] No access_token in response")
                break
        except requests.exceptions.RequestException as e:
            if attempt == 3:
                print(f"[Zoho Refresh] All attempts failed: {e}. Falling back to existing token.")
            else:
                print(f"[Zoho Refresh] Attempt {attempt} failed: {e}. Retrying in {backoff}s…")
                time.sleep(backoff)
                backoff *= 2

    # 3) If we reach here, refresh has failed — return what we have (even if expired)
    if current_token:
        print("[Zoho Refresh] Using existing token despite refresh errors.")
        return current_token

    raise Exception("Could not obtain a Zoho OAuth token.")


        
def get_csr_and_trustee_users(auth_token):
    """
    Retrieves CSR and Trustee users from Zoho CRM
    
    Args:
        auth_token (str): Zoho OAuth token
        
    Returns:
        tuple: (CSR_Representatives, Trustee_Employees) - two lists of user objects
    """
    
    url = "https://crm.zoho.com/crm/v2.2/users"
    
    headers = {
        'Authorization': f'Zoho-oauthtoken {auth_token}',
    }
    
    CSR_Representatives = []
    Trustee_Employees = []
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        users_data = response.json()
        
        if 'users' in users_data:
            for user in users_data['users']:
                role_name = user.get('profile', {}).get('name', '').lower()
                
                if 'csr' in role_name:
                    CSR_Representatives.append(user)
                elif 'trustee' in role_name:
                    Trustee_Employees.append(user)
                    
    except requests.exceptions.RequestException as e:
        print(f"Error fetching users: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
    
    return CSR_Representatives, Trustee_Employees









def next_booking_id(access_token: str) -> str:
    # 1) pull all Deals from the domain returned by OAuth
    url = f"https://crm.zoho.com/crm/v2.2/Deals"
    headers = {'Authorization': f'Zoho-oauthtoken {access_token}'}
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    entries = resp.json().get("data", [])

    # 2) collect and filter
    booking_ids = [e.get("Booking_Id") for e in entries if e.get("Booking_Id")]
    valid = [b for b in booking_ids if not b.endswith("9999")]
    # 3) find highest numeric suffix
    def keyfn(s):
        return int(s.split("-", 1)[1])
    highest = max(valid, key=keyfn)
    prefix, num = highest.split("-", 1)
    next_num = int(num) + 1
    return f"{prefix}-{next_num:05d}"




def build_deal_payload_old(
    results: list,
    person_roles: list,
    selected_procedure: str,
    appt_date: str,     # e.g. "12-05-2025"
    time_slot: str,     # e.g. "08:15 AM"
    booking_id:str,
    owner: dict,
    assigned_trustee: dict,
    token:str
) -> dict:
    # A) Booking Id
    auth_token = get_auth_token(token)
    # booking_id = next_booking_id(auth_token)

    # B) Deal Name = full name of the first buyer
    buyer_rows = [r for r in person_roles if r.get("Role") == "buyer"]
    deal_name = buyer_rows[0]["Name"] if buyer_rows else ""

    # C) Selling price from Contract F
    price = None
    for d in results:
        if "contract f" in d.get("doc_type", "").lower():
            unified = unify_contract_f(d["extracted_data"])
            price_str = unified["Property Financial Information"]["Sell Price"]
            price = price_str.replace("AED", "").replace(",", "").strip()
            break

    # D) Build Buyer & Seller details
    def build_party_details(main_role, poa_role, prefix):
        mains = [r for r in person_roles if r["Role"] == main_role]
        poas  = [r for r in person_roles if r["Role"] == poa_role]
        details = []

        for m in mains:
            name_parts = m["Name"].split()
            entry = {}

            if prefix == "Seller":
                # Zoho’s API name for seller-first-name is Seller_fName
                entry["Seller_fName"]      = name_parts[0] if name_parts else ""
                entry["Seller_Last_Name"]  = name_parts[-1] if name_parts else ""
            else:
                # Buyer uses Buyer_First_Name
                entry["Buyer_First_Name"]  = name_parts[0] if name_parts else ""
                entry["Buyer_Last_Name"]   = name_parts[-1] if name_parts else ""

            # POA fields
            entry[f"{prefix}_POA_First_Name"] = ""
            entry[f"{prefix}_POA_Last_Name"]  = ""
            if poas:
                poa_parts = poas[0]["Name"].split()
                entry[f"{prefix}_POA_First_Name"] = poa_parts[0] if poa_parts else ""
                entry[f"{prefix}_POA_Last_Name"]  = poa_parts[-1] if poa_parts else ""

            entry[f"Is_{prefix.lower()}_Individual_Company"] = "Individual"
            details.append(entry)

        return details

    buyer_details  = build_party_details("buyer",   "poa_buyer",  "Buyer")
    seller_details = build_party_details("seller",  "poa_seller", "Seller")

    # E) Owner / CSR / Trustee blocks
    owner_block = {
        "name":      owner["name"],
        "id":        owner["id"],
        "email":     owner.get("email"),
        "full_name": owner["full_name"]
    } if owner else {}

    csr_block = {
        "module": "Users",
        "name":   owner["name"],
        "id":     owner["id"]
    } if owner else {}

    trustee_block = {
        "id":        assigned_trustee["id"],
        "name":      assigned_trustee["name"],
        "full_name": assigned_trustee["full_name"]
    } if assigned_trustee else {}

    # F) Parse and format the date properly:
    dt = datetime.strptime(appt_date, "%d-%m-%Y")
    iso_date = dt.strftime("%Y-%m-%d")

    # G) Assemble the record
    record = {
        "Deal_Name":            deal_name,
        "Booking_Id":           booking_id,
        "Appointment_Status":   "Verification Pending",
        "Date":                 iso_date,          # ← now correctly sent
        "Time":                 time_slot,
        **({"Owner": owner_block}          if owner_block else {}),
        **({"Assigned_CSR": csr_block}     if csr_block else {}),
        **({"Assigned_trustee": trustee_block} if trustee_block else {}),
        "Buyer_Details1":       buyer_details,
        "Seller_Details1":      seller_details,
        "Stage":                "Document Verification pending from CSR",
        "Individual_Company":   "Individual",
        "Procedure_Type":       selected_procedure,
        "Selling_Price":        float(price) if price else None,
        "Lead_Source":          "Booking Form"
    }

    return {"data": [record]}


def build_deal_payload(
    results: list,
    person_roles: list,
    selected_procedure: str,
    appt_date: str,     # "12-05-2025"
    time_slot: str,     # "08:15 AM"
    booking_id: str,
    owner: dict,
    assigned_trustee: dict,
    token: str
) -> dict:
    auth_token = get_auth_token(token)

    # Helper: build the name/POA entries without the contact block yet
    def build_party_details(main_role, poa_role, prefix):
        mains = [r for r in person_roles if r["Role"] == main_role]
        poas  = [r for r in person_roles if r["Role"] == poa_role]
        details = []
        for m in mains:
            first, last = m["Name"].split()[0], m["Name"].split()[-1]
            entry = {
                f"{prefix}_First_Name":     first,
                f"{prefix}_Last_Name":      last,
                f"{prefix}_POA_First_Name": "",
                f"{prefix}_POA_Last_Name":  "",
                f"Is_{prefix.lower()}_Individual_Company": "Individual",
            }
            if poas:
                pp = poas[0]["Name"].split()
                entry[f"{prefix}_POA_First_Name"] = pp[0]
                entry[f"{prefix}_POA_Last_Name"]  = pp[-1]
            details.append(entry)
        return details

    # 1) Build the “bare” detail entries
    buyer_details  = build_party_details("buyer", "poa_buyer",   "Buyer")
    seller_details = build_party_details("seller","poa_seller", "Seller")

    # 2) Create contacts and collect their Zoho IDs
    buyer_contacts = []
    for b in [r for r in person_roles if r["Role"] == "buyer"]:
        fn, ln = b["Name"].split()[0], b["Name"].split()[-1]
        resp = create_contact(
            auth_token, fn, ln,
            email=b.get("Email",""),
            phone=b.get("Phone",""),
            billing_phone=b.get("Phone",""),
            owner=owner,
            created_by=owner,
            lead_source="Zoho Bookings"
        )
        details = resp["data"][0]["details"]
        buyer_contacts.append({
            "module":  "Contacts",
            "name":    f"{fn} {ln}",
            "id":      details["id"]
        })

    seller_contacts = []
    for s in [r for r in person_roles if r["Role"] == "seller"]:
        fn, ln = s["Name"].split()[0], s["Name"].split()[-1]
        resp = create_contact(
            auth_token, fn, ln,
            email=s.get("Email",""),
            phone=s.get("Phone",""),
            billing_phone=s.get("Phone",""),
            owner=owner,
            created_by=owner,
            lead_source="Zoho Bookings"
        )
        details = resp["data"][0]["details"]
        seller_contacts.append({
            "module":  "Contacts",
            "name":    f"{fn} {ln}",
            "id":      details["id"]
        })

    # 3) Merge each detail entry with its matching contact
    #    (assumes the same order in details & contacts lists)
    for i, entry in enumerate(buyer_details):
        entry["Buyer_contact"] = buyer_contacts[i]
    for i, entry in enumerate(seller_details):
        entry["Seller_Contact"] = seller_contacts[i]

    # 4) Extract price (as before)
    price = None
    for d in results:
        if "contract f" in d.get("doc_type", "").lower():
            unified = unify_contract_f(d["extracted_data"])
            price = (
                unified["Property Financial Information"]["Sell Price"]
                .replace("AED","")
                .replace(",","")
                .strip()
            )
            break

    # 5) Format the appointment date to ISO
    dt = datetime.strptime(appt_date, "%d-%m-%Y")
    iso_date = dt.strftime("%Y-%m-%d")

    # 6) Assemble the final Zoho payload
    record = {
        "Deal_Name":           person_roles[0]["Name"],
        "Booking_Id":          booking_id,
        "Appointment_Status":  "Verification Pending",
        "Date":                iso_date,
        "Time":                time_slot,
        "Buyer_Details1":      buyer_details,
        "Seller_Details1":     seller_details,
        # Note: top‐level blocks no longer needed, because now they're inside details:
        "Buyer_contact":       buyer_contacts[0],
        "Seller_Contact":      seller_contacts[0],
        **({"Owner": owner} if owner else {}),
        **({"Assigned_CSR": {"module":"Users","name":owner["name"],"id":owner["id"]}} if owner else {}),
        **({"Assigned_trustee": assigned_trustee} if assigned_trustee else {}),
        "Stage":               "Document Verification pending from CSR",
        "Individual_Company":  "Individual",
        "Procedure_Type":      selected_procedure,
        "Selling_Price":       float(price) if price else None,
        "Lead_Source":         "Booking Form"
    }

    return {"data": [record]}
