# scripts/procedure_recognition.py

def suggest_procedure(document_results, procedure_name: str = None):
    """
    Suggest one of five procedures based on processed documents:

      1. Blocking
      2. Sell pre Registration
      3. Company Registration
      4. Sell + Mortgage Transfer
      5. Transfer sell

    If procedure_name is provided, return that procedure’s requirements/missing;
    otherwise auto-detect which procedure applies.
    """
    # Helper to check presence by doc_type or filename
    def has_doc(name: str) -> bool:
        return any(
            name in doc.get("doc_type", "").lower().strip()
            or name in doc.get("filename", "").lower().strip()
            for doc in document_results
        )

    # Gather available doc_types
    available_doc_types = {doc.get("doc_type", "").lower().strip() for doc in document_results}

    # Precompute requirements and missing lists for each procedure
    # 1) Blocking
    blocking_required = [
        "liability letter",
        "mortgage contract",
        "valuation report",
        "mortgage letter/registration",
        "ids"
    ]
    found_blocking = set()
    for doc in document_results:
        dt = doc.get("doc_type", "").lower().strip()
        fn = doc.get("filename", "").lower().strip()
        for req in blocking_required:
            if req == "mortgage letter/registration":
                if dt in ["mortgage letter", "mortgage registration"]:
                    found_blocking.add(req)
            elif req in dt or req in fn:
                found_blocking.add(req)
    missing_blocking = [r for r in blocking_required if r not in found_blocking]

    # 2) Sell pre Registration
    sell_pre_required = [
        "ids",
        "poa",
        "contract f",
        "initial contract of sale",
        "noc non objection certificate",
        "soa"
    ]
    found_sell_pre = {req for req in sell_pre_required if has_doc(req)}
    missing_sell_pre = [r for r in sell_pre_required if r not in found_sell_pre]

    # 3) Company Registration
    company_required = [
        "moa",
        "commercial license",
        "shareholder ids",
        "title deed/pre title deed/initial contract of sale"
    ]
    found_company = {req for req in company_required if has_doc(req)}
    missing_company = [r for r in company_required if r not in found_company]

    # 4) Sell + Mortgage Transfer
    sell_mort_required = [
        "contract f",
        "ids",
        "noc from the developer",
        "poa if applicable",
        "manager cheque"
    ]
    found_sell_mort = {req for req in sell_mort_required if has_doc(req)}
    missing_sell_mort = [r for r in sell_mort_required if r not in found_sell_mort]

    # 5) Transfer sell
    transfer_required = []
    has_mortgage_docs = any(has_doc(x) for x in ["mortgage letter", "mortgage contract", "mortgage registration"])
    has_company_docs  = any(has_doc(x) for x in ["moa", "commercial license", "company registration"])
    if not has_mortgage_docs and not has_company_docs:
        if "title deed" in available_doc_types:
            transfer_required = ["ids", "contract f", "noc non objection certificate", "cheques"]
        elif any(t in available_doc_types for t in ["pre title deed", "initial contract of sale"]):
            transfer_required = [
                "ids",
                "contract f",
                "noc non objection certificate",
                "cheques",
                "soa",
                "noc non objection certificate"
            ]
    found_transfer = {req for req in transfer_required if has_doc(req)}
    missing_transfer = [r for r in transfer_required if r not in found_transfer]

    # Map of procedure data
    proc_map = {
        "blocking": ("Blocking", blocking_required, missing_blocking),
        "sell pre registration": ("Sell pre Registration", sell_pre_required, missing_sell_pre),
        "company registration": ("Company Registration", company_required, missing_company),
        "sell + mortgage transfer": ("Sell + Mortgage Transfer", sell_mort_required, missing_sell_mort),
        "transfer sell": ("Transfer sell", transfer_required, missing_transfer)
    }

    # 1) Override by explicit name
    if procedure_name:
        key = procedure_name.lower().strip()
        if key in proc_map:
            name, reqs, miss = proc_map[key]
            return {"procedure": name, "required_documents": reqs, "missing_documents": miss}
        else:
            return {"procedure": procedure_name, "required_documents": [], "missing_documents": []}

    # 2) Auto‑detect in order
    # Blocking condition
    liability_ok = has_doc("liability letter")
    mort_contract_ok = has_doc("mortgage contract")
    val_report_ok = has_doc("valuation report")
    mort_letter_ok = any(doc.get("doc_type", "").lower().strip() in ["mortgage letter", "mortgage registration"] for doc in document_results)
    # mortgage status check
    status_ok = False
    for doc in document_results:
        dt = doc.get("doc_type", "").lower().strip()
        if dt in {"title deed", "pre title deed", "initial contract of sale"}:
            ed = doc.get("extracted_data")
            text = ""
            if isinstance(ed, dict):
                text = next((str(v) for k, v in ed.items() if k.lower() == "mortgage status"), "")
            else:
                text = str(ed)
            if "mortgaged" in text.lower() and "not" not in text.lower():
                status_ok = True
                break
    if liability_ok and mort_contract_ok and val_report_ok and mort_letter_ok and status_ok:
        name, reqs, miss = proc_map["blocking"]
        return {"procedure": name, "required_documents": reqs, "missing_documents": miss}

    # Sell pre Registration
    if has_doc("initial contract of sale") and has_doc("noc non objection certificate") and has_doc("soa"):
        name, reqs, miss = proc_map["sell pre registration"]
        return {"procedure": name, "required_documents": reqs, "missing_documents": miss}

    # Company Registration
    if ((has_doc("moa") or has_doc("memorandum of association"))
        and has_doc("commercial license")
        and has_doc("shareholder")
        and any(t in available_doc_types for t in ["title deed", "pre title deed", "initial contract of sale"])):
        name, reqs, miss = proc_map["company registration"]
        return {"procedure": name, "required_documents": reqs, "missing_documents": miss}

    # Sell + Mortgage Transfer
    if ((any(has_doc(x) for x in ["mortgage letter", "mortgage contract", "mortgage registration"]))
        and status_ok
        and not has_doc("valuation report")):
        name, reqs, miss = proc_map["sell + mortgage transfer"]
        return {"procedure": name, "required_documents": reqs, "missing_documents": miss}

    # Transfer sell
    name, reqs, miss = proc_map["transfer sell"]
    if name == "Transfer sell":
        return {"procedure": name, "required_documents": reqs, "missing_documents": miss}

    # Fallback
    return {"procedure": "others", "required_documents": [], "missing_documents": []}