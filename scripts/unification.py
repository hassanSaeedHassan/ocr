import json
import re
from collections import defaultdict
from datetime import datetime
import streamlit as st


def preprocess_pages(raw_pages, clean_json_string):
    """
    1) For each page, if it has raw_text, strip markdown fences.
    2) Remove any { … } block that contains NO colon (:) inside — those are invalid single‑string objects.
    3) JSON‑parse the cleaned text back into a dict.
    """
    pages = {}
    for pname, content in raw_pages.items():
        if isinstance(content, dict) and "raw_text" in content:
            cleaned = clean_json_string(content["raw_text"])
            # REMOVE any {...} block with no ':' inside (invalid single‑string objects)
            cleaned = re.sub(r'\{[^:{}]*\}', '{}', cleaned)
            try:
                pages[pname] = json.loads(cleaned)
            except json.JSONDecodeError:
                # fallback: leave original
                pages[pname] = content
        else:
            pages[pname] = content
    return pages






def unify_contract_f(raw, clean_json_string):
    """
    Normalize and unify multi-page 'contract f' extractions into a single dict.
    - Unwraps `raw_text` pages
    - Normalizes key variants (spaces vs underscores)
    - Collects Contract, Owner, Buyers Share, Property, Mortgage, Brokers
    - Gathers ordered lists of Person Details, National ID, Passport
    - Zips them into "Person Details Buyer # N"
    - Fixes swapped Property fields (Unit vs Area Size)
    - Ensures default Person Details if missing
    """
    # Helper to normalize keys (strip spaces/underscores, lowercase)
    def norm_key(k: str) -> str:
        return k.replace(" ", "").replace("_", "").lower()

    # 1) Parse raw into pages dict
    if isinstance(raw, str):
        try:
            pages = json.loads(clean_json_string(raw))
        except json.JSONDecodeError:
            pages = {}
    else:
        pages = raw or {}

    # 2) Unwrap any raw_text fields
    for pname, content in list(pages.items()):
        if isinstance(content, dict) and "raw_text" in content:
            try:
                pages[pname] = json.loads(clean_json_string(content["raw_text"]))
            except json.JSONDecodeError:
                pass

    # 3) Sort key for pages
    def page_key(k):
        m = re.search(r"_(\d+)$", k)
        return int(m.group(1)) if m else 0

    # 4) Prepare collectors
    persons = []
    nids    = []
    ppts    = []
    contract, owner, buyer_shares = {}, {}, {}
    prop, mortgage, sb, bb = {}, {}, {}, {}

    # 5) Walk pages in order
    for pname in sorted(pages, key=page_key):
        pg = pages[pname] or {}
        # build normalized lookup
        norm_pg = { norm_key(k): v for k, v in pg.items() }

        # top-level sections (catch both spaced and underscored keys)
        contract     = norm_pg.get("contractinformation", contract)
        owner        = norm_pg.get("ownerdetails", owner)
        buyer_shares = norm_pg.get("buyerssharedetails", buyer_shares)
        prop         = norm_pg.get("propertydetails", prop)
        mortgage     = norm_pg.get("mortgagedetails", mortgage)
        sb           = norm_pg.get("sellerbrokerdetails", sb)
        bb           = norm_pg.get("buyerbrokerdetails", bb)

        # Person Details
        if "persondetails" in norm_pg:
            persons.append(norm_pg["persondetails"])

        # National ID Information
        if "nationalidinformation" in norm_pg:
            nid_blk = norm_pg["nationalidinformation"]
            clean_nid = {
                k: v for k, v in nid_blk.items()
                if k not in ("passportinformation","addressinformation",
                             "persondetails","nationalidinformation")
            }
            nids.append(clean_nid)
            # nested under National ID
            nested_nid = nid_blk.get("nationalidinformation")
            if isinstance(nested_nid, dict):
                nids.append(nested_nid)
            if "persondetails" in nid_blk:
                persons.append(nid_blk["persondetails"])
            if "passportinformation" in nid_blk:
                ppts.append(nid_blk["passportinformation"])

        # Passport Information at top level
        if "passportinformation" in norm_pg:
            ppts.append(norm_pg["passportinformation"])

    # 6) Normalize Buyers Share Details labels
    pat = re.compile(r"Buyer\s*#\s*(\d+)")
    if not any(pat.match(k) for k in buyer_shares):
        buyer_shares = {"Buyer # 1": buyer_shares}
    labels = sorted(buyer_shares, key=lambda k: int(pat.match(k).group(1)))

    # 7) Fix swapped Property fields
    if prop.get("Type of Property") == "Area Size (SqMt)" and "Unit" in prop:
        prop["Area Size (SqMt)"] = prop.pop("Unit")
        prop["Type of Property"] = "Unit"
    elif prop.get("Type of Property").strip() == "" and "Unit" in prop:
        prop["Area Size (SqMt)"] = prop["Unit"]
        prop["Type of Property"] = "Unit"
        del prop["Unit"]

    elif prop.get("Type of Property").strip() == "":
        prop["Type of Property"] = "Unit"

    # 8) Build unified output
    out = {
        "Contract Information": contract,
        "Owner Details":      owner,
        "Buyers Share Details": buyer_shares,
        "Property Details":     prop,
    }
    if mortgage:
        out["Mortgage Details"] = mortgage

    # 9) Zip into Person Details Buyer # N
    for i, lbl in enumerate(labels):
        entry = {}
        # default Person Details
        pd = persons[i] if i < len(persons) else {}
        if not pd:
            pd = {"Person Type": "Resident", "Contract Signature Date": ""}
        entry["Person Details"] = pd
        entry["National ID Information"] = nids[i] if i < len(nids) else {}
        entry["Passport Information"]    = ppts[i] if i < len(ppts) else {}
        out[f"Person Details Buyer # {i+1}"] = entry

    # 10) Broker sections
    out["Seller Broker Details"] = sb
    out["Buyer Broker Details"]  = bb

    return out





# Arabic month name mapping (extend as needed)
ARABIC_MONTHS = {
    'يناير': '01', 'فروری': '02', 'مارس': '03', 'أبريل': '04',
    'مايو': '05', 'يونيو': '06', 'يوليو': '07', 'أغسطس': '08',
    'سبتمبر': '09', 'أكتوبر': '10', 'نوفمبر': '11', 'ديسمبر': '12'
}

def _recover_json(text: str) -> str:
    """
    1) Trim everything after the last '}' (drops incomplete fragments)
    2) Append missing '}' if there are more '{' than '}'
    """
    # 1) cut trailing noise
    idx = text.rfind('}')
    if idx != -1:
        text = text[: idx + 1]
    # 2) balance braces
    opens = text.count('{')
    closes = text.count('}')
    if opens > closes:
        text += '}' * (opens - closes)
    return text

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

def unify_commercial_license(raw_data, clean_json_string):
    """
    Recover from truncated JSON, then extract only:
      1. company_name
      2. registered_number
      3. issue_date
      4. expiry_date
      5. incorporation_date (if exists)
      6. incumbency_date (if exists)
    """
    # 1) Raw → text cleanup → recover braces → parse JSON
    if isinstance(raw_data, str):
        txt = clean_json_string(raw_data)
        txt = _recover_json(txt)
        try:
            data = json.loads(txt)
        except json.JSONDecodeError:
            data = {}
    else:
        data = raw_data.copy()

    # 2) unwrap {"raw_text": "..."} if present
    if isinstance(data, dict) and "raw_text" in data and isinstance(data["raw_text"], str):
        inner = clean_json_string(data["raw_text"])
        inner = _recover_json(inner)
        try:
            data = json.loads(inner)
        except:
            pass

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
