import json
from datetime import datetime, timedelta
import difflib
import streamlit as st
from PIL import Image, ImageOps
import io
import fitz
from io import BytesIO
from scripts.vlm_utils import create_pdf_from_pages
import re
from dateutil.relativedelta import relativedelta


def validate_id_data(id_extracted_data):
    """
    Validates expiry_date in an ID extracted data (dd/mm/yyyy).
    Returns (is_valid, name_english, message).
    """
    try:
        if isinstance(id_extracted_data, str):
            id_extracted_data = safe_json_loads(id_extracted_data)
        front = id_extracted_data.get("front", {})
        expiry = front.get("expiry_date", "").strip()
        name = front.get("name_english", "").strip()
        if not expiry or expiry.lower() in ["not mentioned", ""]:
            return False, name, "Expiry date not provided."
        exp_dt = datetime.strptime(expiry, "%d/%m/%Y")
        if exp_dt < datetime.today():
            return False, name, f"ID expired on {expiry}."
        return True, name, f"ID is valid until {expiry}."
    except Exception as e:
        return False, "", f"Error validating ID: {e}"


def safe_json_loads(text):
    if not isinstance(text, str):
        return text
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[len("```json"):].strip()
    if cleaned.startswith("```"):
        cleaned = cleaned[3:].strip()
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3].strip()
    try:
        return json.loads(cleaned)
    except:
        return {}


def save_document(result):
    classification = result["doc_type"].lower().replace(" ", "_")
    original = result["filename"]
    image_bytes = result.get("image_bytes")
    if "doc_counts" not in st.session_state:
        st.session_state.doc_counts = {}

    # IDs
    if classification == "ids":
        try:
            id_data = safe_json_loads(result["extracted_data"])
            name = id_data.get("front", {}).get("name_english", "").strip()
            if not name and "Page_1" in id_data:
                for k, v in id_data["Page_1"].items():
                    if "name" in k.lower() and isinstance(v, str) and v.strip():
                        name = v.strip(); break
            if not name:
                raise Exception("Missing name_english in ID extracted data")
            role = "id"
            contract_doc = next((d for d in st.session_state.results if d["doc_type"].lower()=="contract f"), None)
            if contract_doc:
                cd = safe_json_loads(contract_doc["extracted_data"])
                seller = cd.get("Page_1", {}).get("Owner Details", {}).get("Seller Name", "").strip().lower()
                buyer = cd.get("Page_1", {}).get("Buyers Share Details", {}).get("Buyer Name", "").strip().lower()
                if seller and seller in name.lower(): role = "seller"
                elif buyer and buyer in name.lower(): role = "buyer"
            safe_name = "_".join(name.split())
            new_filename = f"{role}_{safe_name}.pdf"
        except Exception as e:
            count = st.session_state.doc_counts.get(classification, 0) + 1
            st.session_state.doc_counts[classification] = count
            new_filename = f"{classification}_{count}.pdf"

    # Passport
    elif classification == "passport":
        try:
            pdata = safe_json_loads(result["extracted_data"])
            given = pdata.get("Given Name", "").strip()
            surname = pdata.get("Surname", "").strip()
            if (not given or not surname) and "Page_1" in pdata:
                p1 = pdata["Page_1"]
                given = p1.get("Given Name", given).strip()
                surname = p1.get("Surname", surname).strip()
            if not (given and surname): raise Exception("Missing Given Name or Surname in passport")
            new_filename = f"passport_{'_'.join(given.split()).lower()}_{'_'.join(surname.split()).lower()}.pdf"
        except:
            count = st.session_state.doc_counts.get(classification, 0) + 1
            st.session_state.doc_counts[classification] = count
            new_filename = f"{classification}_{count}.pdf"

    # Residence Visa
    elif classification == "residence_visa":
        try:
            vdata = safe_json_loads(result["extracted_data"])
            full = vdata.get("full_name", "").strip()
            if not full and "Page_1" in vdata:
                full = vdata["Page_1"].get("full_name", "").strip()
            if not full: raise Exception("Missing full_name in residence visa data")
            new_filename = f"residence_visa_{'_'.join(full.split()).lower()}.pdf"
        except:
            count = st.session_state.doc_counts.get(classification, 0) + 1
            st.session_state.doc_counts[classification] = count
            new_filename = f"{classification}_{count}.pdf"

    # Cheque
    elif classification in ["cheques", "cheque"]:
        try:
            cdata = safe_json_loads(result["extracted_data"])
            payer = cdata[0].get("Payer Name", "").strip().lower() if isinstance(cdata, list) and cdata else ""
            if "dubai land department" in payer:
                new_filename = "DLD_cheque.pdf"
            else:
                contract_doc = next((d for d in st.session_state.results if d["doc_type"].lower()=="contract f"), None)
                if contract_doc:
                    cd = safe_json_loads(contract_doc["extracted_data"])
                    seller = cd.get("Page_1", {}).get("Owner Details", {}).get("Seller Name", "").strip().lower()
                    if any(tok in payer for tok in seller.split()): new_filename = "manager_cheque.pdf"
                    else: new_filename = "cheque.pdf"
                else:
                    new_filename = "cheque.pdf"
        except:
            new_filename = "cheque.pdf"

    else:
        count = st.session_state.doc_counts.get(classification, 0) + 1
        st.session_state.doc_counts[classification] = count
        new_filename = f"{classification}_{count}.pdf"

    # Save file
    try:
        if original.lower().endswith("pdf"):
            pdf_bytes = (create_pdf_from_pages(result["original_pdf_bytes"], result.get("pages"))
                         if result.get("pages") else result.get("original_pdf_bytes", image_bytes))
            with open(new_filename, "wb") as f: f.write(pdf_bytes)
            st.write(f"Saved PDF as {new_filename}")
        else:
            img = Image.open(io.BytesIO(image_bytes))
            img = ImageOps.exif_transpose(img)
            if img.mode != "RGB": img = img.convert("RGB")
            buf = io.BytesIO(); img.save(buf, format="PDF")
            with open(new_filename, "wb") as f: f.write(buf.getvalue())
            st.write(f"Converted and saved image as {new_filename}")
    except Exception as e:
        st.error(f"Error saving document {original}: {e}")


def normalize_keys(d):
    if not isinstance(d, dict): return d
    return {k.lower().replace(" ", "_").strip(): normalize_keys(v) if isinstance(v, dict) else v
            for k, v in d.items()}


def validate_documents(results):
    validation_results = {}

    # NOC Validation
    noc = [d for d in results if d["doc_type"].lower()=="noc non objection certificate"]
    if noc:
        try:
            nd = normalize_keys(safe_json_loads(noc[0]["extracted_data"]))
            field = (nd.get("validation_date_or_period") or "").strip()
            if not field or field.lower() in ["not provided", "not mentioned"]:
                validation_results["NOC"] = "Validation Date or Period not provided."
            else:
                try:
                    vd = datetime.strptime(field, "%d/%m/%Y")
                    validation_results["NOC"] = (
                        f"Validation date {field} has expired." if vd < datetime.today()
                        else f"Validation date {field} is valid."
                    )
                except:
                    m = re.match(r"(\d+)\s*(days?|months?)", field, re.IGNORECASE)
                    if m:
                        num, unit = int(m.group(1)), m.group(2).lower()
                        issue = nd.get("issuing_date", "").strip()
                        if issue:
                            try:
                                idt = datetime.strptime(issue, "%d/%m/%Y")
                                exp = idt + (timedelta(days=num) if "day" in unit else relativedelta(months=num))
                                validation_results["NOC"] = (
                                    f"Validation period expired (expiry date: {exp.strftime('%d/%m/%Y')})." if exp < datetime.today()
                                    else f"Validation period is valid until {exp.strftime('%d/%m/%Y')}"
                                )
                            except Exception as e:
                                validation_results["NOC"] = f"Error parsing issuing date: {e}"
                        else:
                            validation_results["NOC"] = "Issuing date not provided for NOC."
                    else:
                        validation_results["NOC"] = "Validation Date or Period is in an unrecognized format."
        except Exception as e:
            validation_results["NOC"] = f"Error processing NOC data: {e}"
    else:
        validation_results["NOC"] = "No NOC document found."

    # ID Validation
    id_docs = [d for d in results if d["doc_type"].lower()=="ids"]
    id_msgs = set(); valid_id_names = set(); expired_id_names = set()
    for doc in id_docs:
        v, name, msg = validate_id_data(doc.get("extracted_data", {}))
        key = name.lower().strip() or "unknown"
        id_msgs.add(f"ID '{key}': {msg}")
        (valid_id_names if v else expired_id_names).add(key)
    validation_results["IDs"] = "\n".join(sorted(id_msgs)) if id_msgs else "No ID documents found."

    # Passport Validation
    passport_docs = [d for d in results if d["doc_type"].lower()=="passport"]
    pass_msgs = []
    for doc in passport_docs:
        try:
            pd = safe_json_loads(doc["extracted_data"])
            full = pd.get("fullname","").strip() or pd.get("Full Name","").strip()
            exp = pd.get("Date of Expiry","").strip() or pd.get("expiry_date","").strip()
            if not exp:
                pass_msgs.append(f"Passport '{full}' expiry date not provided.")
            else:
                try:
                    ed = datetime.strptime(exp, "%d/%m/%Y")
                    if ed < datetime.today():
                        pass_msgs.append(f"Passport '{full}' expired on {exp}.")
                    else:
                        pass_msgs.append(f"Passport '{full}' is valid until {exp}.")
                except:
                    pass_msgs.append(f"Passport '{full}' expiry date format unrecognized: {exp}.")
        except Exception as e:
            pass_msgs.append(f"Error validating passport: {e}")
    validation_results["Passports"] = "\n".join(pass_msgs) if pass_msgs else "No passport documents found."

    # Contract F Validation (with end-date & inverted-name)
    contract_docs = [d for d in results if d["doc_type"].lower()=="contract f"]
    contract_docs = [d for d in results if d["doc_type"].lower() == "contract f"]
    passport_docs = [d for d in results if d["doc_type"].lower() == "passport"]
    passport_info = []  # (fullname_lower, is_valid, message)
    for doc in passport_docs:
        try:
            pd = safe_json_loads(doc["extracted_data"])
            full = pd.get("fullname", "").strip()
            exp = pd.get("Date of Expiry", "").strip()
            valid = False
            msg = "No expiry date in passport."
            if exp:
                dt = datetime.strptime(exp, "%d/%m/%Y")
                valid = dt >= datetime.today()
                msg = f"Passport {'valid' if valid else 'expired'} on {exp}."
            passport_info.append((full.lower(), valid, msg))
        except Exception as e:
            passport_info.append(("", False, f"Error processing passport: {e}"))

    if contract_docs:
        try:
            cd = safe_json_loads(contract_docs[0]["extracted_data"])
            p1 = cd.get("Page_1", {})
            ci = p1.get("Contract Information", {})

            # End-date check
            end_str = ci.get("End Date", "").strip()
            if end_str:
                try:
                    ed = datetime.strptime(end_str, "%d/%m/%Y")
                    end_msg = (
                        f"Contract end date {end_str} has passed." if ed < datetime.today()
                        else f"Contract end date is valid until {end_str}."
                    )
                except:
                    end_msg = f"Unrecognized end date format: {end_str}."
            else:
                end_msg = "End Date not provided in Contract F."

            # Extract seller & buyer names
            seller_names = set()
            od = p1.get("Owner Details", {})
            if isinstance(od, dict):
                if od.get("Seller Name", "").strip():
                    seller_names.add(od.get("Seller Name").strip().lower())
                for k, v in od.items():
                    if isinstance(v, dict):
                        nm = v.get("Seller Name", "").strip()
                        if nm: seller_names.add(nm.lower())
                    elif isinstance(v, str) and "seller name" in k.lower() and v.strip():
                        seller_names.add(v.strip().lower())

            buyer_names = set()
            bd = p1.get("Buyers Share Details", {})
            if isinstance(bd, dict):
                if bd.get("Buyer Name", "").strip():
                    buyer_names.add(bd.get("Buyer Name").strip().lower())
                for k, v in bd.items():
                    if isinstance(v, str) and "buyer name" in k.lower() and v.strip():
                        buyer_names.add(v.strip().lower())

            # Helper for matching with inversion
            def matches(name, candidates, thresh=0.7):
                for c in candidates:
                    if difflib.SequenceMatcher(None, name, c).ratio() >= thresh:
                        return True
                parts = name.split()
                if len(parts) == 2:
                    inv = f"{parts[1]} {parts[0]}"
                    for c in candidates:
                        if difflib.SequenceMatcher(None, inv, c).ratio() >= thresh:
                            return True
                return False

            msgs = []
            for s in seller_names:
                if matches(s, valid_id_names):
                    msgs.append(f"Seller ID for '{s}' is valid.")
                elif matches(s, expired_id_names):
                    msgs.append(f"Seller ID for '{s}' is found but expired.")
                else:
                    pm = next((p for p in passport_info if matches(s, [p[0]])), None)
                    if pm:
                        status = 'valid' if pm[1] else 'expired'
                        msgs.append(f"Seller passport for '{s}' is {status} ({pm[2]}).")
                    else:
                        msgs.append(f"Seller ID/passport for '{s}' not found.")
            for b in buyer_names:
                if matches(b, valid_id_names):
                    msgs.append(f"Buyer ID for '{b}' is valid.")
                elif matches(b, expired_id_names):
                    msgs.append(f"Buyer ID for '{b}' is found but expired.")
                else:
                    pm = next((p for p in passport_info if matches(b, [p[0]])), None)
                    if pm:
                        status = 'valid' if pm[1] else 'expired'
                        msgs.append(f"Buyer passport for '{b}' is {status} ({pm[2]}).")
                    else:
                        msgs.append(f"Buyer ID/passport for '{b}' not found.")

            validation_results["Contract F"] = " ".join(msgs + [end_msg])
        except Exception as e:
            validation_results["Contract F"] = f"Error processing Contract F data: {e}"
    else:
        validation_results["Contract F"] = "No Contract F document found."

    # POA validation (unchanged)
    # Enhanced POA validation: report specific attorney and principal names
    poa_docs = [d for d in results if d["doc_type"].lower() == "poa"]
    if poa_docs:
        try:
            poa_data = safe_json_loads(poa_docs[0]["extracted_data"])
            if not poa_data:
                validation_results["POA"] = "No valid POA extracted data."
            else:
                # Extract attorneys and principals
                attorneys = poa_data.get("attorneys", [])
                principals = poa_data.get("principals", []) or poa_data.get("principal", [])

                # Build set of valid Emirates IDs from ID documents
                valid_eids = set()
                for doc in results:
                    if doc["doc_type"].lower() == "ids":
                        id_data = safe_json_loads(doc.get("extracted_data", {}))
                        eid = id_data.get("front", {}).get("emirates_id", "").replace("-", "").strip()
                        if eid:
                            valid_eids.add(eid)

                # Find matches
                matched_attorneys = [a for a in attorneys if a.get("emirates_id", "").replace("-", "").strip() in valid_eids]
                matched_principals = [p for p in principals if p.get("emirates_id", "").replace("-", "").strip() in valid_eids]

                if matched_attorneys or matched_principals:
                    # Get human-readable names
                    att_names = [a.get("name", a.get("full_name", "Unknown")) for a in matched_attorneys]
                    p_names   = [p.get("name", p.get("full_name", "Unknown")) for p in matched_principals]

                    parts = []
                    if att_names:
                        parts.append("Attorney(s): " + ", ".join(att_names))
                    if p_names:
                        parts.append("Principal(s): " + ", ".join(p_names))
                    validation_results["POA"] = "; ".join(parts)
                else:
                    validation_results["POA"] = "No matching Emirates IDs found for attorneys or principals."
        except Exception as e:
            validation_results["POA"] = f"Error processing POA data: {e}"
    else:
        validation_results["POA"] = "No POA document found."

    # Mortgage contract
    mortgage_msgs = []
    for doc in results:
        if doc["doc_type"].lower() == "mortgage contract" and doc["filename"].lower().endswith("pdf"):
            try:
                pdf_bytes = doc.get("original_pdf_bytes")
                pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                pages = pdf_doc.page_count
                mortgage_msgs.append(
                    f"Mortgage contract {'valid: 3 copies exist' if pages % 3 == 0 else f'invalid: {pages % 3} copies exist'}."
                )
                pdf_doc.close()
            except Exception as e:
                mortgage_msgs.append(f"Error checking mortgage contract pages: {e}")
    if mortgage_msgs:
        validation_results["Mortgage Contract"] = " ".join(mortgage_msgs)

    # Valuation report check
    has_reg = any(d["doc_type"].lower() in ["registration of mortgages", "mortgage letter"] for d in results)
    has_contract = any(d["doc_type"].lower() == "mortgage contract" for d in results)
    has_val = any(d["doc_type"].lower() == "valuation report" for d in results)
    if (has_reg or has_contract) and has_contract:
        validation_results["Valuation Report"] = (
            "Valuation report is provided." if has_val
            else "Valuation report is missing but registration/mortgage contract present."
        )

    return validation_results
