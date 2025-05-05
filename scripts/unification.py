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
    - Extracts first Property Financial Information, DLD Registration Fees, Payment Details
    - Restricts Property Details to specified fields, drops empty values except Area Size
    - Ignores Person Details, National ID, Address, Additional Info, Buyer Broker Commission Detail, Tenancy Info, Facilities
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

    # 3) Sort pages by trailing number
    def page_key(k):
        m = re.search(r"_(\d+)$", k)
        return int(m.group(1)) if m else 0

    # 4) Prepare collectors
    contract = {}
    owner = {}
    buyer_shares = {}
    prop = {}
    mortgage = {}
    sb = {}
    bb = {}
    prop_financial = {}
    dld_fees = {}
    payment_details = {}

    # Keys for DLD Registration Fees
    dld_fields = [
        "Percentage of DLD Registration Fees",
        "Covered Percentage of DLD Registration Fees by Buyer",
        "Covered Amount of DLD Registration Fees by Buyer",
        "Covered Percentage of DLD Registration Fees by Seller",
        "Covered Amount of DLD Registration Fees by Seller"
    ]
    # Keys for Payment Details
    pay_fields = ["Payment Type", "Amount", "Cheque Number", "Cheque Date", "Bank Name"]

    # 5) Walk pages and collect
    for pname in sorted(pages, key=page_key):
        pg = pages[pname] or {}
        norm_pg = {norm_key(k): v for k, v in pg.items()}

        contract = norm_pg.get("contractinformation", contract)
        owner = norm_pg.get("ownerdetails", owner)
        buyer_shares = norm_pg.get("buyerssharedetails", buyer_shares)
        prop = norm_pg.get("propertydetails", prop)
        mortgage = norm_pg.get("mortgagedetails", mortgage)
        sb = norm_pg.get("sellerbrokerdetails", sb)
        bb = norm_pg.get("buyerbrokerdetails", bb)

        # First Property Financial Information
        if not prop_financial and "propertyfinancialinformation" in norm_pg:
            prop_financial = norm_pg.get("propertyfinancialinformation", {})

        # First DLD Registration Fees
        if not dld_fees and "dldregistrationfees" in norm_pg:
            raw_dld = norm_pg.get("dldregistrationfees", {})
            dld_fees = {k: raw_dld.get(k, "") for k in dld_fields}

        # First Payment Details
        if not payment_details and "paymentdetails" in norm_pg:
            raw_pay = norm_pg.get("paymentdetails", {})
            filtered = {k: raw_pay.get(k, "") for k in pay_fields}
            # normalize cheque type
            pt = filtered.get("Payment Type", "")
            if "cheque" in pt.lower():
                filtered["Payment Type"] = "cheque"
            payment_details = filtered

    # 6) Fix swapped Property fields
    if prop.get("Type of Property") is None:
        prop["Type of Property"] = ""
    unit_val = prop.get("Unit", "").strip()
    area_val = prop.get("Area Size (SqMt)", "").strip()
    if prop.get("Type of Property") == "Area Size (SqMt)" and unit_val:
        prop["Area Size (SqMt)"] = prop.pop("Unit")
        prop["Type of Property"] = "Unit"
    elif prop.get("Type of Property", "").strip() == "" and unit_val and not area_val:
        prop["Area Size (SqMt)"] = prop.pop("Unit")
        prop["Type of Property"] = "Unit"
    elif prop.get("Type of Property", "").strip() == "":
        prop["Type of Property"] = "Unit"

    # 7) Filter Property Details fields and drop empty except Area Size
    allowed_prop = [
        "Location", "Type of Property", "Type of Area", "Area Size (SqMt)",
        "Usage", "Property Number", "Number of Units", "Plot Number","Building Name"
    ]
    prop = {k: v for k, v in prop.items() if k in allowed_prop and (v != "" or k == "Area Size (SqMt)")}

    # 8) Build output
    out = {
        "Contract Information": contract,
        "Owner Details": owner,
        "Buyers Share Details": buyer_shares,
        "Property Details": prop,
    }
    if prop_financial:
        out["Property Financial Information"] = prop_financial
    if mortgage:
        out["Mortgage Details"] = mortgage
    if dld_fees:
        out["DLD Registration Fees"] = dld_fees
    if payment_details:
        out["Payment Details"] = payment_details
    out["Seller Broker Details"] = sb
    out["Buyer Broker Details"] = bb
    
    if out["DLD Registration Fees"]['Covered Amount of DLD Registration Fees by Buyer']=='':
        try:
            out["DLD Registration Fees"]['Covered Amount of DLD Registration Fees by Buyer']=str(float(out["Property Financial Information"]["Sell Price"].replace('AED','').replace(',',''))*0.04)+" AED"
        except:
            out["DLD Registration Fees"]['Covered Amount of DLD Registration Fees by Buyer']==''

    return out

def unify_contract_f_old(raw, clean_json_string):
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
    
    if prop.get("Type of Property")==None:
        prop["Type of Property"] = ""
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


def unify_title_deed(raw_data, clean_json_string):
    """
    Unify and clean the title deed JSON:
    - Removes "Transaction Details"
    - Removes any fields with the value "Not mentioned"
    - Custom handling for Land vs Flat property types
    """
    
    # 1) Raw → text cleanup → parse JSON
    if isinstance(raw_data, str):
        txt = clean_json_string(raw_data)
        try:
            data = json.loads(txt)
        except json.JSONDecodeError:
            data = {}
    else:
        data = raw_data.copy()

    # 2) Remove Transaction Details
    if "Transaction Details" in data:
        del data["Transaction Details"]

    # 3) Clean 'Not mentioned' values
    def clean_not_mentioned(d):
        if isinstance(d, dict):
            return {k: clean_not_mentioned(v) for k, v in d.items() if v != "Not mentioned"}
        elif isinstance(d, list):
            return [clean_not_mentioned(i) for i in d if i != "Not mentioned"]
        else:
            return d
    
    data = clean_not_mentioned(data)

    # 4) Normalize and unify Title Deed details (e.g. Area, Owners, Property)
    title_deed = data.get("Title Deed", {})
    owners = data.get("Owners", [])

    # 5) Check Property Type and include relevant fields
    property_type = title_deed.get("Property Type", "").lower()
    if property_type == "land":
        # Fields specific to Land property type
        unified_data = {
            "Title Deed": {
                "Issue Date": title_deed.get("Issue Date"),
                "Mortgage Status": title_deed.get("Mortgage Status"),
                "Property Type": title_deed.get("Property Type"),
                "Community": title_deed.get("Community"),
                "Plot No": title_deed.get("Plot No"),
                "Municipality No": title_deed.get("Municipality No"),
                "Area Sq Meter": title_deed.get("Area Sq Meter"),
                "Area Sq Feet": title_deed.get("Area Sq Feet"),
            },
            "Owners": owners
        }
    elif property_type == 'villa':
        # Fields specific to Villa property type
        unified_data = {
            "Title Deed": {
                "Issue Date": title_deed.get("Issue Date"),
                "Mortgage Status": title_deed.get("Mortgage Status"),
                "Property Type": title_deed.get("Property Type"),
                "Community": title_deed.get("Community"),
                "Plot No": title_deed.get("Plot No"),
                "Building No": title_deed.get("Building No"),
                "Municipality No": title_deed.get("Municipality No"),
                "Area Sq Meter": title_deed.get("Area Sq Meter"),
                "Area Sq Feet": title_deed.get("Area Sq Feet"),
            },
            "Owners": owners
        }
    elif property_type == "flat":
        # Fields specific to Flat property type
        unified_data = {
            "Title Deed": {
                "Issue Date": title_deed.get("Issue Date"),
                "Mortgage Status": title_deed.get("Mortgage Status"),
                "Property Type": title_deed.get("Property Type"),
                "Community": title_deed.get("Community"),
                "Plot No": title_deed.get("Plot No"),
                "Municipality No": title_deed.get("Municipality No"),
                "Building No": title_deed.get("Building No"),
                "Building Name": title_deed.get("Building Name"),
                "Property No": title_deed.get("Property No"),
                "Floor No": title_deed.get("Floor No"),
                "Parkings": title_deed.get("Parkings"),
                "Suite Area": title_deed.get("Suite Area"),
                "Balcony Area": title_deed.get("Balcony Area"),
                "Area Sq Meter": title_deed.get("Area Sq Meter"),
                "Area Sq Feet": title_deed.get("Area Sq Feet"),
                "Common Area": title_deed.get("Common Area")
            },
            "Owners": owners
        }
    else:
        # Default case: if Property Type is unknown or missing, we can return an empty structure or handle it differently
        unified_data = {
            "Title Deed": title_deed,  # Returning as is if the Property Type is neither "Land" nor "Flat"
            "Owners": owners
        }

    # 6) Unify Owners
    if owners:
        owner_dict = defaultdict(lambda: {"Owner Name (English)": "", "Owner Name (Arabic)": "", "Share (Sq Meter)": 0.0})

        # Process the owners to merge them based on Owner ID
        for owner in owners:
            owner_id = owner["Owner ID"].strip("()")  # Remove parentheses from Owner ID
            
            # Concatenate names with space if the same Owner ID is found
            if owner_dict[owner_id]["Owner Name (English)"]:
                owner_dict[owner_id]["Owner Name (English)"] += ' '
                owner_dict[owner_id]["Owner Name (English)"] += f" {owner['Owner Name (English)']}".strip()
                owner_dict[owner_id]["Owner Name (Arabic)"] += ' '
                owner_dict[owner_id]["Owner Name (Arabic)"] += f"  {owner['Owner Name (Arabic)']}".strip()
            else:
                # Only assign the name if this is the first occurrence of the Owner ID
                owner_dict[owner_id]["Owner Name (English)"] = owner["Owner Name (English)"]
                owner_dict[owner_id]["Owner Name (Arabic)"] = owner["Owner Name (Arabic)"]

            # Retain the share for the first owner with that ID
            if owner_dict[owner_id]["Share (Sq Meter)"] == 0.0:
                owner_dict[owner_id]["Share (Sq Meter)"] = float(owner["Share (Sq Meter)"])

        # Prepare the final list of merged owners with the correct format
        merged_owners = []
        for idx, (owner_id, owner_data) in enumerate(owner_dict.items(), start=1):
            # Ensure correct spacing between names in Arabic
            arabic_name = owner_data["Owner Name (Arabic)"].strip()

            merged_owners.append({
                "Owner ID": f"{owner_id}",  # Optional: keep the parentheses if needed
                "Owner Name (English)": owner_data["Owner Name (English)"].strip(),
                "Owner Name (Arabic)": arabic_name,
                "Share (Sq Meter)": f"{owner_data['Share (Sq Meter)']:.2f}"
            })
        
        # Update the owners section with merged data
        unified_data["Owners"] = {f"Owner {idx}": owner for idx, owner in enumerate(merged_owners, start=1)}

    return unified_data


def unify_usufruct_right_certificate(raw_data, clean_json_string):
    """
    Unify and clean the Usufruct Right Certificate JSON:
    - Removes "Property Type"
    - Removes "Transaction Details"
    - Removes any fields with the value "Not mentioned"
    - Custom handling for Usufruct Right Certificate with Lessors and Lessees
    """
    
    # 1) Raw → text cleanup → parse JSON
    if isinstance(raw_data, str):
        txt = clean_json_string(raw_data)
        try:
            data = json.loads(txt)
        except json.JSONDecodeError:
            data = {}
    else:
        data = raw_data.copy()

    # 2) Remove "Transaction Details"
    if "Transaction Details" in data:
        del data["Transaction Details"]

    # 3) Clean 'Not mentioned' values
    def clean_not_mentioned(d):
        if isinstance(d, dict):
            return {k: clean_not_mentioned(v) for k, v in d.items() if v != "Not mentioned"}
        elif isinstance(d, list):
            return [clean_not_mentioned(i) for i in d if i != "Not mentioned"]
        else:
            return d
    
    data = clean_not_mentioned(data)

    # 4) Normalize and unify Usufruct Right Certificate details
    usufruct = data.get("Usufruct Right Certificate", {})
    lessors = data.get("Lessors", [])
    lessees = data.get("Lessees", [])

    # 5) Right Type and other common fields (Remove Property Type and retain the rest)
    unified_data = {
        "Usufruct Right Certificate": {}
    }

    # Add valid fields from Usufruct Right Certificate (skip "Not mentioned" ones)
    for key in ["Issue Date", "Mortgage Status", "Community", "Plot No", "Municipality No", "Building No",
                "Building Name", "Property No", "Floor No", "Parkings", "Suite Area", "Balcony Area",
                "Area Sq Meter", "Area Sq Feet", "Common Area", "Right Type"]:
        value = usufruct.get(key)
        if value != "Not mentioned" and value:
            unified_data["Usufruct Right Certificate"][key] = value

    # 6) Unify Lessors (similar to Owners merging)
    if lessors:
        lessor_dict = defaultdict(lambda: {"Lessor Name (English)": "", "Lessor Name (Arabic)": "", "Share (Sq Meter)": 0.0})

        # Process the lessors to merge them based on Lessor ID
        for lessor in lessors:
            lessor_id = lessor["Lessor ID"].strip("()")  # Remove parentheses from Lessor ID
            
            # Concatenate names with space if the same Lessor ID is found
            if lessor_dict[lessor_id]["Lessor Name (English)"]:
                lessor_dict[lessor_id]["Lessor Name (English)"] += ' '
                lessor_dict[lessor_id]["Lessor Name (English)"] += f" {lessor['Lessor Name (English)']}".strip()
                lessor_dict[lessor_id]["Lessor Name (Arabic)"] += ' '
                lessor_dict[lessor_id]["Lessor Name (Arabic)"] += f" {lessor['Lessor Name (Arabic)']}".strip()
            else:
                # Only assign the name if this is the first occurrence of the Lessor ID
                lessor_dict[lessor_id]["Lessor Name (English)"] = lessor["Lessor Name (English)"]
                lessor_dict[lessor_id]["Lessor Name (Arabic)"] = lessor["Lessor Name (Arabic)"]

            # Retain the share for the first lessor with that ID
            if lessor_dict[lessor_id]["Share (Sq Meter)"] == 0.0:
                lessor_dict[lessor_id]["Share (Sq Meter)"] = float(lessor["Share (Sq Meter)"])

        # Prepare the final list of merged lessors with the correct format
        merged_lessors = []
        for idx, (lessor_id, lessor_data) in enumerate(lessor_dict.items(), start=1):
            merged_lessors.append({
                "Lessor ID": f"{lessor_id}",  # Optional: keep the parentheses if needed
                "Lessor Name (English)": lessor_data["Lessor Name (English)"].strip(),
                "Lessor Name (Arabic)": lessor_data["Lessor Name (Arabic)"].strip(),
                "Share (Sq Meter)": f"{lessor_data['Share (Sq Meter)']:.2f}"
            })
        
        unified_data["Lessors"] = {f"Lessor {idx}": lessor for idx, lessor in enumerate(merged_lessors, start=1)}

    # 7) Unify Lessees (similar to Owners merging)
    if lessees:
        lessee_dict = defaultdict(lambda: {"Lessee Name (English)": "", "Lessee Name (Arabic)": "", "Share (Sq Meter)": 0.0})

        # Process the lessees to merge them based on Lessee ID
        for lessee in lessees:
            lessee_id = lessee["Lessor ID"].strip("()")  # Remove parentheses from Lessee ID (same as lessor)

            # Concatenate names with space if the same Lessee ID is found
            if lessee_dict[lessee_id]["Lessee Name (English)"]:
                lessee_dict[lessee_id]["Lessee Name (English)"] += ' '
                lessee_dict[lessee_id]["Lessee Name (English)"] += f" {lessee['Lessor Name (English)']}".strip()
                lessee_dict[lessee_id]["Lessee Name (Arabic)"] += ' '
                lessee_dict[lessee_id]["Lessee Name (Arabic)"] += f" {lessee['Lessor Name (Arabic)']}".strip()
            else:
                # Only assign the name if this is the first occurrence of the Lessee ID
                lessee_dict[lessee_id]["Lessee Name (English)"] = lessee["Lessor Name (English)"]
                lessee_dict[lessee_id]["Lessee Name (Arabic)"] = lessee["Lessor Name (Arabic)"]

            # Retain the share for the first lessee with that ID
            if lessee_dict[lessee_id]["Share (Sq Meter)"] == 0.0:
                lessee_dict[lessee_id]["Share (Sq Meter)"] = float(lessee["Share (Sq Meter)"])

        # Prepare the final list of merged lessees with the correct format
        merged_lessees = []
        for idx, (lessee_id, lessee_data) in enumerate(lessee_dict.items(), start=1):
            merged_lessees.append({
                "Lessee ID": f"{lessee_id}",  # Optional: keep the parentheses if needed
                "Lessee Name (English)": lessee_data["Lessee Name (English)"].strip(),
                "Lessee Name (Arabic)": lessee_data["Lessee Name (Arabic)"].strip(),
                "Share (Sq Meter)": f"{lessee_data['Share (Sq Meter)']:.2f}"
            })
        
        unified_data["Lessees"] = {f"Lessee {idx}": lessee for idx, lessee in enumerate(merged_lessees, start=1)}

    return unified_data


def unify_pre_title_deed(raw_data, clean_json_string):
    """
    Unify and clean the Pre Title Deed and Usufruct Right Certificate JSON:
    - Removes "Transaction Details"
    - Removes any fields with the value "Not mentioned"
    - Custom handling for Pre Title Deed and Usufruct Right Certificate with Property Type handling (Land, Villa, Flat)
    - Merges Buyers, Sellers, and Owners
    """
    
    # 1) Raw → text cleanup → parse JSON
    if isinstance(raw_data, str):
        txt = clean_json_string(raw_data)
        try:
            data = json.loads(txt)
        except json.JSONDecodeError:
            data = {}
    else:
        data = raw_data.copy()

    # 2) Remove "Transaction Details"
    if "Transaction Details" in data:
        del data["Transaction Details"]

    # 3) Clean 'Not mentioned' values
    def clean_not_mentioned(d):
        if isinstance(d, dict):
            return {k: clean_not_mentioned(v) for k, v in d.items() if v != "Not mentioned"}
        elif isinstance(d, list):
            return [clean_not_mentioned(i) for i in d if i != "Not mentioned"]
        else:
            return d
    
    data = clean_not_mentioned(data)

    # 4) Normalize and unify Pre Title Deed / Usufruct Right Certificate details
    title_deed = data.get("Pre Title Deed", data.get("Usufruct Right Certificate", {}))
    owners = data.get("Owners", [])
    buyers = data.get("Buyers", [])

    # 5) Check Property Type and include relevant fields
    property_type = title_deed.get("Property Type", "").lower()
    
    unified_data = {
        "Title Deed": {}
    }

    if property_type == "land":
        # Fields specific to Land property type
        unified_data["Title Deed"] = {
            "Issue Date": title_deed.get("Issue Date"),
            "Mortgage Status": title_deed.get("Mortgage Status"),
            "Property Type": title_deed.get("Property Type"),
            "Community": title_deed.get("Community"),
            "Plot No": title_deed.get("Plot No"),
            "Municipality No": title_deed.get("Municipality No"),
            "Area Sq Meter": title_deed.get("Area Sq Meter"),
            "Area Sq Feet": title_deed.get("Area Sq Feet"),
        }
    elif property_type == 'villa':
        # Fields specific to Villa property type
        unified_data["Title Deed"] = {
            "Issue Date": title_deed.get("Issue Date"),
            "Mortgage Status": title_deed.get("Mortgage Status"),
            "Property Type": title_deed.get("Property Type"),
            "Community": title_deed.get("Community"),
            "Plot No": title_deed.get("Plot No"),
            "Building No": title_deed.get("Building No"),
            "Municipality No": title_deed.get("Municipality No"),
            "Area Sq Meter": title_deed.get("Area Sq Meter"),
            "Area Sq Feet": title_deed.get("Area Sq Feet"),
        }
    elif property_type == "flat":
        # Fields specific to Flat property type
        unified_data["Title Deed"] = {
            "Issue Date": title_deed.get("Issue Date"),
            "Mortgage Status": title_deed.get("Mortgage Status"),
            "Property Type": title_deed.get("Property Type"),
            "Community": title_deed.get("Community"),
            "Plot No": title_deed.get("Plot No"),
            "Municipality No": title_deed.get("Municipality No"),
            "Building No": title_deed.get("Building No"),
            "Building Name": title_deed.get("Building Name"),
            "Property No": title_deed.get("Property No"),
            "Floor No": title_deed.get("Floor No"),
            "Parkings": title_deed.get("Parkings"),
            "Suite Area": title_deed.get("Suite Area"),
            "Balcony Area": title_deed.get("Balcony Area"),
            "Area Sq Meter": title_deed.get("Area Sq Meter"),
            "Area Sq Feet": title_deed.get("Area Sq Feet"),
            "Common Area": title_deed.get("Common Area")
        }
    else:
        # Default case: if Property Type is unknown or missing
        unified_data["Title Deed"] = title_deed  # Returning as is if the Property Type is neither "Land" nor "Flat"

    # 6) Unify Owners (similar to Title Deed merging)
    if owners:
        owner_dict = defaultdict(lambda: {"Owner Name (English)": "", "Owner Name (Arabic)": "", "Share (Sq Meter)": 0.0})

        # Process the owners to merge them based on Owner ID
        for owner in owners:
            owner_id = owner["Owner ID"].strip("()")  # Remove parentheses from Owner ID
            
            # Concatenate names with space if the same Owner ID is found
            if owner_dict[owner_id]["Owner Name (English)"]:
                owner_dict[owner_id]["Owner Name (English)"] += ' '
                owner_dict[owner_id]["Owner Name (English)"] += f" {owner['Owner Name (English)']}".strip()
                owner_dict[owner_id]["Owner Name (Arabic)"] += ' '
                owner_dict[owner_id]["Owner Name (Arabic)"] += f" {owner['Owner Name (Arabic)']}".strip()
            else:
                # Only assign the name if this is the first occurrence of the Owner ID
                owner_dict[owner_id]["Owner Name (English)"] = owner["Owner Name (English)"]
                owner_dict[owner_id]["Owner Name (Arabic)"] = owner["Owner Name (Arabic)"]

            # Retain the share for the first owner with that ID
            if owner_dict[owner_id]["Share (Sq Meter)"] == 0.0:
                owner_dict[owner_id]["Share (Sq Meter)"] = float(owner["Share (Sq Meter)"])

        # Prepare the final list of merged owners with the correct format
        merged_owners = []
        for idx, (owner_id, owner_data) in enumerate(owner_dict.items(), start=1):
            merged_owners.append({
                "Owner ID": f"{owner_id}",  # Optional: keep the parentheses if needed
                "Owner Name (English)": owner_data["Owner Name (English)"].strip(),
                "Owner Name (Arabic)": owner_data["Owner Name (Arabic)"].strip(),
                "Share (Sq Meter)": f"{owner_data['Share (Sq Meter)']:.2f}"
            })
        
        unified_data["Owners"] = {f"Owner {idx}": owner for idx, owner in enumerate(merged_owners, start=1)}

    # 7) Unify Buyers (similar to Owners merging)
    if buyers:
        buyer_dict = defaultdict(lambda: {"Buyer Name (English)": "", "Buyer Name (Arabic)": "", "Share (Sq Meter)": 0.0})

        # Process the buyers to merge them based on Buyer ID
        for buyer in buyers:
            buyer_id = buyer["Buyer ID"].strip("()")  # Remove parentheses from Buyer ID
            
            # Concatenate names with space if the same Buyer ID is found
            if buyer_dict[buyer_id]["Buyer Name (English)"]:
                buyer_dict[buyer_id]["Buyer Name (English)"] += ' '
                buyer_dict[buyer_id]["Buyer Name (English)"] += f" {buyer['Buyer Name (English)']}".strip()
                buyer_dict[buyer_id]["Buyer Name (Arabic)"] += ' '
                buyer_dict[buyer_id]["Buyer Name (Arabic)"] += f" {buyer['Buyer Name (Arabic)']}".strip()
            else:
                # Only assign the name if this is the first occurrence of the Buyer ID
                buyer_dict[buyer_id]["Buyer Name (English)"] = buyer["Buyer Name (English)"]
                buyer_dict[buyer_id]["Buyer Name (Arabic)"] = buyer["Buyer Name (Arabic)"]

            # Retain the share for the first buyer with that ID
            if buyer_dict[buyer_id]["Share (Sq Meter)"] == 0.0:
                buyer_dict[buyer_id]["Share (Sq Meter)"] = float(buyer["Share (Sq Meter)"])

        # Prepare the final list of merged buyers with the correct format
        merged_buyers = []
        for idx, (buyer_id, buyer_data) in enumerate(buyer_dict.items(), start=1):
            merged_buyers.append({
                "Buyer ID": f"{buyer_id}",  # Optional: keep the parentheses if needed
                "Buyer Name (English)": buyer_data["Buyer Name (English)"].strip(),
                "Buyer Name (Arabic)": buyer_data["Buyer Name (Arabic)"].strip(),
                "Share (Sq Meter)": f"{buyer_data['Share (Sq Meter)']:.2f}"
            })
        
        unified_data["Buyers"] = {f"Buyer {idx}": buyer for idx, buyer in enumerate(merged_buyers, start=1)}

    return unified_data

def unify_title_deed_lease_finance(raw_data, clean_json_string):
    """
    Unify and clean the Title Deed (Lease Finance) JSON:
    - Removes "Transaction Details"
    - Removes any fields with the value "Not mentioned"
    - Custom handling for Title Deed (Lease Finance) with Owners and Lessees
    - Handles Property Type (Land, Villa, Flat)
    """
    
    # 1) Raw → text cleanup → parse JSON
    if isinstance(raw_data, str):
        txt = clean_json_string(raw_data)
        try:
            data = json.loads(txt)
        except json.JSONDecodeError:
            data = {}
    else:
        data = raw_data.copy()

    # 2) Remove "Transaction Details"
    if "Transaction Details" in data:
        del data["Transaction Details"]

    # 3) Clean 'Not mentioned' values
    def clean_not_mentioned(d):
        if isinstance(d, dict):
            return {k: clean_not_mentioned(v) for k, v in d.items() if v != "Not mentioned"}
        elif isinstance(d, list):
            return [clean_not_mentioned(i) for i in d if i != "Not mentioned"]
        else:
            return d
    
    data = clean_not_mentioned(data)

    # 4) Normalize and unify Title Deed (Lease Finance) details
    title_deed = data.get("Title Deed (Lease Finance)",  {})
    owners = data.get("Owners", [])
    lessees = data.get("Lessees", [])

    # 5) Property Type is "Flat", "Villa", or "Land" — apply relevant fields
    property_type = title_deed.get("Property Type", "").lower()
    
    unified_data = {
        "Title Deed (Lease Finance)": {}
    }

    if property_type == "land":
        # Fields specific to Land property type
        unified_data["Title Deed (Lease Finance)"] = {
            "Issue Date": title_deed.get("Issue Date"),
            "Property Type": title_deed.get("Property Type"),
            "Community": title_deed.get("Community"),
            "Plot No": title_deed.get("Plot No"),
            "Municipality No": title_deed.get("Municipality No"),
            "Area Sq Meter": title_deed.get("Area Sq Meter"),
            "Area Sq Feet": title_deed.get("Area Sq Feet"),
        }
    elif property_type == 'villa':
        # Fields specific to Villa property type
        unified_data["Title Deed (Lease Finance)"] = {
            "Issue Date": title_deed.get("Issue Date"),
            "Property Type": title_deed.get("Property Type"),
            "Community": title_deed.get("Community"),
            "Plot No": title_deed.get("Plot No"),
            "Building No": title_deed.get("Building No"),
            "Municipality No": title_deed.get("Municipality No"),
            "Area Sq Meter": title_deed.get("Area Sq Meter"),
            "Area Sq Feet": title_deed.get("Area Sq Feet"),
        }
    elif property_type == "flat":
        # Fields specific to Flat property type
        unified_data["Title Deed (Lease Finance)"] = {
            "Issue Date": title_deed.get("Issue Date"),
            "Property Type": title_deed.get("Property Type"),
            "Community": title_deed.get("Community"),
            "Plot No": title_deed.get("Plot No"),
            "Municipality No": title_deed.get("Municipality No"),
            "Building No": title_deed.get("Building No"),
            "Building Name": title_deed.get("Building Name"),
            "Property No": title_deed.get("Property No"),
            "Floor No": title_deed.get("Floor No"),
            "Parkings": title_deed.get("Parkings"),
            "Suite Area": title_deed.get("Suite Area"),
            "Balcony Area": title_deed.get("Balcony Area"),
            "Area Sq Meter": title_deed.get("Area Sq Meter"),
            "Area Sq Feet": title_deed.get("Area Sq Feet"),
            "Common Area": title_deed.get("Common Area")
        }
    else:
        # Default case: if Property Type is unknown or missing, we can return an empty structure or handle it differently
        unified_data["Title Deed (Lease Finance)"] = title_deed  # Returning as is if the Property Type is neither "Land" nor "Flat"

    # 6) Unify Owners (similar to Title Deed merging)
    if owners:
        owner_dict = defaultdict(lambda: {"Owner Name (English)": "", "Owner Name (Arabic)": "", "Share (Sq Meter)": 0.0})

        # Process the owners to merge them based on Owner ID
        for owner in owners:
            owner_id = owner["Owner ID"].strip("()")  # Remove parentheses from Owner ID
            
            # Concatenate names with space if the same Owner ID is found
            if owner_dict[owner_id]["Owner Name (English)"]:
                owner_dict[owner_id]["Owner Name (English)"] += ' '
                owner_dict[owner_id]["Owner Name (English)"] += f" {owner['Owner Name (English)']}".strip()
                owner_dict[owner_id]["Owner Name (Arabic)"] += ' '
                owner_dict[owner_id]["Owner Name (Arabic)"] += f" {owner['Owner Name (Arabic)']}".strip()
            else:
                # Only assign the name if this is the first occurrence of the Owner ID
                owner_dict[owner_id]["Owner Name (English)"] = owner["Owner Name (English)"]
                owner_dict[owner_id]["Owner Name (Arabic)"] = owner["Owner Name (Arabic)"]

            # Retain the share for the first owner with that ID
            if owner_dict[owner_id]["Share (Sq Meter)"] == 0.0:
                owner_dict[owner_id]["Share (Sq Meter)"] = float(owner["Share (Sq Meter)"])

        # Prepare the final list of merged owners with the correct format
        merged_owners = []
        for idx, (owner_id, owner_data) in enumerate(owner_dict.items(), start=1):
            merged_owners.append({
                "Owner ID": f"{owner_id}",  # Optional: keep the parentheses if needed
                "Owner Name (English)": owner_data["Owner Name (English)"].strip(),
                "Owner Name (Arabic)": owner_data["Owner Name (Arabic)"].strip(),
                "Share (Sq Meter)": f"{owner_data['Share (Sq Meter)']:.2f}"
            })
        
        unified_data["Owners"] = {f"Owner {idx}": owner for idx, owner in enumerate(merged_owners, start=1)}

    # 7) Unify Lessees (similar to Owners merging)
    if lessees:
        lessee_dict = defaultdict(lambda: {"Lessee Name (English)": "", "Lessee Name (Arabic)": "", "Share (Sq Meter)": 0.0})

        # Process the lessees to merge them based on Lessee ID
        for lessee in lessees:
            lessee_id = lessee["Lessee ID"].strip("()")  # Remove parentheses from Lessee ID
            
            # Concatenate names with space if the same Lessee ID is found
            if lessee_dict[lessee_id]["Lessee Name (English)"]:
                lessee_dict[lessee_id]["Lessee Name (English)"] += ' '
                lessee_dict[lessee_id]["Lessee Name (English)"] += f" {lessee['Lessee Name (English)']}".strip()
                lessee_dict[lessee_id]["Lessee Name (Arabic)"] += ' '
                lessee_dict[lessee_id]["Lessee Name (Arabic)"] += f" {lessee['Lessee Name (Arabic)']}".strip()
            else:
                # Only assign the name if this is the first occurrence of the Lessee ID
                lessee_dict[lessee_id]["Lessee Name (English)"] = lessee["Lessee Name (English)"]
                lessee_dict[lessee_id]["Lessee Name (Arabic)"] = lessee["Lessee Name (Arabic)"]

            # Retain the share for the first lessee with that ID
            if lessee_dict[lessee_id]["Share (Sq Meter)"] == 0.0:
                lessee_dict[lessee_id]["Share (Sq Meter)"] = float(lessee["Share (Sq Meter)"])

        # Prepare the final list of merged lessees with the correct format
        merged_lessees = []
        for idx, (lessee_id, lessee_data) in enumerate(lessee_dict.items(), start=1):
            merged_lessees.append({
                "Lessee ID": f"{lessee_id}",  # Optional: keep the parentheses if needed
                "Lessee Name (English)": lessee_data["Lessee Name (English)"].strip(),
                "Lessee Name (Arabic)": lessee_data["Lessee Name (Arabic)"].strip(),
                "Share (Sq Meter)": f"{lessee_data['Share (Sq Meter)']:.2f}"
            })
        
        unified_data["Lessees"] = {f"Lessee {idx}": lessee for idx, lessee in enumerate(merged_lessees, start=1)}

    return unified_data


def unify_title_deed_lease_to_own(raw_data, clean_json_string):
    """
    Unify and clean the Title Deed (Lease To Own) JSON:
    - Removes "Transaction Details"
    - Removes any fields with the value "Not mentioned"
    - Custom handling for Title Deed (Lease To Own) with Owners and Lessees
    - Handles Property Type (Flat)
    """
    
    # 1) Raw → text cleanup → parse JSON
    if isinstance(raw_data, str):
        txt = clean_json_string(raw_data)
        try:
            data = json.loads(txt)
        except json.JSONDecodeError:
            data = {}
    else:
        data = raw_data.copy()

    # 2) Remove "Transaction Details"
    if "Transaction Details" in data:
        del data["Transaction Details"]

    # 3) Clean 'Not mentioned' values
    def clean_not_mentioned(d):
        if isinstance(d, dict):
            return {k: clean_not_mentioned(v) for k, v in d.items() if v != "Not mentioned"}
        elif isinstance(d, list):
            return [clean_not_mentioned(i) for i in d if i != "Not mentioned"]
        else:
            return d
    
    data = clean_not_mentioned(data)

    # 4) Normalize and unify Title Deed (Lease To Own) details
    title_deed = data.get("Title Deed (Lease To Own)", {})
    owners = data.get("Owners", [])
    lessees = data.get("Lessees", [])

    # 5) Property Type is "Flat", apply relevant fields for Flat
    property_type = title_deed.get("Property Type", "").lower()

    unified_data = {
        "Title Deed (Lease To Own)": {}
    }

    if property_type == "land":
        # Fields specific to Land property type
        unified_data["Title Deed (Lease To Own)"] = {
            "Issue Date": title_deed.get("Issue Date"),
            "Property Type": title_deed.get("Property Type"),
            "Community": title_deed.get("Community"),
            "Plot No": title_deed.get("Plot No"),
            "Municipality No": title_deed.get("Municipality No"),
            "Area Sq Meter": title_deed.get("Area Sq Meter"),
            "Area Sq Feet": title_deed.get("Area Sq Feet"),
        }
    elif property_type == 'villa':
        # Fields specific to Villa property type
        unified_data["Title Deed (Lease To Own)"] = {
            "Issue Date": title_deed.get("Issue Date"),
            "Property Type": title_deed.get("Property Type"),
            "Community": title_deed.get("Community"),
            "Plot No": title_deed.get("Plot No"),
            "Building No": title_deed.get("Building No"),
            "Municipality No": title_deed.get("Municipality No"),
            "Area Sq Meter": title_deed.get("Area Sq Meter"),
            "Area Sq Feet": title_deed.get("Area Sq Feet"),
        }
    elif property_type == "flat":
        # Fields specific to Flat property type
        unified_data["Title Deed (Lease To Own)"] = {
            "Issue Date": title_deed.get("Issue Date"),
            "Property Type": title_deed.get("Property Type"),
            "Community": title_deed.get("Community"),
            "Plot No": title_deed.get("Plot No"),
            "Municipality No": title_deed.get("Municipality No"),
            "Building No": title_deed.get("Building No"),
            "Building Name": title_deed.get("Building Name"),
            "Property No": title_deed.get("Property No"),
            "Floor No": title_deed.get("Floor No"),
            "Parkings": title_deed.get("Parkings"),
            "Suite Area": title_deed.get("Suite Area"),
            "Balcony Area": title_deed.get("Balcony Area"),
            "Area Sq Meter": title_deed.get("Area Sq Meter"),
            "Area Sq Feet": title_deed.get("Area Sq Feet"),
            "Common Area": title_deed.get("Common Area")
        }
    else:
        # Default case: if Property Type is unknown or missing
        unified_data["Title Deed (Lease To Own)"] = title_deed  # Returning as is if the Property Type is neither "Land" nor "Flat"

    # 6) Unify Owners (similar to Title Deed merging)
    if owners:
        owner_dict = defaultdict(lambda: {"Owner Name (English)": "", "Owner Name (Arabic)": "", "Share (Sq Meter)": 0.0})

        # Process the owners to merge them based on Owner ID
        for owner in owners:
            owner_id = owner["Owner ID"].strip("()")  # Remove parentheses from Owner ID
            
            # Concatenate names with space if the same Owner ID is found
            if owner_dict[owner_id]["Owner Name (English)"]:
                owner_dict[owner_id]["Owner Name (English)"] += ' '
                owner_dict[owner_id]["Owner Name (English)"] += f" {owner['Owner Name (English)']}".strip()
                owner_dict[owner_id]["Owner Name (Arabic)"] += ' '
                owner_dict[owner_id]["Owner Name (Arabic)"] += f" {owner['Owner Name (Arabic)']}".strip()
            else:
                # Only assign the name if this is the first occurrence of the Owner ID
                owner_dict[owner_id]["Owner Name (English)"] = owner["Owner Name (English)"]
                owner_dict[owner_id]["Owner Name (Arabic)"] = owner["Owner Name (Arabic)"]

            # Retain the share for the first owner with that ID
            if owner_dict[owner_id]["Share (Sq Meter)"] == 0.0:
                owner_dict[owner_id]["Share (Sq Meter)"] = float(owner["Share (Sq Meter)"])

        # Prepare the final list of merged owners with the correct format
        merged_owners = []
        for idx, (owner_id, owner_data) in enumerate(owner_dict.items(), start=1):
            merged_owners.append({
                "Owner ID": f"{owner_id}",  # Optional: keep the parentheses if needed
                "Owner Name (English)": owner_data["Owner Name (English)"].strip(),
                "Owner Name (Arabic)": owner_data["Owner Name (Arabic)"].strip(),
                "Share (Sq Meter)": f"{owner_data['Share (Sq Meter)']:.2f}"
            })
        
        unified_data["Owners"] = {f"Owner {idx}": owner for idx, owner in enumerate(merged_owners, start=1)}

    # 7) Unify Lessees (similar to Owners merging)
    if lessees:
        lessee_dict = defaultdict(lambda: {"Lessee Name (English)": "", "Lessee Name (Arabic)": "", "Share (Sq Meter)": 0.0})

        # Process the lessees to merge them based on Lessee ID
        for lessee in lessees:
            lessee_id = lessee["Lessee ID"].strip("()")  # Remove parentheses from Lessee ID
            
            # Concatenate names with space if the same Lessee ID is found
            if lessee_dict[lessee_id]["Lessee Name (English)"]:
                lessee_dict[lessee_id]["Lessee Name (English)"] += ' '
                lessee_dict[lessee_id]["Lessee Name (English)"] += f" {lessee['Lessee Name (English)']}".strip()
                lessee_dict[lessee_id]["Lessee Name (Arabic)"] += ' '
                lessee_dict[lessee_id]["Lessee Name (Arabic)"] += f" {lessee['Lessee Name (Arabic)']}".strip()
            else:
                # Only assign the name if this is the first occurrence of the Lessee ID
                lessee_dict[lessee_id]["Lessee Name (English)"] = lessee["Lessee Name (English)"]
                lessee_dict[lessee_id]["Lessee Name (Arabic)"] = lessee["Lessee Name (Arabic)"]

            # Retain the share for the first lessee with that ID
            if lessee_dict[lessee_id]["Share (Sq Meter)"] == 0.0:
                lessee_dict[lessee_id]["Share (Sq Meter)"] = float(lessee["Share (Sq Meter)"])

        # Prepare the final list of merged lessees with the correct format
        merged_lessees = []
        for idx, (lessee_id, lessee_data) in enumerate(lessee_dict.items(), start=1):
            merged_lessees.append({
                "Lessee ID": f"{lessee_id}",  # Optional: keep the parentheses if needed
                "Lessee Name (English)": lessee_data["Lessee Name (English)"].strip(),
                "Lessee Name (Arabic)": lessee_data["Lessee Name (Arabic)"].strip(),
                "Share (Sq Meter)": f"{lessee_data['Share (Sq Meter)']:.2f}"
            })
        
        unified_data["Lessees"] = {f"Lessee {idx}": lessee for idx, lessee in enumerate(merged_lessees, start=1)}

    return unified_data
def unify_cheques(raw_data, clean_json_string):
    """
    Unify and clean the Cheque JSON:
    - Remove 'AED' from 'Amount in AED'
    - Create an indexed structure for each cheque
    - Keep only relevant fields: Bank Name, Payer Name, Amount, Issue Date, Cheque Number, Validity Period
    - Normalize dates to dd/mm/yyyy format
    """
    # Helper function to clean and normalize dates
    def clean_date(date_str):
        """Normalize and format dates to DD/MM/YYYY where possible."""
        if not date_str or date_str.lower() in {"not mentioned", "n/a"}:
            return None

        # try common known formats
        for fmt in ("%d/%m/%Y", "%d-%b-%Y", "%d %B %Y", "%d/%b/%Y"):
            try:
                return datetime.strptime(date_str, fmt).strftime("%d/%m/%Y")
            except:
                pass

        # fallback: return original string if not matched
        return date_str

    # 1) Parse JSON if it's a string
    if isinstance(raw_data, str):
        txt = clean_json_string(raw_data)
        try:
            data = json.loads(txt)
        except json.JSONDecodeError:
            data = []
    else:
        data = raw_data.copy()

    # 2) Prepare the unified cheques structure
    unified_data = {}

    for idx, cheque in enumerate(data, start=1):
        unified_data[f"Cheque {idx}"] = {
            "Bank Name": cheque.get("Bank Name"),
            "Cheque Number": cheque.get("Cheque Number"),
            "Payer Name": cheque.get("Payer Name").replace('*', ''),
            "Amount": cheque.get("Amount in AED", "").replace(" AED", "").strip(),
            "Issue Date": clean_date(cheque.get("Issue Date", "")),
            "Validity Period": cheque.get("Validity Period")
        }

    return unified_data





def clean_poa_data(poa_data, clean_json_string):
    """
    Cleans and formats POA data based on specific rules:
    - Remove titles (Mr., Mrs., etc.) from names
    - Remove "National" from nationality
    - Remove dashes from Emirates IDs and move them to Emirates ID field if passport contains a 15-character ID
    - Only show virtue_attorneys if exists
    - Show principals as Principal 1, Principal 2, etc., and attorneys as Attorney 1, Attorney 2, etc.
    """
    def remove_titles(name: str) -> str:
        """Remove titles like Mr., Mrs., etc., from the name"""
        return re.sub(r'^(Mr\.|Mrs\.|Ms\.|Dr\.|Mrs)\s+', '', name)

    def clean_nationality(nationality: str) -> str:
        """Remove 'National' from nationality field."""
        return nationality.replace(" National", "").replace(' national','')

    def process_emirates_id_and_passport(emirates_id: str, passport_no: str) -> (str, str):
        """Check passport number length and move it to Emirates ID if necessary."""

        # Check if emirates_id is provided and perform the character replacements
        if emirates_id:
            # Replace specific characters
            emirates_id = emirates_id.replace("V", "7").replace("A", "8").replace("E", "4").replace(".", "0").replace('(','').replace(')','')
            emirates_id = emirates_id.replace("-", "")  # Remove any dashes, just in case

        # Clean passport number (remove dashes)
        passport_no = passport_no.replace("-", "") if passport_no else ""

        # If passport number is 15 characters long, use it as Emirates ID
        if len(passport_no) == 15:
            passport_no = passport_no.replace("V", "7").replace("A", "8").replace("E", "4").replace(".", "0").replace('(','').replace(')','')
            return passport_no, ""  # Use passport as Emirates ID, clear passport_no

        return emirates_id, passport_no 

    # 1) Parse JSON if it's a string (adapted from unify_cheques)
    if isinstance(poa_data, str):
        txt = clean_json_string(poa_data)
        try:
            poa_data = json.loads(txt)
        except json.JSONDecodeError:
            raise ValueError("Invalid POA data string. Cannot parse JSON.")
    elif not isinstance(poa_data, dict):
        raise ValueError("Expected POA data to be a dictionary or a valid JSON string.")

    # Process principals and assign numbered keys
    cleaned_principals = {}
    for idx, principal in enumerate(poa_data.get("principals", []), 1):
        principal["name"] = remove_titles(principal["name"])
        principal["nationality"] = clean_nationality(principal["nationality"])
        principal["emirates_id"], principal["passport_no"] = process_emirates_id_and_passport(principal["emirates_id"], principal["passport_no"])
        cleaned_principals[f"Principal {idx}"] = principal

    # Process attorneys and assign numbered keys
    cleaned_attorneys = {}
    for idx, attorney in enumerate(poa_data.get("attorneys", []), 1):
        attorney["name"] = remove_titles(attorney["name"])
        attorney["nationality"] = clean_nationality(attorney["nationality"])
        attorney["emirates_id"], attorney["passport_no"] = process_emirates_id_and_passport(attorney["emirates_id"], attorney["passport_no"])
        cleaned_attorneys[f"Attorney {idx}"] = attorney

    # Remove "virtue_attorneys" field if it is empty
    if not poa_data.get("virtue_attorneys"):
        del poa_data["virtue_attorneys"]

    # Replace 'principals' and 'attorneys' with the cleaned dictionaries
    poa_data["principals"] = cleaned_principals
    poa_data["attorneys"] = cleaned_attorneys

    return poa_data

def unify_noc(raw_data, clean_json_string):
    """
    Unify and clean the NOC (No Objection Certificate) data:
    - Change "Dubai Land Department" to "Addressed to DLD".
    - If "Found", change to "Yes", otherwise to "No".
    - Remove brackets and quotes when displaying values.
    """
    # 1) Parse JSON if it's a string
    if isinstance(raw_data, str):
        txt = clean_json_string(raw_data)
        try:
            data = json.loads(txt)
        except json.JSONDecodeError:
            data = {}
    else:
        data = raw_data.copy()

    # 2) Update "Dubai Land Department" to "Addressed to DLD"
    if "Dubai Land Department" in data:
        data["Addressed to DLD"] = data["Dubai Land Department"]
        del  data["Dubai Land Department"]
    
    # 3) Change "Found" to "Yes" or "No" for certain fields
    for key in ["Addressed to DLD", "Arabic Found"]:
        if data.get(key) == "Found":
            data[key] = "Yes"
        elif data.get(key) != "Yes":  # If not already "Yes", change to "No"
            data[key] = "No"

    # 4) Remove brackets and quotes from values for display
    data = {key: str(value).strip("[]").replace('"', '').replace("'", '') for key, value in data.items()}

    return data
