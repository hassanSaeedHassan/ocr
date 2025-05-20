import streamlit as st
import time
import fitz  # PyMuPDF
import base64
import tempfile
import io
import os
import json
import zipfile
from datetime import datetime
from PIL import Image, ImageOps
from scripts.validation import *    
from scripts.vlm_utils import *      
from openai import OpenAI
from scripts.config import *
from scripts.extractors.poa_extractor import *
from scripts.extractors.id_extractor import *
from scripts.ui_helpers.ui_functions import *
from scripts.ui_helpers.ui_render import *
from scripts.unifiers import *
from scripts.procedure_recognition import suggest_procedure
import streamlit.components.v1 as components
from openai import APIStatusError
# ---------- SINGLE DOCUMENT PROCESSING FUNCTION ----------
THRESHOLD_BYTES = int(1.3 * 1024 * 1024)
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
                extraction_data_uri = adjusted_data_uri
        else:
            extraction_data_uri = adjusted_data_uri
            if doc_type == "ids" and not downsized_flag:
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
                extracted_data = extracted_data.replace("```json", "").replace("```", "").strip()
                extracted_data = post_processing(extracted_data)
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
        # build a PDF containing all pages
        all_pages = list(
            range(
                1,
                fitz.open(stream=original_pdf_bytes, filetype="pdf")
                   .page_count
                + 1
            )
        )
        result["pdf_bytes"] = create_pdf_from_pages(original_pdf_bytes, all_pages)
    
    return result
