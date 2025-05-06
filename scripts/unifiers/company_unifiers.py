import json
import re
from collections import defaultdict
from datetime import datetime
import streamlit as st
from typing import Any, Union
from scripts.utils.json_utils import post_processing


# Arabic month name mapping (extend as needed)
ARABIC_MONTHS = {
    'يناير': '01', 'فبراير': '02', 'مارس': '03', 'أبريل': '04',
    'مايو': '05', 'يونيو': '06', 'يوليو': '07', 'أغسطس': '08',
    'سبتمبر': '09', 'أكتوبر': '10', 'نوفمبر': '11', 'ديسمبر': '12'
}



def clean_date(date_str: str) -> str | None:
    """Normalize and format dates to DD/MM/YYYY where possible."""
    if not date_str or date_str.lower() in {"not mentioned", "n/a"}:
        return None

    # replace Arabic month names with numbers
    for ar, num in ARABIC_MONTHS.items():
        date_str = date_str.replace(ar, num)

    # catch "DD MM YYYY" with spaces → "DD/MM/YYYY"
    m = re.match(r'^\s*(\d{1,2})\s+(\d{1,2})\s+(\d{4})\s*$', date_str)
    if m:
        day, mon, year = m.groups()
        return f"{int(day):02d}/{int(mon):02d}/{year}"

    # try common known formats
    for fmt in ("%d/%m/%Y", "%d-%b-%Y", "%d %B %Y"):
        try:
            return datetime.strptime(date_str, fmt).strftime("%d/%m/%Y")
        except:
            pass

    # fallback: return original string
    return date_str

def get_value(d: dict, keys: list[str]) -> str | None:
    """
    Look for any key in `keys` (normalized) in dict d and return its non-empty value.
    """
    for cand in keys:
        norm = cand.lower().replace(" ", "").replace("_", "")
        for k, v in d.items():
            if k.lower().replace(" ", "").replace("_", "") == norm and str(v).strip():
                vl = str(v).strip()
                if vl.lower() not in {"not mentioned", "n/a"}:
                    return vl
    return None





def unify_commercial_license(raw_data: Union[str, dict]) -> dict:


    data = raw_data.copy()
    lic = data.get("LicenseDetails", {})

    unified = {
        "company_name":       get_value(lic, ["CompanyName", "BusinessName"]),
        "registered_number":  get_value(lic, ["RegistrationNumber", "LicenseNumber", "CommercialNumber"]),
        "issue_date":         clean_date(get_value(lic, ["IssueDate", "ReleaseDate"])),
        "expiry_date":        clean_date(get_value(lic, ["ExpiryDate", "ExpirationDate"])),
        "incorporation_date": clean_date(get_value(lic, ["IncorporationDate", "EstablishmentDate"])),
        "incumbency_date":    clean_date(
                                  get_value(data.get("AuthorizedSignatory", {}), ["IncumbencyDate", "AppointmentDate"])
                                  or get_value(data, ["IncumbencyDate", "LastRenewalDate"])
                              )
    }

    # drop any keys whose value ended up None
    return {k: v for k, v in unified.items() if v is not None}