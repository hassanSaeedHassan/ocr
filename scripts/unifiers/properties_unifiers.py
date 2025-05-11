import json
import re
from collections import defaultdict
from datetime import datetime
import streamlit as st
from typing import Any, Union
from scripts.utils.json_utils import post_processing


def unify_contract_f(raw: Union[str, dict]) -> dict:
    """
    Normalize and unify multi-page 'contract f' extractions into a single dict,
    pulling exactly these sections (in this order) if and when they appear:

      1. Contract Information
      2. Mortgage Details (optional)
      3. Owner Details
      4. Buyers Share Details
      5. Property Details
      6. Property Financial Information
      7. Seller Broker Details
      8. Buyer Broker Details
      9. DLD Registration Fees
     10. Payment Details
    """
    pages = post_processing(raw) if isinstance(raw, str) else (raw or {})
    if not isinstance(pages, dict):
        return {}

    # unwrap raw_text fields
    for name, content in list(pages.items()):
        if isinstance(content, dict) and "raw_text" in content:
            pages[name] = post_processing(content["raw_text"])

    # helper to sort pages
    def page_key(k: str) -> int:
        m = re.search(r"_(\d+)$", k)
        return int(m.group(1)) if m else 0

    ordered = [pages[k] for k in sorted(pages, key=page_key) if isinstance(pages[k], dict)]

    # initialize placeholders
    contract_info = {}
    mortgage_info = {}
    raw_owners = []
    raw_buyers = []
    prop = {}
    prop_fin = {}
    sb = {}
    bb = {}
    dld_fees = {}
    payment = {}

    # field keys
    dld_fields = [
        "Percentage of DLD Registration Fees",
        "Covered Percentage of DLD Registration Fees by Buyer",
        "Covered Amount of DLD Registration Fees by Buyer",
        "Covered Percentage of DLD Registration Fees by Seller",
        "Covered Amount of DLD Registration Fees by Seller",
    ]
    pay_fields = ["Payment Type", "Amount", "Cheque Number", "Cheque Date", "Bank Name"]

    def norm_key(k: str) -> str:
        return k.replace(" ", "").replace("_", "").lower()

    # process each page
    for pg in ordered:
        norm_pg = {norm_key(k): v for k, v in pg.items()}

        # 1) Contract Information
        if not contract_info and "contractinformation" in norm_pg:
            contract_info = norm_pg["contractinformation"]

        # 2) Mortgage Details
        if not mortgage_info and "mortgagedetails" in norm_pg:
            mortgage_info = norm_pg["mortgagedetails"]

        # 3) Owner Details
        if "ownerdetails" in norm_pg:
            od = pg.get("Owner Details") or pg.get("ownerdetails")
            if isinstance(od, dict) and any(re.match(r"Owner\s*#", k) for k in od):
                for v in od.values():
                    raw_owners.append(v)
            elif isinstance(od, list):
                raw_owners.extend(od)
            else:
                raw_owners.append(od)

        # 4) Buyers Share Details
        if raw_owners and "buyerssharedetails" in norm_pg:
            bd = pg.get("Buyers Share Details") or pg.get("buyerssharedetails")
            if isinstance(bd, dict) and any(re.match(r"Buyer\s*#", k) for k in bd):
                for v in bd.values():
                    raw_buyers.append(v)
            elif isinstance(bd, list):
                raw_buyers.extend(bd)
            else:
                raw_buyers.append(bd)

        # 5) Property Details
        if raw_buyers and not prop and "propertydetails" in norm_pg:
            prop = pg.get("Property Details") or pg.get("propertydetails", {})

        # 6) Property Financial Information
        if prop and not prop_fin and "propertyfinancialinformation" in norm_pg:
            prop_fin = pg.get("Property Financial Information") or pg.get("propertyfinancialinformation", {})

        # 7) Seller Broker Details
        if prop_fin and not sb and "sellerbrokerdetails" in norm_pg:
            sb = norm_pg["sellerbrokerdetails"]

        # 8) Buyer Broker Details
        if sb and not bb and "buyerbrokerdetails" in norm_pg:
            bb = norm_pg["buyerbrokerdetails"]

        # 9) DLD Registration Fees
        if prop_fin and not dld_fees and "dldregistrationfees" in norm_pg:
            raw_d = pg.get("DLD Registration Fees") or pg.get("dldregistrationfees", {})
            dld_fees = {k: raw_d.get(k, "") for k in dld_fields}

        # 10) Payment Details
        if dld_fees and not payment:
            cand = pg.get("Payment Details") or pg.get("paymentdetails", {})
            if isinstance(cand, dict) and all(f in cand for f in pay_fields):
                f = {fld: cand.get(fld, "").strip() for fld in pay_fields}

                # skip Manager Cheque
                if f["Payment Type"].lower() == "manager cheque":
                    continue

                # only cheque or cash
                pt = f["Payment Type"].lower()
                if "cheque" in pt:
                    f["Payment Type"] = "cheque"
                elif "cash" in pt:
                    f["Payment Type"] = "cash"
                else:
                    continue

                # Cheque Number or WIRE TRANSFER
                cn = f["Cheque Number"]
                f["Cheque Number"] = cn if re.fullmatch(r"\d+", cn) else "WIRE TRANSFER"

                # Cheque Date
                cd = f["Cheque Date"]
                if re.fullmatch(r"\d{2}/\d{2}/\d{2}(?:\d{2})?", cd):
                    f["Cheque Date"] = cd
                else:
                    f["Cheque Date"] = ""

                payment = f

    # fallback mortgage flag
    if not mortgage_info and isinstance(contract_info, dict):
        flag = contract_info.get("Will this property be mortgaged?")
        if isinstance(flag, str):
            mortgage_info = {"Will this property be mortgaged?": flag}

    # --- swap Unit/Area if needed ---
    if prop.get("Type of Property") is None:
        prop["Type of Property"] = ""
    unit = prop.get("Unit", "").strip()
    area = prop.get("Area Size (SqMt)", "").strip()
    tp = prop.get("Type of Property", "").strip()
    if tp == "Area Size (SqMt)" and unit:
        prop["Area Size (SqMt)"] = prop.pop("Unit")
        prop["Type of Property"] = "Unit"
    elif tp == "" and unit and not area:
        prop["Area Size (SqMt)"] = prop.pop("Unit")
        prop["Type of Property"] = "Unit"
    elif tp == "":
        prop["Type of Property"] = "Unit"
    tp = prop.get("Type of Property", "")
    if tp == "Area Size (SqMt)":
        prop["Type of Property"] = "Unit"

    # --- filter property details fields ---
    allowed = [
        "Location","Type of Property","Type of Area","Area Size (SqMt)",
        "Usage","Property Number","Number of Units","Plot Number","Building Name"
    ]
    prop = {k: v for k, v in prop.items() if k in allowed and (v != "" or k == "Area Size (SqMt)")}

    # re-key owners & buyers
    owner = {f"Owner # {i+1}": o for i, o in enumerate(raw_owners)}
    buyer_shares = {f"Buyer # {i+1}": b for i, b in enumerate(raw_buyers)}

    # --- assemble output in precise order ---
    out: dict[str, Any] = {
        "Contract Information": contract_info,
        **({"Mortgage Details": mortgage_info} if mortgage_info else {}),
        **({"Owner Details": owner} if owner else {}),
        **({"Buyers Share Details": buyer_shares} if buyer_shares else {}),
        "Property Details": prop
    }
    if prop_fin:
        out["Property Financial Information"] = prop_fin
    if sb:
        out["Seller Broker Details"] = sb
    if bb:
        out["Buyer Broker Details"] = bb
    if dld_fees:
        out["DLD Registration Fees"] = dld_fees
    if payment:
        out["Payment Details"] = payment

    # --- auto-fill missing DLD amount ---
    cafb = out.get("DLD Registration Fees", {}).get(
        "Covered Amount of DLD Registration Fees by Buyer", ""
    )
    if cafb == "":
        try:
            sp = out["Property Financial Information"]["Sell Price"]
            amt = float(sp.replace("AED","").replace(",","")) * 0.04
            out["DLD Registration Fees"][
                "Covered Amount of DLD Registration Fees by Buyer"
            ] = f"{amt:.2f} AED"
        except:
            pass
    return out




def unify_noc(raw_data: dict) -> dict:
    """
    Unify and clean the NOC (No Objection Certificate) data:
      - Strip titles (Mr./Mrs./Ms./Dr.) from sellers & buyers
      - Collapse sellers/buyers into comma-separated strings
      - Rename "Dubai Land Department" → "Addressed to DLD"
      - Map "Found" → "Yes"/"No" for Addressed to DLD & Arabic Found
      - Flatten all other values to simple strings
    """
    data = raw_data.copy()

    # helper to strip honorifics
    def strip_title(name: str) -> str:
        return re.sub(r'^(Mr\.|Mrs\.|Ms\.|Dr\.)\s*', '', name).strip()

    # 1) Sellers → comma‑joined string
    raw_sellers = data.get("sellers", [])
    if not isinstance(raw_sellers, list):
        # perhaps a single string or bracketed form
        raw_sellers = re.split(r",\s*", str(raw_sellers).strip("[]"))
    cleaned_sellers = [ strip_title(str(n)) for n in raw_sellers if str(n).strip() ]
    data["sellers"] = ", ".join(cleaned_sellers)

    # 2) Buyers → comma‑joined string
    raw_buyers = data.get("buyers", [])
    if not isinstance(raw_buyers, list):
        raw_buyers = re.split(r",\s*", str(raw_buyers).strip("[]"))
    cleaned_buyers = [ strip_title(str(n)) for n in raw_buyers if str(n).strip() ]
    data["buyers"] = ", ".join(cleaned_buyers)

    # 3) Rename & map DLD fields
    if "Dubai Land Department" in data:
        data["Addressed to DLD"] = data.pop("Dubai Land Department")
    for fld in ("Addressed to DLD", "Arabic Found"):
        if fld in data:
            data[fld] = "Yes" if data[fld] == "Found" else "No"

    # 4) Flatten all other fields to strings (strip [] " ' )
    for k, v in list(data.items()):
        if k in ("sellers", "buyers", "Addressed to DLD", "Arabic Found"):
            continue
        data[k] = str(v).strip("[]").replace('"', "").replace("'", "").strip()

    return data
