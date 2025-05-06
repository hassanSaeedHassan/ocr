import base64
import json
import fitz  # PyMuPDF
from openai import OpenAI
import re
import streamlit as st
from scripts.vlm_utils import safe_json_loads,create_pdf_from_pages
from scripts.config.individual_prompts import *
from scripts.config.prompts import PERSONAL_PROMPT
from scripts.vlm_utils import (
    call_vlm,
    pdf_page_to_png,
    downscale_until,
    THRESHOLD_BYTES
)


def get_data_uri_from_page(doc, page_num, zoom=1.75):
    page_bytes = pdf_page_to_png(doc, page_num, zoom=zoom)
    data_uri, image_bytes, _ = downscale_until(page_bytes)
    return data_uri, image_bytes



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
    SIDE_PROMPT = """
Inspect the ID image. If you see the 3‑line machine‑readable zone (MRZ) at the bottom and don't have portrait photo, answer 'back'.
If you see the portrait photo, name fields and no MRZ, answer 'front'.
If both are visible, answer 'both'.
Return exactly one word: 'front', 'back', or 'both'.
"""

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

            pages = [page_idx + 1]
            sliced_pdf = create_pdf_from_pages(pdf_bytes, pages)
        
            group = {
                "filename": filename,
                "doc_type": detail_type,
                "pages": pages,
                "image_bytes": current_image,
                "extracted_data": extracted,
                "original_pdf_bytes": pdf_bytes,
                "pdf_bytes": sliced_pdf        # ← use 'pages' not 'pages_used'
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
                "original_pdf_bytes": pdf_bytes,
                "pdf_bytes": create_pdf_from_pages(pdf_bytes, pages_used)
            }
            groups.append(group)
        else:
            # For any other type (e.g., "personal" or any unrecognized type),
            # skip the page (or handle as desired) and advance the page index.
            st.info(f"Skipping page {page_idx+1} with unsupported type: {detail_type}")
            page_idx += 1

    doc.close()
    return groups