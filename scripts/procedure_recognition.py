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
    otherwise auto‑detect which procedure applies.
    """
    # --- helpers ---
    def has_doc(name: str) -> bool:
        name = name.lower().strip()
        for doc in document_results:
            if name in doc.get("doc_type", "").lower() or name in doc.get("filename", "").lower():
                return True
        return False

    def has_req(req: str) -> bool:
        """Map requirement‑names to real doc synonyms."""
        key = req.lower().strip()
        if key == "noc from the developer":
            return has_doc("noc non objection certificate")
        if key == "manager cheque":
            return has_doc("cheque") or has_doc("cheques")
        return has_doc(key)

    # --- gather all doc_types for transfer‑sell logic ---
    available_doc_types = {
        doc.get("doc_type", "").lower().strip()
        for doc in document_results
    }

    # --- Define requirement lists ---
    proc_requirements = {
        "blocking": [
            "liability letter",
            "mortgage contract",
            "valuation report",
            "mortgage letter/registration",
            "ids"
        ],
        "sell pre registration": [
            "ids",
            "poa",
            "contract f",
            "initial contract of sale",
            "noc non objection certificate",
            "soa"
        ],
        "company registration": [
            "moa",
            "commercial license",
            "shareholder ids",
            "title deed/pre title deed/initial contract of sale"
        ],
        "sell + mortgage transfer": [
            "contract f",
            "ids",
            "noc from the developer",
            "poa if applicable",    # optional
            "manager cheque"
        ],
        "transfer sell": [],  # populated below
    }

    # --- Build Transfer‑sell requirements based on doc types ---
    has_mort_docs    = has_doc("mortgage letter") or has_doc("mortgage registration") or has_doc("mortgage contract")
    has_company_docs = has_doc("moa") or has_doc("commercial license") or has_doc("company registration")

    ts_req = []
    if not has_mort_docs and not has_company_docs:
        if "title deed" in available_doc_types:
            ts_req = ["ids", "contract f", "noc non objection certificate", "cheques"]
        elif any(t in available_doc_types for t in ("pre title deed", "initial contract of sale")):
            ts_req = ["ids", "contract f", "noc non objection certificate", "cheques", "soa"]

    proc_requirements["transfer sell"] = ts_req

    # --- Compute found & missing for each procedure ---
    optional_reqs = {
        "sell + mortgage transfer": {"poa if applicable"}
    }

    proc_map = {}
    for key, reqs in proc_requirements.items():
        found = {r for r in reqs if has_req(r)}
        missing = [
            r for r in reqs
            if r not in found and r not in optional_reqs.get(key, set())
        ]
        # Human‑friendly name
        display = {
            "blocking": "Blocking",
            "sell pre registration": "Sell pre Registration",
            "company registration": "Company Registration",
            "sell + mortgage transfer": "Sell + Mortgage Transfer",
            "transfer sell": "Transfer sell"
        }.get(key, "Others")
        proc_map[key] = (display, reqs, missing)

    # Always include final “others”
    proc_map["others"] = ("Others", [], [])

    # --- 1) Override by explicit name ---
    if procedure_name:
        key = procedure_name.lower().strip()
        if key in proc_map:
            name, reqs, miss = proc_map[key]
            return {"procedure": name, "required_documents": reqs, "missing_documents": miss}
        return {"procedure": procedure_name, "required_documents": [], "missing_documents": []}

    # --- 2) Auto‑detect in original order ---

    # Blocking
    ml_ok = any(
        doc.get("doc_type", "").lower().strip() in ("mortgage letter", "mortgage registration")
        for doc in document_results
    )
    # status_ok = “mortgaged” & not “not”
    status_ok = False
    for doc in document_results:
        dt = doc.get("doc_type", "").lower().strip()
        if dt in ("title deed", "pre title deed", "initial contract of sale"):
            ed = doc.get("extracted_data", "")
            txt = ""
            if isinstance(ed, dict):
                txt = next((str(v) for k, v in ed.items() if k.lower()=="mortgage status"), "")
            else:
                txt = str(ed)
            if "mortgaged" in txt.lower() and "not" not in txt.lower():
                status_ok = True
                break

    if has_doc("liability letter") and has_doc("mortgage contract") and has_doc("valuation report") and ml_ok and status_ok:
        return dict(zip(
            ["procedure","required_documents","missing_documents"],
            proc_map["blocking"]
        ))

    # Sell pre Registration
    if has_doc("initial contract of sale") and has_doc("noc non objection certificate") and has_doc("soa"):
        return dict(zip(
            ["procedure","required_documents","missing_documents"],
            proc_map["sell pre registration"]
        ))

    # Company Registration
    if (has_doc("moa") or has_doc("memorandum of association")) \
       and has_doc("commercial license") \
       and has_doc("shareholder") \
       and any(t in available_doc_types for t in ("title deed","pre title deed","initial contract of sale")):
        return dict(zip(
            ["procedure","required_documents","missing_documents"],
            proc_map["company registration"]
        ))

    # Sell + Mortgage Transfer (original disable‑when‑both‑and‑no‑valuation rule)
    mort_contract_ok = has_doc("mortgage contract")
    sm_cond = (ml_ok or mort_contract_ok or has_doc("mortgage release"))
    if ml_ok and mort_contract_ok and not has_doc("valuation report"):
        sm_cond = False

    if sm_cond and status_ok:
        return dict(zip(
            ["procedure","required_documents","missing_documents"],
            proc_map["sell + mortgage transfer"]
        ))

    # Transfer sell
    if ts_req:
        return dict(zip(
            ["procedure","required_documents","missing_documents"],
            proc_map["transfer sell"]
        ))

    # Fallback
    return {"procedure": "Others", "required_documents": [], "missing_documents": []}
