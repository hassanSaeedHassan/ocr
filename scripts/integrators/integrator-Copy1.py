# scripts/integrator.py
import requests
import json
from typing import Tuple, Dict
import streamlit as st
from datetime import datetime
import re
from scripts.unifiers import *

def get_auth_token(current_auth_token='1000.aa7f6633b0d4c235ef2c317f05695a4d.c9998667002c809f7772a82e082aab67'):
    """
    Checks if current auth token is valid, refreshes if needed
    
    Args:
        current_auth_token (str): Current Zoho OAuth token to test
        
    Returns:
        str: Valid auth token (either original or refreshed)
    """
    
    # First test if current token is still valid
    test_url = "https://crm.zoho.com/crm/v2.2/Deals"  # Simple endpoint to test token
    
    headers = {
        'Authorization': f'Zoho-oauthtoken {current_auth_token}',
    }
    
    try:
        test_response = requests.get(test_url, headers=headers)
        
        # If token is still valid (status code 200-299)
        if 200 <= test_response.status_code < 300:
            return current_auth_token
            
    except requests.exceptions.RequestException:
        pass  # We'll proceed to refresh the token
    
    # If we get here, the token needs refreshing
    refresh_url = "https://accounts.zoho.com/oauth/v2/token"
    
    refresh_payload = {
        'refresh_token': '1000.e5df7eae0ebc8950cb6909334050bf72.4be3953490faab658f39661c4dc64497',
        'client_id': '1000.EMLDH1ZQIDJAUC3G46H1QR14127OSD',
        'client_secret': 'c074d1ccbdbbc4905bb2f78a325fe048668a7b446d',
        'grant_type': 'refresh_token'
    }
    
    refresh_headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
    }
    
    try:
        refresh_response = requests.post(refresh_url, headers=refresh_headers, data=refresh_payload)
        refresh_response.raise_for_status()
        new_token = refresh_response.json().get('access_token')
        
        if new_token:
            return new_token
        else:
            raise Exception("No access_token in refresh response")
            
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to refresh token: {str(e)}")
    except Exception as e:
        raise Exception(f"Error processing token refresh: {str(e)}")
        
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


def upload_attachment_to_deal(
    auth_token: str,
    deal_id: str,
    file_name: str,
    file_content: bytes,
    content_type: str = "application/pdf"
) -> Tuple[bool, str]:
    """
    Uploads an attachment to a Zoho CRM deal
    
    Args:
        auth_token: Zoho OAuth token
        deal_id: The Deal ID to attach the file to
        file_name: Name to give the file in Zoho
        file_content: Binary content of the file
        content_type: MIME type of the file (default: "application/pdf")
    
    Returns:
        Tuple of (success_status, message) 
        - success_status: True if successful, False if failed
        - message: Success URL or error message
    """
    upload_url = f"https://crm.zoho.com/crm/v2.2/Deals/{deal_id}/Attachments"
    
    headers = {
        'Authorization': f'Zoho-oauthtoken {auth_token}',
    }
    
    try:
        files = {
            'file': (file_name, file_content, content_type)
        }
        
        response = requests.post(upload_url, headers=headers, files=files)
        response.raise_for_status()
        
        result = response.json()
        
        if isinstance(result, dict) and result.get('data'):
            return (True, result['data'][0].get('download_url', ''))
        return (False, "Unexpected response format from Zoho")
        
    except requests.exceptions.RequestException as e:
        return (False, f"HTTP request failed: {str(e)}")
    except Exception as e:
        return (False, f"Unexpected error: {str(e)}")


def get_deal_id_by_booking_id(
    auth_token: str,
    booking_id:  str
) -> str | None:
    """
    Retrieves the Deal ID from Zoho CRM using the Booking ID,
    re-using your passed-in auth_token and only refreshing it on a 401.
    Safely handles cases where Zoho returns no JSON body.

    Returns:
      deal_id or None
    """

    search_url = "https://crm.zoho.com/crm/v2.2/Deals/search"
    params     = {"criteria": f"(Booking_Id:equals:{booking_id})"}

    def _call(token: str):
        return requests.get(
            search_url,
            headers={"Authorization": f"Zoho-oauthtoken {token}"},
            params=params,
            timeout=10
        )

    # 1) Try with the token you passed in
    resp = _call(auth_token)

    # 2) If expired, refresh once
    if resp.status_code == 401:
        auth_token = get_auth_token(auth_token)  # will test/refresh
        resp = _call(auth_token)

    # 3) For any other HTTP error, log and bail
    try:
        resp.raise_for_status()
    except requests.exceptions.HTTPError:
        print(f"[Zoho Search] HTTP {resp.status_code}: {resp.text}")
        return None

    # 4) Try to parse JSON safely
    try:
        payload = resp.json()
    except ValueError:
        # not JSON – maybe empty body
        # use a plain ASCII hyphen and repr() to avoid encoding errors
        print(f"[Zoho Search] Non-JSON response ({resp.status_code}): {repr(resp.text)}")
        return None

    # 5) Extract 'data'
    data = payload.get("data") or []
    if not data:
        # no matching record
        return None

    # 6) Return the first deal's id
    return data[0].get("id")



def post_booking(auth_token: str, booking_payload: Dict) -> bool:
    """
    Posts a booking to Zoho CRM Deals. If the first attempt comes back 401,
    it will refresh the token and retry exactly once.
    """
    url     = "https://crm.zoho.com/crm/v2.2/Deals"
    headers = {'Content-Type': 'application/json'}

    def _call(token: str):
        return requests.post(
            url,
            headers={**headers, 'Authorization': f'Zoho-oauthtoken {token}'},
            json=booking_payload,
            timeout=10
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
        # Log the full response text for debugging
        print(f"[Zoho POST /Deals] HTTP {resp.status_code}: {resp.text}")
        return False

    # 4) Check body for success
    data = resp.json().get('data')
    return bool(data)





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
    appt_date: str,
    time_slot: str
) -> dict:
    """
    Assemble the final payload dict to send to Zoho.
    """
    # A) Booking Id
    auth_token = get_auth_token()
    
#     token, api_domain = fetch_zoho_access_token()
    booking_id = next_booking_id(auth_token)

    # B) Deal Name = full name of the first buyer
    buyer_rows = [r for r in person_roles if r.get("Role") == "buyer"]
    deal_name = buyer_rows[0]["Name"] if buyer_rows else ""

    # C) Selling price from Contract F
    price = None
    for d in results:
        if "contract f" in d.get("doc_type", "").lower():
            unified = unify_contract_f(d["extracted_data"])
            price = unified["Property Financial Information"]["Sell Price"].replace("AED", "").strip()
            break

    # D) Build Buyer_Details1 & Seller_Details1
    def build_party_details(main_role, poa_role, prefix):
        # 1) extract main and POA rows
        mains = [r for r in person_roles if r["Role"] == main_role]
        poas  = [r for r in person_roles if r["Role"] == poa_role]

        details = []
        for m in mains:
            name_parts = m["Name"].split()
            entry = {
                f"{prefix}_First_Name":          name_parts[0] if name_parts else "",
                f"{prefix}_Last_Name":           name_parts[-1] if name_parts else "",
                f"{prefix}_POA_First_Name":      "",
                f"{prefix}_POA_Last_Name":       "",
                f"Is_{prefix.lower()}_Individual_Company": "Individual",
            }
            # 2) if there's a corresponding POA, merge its name here
            if poas:
                poa_parts = poas[0]["Name"].split()
                entry[f"{prefix}_POA_First_Name"] = poa_parts[0] if poa_parts else ""
                entry[f"{prefix}_POA_Last_Name"]  = poa_parts[-1] if poa_parts else ""
            details.append(entry)

        return details

    buyer_details  = build_party_details("buyer",     "poa_buyer",  "Buyer")
    seller_details = build_party_details("seller",    "poa_seller", "Seller")



    return {
        "data": [
            {
                "Deal_Name":               deal_name,
                "Booking_Id":              booking_id,
                "Appointment_Status":      "Verification Pending",
                "Date":                    appt_date,    
                "Time":                    time_slot,    
                "Buyer_Details1":          buyer_details,
                "Stage":                   "Document Verification pending from CSR",
                "Individual_Company":      "Individual",
                "Procedure_Type":          selected_procedure,
                "Selling_Price":           price if price else None,
                "Lead_Source":             "Booking Form",
                "Seller_Details1":         seller_details
            }
        ]
    }




def build_deal_payload(
    results: list,
    person_roles: list,
    selected_procedure: str,
    appt_date: str,     # e.g. "12-05-2025"
    time_slot: str,     # e.g. "08:15 AM"
    owner: dict,
    assigned_trustee: dict,
    token:str
) -> dict:
    # A) Booking Id
    auth_token = get_auth_token(token)
    booking_id = next_booking_id(auth_token)

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
