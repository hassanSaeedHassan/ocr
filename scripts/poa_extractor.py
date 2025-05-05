import tabula
import base64
import json
import fitz  # PyMuPDF
from openai import OpenAI
import re
import streamlit as st
from scripts.vlm_utils import safe_json_loads
from scripts.vlm_utils import (
    call_vlm,
    pdf_page_to_png,
    downscale_until,
    THRESHOLD_BYTES
)
def unify_poa_data(raw_data) -> dict:
    """
    Normalize raw POA output into a dict with:
      - principals: mapping "principal {i}" → record
      - attorneys:  mapping "attorney {i}" → record
    Always returns at least one (empty) entry if none found.
    Drops virtue_attorneys if empty.

    Special handling:
      * If any record has a 'role' field, classification is driven by:
          - 'وكيل' in role → principal
          - 'موكل' in role → attorney
      * passport_number → passport_no
      * Passport numbers starting with '784' reclassified as emirates_id
      * Only digits are kept in emirates_id
      * Duplicate records with identical names are collapsed (no concatenation)
      * Records with same ID but different names are merged by concatenation
      * If a person appears in both principals and attorneys and
        their attorney record has both emirates_id and passport_no empty,
        that attorney entry is dropped.
    """
    # 1) Parse raw_data into dict
    if isinstance(raw_data, str):
        try:
            poa = json.loads(raw_data)
        except json.JSONDecodeError:
            poa = safe_json_loads(raw_data)
    elif isinstance(raw_data, dict):
        poa = raw_data.copy()
    else:
        poa = {}

    # 2) Aggregate all entries for role-based classification
    all_records = []
    for section in ('principals', 'attorneys', 'virtue_attorneys'):
        items = poa.get(section)
        if isinstance(items, list):
            for rec in items:
                if isinstance(rec, dict):
                    all_records.append(rec)

    # 3) Determine if we should use 'role' for classification
    role_based = any('role' in rec for rec in all_records)
    if role_based:
        principals_raw = [r for r in all_records if 'وكيل' in r.get('role', '')]
        attorneys_raw  = [r for r in all_records if 'موكل' in r.get('role', '')]
    else:
        principals_raw = poa.get('principals') if isinstance(poa.get('principals'), list) else []
        attorneys_raw  = poa.get('attorneys')  if isinstance(poa.get('attorneys'), list)  else []
    virtues_raw = poa.get('virtue_attorneys') if isinstance(poa.get('virtue_attorneys'), list) else []

    # 4) Cleaning helpers
    def clean_name(name: str) -> str:
        return re.sub(r'^(?:Mr\.|Mrs\.|Ms\.)\s*', '', (name or '')).strip()

    def clean_nationality(nat: str) -> str:
        return re.sub(r'\bالجنسية|\s*Nationality$', '', (nat or '')).strip()

    # 5) Normalize single record
    def normalize_record(rec: dict) -> dict:
        name = clean_name(rec.get('name', ''))
        nationality = clean_nationality(rec.get('nationality', ''))
        # unify passport field
        pid = rec.get('passport_no', '') or rec.get('passport_number', '') or ''
        eid = rec.get('emirates_id', '') or rec.get('national_id', '') or ''
        # fallback document_number
        if not eid and not pid:
            dt, dn = rec.get('document_type', ''), rec.get('document_number', '')
            if 'هوية' in dt:
                eid = dn
            else:
                pid = dn
        # reclassify passport-looking ID
        if pid.startswith('784'):
            eid, pid = pid, ''
        # keep digits only for eid
        eid = re.sub(r'\D', '', eid)
        return {'name': name, 'nationality': nationality, 'emirates_id': eid, 'passport_no': pid}

    # 6) Deduplicate and merge
    def dedupe(records):
        seen = {}
        for rec in (records or []):
            if not isinstance(rec, dict):
                continue
            norm = normalize_record(rec)
            key = norm['emirates_id'] or norm['passport_no'] or norm['name']
            if not key:
                continue
            if key in seen:
                # if same name, skip; else concatenate
                if seen[key]['name'] != norm['name']:
                    seen[key]['name'] += ' ' + norm['name']
            else:
                seen[key] = norm
        return list(seen.values())

    principals_list = dedupe(principals_raw)
    attorneys_list  = dedupe(attorneys_raw)
    virtues_list    = dedupe(virtues_raw)

    # 7) Drop attorney entries with empty IDs if also in principals
    principal_names = {rec['name'] for rec in principals_list}
    attorneys_list = [
        rec for rec in attorneys_list
        if not (rec['name'] in principal_names and not rec['emirates_id'] and not rec['passport_no'])
    ]

    # 8) Ensure at least one empty
    if not principals_list:
        principals_list = [{'name':'','nationality':'','emirates_id':'','passport_no':''}]
    if not attorneys_list:
        attorneys_list = [{'name':'','nationality':'','emirates_id':'','passport_no':''}]

    # 9) Convert to keyed dict
    principals = {f'principal {i+1}': rec for i, rec in enumerate(principals_list)}
    attorneys  = {f'attorney {i+1}':  rec for i, rec in enumerate(attorneys_list)}
    result = {'principals': principals, 'attorneys': attorneys}
    if virtues_list:
        virtues = {f'virtue_attorney {i+1}': rec for i, rec in enumerate(virtues_list)}
        result['virtue_attorneys'] = virtues
    return result



# ------------------------- Prompts -------------------------
LANGUAGE_PROMPT_TABLE_DETECT = (
    """
if you found "power of attorney" in the content of the page then it contains English
Answer with exactly "yes" if it is English, otherwise "no".
"""
)

LANGUAGE_PROMPT_IMAGE_DETECT = (
    """
some pages mix English and Arabic in two columns as the page is split into two columns,
the right one includes Arabic and the left includes English.
if you found power of attorney in the page then it contains English
Check if this page contains the principal/attorney data in English.
Answer with exactly "yes" if it is English, otherwise "no".
You will see the start of the English block after a line of dashes:
-----------------------------------------------
"""
)

POA_PROMPT_ENG = (
    """
Extract the following from the English section of this power-of-attorney document image and return valid JSON.
Roles:
  • Principals: individuals referred to as "The Principal"
  • Attorneys: individuals referred to as "The Attorney"
  • Virtue Attorneys: individuals referred to as "The Virtue Attorney" (if any)

For each person, extract:
  - name: full name (e.g., "Mr. Samuel Dunnachie")
  - nationality: (e.g., "British National")
  - emirates_id: the Emirates ID number  which could be  و يحمل هوية رقم  or empty string if none
  - passport_no: passport number which could be  و يحمل جواز سفر رقم or empty string if none 

Return a single JSON object:
{
  "principals": [ … ],
  "attorneys":  [ … ],
  "virtue_attorneys": [ … ]
}
"""
)

POA_PROMPT_ARABIC = (
    """
extract the text data including the names of persons mentioned and the roles in arabic either principal or attorney
which will be found in the first paragraph in the document so ignore the terms.
- Note sometimes the data is in tables with header indicating the role, first column name, second nationality,
  third document type, fourth document number; ignore other columns.
- Do not repeat the same person under multiple roles.
- so if there is no tables you need to extract the whole paragraph declaring who are the principals and attorneys and mention the role in english (Either principal or attorney).
- note you will find و يشار اليه بالوكيل after the details of the attorneys
- while you will find "ويشار اليه بالموكل" after the details of the principals
"""
)

# Initialize VLM client once
_client = OpenAI(
    base_url="https://mf32siy1syuf3src.us-east-1.aws.endpoints.huggingface.cloud/v1/",
    api_key="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"
)


def _concatenate_tables_as_string(tables):
    """
    Clean and concatenate a list of DataFrame tables into a single string.
    """
    parts = []
    for table in tables:
        table = table.dropna(how="all")
        s = table.to_string(index=False, header=True, na_rep="")
        if s.strip():
            parts.append(s)
    return "\n\n".join(parts)



def extract_power_of_attorney(pdf_path: str, max_pages: int = None) -> dict:
    """
    Extract power-of-attorney data by:
      1. Attempting table-based extraction via Tabula.
      2. Falling back to VLM image-based extraction (English then Arabic).
      3. Ensuring valid JSON, converting if needed.
      4. Unifying and normalizing fields.

    Returns a Python dict ready for downstream processing.
    """
    # 1) Table-based extraction
    try:
        tables = tabula.read_pdf(pdf_path, pages=[1,2,3,4], multiple_tables=True)
        concatenated = _concatenate_tables_as_string(tables)
    except Exception:
        concatenated = ""

    extracted_raw = None
    if concatenated.strip()and ' وكالة خاصة - العقارات' not in concatenated and 'وكالة خاصة' not in concatenated and 'رقم المعاملة' not in concatenated and "بيانات" in concatenated :
        prompt = (
            f"Extract the following data from the table content:\n{concatenated}\n"
            "Note for the emirates id return them as strings not scientific numbers\n"
            "Return only the JSON object with keys principals, attorneys, virtue_attorneys."
            "don't include any reasoning or notes"
        )
        resp, _ = call_vlm([{"type": "text", "text": prompt}], _client)
        extracted_raw = resp
    else:
        # 2) Image-based extraction
        with open(pdf_path, 'rb') as f:
            data = f.read()
        doc = fitz.open(stream=data, filetype="pdf")
        limit = doc.page_count if max_pages is None else min(doc.page_count, max_pages)

        for p in range(limit):
            img_bytes = pdf_page_to_png(doc, p)
            if len(img_bytes) > THRESHOLD_BYTES:
                data_uri, img_bytes, _ = downscale_until(img_bytes)
            else:
                enc = base64.b64encode(img_bytes).decode('utf-8')
                data_uri = f"data:image/png;base64,{enc}"

            lang_resp, _ = call_vlm([
                {"type": "image_url", "image_url": {"url": data_uri}},
                {"type": "text",       "text": LANGUAGE_PROMPT_IMAGE_DETECT}
            ], _client)

            if "yes" in lang_resp.lower():
                extracted_raw, _ = call_vlm([
                    {"type": "image_url", "image_url": {"url": data_uri}},
                    {"type": "text",       "text": POA_PROMPT_ENG}
                ], _client)
                break
        else:
            # fallback to Arabic extraction on page 0
            img_bytes = pdf_page_to_png(doc, 0)
            if len(img_bytes) > THRESHOLD_BYTES:
                data_uri, img_bytes, _ = downscale_until(img_bytes)
            else:
                enc = base64.b64encode(img_bytes).decode('utf-8')
                data_uri = f"data:image/png;base64,{enc}"
            extracted_raw, _ = call_vlm([
                {"type": "image_url", "image_url": {"url": data_uri}},
                {"type": "text",       "text": POA_PROMPT_ARABIC}
            ], _client)
        doc.close()

    # 3) Parse and clean raw JSON output
    st.write(extracted_raw)
    raw = extracted_raw or ""
    if isinstance(raw, str):
        raw = raw.strip()
        if raw.startswith("```json"):
            raw = raw[len("```json"):].strip().rstrip("```")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        conv = (
            "Convert the following into valid JSON with keys principals, attorneys only.\n"
            f"{raw}"
            "وكيل means principal and موكل is attorney "
            "so if وكيل found in the line this person should be principal"
            "and if موكل found in the line then this person should be attorney"
            "Return only the JSON object with keys principals, attorneys."
            "Each person should be found only one time under one key either pricncipal or attorney"
            "don't include any reasoning or notes"
            "only consider working on lines containing both names and either emirates_id or passport_no"
            "so if the line contain a name and just a statment of empowring ignore it"
            "also for each person you should return emirates_id (empty if doesn't exist) and passport_no (empty if doesn't exists)"
            ""
        )
        fixed, _ = call_vlm([{"type": "text", "text": conv}], _client)
        st.write(fixed)
        try:
            parsed = json.loads(fixed)
        except json.JSONDecodeError:
            parsed = safe_json_loads(fixed)
    
    # 4) Unify and normalize structure, returning a dict
    unified = unify_poa_data(parsed)
    return unified
