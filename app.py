import streamlit as st
import time
import fitz  # PyMuPDF
import base64
import tempfile
import io
import os
import json
from datetime import datetime
from PIL import Image, ImageOps
from scripts.validation import *    # This imports safe_json_loads, validate_documents, save_document, etc.
from scripts.vlm_utils import *       # Includes call_vlm, process_pdf_file, process_image_file, downscale_until, etc.
from openai import OpenAI
from scripts.prompts_legal import *        # Contains LEGAL_PROMPT, NOC_vlm_prompt, etc.
from scripts.individual_prompts import *     # Contains PERSONAL_PROMPT, passport_prompt, VISA_PROMPT, etc.
from scripts.company_prompts import *
from scripts.prompts import *
from scripts.ui_functions import *
from scripts.unification import *
from scripts.poa_extractor import *
from scripts.vlm_utils import create_pdf_from_pages
from scripts.procedure_recognition import suggest_procedure
import streamlit.components.v1 as components

# ----------------- SET AUTHENTICATION & CLIENT IN SESSION ------------------
if "client" not in st.session_state:
    st.session_state.client = OpenAI(
#         base_url="https://router.huggingface.co/hf-inference/models/Qwen/Qwen2.5-VL-7B-Instruct/v1",
        base_url = "https://mf32siy1syuf3src.us-east-1.aws.endpoints.huggingface.cloud/v1/",

        api_key="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",


    )
if "token" not in st.session_state:

    st.session_state.token='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'

st.set_page_config(
    page_title="Injaz OCR System",
    page_icon="https://bunny-wp-pullzone-x8psmhth4d.b-cdn.net/wp-content/uploads/2022/12/Asset-1.svg",
    layout="wide"
)

st.markdown("""
  <style>
    /* force background and panels white/lemon */
    .css-1lcbmhc, .css-12w0qpk {background-color: #FFFACD !important;}
    .css-1v3fvcr {background-color: #FFFFFF !important;}
    /* force text black */
    .css-1v4dx5s {color: #000000 !important;}
  </style>
""", unsafe_allow_html=True)
THRESHOLD_BYTES = int(1.3 * 1024 * 1024)

# ---------- SIDE_PROMPT (others are imported externally) ----------
SIDE_PROMPT2 = """
For the provided image of an Emirates ID page, indicate if the image shows the front side, the back side, or both. Respond with 'front', 'back', or 'both'.
NOTES:
the front side contains: an image of the person, name in both Arabic and English, and may include the issuing date. It does not include the machine readable zone.
the back side must have the machine readable zone.
Return only one of the following: 'front', 'back', or 'both'.
"""
SIDE_PROMPT = """
Inspect the ID image. If you see the 3‑line machine‑readable zone (MRZ) at the bottom and don't have portrait photo, answer 'back'.
If you see the portrait photo, name fields and no MRZ, answer 'front'.
If both are visible, answer 'both'.
Return exactly one word: 'front', 'back', or 'both'.
"""

# ---------- RECURSIVE FORM RENDERING HELPER ----------
def clean_json_string(json_str):
    """
    Remove markdown/code-fence markers if present and extra whitespace.
    For example, remove leading and trailing ```json and ``` markers.
    """
    cleaned = json_str.strip()
    # If the string starts with a code fence, remove the first and last lines if they are fences.
    if cleaned.startswith("```"):
        # Split by lines.
        lines = cleaned.splitlines()
        # Remove first line if it starts with ```
        if lines[0].strip().startswith("```"):
            lines = lines[1:]
        # Remove last line if it is a code fence.
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return cleaned



def render_dict(d, indent_level=0, parent_key="", use_expander=True):
    """
    Recursively render a dict:
      - Unwrap any {"raw_text": "<json>"} at every nesting level.
      - Keys become static markdown labels (indented).
      - Values become st.text_input fields (or nested render_dict calls).
    """
    inputs = {}
    simple_fields = []
    indent = "  " * indent_level  # two non-breaking spaces per level

    for key, value in d.items():
        # ——— Unwrap raw_text if it's valid JSON ———
        if (
            isinstance(value, dict)
            and set(value.keys()) == {"raw_text"}
            and isinstance(value["raw_text"], str)
        ):
            inner = clean_json_string(value["raw_text"])
            try:
                value = json.loads(inner)
            except json.JSONDecodeError:
                pass  # leave as-is if not valid JSON

        raw_label = key.replace("_", " ")
        widget_key = f"{parent_key}_{key}" if parent_key else key

        # ——— Nested dict ———
        if isinstance(value, dict):
            # Inline if only one child or same as parent
            if len(value) == 1 or (parent_key and key.lower() == parent_key.lower()):
                st.markdown(f"{indent}**{raw_label}:**")
                inputs[key] = render_dict(
                    value,
                    indent_level=indent_level + 1,
                    parent_key=widget_key,
                    use_expander=False,
                )
            else:
                # flush pending simple fields first
                for i in range(0, len(simple_fields), 2):
                    cols = st.columns(2)
                    k1, v1, lbl1, wkey1 = simple_fields[i]
                    with cols[0]:
                        inputs[k1] = st.text_input(lbl1, value=str(v1), key=wkey1)
                    if i + 1 < len(simple_fields):
                        k2, v2, lbl2, wkey2 = simple_fields[i + 1]
                        with cols[1]:
                            inputs[k2] = st.text_input(lbl2, value=str(v2), key=wkey2)
                simple_fields.clear()

                if use_expander:
                    with st.expander(f"{indent}{raw_label}", expanded=True):
                        inputs[key] = render_dict(
                            value,
                            indent_level=indent_level + 1,
                            parent_key=widget_key,
                            use_expander=False,
                        )
                else:
                    st.markdown(f"{indent}**{raw_label}:**")
                    inputs[key] = render_dict(
                        value,
                        indent_level=indent_level + 1,
                        parent_key=widget_key,
                        use_expander=False,
                    )

        # ——— List ———
        elif isinstance(value, list):
            # flush any pending simple fields
            for i in range(0, len(simple_fields), 2):
                cols = st.columns(2)
                k1, v1, lbl1, wkey1 = simple_fields[i]
                with cols[0]:
                    inputs[k1] = st.text_input(lbl1, value=str(v1), key=wkey1)
                if i + 1 < len(simple_fields):
                    k2, v2, lbl2, wkey2 = simple_fields[i + 1]
                    with cols[1]:
                        inputs[k2] = st.text_input(lbl2, value=str(v2), key=wkey2)
            simple_fields.clear()

            st.markdown(f"{indent}**{raw_label}:**")
            if value and isinstance(value[0], dict):
                inputs[key] = []
                for idx, item in enumerate(value):
                    st.markdown(f"{indent}- Item {idx+1}")
                    inputs[key].append(
                        render_dict(
                            item,
                            indent_level=indent_level + 1,
                            parent_key=f"{widget_key}_{idx}",
                            use_expander=False,
                        )
                    )
            else:
                inputs[key] = st.text_input(raw_label, value=str(value), key=widget_key)

        # ——— Simple fields ———
        else:
            simple_fields.append((key, value, raw_label, widget_key))

    # flush any remaining simple fields
    for i in range(0, len(simple_fields), 2):
        cols = st.columns(2)
        k1, v1, lbl1, wkey1 = simple_fields[i]
        with cols[0]:
            inputs[k1] = st.text_input(lbl1, value=str(v1), key=wkey1)
        if i + 1 < len(simple_fields):
            k2, v2, lbl2, wkey2 = simple_fields[i + 1]
            with cols[1]:
                inputs[k2] = st.text_input(lbl2, value=str(v2), key=wkey2)

    return inputs


def render_data_form(extracted_data, form_key):
    """
    Wraps render_dict in a form, unwrapping any top-level {"raw_text": ...} JSON blob first.
    """
    # 1) If it's a raw string, try parsing JSON
    if isinstance(extracted_data, str):
        cleaned = clean_json_string(extracted_data)
        try:
            extracted_data = json.loads(cleaned)
        except json.JSONDecodeError:
            extracted_data = {"raw_text": cleaned}

    # 2) Unwrap a single-level {"raw_text": ...} if present
    if (
        isinstance(extracted_data, dict)
        and set(extracted_data.keys()) == {"raw_text"}
        and isinstance(extracted_data["raw_text"], str)
    ):
        inner = clean_json_string(extracted_data["raw_text"])
        try:
            extracted_data = json.loads(inner)
        except json.JSONDecodeError:
            pass

    # 3) If it’s a list of dicts, wrap for iteration
    if isinstance(extracted_data, list):
        if extracted_data and isinstance(extracted_data[0], dict):
            extracted_data = {"Documents": extracted_data}
        else:
            extracted_data = {"raw_text": str(extracted_data)}

    # 4) Guarantee a dict
    if not isinstance(extracted_data, dict):
        extracted_data = {"raw_text": str(extracted_data)}

    with st.form(key=f"ocr_data_form_{form_key}"):

        # use the form_key to namespace widget keys
        form_inputs = render_dict(
            extracted_data,
            indent_level=0,
            parent_key=f"form{form_key}",
            use_expander=False,
        )

        # When they click “Save Changes”:
        submitted = st.form_submit_button("Save Changes")
        if submitted:
            st.session_state.results[form_key]["extracted_data"] = form_inputs
            st.success("Changes saved!")
            # force the whole script to restart now that session_state is updated
            try:
                st.experimental_rerun()
            except AttributeError:
                # if your Streamlit version lives under st.rerun()
                st.rerun()

    # returning here is optional—once we rerun the app, you’ll see the updated form
    return None




# ---------- HELPER FUNCTIONS ----------
def get_data_uri_from_page(doc, page_num, zoom=1.75):
    page_bytes = pdf_page_to_png(doc, page_num, zoom=zoom)
    data_uri, image_bytes, _ = downscale_until(page_bytes)
    return data_uri, image_bytes

def create_pdf_from_pages(original_pdf_bytes, page_numbers):
    src_doc = fitz.open(stream=original_pdf_bytes, filetype="pdf")
    new_doc = fitz.open()  # empty PDF
    for p in page_numbers:
        new_doc.insert_pdf(src_doc, from_page=p-1, to_page=p-1)
    pdf_bytes = new_doc.write()
    new_doc.close()
    src_doc.close()
    return pdf_bytes

def merge_ids(front_extracted, back_extracted):
    st.write(front_extracted)
    st.write(back_extracted)
    front_inner = front_extracted.get("front", {}).copy()
    back_inner = back_extracted.get("front", {})

    for key in front_inner:
        front_val = str(front_inner.get(key, "")).strip().lower()
        if front_val == "not mentioned":
            back_val = str(back_inner.get(key, "not mentioned")).strip().lower()
            if back_val != "not mentioned":
                front_inner[key] = back_inner.get(key)
    return {"front": front_inner, "back": front_extracted.get("back", {})}

def merge_ids_complete(front_extracted, back_extracted):
    merged_front = front_extracted.get("front", {}).copy()
    back_front = back_extracted.get("front", {})
    for key in merged_front:
        if str(merged_front.get(key, "")).strip().lower() == "not mentioned":
            if str(back_front.get(key, "not mentioned")).strip().lower() != "not mentioned":
                merged_front[key] = back_front.get(key)
    
    merged_back = front_extracted.get("back", {}).copy()
    back_back = back_extracted.get("back", {})
    for key in merged_back:
        if str(merged_back.get(key, "")).strip().lower() == "not mentioned":
            if str(back_back.get(key, "not mentioned")).strip().lower() != "not mentioned":
                merged_back[key] = back_back.get(key)
    
    return {"front": merged_front, "back": merged_back}

# ---------- MULTI-DOCUMENT PROCESSING FUNCTION (for IDs, passports, and residence visas) ----------
def process_multi_document_ids(file_data, filename):
    groups = []
    pdf_bytes = file_data.read()
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    total_pages = doc.page_count
    st.write(f"Total pages in PDF: {total_pages}")
    
    page_idx = 0
    pending_back = None
    while page_idx < total_pages:
        data_uri, current_image = get_data_uri_from_page(doc, page_idx)
        messages_detail = [
            {"type": "image_url", "image_url": {"url": data_uri}},
            {"type": "text", "text": PERSONAL_PROMPT}
        ]
        with st.spinner(f"Classifying page {page_idx+1}..."):
            detail_result, _ = call_vlm(messages_detail, st.session_state.client)
        detail_type = detail_result.lower().strip()
        st.write(f"Page {page_idx+1} detailed type: {detail_type}")
        
        if detail_type in ["passport", "residence visa"]:
            extraction_prompt = passport_prompt if detail_type == "passport" else VISA_PROMPT
            messages_extract = [
                {"type": "image_url", "image_url": {"url": data_uri}},
                {"type": "text", "text": extraction_prompt}
            ]
            with st.spinner(f"Extracting data from page {page_idx+1} ({detail_type})..."):
                extraction_response, _ = call_vlm(messages_extract, st.session_state.client)
            try:
                cleaned = extraction_response.replace("```json", "").replace("```", "").strip()
                extracted = json.loads(cleaned)
            except json.JSONDecodeError:
                extracted = {"raw_text": extraction_response}
            group = {
                "filename": filename,
                "doc_type": detail_type,
                "pages": [page_idx+1],
                "image_bytes": current_image,
                "extracted_data": extracted,
                "original_pdf_bytes": pdf_bytes
            }
            groups.append(group)
            page_idx += 1

        elif detail_type == "ids":
            messages_side = [
                {"type": "image_url", "image_url": {"url": data_uri}},
                {"type": "text", "text": SIDE_PROMPT}
            ]
            with st.spinner(f"Determining side for page {page_idx+1} (ids)..."):
                side_response, _ = call_vlm(messages_side, st.session_state.client)
            side = side_response.lower().strip()
            st.write(f"Page {page_idx+1} side: {side}")

            if side == "back":
                st.info(f"Page {page_idx+1} is a back page (out-of-order). Storing as pending back.")
                extraction_prompt = ID_vlm_prompt
                messages_extract_back = [
                    {"type": "image_url", "image_url": {"url": data_uri}},
                    {"type": "text", "text": extraction_prompt}
                ]
                with st.spinner(f"Extracting data from pending back (page {page_idx+1})..."):
                    back_response, _ = call_vlm(messages_extract_back, st.session_state.client)
                try:
                    cleaned_back = back_response.replace("```json", "").replace("```", "").strip()
                    pending_back = {
                        "page": page_idx+1,
                        "extracted": json.loads(cleaned_back),
                        "image": current_image
                    }
                except json.JSONDecodeError:
                    pending_back = {
                        "page": page_idx+1,
                        "extracted": {"raw_text": back_response},
                        "image": current_image
                    }
                page_idx += 1
                continue

            extraction_prompt = ID_vlm_prompt
            messages_extract_front = [
                {"type": "image_url", "image_url": {"url": data_uri}},
                {"type": "text", "text": extraction_prompt}
            ]
            with st.spinner(f"Extracting data from Emirates ID front (page {page_idx+1})..."):
                front_response, _ = call_vlm(messages_extract_front, st.session_state.client)
            try:
                cleaned_front = front_response.replace("```json", "").replace("```", "").strip()
                front_extracted = json.loads(cleaned_front)
            except json.JSONDecodeError:
                front_extracted = {"raw_text": front_response}

            pages_used = [page_idx+1]
            group_front_img = current_image

            if pending_back is not None:
                st.info(f"Merging pending back (page {pending_back['page']}) with current front (page {page_idx+1}).")
                merged = merge_ids_complete(front_extracted, pending_back["extracted"])
                pending_page = pending_back["page"]
                pending_back = None
                combined_extracted = merged
                pages_used = [pending_page, page_idx+1]
                page_idx += 1
            else:
                if page_idx + 1 < total_pages:
                    next_data_uri, next_image = get_data_uri_from_page(doc, page_idx+1)
                    messages_side_next = [
                        {"type": "image_url", "image_url": {"url": next_data_uri}},
                        {"type": "text", "text": SIDE_PROMPT}
                    ]
                    with st.spinner(f"Determining side for page {page_idx+2} (ids)..."):
                        side_next, _ = call_vlm(messages_side_next, st.session_state.client)
                    side_next = side_next.lower().strip()
                    st.write(f"Page {page_idx+2} side: {side_next}")
                    if side_next == "back":
                        ids_group = [page_idx+1, page_idx+2]
                        messages_extract_back = [
                            {"type": "image_url", "image_url": {"url": next_data_uri}},
                            {"type": "text", "text": extraction_prompt}
                        ]
                        with st.spinner(f"Extracting data from Emirates ID back (page {page_idx+2})..."):
                            back_response, _ = call_vlm(messages_extract_back, st.session_state.client)
                        try:
                            cleaned_back = back_response.replace("```json", "").replace("```", "").strip()
                            back_extracted = json.loads(cleaned_back)
                        except json.JSONDecodeError:
                            back_extracted = {"raw_text": back_response}
                        merged = merge_ids_complete(front_extracted, back_extracted)
                        combined_extracted = merged
                        pages_used = [page_idx+1, page_idx+2]
                        group_front_img = current_image
                        page_idx += 2
                    else:
                        combined_extracted = front_extracted
                        pages_used = [page_idx+1]
                        page_idx += 1
                else:
                    combined_extracted = front_extracted
                    pages_used = [page_idx+1]
                    page_idx += 1

            group = {
                "filename": filename,
                "doc_type": "ids",
                "pages": pages_used,
                "image_bytes": group_front_img,
                "extracted_data": combined_extracted,
                "original_pdf_bytes": pdf_bytes
            }
            groups.append(group)
        else:
            # For any other type (e.g., "personal" or any unrecognized type),
            # skip the page (or handle as desired) and advance the page index.
            st.info(f"Skipping page {page_idx+1} with unsupported type: {detail_type}")
            page_idx += 1

    doc.close()
    return groups


# ---------- SINGLE DOCUMENT PROCESSING FUNCTION ----------
def process_document(file_data, filename):
    if filename.lower().endswith("pdf"):
        file_data.seek(0)
        original_pdf_bytes = file_data.read()
        file_data.seek(0)
        data_uri, image_bytes = process_pdf_file(io.BytesIO(original_pdf_bytes))
    elif filename.lower().endswith(("jpg", "jpeg")):
        file_data.seek(0)
        original_bytes = file_data.read()
        image = Image.open(io.BytesIO(original_bytes))
        image = ImageOps.exif_transpose(image)
        if image.mode != "RGB":
            image = image.convert("RGB")
        image = image.resize((1024, 1024))
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG")
        resized_bytes = buffer.getvalue()
        encoded_image = base64.b64encode(resized_bytes).decode("utf-8")
        data_uri = f"data:image/jpeg;base64,{encoded_image}"
        image_bytes = resized_bytes
        original_pdf_bytes = None
    else:
        data_uri, image_bytes = process_image_file(file_data)
        original_pdf_bytes = None

    if not filename.lower().endswith("pdf"):
        if len(image_bytes) > THRESHOLD_BYTES:
            st.info(f"Original image size is {len(image_bytes)/(1024*1024):.2f} MB; downscaling to <=0.9MB...")
            adjusted_data_uri, adjusted_image_bytes, downsized_flag = downscale_until(image_bytes)
        else:
            adjusted_data_uri, adjusted_image_bytes = data_uri, image_bytes
            downsized_flag = False
    else:
        adjusted_data_uri, adjusted_image_bytes = data_uri, image_bytes
        downsized_flag = False

    messages = [
        {"type": "image_url", "image_url": {"url": adjusted_data_uri}},
        {"type": "text", "text": BROAD_CLASSIFICATION_PROMPT}
    ]
    with st.spinner("Performing broad classification..."):
        try:
            broad_result, _ = call_vlm(messages, st.session_state.client)
            st.write("Broad classification result:", broad_result)
        except Exception as e:
            st.write(e)
            broad_result = "others"
    broad_category = broad_result.lower().strip()

    if broad_category == "legal":
        second_prompt = LEGAL_PROMPT
    elif broad_category == "company":
        second_prompt = COMPANY_PROMPT
    elif broad_category == "bank":
        second_prompt = BANK_PROMPT
    elif broad_category == "property":
        second_prompt = PROPERTY_PROMPT
    elif broad_category == "personal":
        second_prompt = PERSONAL_PROMPT
    else:
        second_prompt = None

    if second_prompt:
        messages_second = [
            {"type": "image_url", "image_url": {"url": adjusted_data_uri}},
            {"type": "text", "text": second_prompt}
        ]
        with st.spinner("Performing detailed classification..."):
            try:
                detailed_result, _ = call_vlm(messages_second, st.session_state.client)
                st.write("Detailed classification result:", detailed_result)
            except Exception as e:
                st.write(e)
                detailed_result = "others"
    else:
        detailed_result = "others"
        
    if detailed_result.lower().strip() in ["legal",'property']:
        second_prompt = """
        - this document was classified as legal so i want to check if it is a POA or not.
        - power of attorney (POA) is considered personal document; you will find key words like "بيانات الوكيل" or "بيانات الموكل"
          and they may appear in tables or as a header with "توكيل".
        - if this document is POA, return only 'poa in lower.
        """
        messages_second = [
            {"type": "image_url", "image_url": {"url": adjusted_data_uri}},
            {"type": "text", "text": second_prompt}
        ]
        with st.spinner("Performing detailed classification for POA check..."):
            try:
                detailed_result, _ = call_vlm(messages_second, st.session_state.client)
                st.write("Detailed classification result:", detailed_result)
            except Exception as e:
                detailed_result = "others"
                
    elif detailed_result.lower().strip() in ["legal",'property']:
        second_prompt = """
        - this document was classified as legal so i want to check if it is a  pre title deed or not.
        - pre title deed must contain 'شهادة بيع مبدئي'.
        - if this document is a pre title deed return 'pre title deed' only in lower.
        """
        messages_second = [
            {"type": "image_url", "image_url": {"url": adjusted_data_uri}},
            {"type": "text", "text": second_prompt}
        ]
        with st.spinner("Performing detailed classification for POA check..."):
            try:
                detailed_result, _ = call_vlm(messages_second, st.session_state.client)
                st.write("Detailed classification result:", detailed_result)
            except Exception as e:
                detailed_result = "others"
    doc_type = detailed_result.lower().strip()

    if filename.lower().endswith("pdf"):
        file_data.seek(0)
        pdf_bytes = file_data.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        total_pages = doc.page_count
        doc.close()
        if total_pages > 1 and doc_type in ["ids", "passport", "residence visa"]:
            file_data.seek(0)
            groups = process_multi_document_ids(file_data, filename)
            # Return all groups, not just the first one.
            return groups

    if doc_type == "noc non objection certificate" or doc_type == "noc":
        extraction_prompt = NOC_vlm_prompt
    elif doc_type == "ids":
        extraction_prompt = ID_vlm_prompt
    elif doc_type == "cheques":
        extraction_prompt = cheque_vlm_prompt
    elif doc_type in ["mortgage letter", "liability letter","mortgage contract"]:
        extraction_prompt = MORTGAGE_LETTER_EXTRACTION_PROMPT
    elif doc_type in ["title deed (lease to own)", "title deed lease to own"]:
        extraction_prompt = TD_lease_vlm_prompt
    elif doc_type == "commercial license":
        extraction_prompt = company_license_prompt
    elif doc_type == "incumbency certificate":
        extraction_prompt = incumbency_prompt
    elif doc_type == "incorporation certificate":
        extraction_prompt = Incorporation_Certificate_prompt
    elif doc_type == "certificate of good standing":
        extraction_prompt = certificate_good_stand_prompt
    elif doc_type == "title deed":
        extraction_prompt = Titledeed__prompt 
    elif doc_type == "usufruct right certificate":
        extraction_prompt = usufruct_right_certificate_prompt
    elif doc_type == "pre title deed":
        extraction_prompt = preTitledeed__prompt 
    elif doc_type in ["title deed (lease finance)", "title deed lease finance"]:
        extraction_prompt = TD_finance_vlm_prompt
    elif doc_type in ['contract f', '**contract f**']:
        extraction_prompt = CONTRACT_F_PROMPT
    elif doc_type == 'passport':
        extraction_prompt = passport_prompt
    elif doc_type == 'residence visa':
        extraction_prompt = VISA_PROMPT
    elif doc_type == "initial contract of sale":
        # Read bytes
        file_data.seek(0)
        pdf_bytes = file_data.read()
        # Extract multi-page contract
        extracted = process_initial_contract(pdf_bytes, st.session_state.client)
        # Build result dict
        result = {
            'filename': filename,
            'doc_type': doc_type,
            'image_bytes': None,            # as you prefer
            'extracted_data': extracted,
            'original_pdf_bytes': pdf_bytes
        }
        return result
    elif doc_type in [
        "restrain property certificate", "initial contract of usufruct",
        "usufruct right certificate", "donation contract"  ]:
        extraction_prompt = TD_vlm_prompt
    elif 'customer statement' in doc_type.lower():
        doc_type='SOA'
    else:
        extraction_prompt = None
    if doc_type in ("customer statement", "soa","SOA"):
        
        # Just return an empty extraction for these two types
        result = {
            "filename": filename,
            "doc_type": 'soa',
            "image_bytes": adjusted_image_bytes,
            "extracted_data": {}
        }
        if filename.lower().endswith("pdf"):
            result["original_pdf_bytes"] = original_pdf_bytes
        return result
    if extraction_prompt and doc_type not in ['contract f','**contract f**','POA','poa']:
        if filename.lower().endswith("pdf"):
            zoom_factors = [1.75, 1, 0.75, 0.4]
            extraction_data_uri = None
            last_error = None
            for z in zoom_factors:
                try:
                    file_data.seek(0)
                    pdf_bytes = file_data.read()
                    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                    page = doc.load_page(0)
                    matrix = fitz.Matrix(z, z)
                    pix = page.get_pixmap(matrix=matrix)
                    highres_image_bytes = pix.tobytes("png")
                    encoded_image = base64.b64encode(highres_image_bytes).decode("utf-8")
                    extraction_data_uri = f"data:image/png;base64,{encoded_image}"
                    break
                except Exception as e:
                    last_error = e
            if extraction_data_uri is None:
                st.error(f"Failed to generate high-res image for PDF: {last_error}")
                extraction_data_uri = adjusted_data_uri
        else:
            extraction_data_uri = adjusted_data_uri
            if doc_type == "ids" and not downsized_flag:
                st.info("Document classified as 'ids' and not downscaled; upscaling image to 1.75x for extraction.")
                new_data_uri, new_image_bytes = upscale_image(adjusted_image_bytes, zoom=1.75, filetype="png")
                if new_data_uri is not None:
                    extraction_data_uri = new_data_uri

        extraction_image_data = extraction_data_uri.split(",")[1]
        extraction_bytes = base64.b64decode(extraction_image_data)
        EXTRACTION_MAX_BYTES = int(1.3 * 1024 * 1024)
        if len(extraction_bytes) > EXTRACTION_MAX_BYTES:
            st.info("Extraction image is too large; downscaling further for extraction.")
            new_data_uri, extraction_bytes, _ = downscale_until(extraction_bytes, threshold=EXTRACTION_MAX_BYTES)
            extraction_data_uri = new_data_uri

        messages_extraction = [
            {"type": "image_url", "image_url": {"url": extraction_data_uri}},
            {"type": "text", "text": extraction_prompt}
        ]
        with st.spinner("Extracting document data..."):
            try:
                extracted_data, _ = call_vlm(messages_extraction, st.session_state.client)
            except Exception as e:
                st.error(f"VLM extraction error: {e}")
                extracted_data = "{}"
    elif doc_type in ['contract f','**contract f**']:
        doc_type = 'contract f'
        file_data.seek(0)
        extracted_data = process_multipage_document(file_data, extraction_prompt)
        if filename.lower().endswith("pdf"):
            result = {
                "filename": filename,
                "doc_type": doc_type,
                "image_bytes": adjusted_image_bytes,
                "extracted_data": extracted_data
            }
            result["original_pdf_bytes"] = original_pdf_bytes
        return result
#     elif doc_type in ['POA','poa']:
#         doc_type = 'POA'
#         file_data.seek(0)
#         extracted_data = extract_data_from_pdf_pages_poa(file_data, LANGUAGE_PROMPT, POA_PROMPT_ENG, POA_PROMPT_ARABIC)
#         if filename.lower().endswith("pdf"):
#             result = {
#                 "filename": filename,
#                 "doc_type": doc_type,
#                 "image_bytes": adjusted_image_bytes,
#                 "extracted_data": extracted_data
#             }
#             result["original_pdf_bytes"] = original_pdf_bytes
#         return result
    elif doc_type in ['POA','poa']:
        doc_type = 'POA'
        # make sure we’re at the start of the stream
        file_data.seek(0)
        pdf_bytes = file_data.read()

        # write to a temporary file so our extractor can read via path
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp.flush()
            poa_json = extract_power_of_attorney(tmp.name, max_pages=4)

        result = {
            "filename": filename,
            "doc_type": doc_type,
            "image_bytes": adjusted_image_bytes,
            "extracted_data": poa_json,
            "original_pdf_bytes": pdf_bytes
        }
        return result
    else:
        extracted_data = "{}"

    result = {
        "filename": filename,
        "doc_type": detailed_result.lower().strip(),
        "image_bytes": adjusted_image_bytes,
        "extracted_data": extracted_data
    }
    if filename.lower().endswith("pdf"):
        result["original_pdf_bytes"] = original_pdf_bytes
    
    return result
# ---------- STREAMLIT UI ----------
# ---------- STREAMLIT UI ----------
st.markdown("""
    <style>
      .navbar {
        background-color: #ffffff;
        padding: 0.5rem 1rem;
        display: flex;
        align-items: center;
        border-bottom: 1px solid #e0e0e0;
      }
      .navbar img {
        height: 40px;
      }
      .navbar .title {
        flex: 1;
        text-align: center;
        font-size: 1.5rem;
        font-weight: bold;
        margin-right: 40px;  /* to offset the logo width */
      }
    </style>
    <div class="navbar">
      <img src="https://bunny-wp-pullzone-x8psmhth4d.b-cdn.net/wp-content/uploads/2022/12/Asset-1.svg" alt="Logo">
      <div class="title">Injaz OCR System</div>
    </div>
""", unsafe_allow_html=True)

st.markdown("Upload image(s) or PDF(s) for OCR, classification, extraction, and saving as PDFs.")

uploaded_files = st.file_uploader("Upload files", type=["png", "jpg", "jpeg", "pdf"], accept_multiple_files=True)

if st.button("Submit") and uploaded_files:
    st.session_state.results = []
    overall_start_time = time.time()
    st.session_state.documents_saved = False
    for uploaded_file in uploaded_files:
        with st.spinner(f"Processing file: {uploaded_file.name}"):
            try:
                result = process_document(uploaded_file, uploaded_file.name)
                if isinstance(result, list):
                    st.session_state.results.extend(result)
                else:
                    st.session_state.results.append(result)
            except Exception as e:
                st.error(f"Error processing file {uploaded_file.name}: {e}")
    overall_end_time = time.time()
    st.session_state.current_index = 0
    st.success(f"Total processing time: {overall_end_time - overall_start_time:.2f} seconds")
    
if st.button("Save All Documents") and not st.session_state.get("documents_saved", False):
    for result in st.session_state.results:
        save_document(result)
    st.session_state.documents_saved = True
    st.success("Documents saved successfully.")

if "results" in st.session_state and st.session_state.results:

    # — Group roles & validations under one section —
    st.markdown("### Roles and validations")
    # 1) Roles accordion
    with st.expander("Roles and validations", expanded=True):
        render_person_roles_editor(st.session_state.results)


    # 2) Validation accordion (skipping IDs & Passports)
    validation_outcomes = validate_documents(st.session_state.results)
    skip = {"IDs", "Passports"}
    to_show = {k: v for k, v in validation_outcomes.items() if k not in skip}
    if to_show:
        with st.expander("Validation Results", expanded=False):
            for key, message in to_show.items():
                st.write(f"**{key}:** {message}")
    

    with st.expander("Procedure & Required Documents", expanded=True):
        # 1) List all procedures in the same order/labels your function recognizes
        PROCEDURES = [
            "Blocking",
            "Sell pre Registration",
            "Company Registration",
            "Sell + Mortgage Transfer",
            "Transfer sell",
            "Others"
        ]

        # 2) Auto‑detect first pass (no override)
        auto = suggest_procedure(st.session_state.results)
        inferred = auto.get("procedure", "others")

        # 3) Determine default index (fall back to 0 if not found)
        default_idx = PROCEDURES.index(inferred) if inferred in PROCEDURES else 0

        # 4) Let the user pick (inside the accordion)
        selected = st.selectbox(
            "Choose procedure to inspect:",
            PROCEDURES,
            index=default_idx,
            key="proc_selector"
        )

        # 5) Compute requirements/missing for the chosen procedure
        proc = suggest_procedure(st.session_state.results, procedure_name=selected)
        required = proc.get("required_documents", [])
        missing  = proc.get("missing_documents", [])

        # 6) Side‑by‑side display
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Found documents**")
            have = [d for d in required if d not in missing]
            if have:
                for doc in have:
                    st.write(f"- {doc}")
            else:
                st.write("_None_")
        with col2:
            st.markdown("**Missing documents**")
            if missing:
                for doc in missing:
                    st.write(f"- {doc}")
            else:
                st.success("All required documents are present!")
    st.markdown("### Document Review")
    options = []
    for i, doc in enumerate(st.session_state.results, start=1):
        dt = doc.get("doc_type", "document").lower().strip()
        raw = doc.get("extracted_data", {})

        # 1) Normalize into a dict, even if it’s wrapped in raw_text with backticks
        if isinstance(raw, str):
            try:
                data = json.loads(raw)
            except:
                data = {"raw_text": raw}
        else:
            data = raw

        # If data only has raw_text, try stripping fences and re-loading
        if "raw_text" in data and isinstance(data["raw_text"], str):
            inner = clean_json_string(data["raw_text"])
            try:
                data = json.loads(inner)
            except:
                pass

        # 2) Pull out the person name for ID‑style docs
        if dt == "ids":
            person = data.get("front", {}).get("name_english", "")
        elif dt == "passport":
            person = data.get("fullname", "")
        elif dt == "residence visa":
            person = data.get("full_name", "") or data.get("arabic_name", "")
        else:
            person = ""

        # Fallback if still empty
        person_name = person.strip() or "Unknown"

        # 3) Build the label WITHOUT the original filename
        if dt in ['ids','passport','residence visa']:
            label = f"{i}.{dt} — {person_name}"
        else:
            label = f"{i}.{dt}"
        options.append(label)

    selected_option = st.selectbox("Pick a sub-document:", options)
    selected_index = options.index(selected_option)
    current = st.session_state.results[selected_index]
    
    # Display PDF or image from the selected document

    col_pdf, col_ocr = st.columns(2)


    with col_pdf:
        filename = current.get("filename", "document")
        doc_type = current.get("doc_type", "document")
        st.write(f"{filename} classified as: {doc_type}")

        # Image fallback
        if current.get("image_bytes") and not current.get("original_pdf_bytes"):
            st.image(
                current["image_bytes"],
                caption=f"{filename} (Image)",
                use_container_width=True
            )

        # PDF viewer
        elif current.get("original_pdf_bytes"):
            pdf_bytes = current["original_pdf_bytes"]

            # Render pages → base64
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            page_imgs = []
            for page in doc:
                pix = page.get_pixmap(matrix=fitz.Matrix(1, 1))
                b64 = base64.b64encode(pix.tobytes("png")).decode("utf-8")
                page_imgs.append(f"data:image/png;base64,{b64}")
            doc.close()

            js_pages = json.dumps(page_imgs)
            n_pages = len(page_imgs)

            html = f"""
    <style>
      .viewer-container {{
        position: relative;
        width:100%; max-width:800px;
        height:1200px; margin:auto;
        border:1px solid #ccc;
      }}
      #docImg {{
        width:100%; height:100%;
        object-fit:contain;
        transform-origin: center center;
        transition: transform 0.2s;
        cursor: zoom-in;
      }}
      .controls {{
        position: absolute; bottom:10px; left:50%;
        transform: translateX(-50%);
        background:rgba(255,255,255,0.9);
        padding:8px; border-radius:6px;
        display:flex; gap:6px; z-index:999;
      }}
      .controls button {{
        padding:6px 10px; border:none;
        border-radius:4px; cursor:pointer;
      }}
      .nav {{ background:#007bff; color:#fff; }}
      .rotate {{ background:#6c757d; color:#fff; }}
      .reset {{ background:#dc3545; color:#fff; }}
    </style>

    <div class="viewer-container">
      <img id="docImg" src="" />
      <div class="controls">
        <button id="prevBtn" class="nav">← Prev</button>
        <span id="pageDisplay">1/{n_pages}</span>
        <button id="nextBtn" class="nav">Next →</button>
        <button id="rotateBtn" class="rotate">⟳</button>
        <button id="resetBtn" class="reset">Reset Zoom</button>
      </div>
    </div>

    <script>
    (function(){{
      const pages = {js_pages};
      let idx = 0, rot = 0, zoom = 1;
      const img = document.getElementById("docImg");
      const disp = document.getElementById("pageDisplay");

      function render() {{
        img.src = pages[idx];
        img.style.transform = `scale(${{zoom}}) rotate(${{rot}}deg)`;
        disp.textContent = `${{idx+1}}/{n_pages}`;
        img.style.cursor = zoom>1 ? 'zoom-out' : 'zoom-in';
      }}

      function resetZoom() {{
        zoom = 1;
        img.style.transformOrigin = 'center center';
      }}
      function setZoomAt(x, y) {{
        resetZoom();
        zoom = 2;
        const rect = img.getBoundingClientRect();
        const px = ((x - rect.left)/rect.width)*100;
        const py = ((y - rect.top)/rect.height)*100;
        img.style.transformOrigin = `${{px}}% ${{py}}%`;
      }}

      document.getElementById("prevBtn").onclick = function() {{
        if(idx>0) idx--;
        resetZoom();
        render();
      }};
      document.getElementById("nextBtn").onclick = function() {{
        if(idx<pages.length-1) idx++;
        resetZoom();
        render();
      }};
      document.getElementById("rotateBtn").onclick = function() {{
        rot = (rot + 90)%360;
        render();
      }};
      document.getElementById("resetBtn").onclick = function() {{
        resetZoom();
        render();
      }};

      img.addEventListener("click", function(e) {{
        if(zoom===1) {{
          setZoomAt(e.clientX, e.clientY);
        }} else {{
          resetZoom();
        }}
        render();
      }});

      render();
    }})();
    </script>
    """

            # set height=1200 here
            components.html(html, height=1200, scrolling=False)

        else:
            st.warning("No preview available for this document.")
        with col_ocr:
            st.markdown("### Extracted Data")
            raw = current.get("extracted_data", "")
            if "contract f" in current.get("doc_type","").lower():
                if isinstance(raw, str):
                    try:
                        raw = json.loads(clean_json_string(raw))
                    except:
                        raw = {}
                if isinstance(raw, dict):
                    pages = preprocess_pages(raw, clean_json_string)
                    raw = unify_contract_f(pages, clean_json_string)
            elif "commercial license" in current.get("doc_type","").lower():
                raw = unify_commercial_license(raw, clean_json_string)
            elif current.get("doc_type","").lower()=='title deed':
                raw = unify_title_deed(raw, clean_json_string)
            elif current.get("doc_type","").lower()=='usufruct right certificate':
                raw = unify_usufruct_right_certificate(raw, clean_json_string)
            elif current.get("doc_type","").lower()=='pre title deed':
                raw = unify_pre_title_deed(raw, clean_json_string)
            elif current.get("doc_type","").lower() in ['title deed lease finance'] :
                raw = unify_title_deed_lease_finance(raw, clean_json_string)
            elif current.get("doc_type","").lower() in ['title deed lease to own'] :
                raw = unify_title_deed_lease_to_own(raw, clean_json_string)
            elif current.get("doc_type","").lower() in ['cheques'] :
                raw = unify_cheques(raw, clean_json_string)
            elif current.get("doc_type","").lower() =='noc non objection certificate' :
                raw = unify_noc(raw, clean_json_string)
                st.session_state.results[selected_index]["extracted_data"] = raw
    
            extracted_raw = raw

            display_mode = "Form"
            if display_mode == "Form":
                render_data_form(extracted_raw, selected_index)

    # Optionally, you can display the filename/index information
    st.markdown(f"Selected Document: {selected_index + 1} of {len(st.session_state.results)}")
    st.markdown(f"Document {st.session_state.current_index + 1} of {len(st.session_state.results)}")


