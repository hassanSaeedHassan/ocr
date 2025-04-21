def suggest_procedure(document_results, procedure_name: str = None):
    """
    Suggest one of five procedures based on processed documents:

      1. Blocking
      2. Sell pre Registration
      3. Company Registration
      4. Sell + Mortgage Transfer
      5. Transfer sell

    If none of these conditions are met, returns "others".
    """
    available_doc_types = {doc.get("doc_type", "").lower().strip() for doc in document_results}
    filenames = {doc.get("filename", "").lower().strip() for doc in document_results}

    # Build a set of found documents by checking both doc_type and filename
    def has_doc(name):
        return any(name in doc.get("doc_type", "").lower().strip() or name in doc.get("filename", "").lower().strip() for doc in document_results)

    found_documents = set()
    for doc in document_results:
        dt = doc.get("doc_type", "").lower().strip()
        fname = doc.get("filename", "").lower().strip()
        found_documents.add(dt)
        found_documents.add(fname)

    # -------------------------- 1. Blocking --------------------------
    liability_letter_exists = any(doc.get("doc_type", "").lower().strip() == "liability letter"
                                  for doc in document_results)
    mortgage_contract_exists = any(doc.get("doc_type", "").lower().strip() == "mortgage contract"
                                   for doc in document_results)
    valuation_report_exists = any(doc.get("doc_type", "").lower().strip() == "valuation report"
                                  for doc in document_results)
    mortgage_letter_or_reg_exists = any(
        doc.get("doc_type", "").lower().strip() in ["mortgage letter", "mortgage registration"]
        for doc in document_results
    )
    blocking_status_ok = False
    candidate_types = {"title deed", "pre title deed", "initial contract of sale"}
    for doc in document_results:
        dt = doc.get("doc_type", "").lower().strip()
        if dt in candidate_types:
            extracted = doc.get("extracted_data")
            status_str = ""
            if isinstance(extracted, dict):
                for key, value in extracted.items():
                    if key.lower() == "mortgage status":
                        status_str = str(value).strip()
                        break
            elif isinstance(extracted, str):
                status_str = extracted.strip()
            if "mortgaged" in status_str.lower() and "not" not in status_str.lower():
                blocking_status_ok = True
                break
    if (liability_letter_exists and mortgage_contract_exists and valuation_report_exists and
        mortgage_letter_or_reg_exists and blocking_status_ok):
        blocking_required_documents = [
            "liability letter",
            "mortgage contract",
            "valuation report",
            "mortgage letter/registration",
            "ids"
        ]
        found_blocking = set()
        for doc in document_results:
            dt = doc.get("doc_type", "").lower().strip()
            fname = doc.get("filename", "").lower()
            for req in blocking_required_documents:
                if req == "mortgage letter/registration":
                    if dt in ["mortgage letter", "mortgage registration"]:
                        found_blocking.add("mortgage letter/registration")
                elif req in dt or req in fname:
                    found_blocking.add(req)
        missing_blocking = [req for req in blocking_required_documents if req not in found_blocking]
        return {
            "procedure": "Blocking",
            "required_documents": blocking_required_documents,
            "missing_documents": missing_blocking
        }

    # -------------------------- 2. Sell pre Registration --------------------------
    initial_contract_exists = any(
        "initial contract of sale" in doc.get("doc_type", "").lower().strip()
        for doc in document_results)
    noc_exists = any(
        "noc non objection certificate" in doc.get("doc_type", "").lower().strip()
        for doc in document_results)
    soa_exists = any(
        "soa" in doc.get("doc_type", "").lower().strip() or
        "soa" in doc.get("filename", "").lower()
        for doc in document_results)
    if initial_contract_exists and noc_exists and soa_exists:
        sell_pre_reg_required = [
            "ids",
            "poa",
            "contract f",
            "initial contract of sale",
            "noc non objection certificate",
            "soa"
        ]
        found_sell_pre = set()
        for doc in document_results:
            dt = doc.get("doc_type", "").lower().strip()
            fname = doc.get("filename", "").lower()
            for req in sell_pre_reg_required:
                if req in dt or req in fname:
                    found_sell_pre.add(req)
        missing_sell_pre = [req for req in sell_pre_reg_required if req not in found_sell_pre]
        return {
            "procedure": "Sell pre Registration",
            "required_documents": sell_pre_reg_required,
            "missing_documents": missing_sell_pre
        }

    # -------------------------- 3. Company Registration --------------------------
    moa_exists = any(
        ("moa" in doc.get("doc_type", "").lower().strip() or
         "memorandum of association" in doc.get("doc_type", "").lower().strip())
        for doc in document_results
    )
    license_exists = any("commercial license" in doc.get("doc_type", "").lower().strip()
                         for doc in document_results)
    shareholder_exists = any("shareholder" in doc.get("filename", "").lower()
                             for doc in document_results)
    supporting_exists = any(
        dt in available_doc_types
        for dt in {"title deed", "pre title deed", "initial contract of sale"}
    )
    if moa_exists and license_exists and shareholder_exists and supporting_exists:
        company_reg_required = [
            "moa",
            "commercial license",
            "shareholder ids",
            "title deed/pre title deed/initial contract of sale"
        ]
        found_company_reg = set()
        for doc in document_results:
            dt = doc.get("doc_type", "").lower().strip()
            fname = doc.get("filename", "").lower()
            for req in company_reg_required:
                if req in dt or req in fname:
                    found_company_reg.add(req)
        missing_company_reg = [req for req in company_reg_required if req not in found_company_reg]
        return {
            "procedure": "Company Registration",
            "required_documents": company_reg_required,
            "missing_documents": missing_company_reg
        }

    # -------------------------- 4. Sell + Mortgage Transfer --------------------------
    mortgage_letter_exists = any(doc.get("doc_type", "").lower().strip() == "mortgage letter"
                                  for doc in document_results)
    mortgage_contract_exists = any(doc.get("doc_type", "").lower().strip() == "mortgage contract"
                                   for doc in document_results)
    release_letter_exists = any(doc.get("doc_type", "").lower().strip() == "mortgage release"
                                 for doc in document_results)
    valuation_report_exists = any(doc.get("doc_type", "").lower().strip() == "valuation report"
                                  for doc in document_results)
    mortgage_condition = mortgage_letter_exists or mortgage_contract_exists or release_letter_exists
    if mortgage_letter_exists and mortgage_contract_exists and not valuation_report_exists:
        mortgage_condition = False

    status_ok = False
    candidate_types = {"title deed", "pre title deed", "initial contract of sale"}
    for doc in document_results:
        dt = doc.get("doc_type", "").lower().strip()
        if dt in candidate_types:
            extracted = doc.get("extracted_data")
            status_str = ""
            if isinstance(extracted, dict):
                for key, value in extracted.items():
                    if key.lower() == "mortgage status":
                        status_str = str(value).strip()
                        break
            elif isinstance(extracted, str):
                status_str = extracted.strip()
            if "not mortgaged" in status_str.lower():
                status_ok = True
                break

    if mortgage_condition and status_ok:
        required_docs = ["contract f", "ids", "noc from the developer", "poa if applicable", "manager cheque"]
        return {
            "procedure": "Sell + Mortgage Transfer",
            "required_documents": required_docs,
            "missing_documents": [req for req in required_docs if not has_doc(req)]
        }

    # -------------------------- 5. Transfer sell --------------------------
    mortgage_docs = {"mortgage letter", "mortgage contract", "mortgage registration"}
    company_docs = {"moa", "memorandum of association", "commercial license", "company registration"}
    has_mortgage_docs = any(has_doc(m) for m in mortgage_docs)
    has_company_docs = any(has_doc(c) for c in company_docs)

    if not has_mortgage_docs and not has_company_docs:
        if "title deed" in available_doc_types:
            required_docs = ["ids", "contract f", "noc non objection certificate", "cheques"]
            return {
                "procedure": "Transfer sell",
                "required_documents": required_docs,
                "missing_documents": [doc for doc in required_docs if not has_doc(doc)]
            }
        elif "pre title deed" in available_doc_types:
            required_docs = [
                "ids", "contract f", "noc non objection certificate", "cheques",
                "soa", "noc non objection certificate"
            ]
            return {
                "procedure": "Transfer sell",
                "required_documents": required_docs,
                "missing_documents": [doc for doc in required_docs if not has_doc(doc)]
            }
        elif "initial contract of sale" in available_doc_types:
            required_docs = [
                "ids", "contract f", "noc non objection certificate", "cheques",
                "soa", "noc non objection certificate"
            ]
            return {
                "procedure": "Transfer sell",
                "required_documents": required_docs,
                "missing_documents": [doc for doc in required_docs if not has_doc(doc)]
            }

    # -------------------------- Fallback --------------------------
    return {
        "procedure": "others",
        "required_documents": [],
        "missing_documents": []
    }
