import json
from datetime import datetime
import difflib
import streamlit as st
from PIL import Image, ImageOps
import io
import fitz
from io import BytesIO
from scripts.vlm_utils import create_pdf_from_pages
import re
from datetime import timedelta
from dateutil.relativedelta import relativedelta



def validate_id_data(id_extracted_data):
    """
    Validates the expiry_date in an ID extracted data.
    Expects the expiry date to be in dd/mm/yyyy format.
    
    Returns a tuple (is_valid, name_english, message) where:
      - is_valid is True if the expiry date is in the future.
      - name_english is the extracted English name (or an empty string if not found).
      - message describes the result.
    """
    try:
        # Convert to dict if it's a string
        if isinstance(id_extracted_data, str):
            id_extracted_data = safe_json_loads(id_extracted_data)
        front_data = id_extracted_data.get("front", {})
        expiry_str = front_data.get("expiry_date", "").strip()
        name_english = front_data.get("name_english", "").strip()
        if not expiry_str or expiry_str.lower() in ["not mentioned", ""]:
            return (False, name_english, "Expiry date not provided.")
        expiry_date = datetime.strptime(expiry_str, "%d/%m/%Y")
        today = datetime.today()
        if expiry_date < today:
            return (False, name_english, f"ID expired on {expiry_str}.")
        else:
            return (True, name_english, f"ID is valid until {expiry_str}.")
    except Exception as e:
        return (False, "", f"Error validating ID: {str(e)}")



    





def safe_json_loads(text):
    # If the input is already a dict, return it as is.
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
    except Exception:
        return {}










def save_document(result):
    """
    Saves the processed document as a PDF with a new naming convention:
    
    - For IDs: Names the file based on the extracted English name from the ID.
    - For Passport: Extracts "Given Name" and "Surname" and names the file accordingly.
    - For Residence Visa: Extracts "full_name" and names the file accordingly.
    - For other document types, uses a generic naming based on the document type and a counter.
    
    The file is then saved as a PDF (either by writing the original PDF bytes or by converting an image to PDF).
    """
    classification = result["doc_type"].lower().replace(" ", "_")
    original_filename = result["filename"]
    image_bytes = result.get("image_bytes")
    
    if "doc_counts" not in st.session_state:
        st.session_state.doc_counts = {}
    
    # ---------- For IDs ----------
    if classification == "ids":
        try:
            id_data = safe_json_loads(result["extracted_data"])
            name = ""
            # Try the expected structure first
            if "front" in id_data:
                name = id_data["front"].get("name_english", "").strip()
            # If not found, try to search in Page_1 (for multipage extractions)
            if not name and "Page_1" in id_data:
                page1_data = id_data["Page_1"]
                for key, value in page1_data.items():
                    if "name" in key.lower() and isinstance(value, str) and value.strip():
                        name = value.strip()
                        break
            if not name:
                raise Exception("Missing name_english in ID extracted data")
            role = None
            # Attempt to get Contract F details to decide role.
            contract_doc = next((doc for doc in st.session_state.results if doc["doc_type"].lower() == "contract f"), None)
            if contract_doc:
                contract_data = safe_json_loads(contract_doc["extracted_data"])
                seller_name = contract_data.get("Page_1", {}).get("Owner Details", {}).get("Seller Name", "").strip()
                buyer_name = contract_data.get("Page_1", {}).get("Buyers Share Details", {}).get("Buyer Name", "").strip()
                if seller_name and seller_name.lower() in name.lower():
                    role = "seller"
                elif buyer_name and buyer_name.lower() in name.lower():
                    role = "buyer"
            if not role:
                role = "id"
            safe_name = "_".join(name.split())
            new_filename = f"{role}_{safe_name}.pdf"
        except Exception as e:
            st.write(e,result['extracted_data'])
            count = st.session_state.doc_counts.get(classification, 0) + 1
            st.session_state.doc_counts[classification] = count
            new_filename = f"{classification}_{count}.pdf"
    
    # ---------- For Passport ----------
    elif classification == "passport":
        try:
            passport_data = safe_json_loads(result["extracted_data"])
            given_name = passport_data.get("Given Name", "").strip()
            surname = passport_data.get("Surname", "").strip()
            # Fallback for multipage extraction structure
            if (not given_name or not surname) and "Page_1" in passport_data:
                page1_data = passport_data["Page_1"]
                given_name = page1_data.get("Given Name", given_name).strip()
                surname = page1_data.get("Surname", surname).strip()
            if not (given_name and surname):
                raise Exception("Missing Given Name or Surname in passport data")
            safe_given = "_".join(given_name.split()).lower()
            safe_surname = "_".join(surname.split()).lower()
            new_filename = f"passport_{safe_given}_{safe_surname}.pdf"
        except Exception as e:
            count = st.session_state.doc_counts.get(classification, 0) + 1
            st.session_state.doc_counts[classification] = count
            new_filename = f"{classification}_{count}.pdf"
    
    # ---------- For Residence Visa ----------
    elif classification == "residence_visa":
        try:
            visa_data = safe_json_loads(result["extracted_data"])
            full_name = visa_data.get("full_name", "").strip()
            if not full_name and "Page_1" in visa_data:
                full_name = visa_data["Page_1"].get("full_name", "").strip()
            if not full_name:
                raise Exception("Missing full_name in residence visa data")
            safe_name = "_".join(full_name.split()).lower()
            new_filename = f"residence_visa_{safe_name}.pdf"
        except Exception as e:
            count = st.session_state.doc_counts.get(classification, 0) + 1
            st.session_state.doc_counts[classification] = count
            new_filename = f"{classification}_{count}.pdf"
    
    # ---------- For Cheques (if needed) ----------
    elif classification in ["cheques", "cheque"]:
        try:
            cheque_data = safe_json_loads(result["extracted_data"])
            if isinstance(cheque_data, list) and len(cheque_data) > 0:
                cheque_item = cheque_data[0]
                payer = cheque_item.get("Payer Name", "").strip().lower()
                if "dubai land department" in payer:
                    new_filename = "DLD_cheque.pdf"
                else:
                    contract_doc = next((doc for doc in st.session_state.results if doc["doc_type"].lower() == "contract f"), None)
                    if contract_doc:
                        contract_data = safe_json_loads(contract_doc["extracted_data"])
                        seller_name = contract_data.get("Page_1", {}).get("Owner Details", {}).get("Seller Name", "").strip().lower()
                        seller_tokens = seller_name.split()
                        if any(token in payer for token in seller_tokens):
                            new_filename = "manager_cheque.pdf"
                        else:
                            new_filename = "cheque.pdf"
                    else:
                        new_filename = "cheque.pdf"
            else:
                new_filename = "cheque.pdf"
        except Exception as e:
            new_filename = "cheque.pdf"
    
    # ---------- For Other Document Types ----------
    else:
        count = st.session_state.doc_counts.get(classification, 0) + 1
        st.session_state.doc_counts[classification] = count
        new_filename = f"{classification}_{count}.pdf"
    
    # ---------- Save the File ----------
    try:
        if original_filename.lower().endswith("pdf"):
            # For PDFs, use only the pages in the result (if defined)
            if "pages" in result and result["pages"]:
                pdf_bytes = create_pdf_from_pages(result["original_pdf_bytes"], result["pages"])
            else:
                pdf_bytes = result.get("original_pdf_bytes", image_bytes)
            with open(new_filename, "wb") as f:
                f.write(pdf_bytes)
            st.write(f"Saved PDF as {new_filename}")
        else:
            try:
                image = Image.open(io.BytesIO(image_bytes))
                image = ImageOps.exif_transpose(image)
                if image.mode != "RGB":
                    image = image.convert("RGB")
                pdf_bytes_io = io.BytesIO()
                image.save(pdf_bytes_io, format="PDF")
                pdf_bytes = pdf_bytes_io.getvalue()
                with open(new_filename, "wb") as f:
                    f.write(pdf_bytes)
                st.write(f"Converted and saved image as {new_filename}")
            except Exception as e:
                st.error(f"Error converting image {original_filename} to PDF: {e}")
    except Exception as e:
        st.error(f"Error saving document {original_filename}: {e}")
        
        
def normalize_keys(d):
    """Recursively normalize dictionary keys: lowercase and replace spaces with underscores."""
    if not isinstance(d, dict):
        return d
    normalized = {}
    for k, v in d.items():
        new_key = k.lower().replace(" ", "_").strip()
        if isinstance(v, dict):
            normalized[new_key] = normalize_keys(v)
        else:
            normalized[new_key] = v
    return normalized
def validate_documents(results):
    """
    Validates documents by performing these checks:
      1. Validates the NOC document's "Validation Date or Period".
      2. Validates each ID document's expiry_date using validate_id_data.
      3. Validates Contract F document by fuzzy matching seller(s) and buyer(s) names with valid IDs.
      4. Validates POA document by checking that at least one attorney's Emirates ID is found among the ID documents (if present).
    
    Returns a dictionary with validation messages for "NOC", "IDs", "Contract F", and "POA" (if applicable).
    """

    validation_results = {}

    # ---------- NOC Validation (unchanged) ----------
    noc_docs = [doc for doc in results if doc["doc_type"].lower() == "noc non objection certificate"]
    if noc_docs:
        try:
            noc_extracted = noc_docs[0]["extracted_data"]
            noc_data = safe_json_loads(noc_extracted)
            noc_data = normalize_keys(noc_data)
            if not noc_data:
                validation_results["NOC"] = "No valid NOC extracted data."
            else:
                validation_field = validation_field = (
                    noc_data.get("validation_date_or_period") or
                    noc_data.get("Validation Date or Period") or
                    ""
                ).strip()

                if not validation_field or validation_field.lower() in ["not provided", "not mentioned"]:
                    validation_results["NOC"] = "Validation Date or Period not provided."
                else:
                    try:
                        validation_date = datetime.strptime(validation_field, "%d/%m/%Y")
                        today = datetime.today()
                        if validation_date < today:
                            validation_results["NOC"] = f"Validation date {validation_field} has expired."
                        else:
                            validation_results["NOC"] = f"Validation date {validation_field} is valid."
                    except Exception:
                        match = re.match(r'(\d+)\s*(days?|months?)', validation_field, re.IGNORECASE)
                        if match:
                            num = int(match.group(1))
                            unit = match.group(2).lower()
                            issuing_date_str = noc_data.get("issuing_date", "").strip()
                            if not issuing_date_str:
                                validation_results["NOC"] = "Issuing date not provided for NOC."
                            else:
                                try:
                                    issuing_date = datetime.strptime(issuing_date_str, "%d/%m/%Y")
                                except Exception as e:
                                    validation_results["NOC"] = f"Error parsing issuing date: {str(e)}"
                                else:
                                    if "day" in unit:
                                        expiry_date = issuing_date + timedelta(days=num)
                                    elif "month" in unit:
                                        expiry_date = issuing_date + relativedelta(months=num)
                                    else:
                                        expiry_date = None

                                    if expiry_date is None:
                                        validation_results["NOC"] = "Unknown unit in validation period."
                                    else:
                                        today = datetime.today()
                                        if expiry_date < today:
                                            validation_results["NOC"] = f"Validation period expired (expiry date: {expiry_date.strftime('%d/%m/%Y')})."
                                        else:
                                            validation_results["NOC"] = f"Validation period is valid until {expiry_date.strftime('%d/%m/%Y')}."
                        else:
                            validation_results["NOC"] = "Validation Date or Period is in an unrecognized format."
        except Exception as e:
            validation_results["NOC"] = f"Error processing NOC data: {str(e)}"
    else:
        validation_results["NOC"] = "No NOC document found."

    # ---------- ID Validation using validate_id_data (remove duplicates) ----------
    id_docs = [doc for doc in results if doc["doc_type"].lower() == "ids"]
    id_validation_msgs = set()  # using a set to avoid duplicate messages
    valid_id_names = set()
    expired_id_names = set()
    for doc in id_docs:
        valid, name_english, msg = validate_id_data(doc.get("extracted_data", {}))
        name_disp = name_english.lower().strip() if name_english else "Unknown"
        # Build a combined message and add to set.
        id_validation_msgs.add(f"ID '{name_disp}': {msg}")
        if valid:
            valid_id_names.add(name_disp)
        else:
            expired_id_names.add(name_disp)
    if id_validation_msgs:
        validation_results["IDs"] = "\n".join(sorted(id_validation_msgs))
    else:
        validation_results["IDs"] = "No ID documents found."

    # ---------- Contract F Validation (updated for multiple sellers/buyers) ----------
    contract_docs = [doc for doc in results if doc["doc_type"].lower() == "contract f"]
    # Collect passport info for fallback checking
    passport_docs = [doc for doc in results if doc["doc_type"].lower() == "passport"]
    passport_info = []  # List of tuples: (fullname, is_valid, expiry_date, message)
    for doc in passport_docs:
        try:
            passport_data = safe_json_loads(doc["extracted_data"])
            fullname = passport_data.get("fullname", "").strip().lower()
            expiry_str = passport_data.get("Date of Expiry", "").strip()
            if expiry_str:
                expiry_date = datetime.strptime(expiry_str, "%d/%m/%Y")
                if expiry_date < datetime.today():
                    passport_info.append((fullname, False, expiry_date, f"Passport expired on {expiry_str}."))
                else:
                    passport_info.append((fullname, True, expiry_date, f"Passport valid until {expiry_str}."))
            else:
                passport_info.append((fullname, False, None, "No expiry date in passport."))
        except Exception as e:
            passport_info.append((fullname, False, None, f"Error processing passport: {str(e)}"))

    if contract_docs:
        try:
            contract_extracted = contract_docs[0]["extracted_data"]
            contract_data = safe_json_loads(contract_extracted)
            if not contract_data:
                validation_results["Contract F"] = "No valid Contract F extracted data."
            else:
                page1 = contract_data.get("Page_1", {})

                # Handle seller(s)
                seller_names = set()
                owner_details = page1.get("Owner Details", {})
                if isinstance(owner_details, dict):
                    # In case the key "Seller Name" is directly provided
                    if owner_details.get("Seller Name", "").strip():
                        seller_names.add(owner_details.get("Seller Name", "").strip().lower())
                    # Iterate over keys – handle nested dicts (e.g., "Seller # 1", "Seller # 2")
                    for key, value in owner_details.items():
                        if isinstance(value, dict):
                            seller_candidate = value.get("Seller Name", "")
                            if seller_candidate:
                                seller_names.add(seller_candidate.strip().lower())
                        elif isinstance(value, str) and "seller name" in key.lower() and value.strip():
                            seller_names.add(value.strip().lower())

                # Handle buyer(s)
                buyer_names = set()
                buyers_details = page1.get("Buyers Share Details", {})
                if isinstance(buyers_details, dict):
                    buyer_candidate = buyers_details.get("Buyer Name", "")
                    if buyer_candidate:
                        buyer_names.add(buyer_candidate.strip().lower())
                    # In case there are additional keys for buyers
                    for key, value in buyers_details.items():
                        if isinstance(value, str) and "buyer name" in key.lower() and value.strip():
                            buyer_names.add(value.strip().lower())

                if not seller_names or not buyer_names:
                    validation_results["Contract F"] = "Seller or Buyer name not found in Contract F."
                else:
                    def is_name_matched(target, names_list, threshold=0.7):
                        target_lower = target.lower()
                        for n in names_list:
                            if difflib.SequenceMatcher(None, target_lower, n).ratio() >= threshold:
                                return True
                        return False

                    seller_messages = []
                    for s in seller_names:
                        if is_name_matched(s, valid_id_names):
                            seller_messages.append(f"Seller ID for '{s}' is valid.")
                        elif is_name_matched(s, expired_id_names):
                            seller_messages.append(f"Seller ID for '{s}' is found but expired (requires human review).")
                        else:
                            passport_match = None
                            for p in passport_info:
                                if is_name_matched(s, [p[0]]):
                                    passport_match = p
                                    break
                            if passport_match:
                                if passport_match[1]:
                                    seller_messages.append(f"Seller passport for '{s}' is valid ({passport_match[3]}).")
                                else:
                                    seller_messages.append(f"Seller passport for '{s}' is found but expired (requires human review): {passport_match[3]}.")
                            else:
                                seller_messages.append(f"Seller ID/passport for '{s}' not found.")

                    buyer_messages = []
                    for b in buyer_names:
                        if is_name_matched(b, valid_id_names):
                            buyer_messages.append(f"Buyer ID for '{b}' is valid.")
                        elif is_name_matched(b, expired_id_names):
                            buyer_messages.append(f"Buyer ID for '{b}' is found but expired (requires human review).")
                        else:
                            passport_match = None
                            for p in passport_info:
                                if is_name_matched(b, [p[0]]):
                                    passport_match = p
                                    break
                            if passport_match:
                                if passport_match[1]:
                                    buyer_messages.append(f"Buyer passport for '{b}' is valid ({passport_match[3]}).")
                                else:
                                    buyer_messages.append(f"Buyer passport for '{b}' is found but expired (requires human review): {passport_match[3]}.")
                            else:
                                buyer_messages.append(f"Buyer ID/passport for '{b}' not found.")

                    combined_messages = list(seller_messages) + list(buyer_messages)
                    validation_results["Contract F"] = " ".join(combined_messages)
        except Exception as e:
            validation_results["Contract F"] = f"Error processing Contract F data: {str(e)}"
    else:
        validation_results["Contract F"] = "No Contract F document found."

    # ---------- POA Validation (unchanged) ----------
    poa_docs = [doc for doc in results if doc["doc_type"].lower() == "poa"]
    if poa_docs:
        try:
            poa_extracted = poa_docs[0]["extracted_data"]
            poa_data = safe_json_loads(poa_extracted)
            if not poa_data:
                validation_results["POA"] = "No valid POA extracted data."
            else:
                attorneys = poa_data.get("attorneys", [])
                valid_emirates_ids = []
                for doc in id_docs:
                    id_data = safe_json_loads(doc.get("extracted_data", {}))
                    eid = id_data.get("front", {}).get("emirates_id", "")
                    if eid:
                        valid_emirates_ids.append(eid.replace("-", "").strip())
                match_found = False
                for attorney in attorneys:
                    att_id = attorney.get("emirates_id", "").replace("-", "").strip()
                    if att_id and att_id in valid_emirates_ids:
                        match_found = True
                        break
                if match_found:
                    validation_results["POA"] = "At least one attorney's ID is verified in the ID documents."
                else:
                    validation_results["POA"] = "No attorney's ID from the POA matches any of the ID documents."
        except Exception as e:
            validation_results["POA"] = f"Error processing POA data: {str(e)}"

    # ---------- Mortgage Contract Validation (unchanged) ----------
    mortgage_docs = [doc for doc in results if doc["doc_type"].lower() == "mortgage contract"]
    mortgage_messages = []
    for doc in mortgage_docs:
        if doc["filename"].lower().endswith("pdf"):
            try:
                pdf_bytes = doc.get("original_pdf_bytes")
                if pdf_bytes:
                    pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                    total_pages = pdf_doc.page_count
                    pdf_doc.close()
                    if total_pages % 3 == 0:
                        mortgage_messages.append(
                            f"Mortgage contract validation: 3 copies exist."
                        )
                    else:
                        mortgage_messages.append(
                            f"Mortgage contract invalid: {total_pages % 3} copies exist."
                        )
            except Exception as e:
                mortgage_messages.append(f"Error checking mortgage contract pages: {str(e)}")
    if mortgage_messages:
        validation_results["Mortgage Contract"] = " ".join(mortgage_messages)

    # ---------- Valuation Report Dependency Check ----------
    # Only include this check if mortgage registration (or mortgage letter) and mortgage contract exist.
    mortgage_reg_docs = [doc for doc in results if doc["doc_type"].lower() == "registration of mortgages"]
    mortgage_letter_docs = [doc for doc in results if doc["doc_type"].lower() == "mortgage letter"]
    mortgage_contract_docs = [doc for doc in results if doc["doc_type"].lower() == "mortgage contract"]
    valuation_report_docs = [doc for doc in results if doc["doc_type"].lower() == "valuation report"]

    if (mortgage_reg_docs or mortgage_letter_docs) and mortgage_contract_docs:
        if not valuation_report_docs:
            validation_results["Valuation Report"] = (
                "Valuation report is missing, but both registration of mortgages (or mortgage letter) and mortgage contract are present. "
                "Please ensure the valuation report is included."
            )
        else:
            validation_results["Valuation Report"] = "Valuation report is provided."
    # If the condition is not met, do not add a Valuation Report message.

    return validation_results
