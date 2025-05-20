# vlm_utils.py

import time
import base64
import io
from io import BytesIO
from openai import OpenAI
from PIL import Image, ImageOps
import json
import streamlit as st
import fitz  # PyMuPDF
from scripts.config.prompts_legal import *
from scripts.utils.json_utils import *

THRESHOLD_BYTES = int(1.3 * 1024 * 1024)

def call_vlm(messages, client):
    """
    Calls the VLM with the provided messages and returns the streamed response text and processing time.
    """
    start_time = time.time()
    chat_completion = client.chat.completions.create(
        model="tgi",
        messages=[{"role": "user", "content": messages}],
        temperature=0,
        max_tokens=1024,
        stream=True,
        seed=2025
    )
    response_text = ""
    for message in chat_completion:
        chunk = message.choices[0].delta.content
        response_text += chunk
    end_time = time.time()
    return response_text.strip(), end_time - start_time

def process_image_file(file_data, target_size=None):
    """
    Opens an image file (provided as a file-like object), optionally resizes it, converts it to PNG bytes,
    and returns a data URI and the image bytes.
    """
    try:
        img = Image.open(file_data)
        img = ImageOps.exif_transpose(img)
        if target_size:
            img = img.resize(target_size)
        if img.mode != "RGB":
            img = img.convert("RGB")
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        image_bytes = buffered.getvalue()
        encoded_image = base64.b64encode(image_bytes).decode("utf-8")
        data_uri = f"data:image/png;base64,{encoded_image}"
        return data_uri, image_bytes
    except Exception as e:
        raise Exception(f"Error processing image file: {e}")

def process_pdf_file(file_data, target_size=(1024, 1024)):
    """
    Converts the first page of a PDF (provided as a file-like object) into an image using PyMuPDF.
    The page is rendered with an explicit zoom factor, then processed with PIL to match the same
    quality and dimensions as image files.
    Returns a data URI and the processed image bytes.
    """
    try:
        # Read PDF bytes and reset pointer if needed.
        pdf_bytes = file_data.read()
        if not pdf_bytes:
            raise Exception("PDF file is empty or could not be read.")

        # Open the PDF from bytes.
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        # Load the first page and render with an explicit zoom (improves resolution).
        page = doc.load_page(0)
        matrix = fitz.Matrix(1.75, 1.75)
        pix = page.get_pixmap(matrix=matrix)
        image_bytes = pix.tobytes("png")
        doc.close()


        img = Image.open(BytesIO(image_bytes))
        img = ImageOps.exif_transpose(img)  # Correct for any EXIF orientation issues.
        if img.mode != "RGB":
            img = img.convert("RGB")
        # Resize to the target dimensions.
        img = img.resize(target_size)
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        processed_bytes = buffered.getvalue()

        # Downscale if needed using the pre-existing THRESHOLD_BYTES.
        if len(processed_bytes) > THRESHOLD_BYTES:
            data_uri, processed_bytes, _ = downscale_until(processed_bytes)
        else:
            encoded_image = base64.b64encode(processed_bytes).decode("utf-8")
            data_uri = f"data:image/png;base64,{encoded_image}"
        
        return data_uri, processed_bytes
    except Exception as e:
        raise Exception(f"Error processing PDF file: {e}")


def downscale_until(image_bytes, threshold=THRESHOLD_BYTES, scale_factor=1, filetype="png"):
    """
    Repeatedly downscale the image by scale_factor until its size is below the threshold.
    Returns a tuple (data_uri, new_image_bytes, downsized_flag).
    """
    downsized = False
    current_bytes = image_bytes
    while len(current_bytes) > threshold:
        try:
            doc = fitz.open(stream=current_bytes, filetype=filetype)
            # For downscaling, use a matrix with the provided scale_factor.
            page = doc[0]
            matrix = fitz.Matrix(scale_factor, scale_factor)
            pix = page.get_pixmap(matrix=matrix)
            current_bytes = pix.tobytes("png")
            downsized = True
        except Exception as ex:
            st.write("Downscaling error:", ex)
            break
    encoded_image = base64.b64encode(current_bytes).decode("utf-8")
    data_uri = f"data:image/png;base64,{encoded_image}"
    return data_uri, current_bytes, downsized



def process_multipage_document_old(file_data, extraction_prompt, max_page=6):
    """
    Extracts text data from the first few pages of a PDF by converting them to images
    and sending each to the VLM. Returns a JSON string of combined, cleaned results.
    """
    combined_results = {}
    doc = fitz.open(stream=file_data.read(), filetype="pdf")

    for page_num in range(min(max_page, len(doc))):
        page = doc.load_page(page_num)
        pix = page.get_pixmap(matrix=fitz.Matrix(1.75, 1.75))
        img_bytes = pix.tobytes("png")
        uri = f"data:image/png;base64,{base64.b64encode(img_bytes).decode()}"

        messages = [
            {"type": "image_url", "image_url": {"url": uri}},
            {"type": "text",      "text": extraction_prompt}
        ]
        with st.spinner(f"Extracting data from page {page_num+1}/{max_page}…"):
            client = OpenAI(
                base_url="https://mf32siy1syuf3src.us-east-1.aws.endpoints.huggingface.cloud/v1/",
                api_key="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"
            )
            raw_output, _ = call_vlm(messages, client)

        # 1. Remove any explicit fences (we could also let post_processing do this)
        stripped = raw_output.replace("```json", "").replace("```", "").strip()
        page_data = post_processing(stripped)

        combined_results[f"Page_{page_num+1}"] = page_data

    # Return a JSON string for whatever downstream uses you have
    return json.dumps(combined_results, indent=2, ensure_ascii=False)

def process_multipage_document(file_data, extraction_prompt, max_page=6):
    """
    Extracts text data from the first few pages of a PDF by converting them to images
    and sending each to the VLM. Returns a JSON string of combined, cleaned results.
    """
    import base64
    from openai import APIStatusError

    combined_results = {}
    doc = fitz.open(stream=file_data.read(), filetype="pdf")

    for page_num in range(min(max_page, len(doc))):
        page = doc.load_page(page_num)
        pix = page.get_pixmap(matrix=fitz.Matrix(1.75, 1.75))
        img_bytes = pix.tobytes("png")
        uri = f"data:image/png;base64,{base64.b64encode(img_bytes).decode()}"

        messages = [
            {"type": "image_url", "image_url": {"url": uri}},
            {"type": "text",      "text": extraction_prompt}
        ]

        with st.spinner(f"Extracting data from page {page_num+1}/{max_page}…"):
            client = OpenAI(
                base_url="https://mf32siy1syuf3src.us-east-1.aws.endpoints.huggingface.cloud/v1/",
                api_key="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"
            )
            try:
                # First attempt
                raw_output, _ = call_vlm(messages, client)

            except APIStatusError as e:
                # If request body too large, downscale and retry
                if "length limit exceeded" in str(e).lower():
                    st.warning(f"Page {page_num+1}: payload too large—downscaling and retrying…")

                    # Decode original bytes, downscale to <100 KB
                    original_bytes = base64.b64decode(uri.split(",", 1)[1])
                    new_uri, small_bytes, _ = downscale_until(
                        original_bytes,
                        threshold=100_000,
                        scale_factor=0.5
                    )

                    # Update the message payload
                    messages[0]["image_url"]["url"] = new_uri

                    # Retry the VLM call
                    raw_output, _ = call_vlm(messages, client)
                else:
                    # Re-raise unexpected errors
                    raise

        # Clean and parse the response
        stripped = raw_output.replace("```json", "").replace("```", "").strip()
        page_data = post_processing(stripped)
        combined_results[f"Page_{page_num+1}"] = page_data

    doc.close()
    return json.dumps(combined_results, indent=2, ensure_ascii=False)





def upscale_image(image_bytes, zoom=1.75, filetype="png"):
    """
    Upscales the image using the specified zoom factor.
    Returns a tuple (data_uri, new_image_bytes). In case of failure, returns the original image.
    """
    try:
        doc = fitz.open(stream=image_bytes, filetype=filetype)
        page = doc[0]
        matrix = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=matrix)
        new_bytes = pix.tobytes("png")
        encoded_image = base64.b64encode(new_bytes).decode("utf-8")
        data_uri = f"data:image/png;base64,{encoded_image}"
        return data_uri, new_bytes
    except Exception as ex:
        st.write("Upscaling failed:", ex)
        encoded_image = base64.b64encode(image_bytes).decode("utf-8")
        return f"data:image/png;base64,{encoded_image}", image_bytes

def safe_json_loads(text):
    """
    Cleans and loads a JSON string by removing common markdown formatting.
    If the input is already a dict or list, returns it unchanged.
    Returns an empty dict if parsing fails.
    """
    # If it’s already parsed, just return it
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


def pdf_page_to_png(doc, page_num, zoom=1.75):
    """
    Converts a specific PDF page (from a fitz.Document) to PNG image bytes.
    """
    page = doc.load_page(page_num)
    matrix = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=matrix)
    return pix.tobytes("png")






def create_pdf_from_pages(original_pdf_bytes, page_numbers):
    """
    Given the original PDF bytes and a list of 1-indexed page numbers,
    creates a new PDF containing only those pages and returns its bytes.
    """
    src_doc = fitz.open(stream=original_pdf_bytes, filetype="pdf")
    new_doc = fitz.open()  # create a new empty PDF document
    for p in page_numbers:
        new_doc.insert_pdf(src_doc, from_page=p-1, to_page=p-1)
    pdf_bytes = new_doc.write()  # get the bytes of the new PDF
    new_doc.close()
    src_doc.close()
    return pdf_bytes


def process_initial_contract(pdf_bytes: bytes, client: OpenAI, max_pages: int = None) -> dict:
    """
    Extracts and combines data from all pages of an Initial Contract of Sale PDF.
    First page extracts full contract + initial parties.
    Subsequent pages: detect PARTIES section, then extract parties and vouchers.
    In combining, only keep 'sellers' and 'buyers', discarding 'voucher_list'.
    Return ordered dict: contract fields first, then sellers and buyers.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages_to_check = doc.page_count if max_pages is None else min(doc.page_count, max_pages)

    combined = {'sellers': [], 'buyers': []}

    # Process first page: full contract + parties
    if pages_to_check > 0:
        page0 = doc.load_page(0)
        pix = page0.get_pixmap(matrix=fitz.Matrix(1.75, 1.75))
        img0 = pix.tobytes("png")
        if len(img0) > THRESHOLD_BYTES:
            uri0, img0, _ = downscale_until(img0)
        else:
            uri0 = "data:image/png;base64," + base64.b64encode(img0).decode()
        messages0 = [
            {"type": "image_url", "image_url": {"url": uri0}},
            {"type": "text", "text": INITIAL_CONTRACT_OF_SALE_PROMPT}
        ]
        raw0, _ = call_vlm(messages0, client)
        cleaned0 = raw0.strip().lstrip("```json").rstrip("```").strip()
#         st.write(cleaned0)
        try:
            data0 = json.loads(cleaned0)
        except json.JSONDecodeError:
            data0 = {}
        # Merge contract fields and initial parties
        for k, v in data0.items():
            if k in ('sellers', 'buyers'):
                combined[k].extend(v)
            else:
                combined[k] = v

    # Process subsequent pages for additional parties & voucher_list
    for page_num in range(1, pages_to_check):
        page = doc.load_page(page_num)
        # render page
        pix = page.get_pixmap(matrix=fitz.Matrix(1.75, 1.75))
        img = pix.tobytes("png")
        if len(img) > THRESHOLD_BYTES:
            uri, img, _ = downscale_until(img)
        else:
            uri = "data:image/png;base64," + base64.b64encode(img).decode()

        # Detect PARTIES section
        resp, _ = call_vlm([
            {"type": "image_url", "image_url": {"url": uri}},
            {"type": "text", "text": detect_parties_prompt}
        ], client)
#         st.write(resp)
        if resp.strip().lower() != 'yes':
            continue

        # Extract parties and vouchers
        raw, _ = call_vlm([
            {"type": "image_url", "image_url": {"url": uri}},
            {"type": "text", "text": extract_parties_and_vouchers_prompt}
        ], client)
        cleaned = raw.strip().lstrip("```json").rstrip("```").strip()
#         st.write(cleaned)
        try:
            page_data = json.loads(cleaned)
        except json.JSONDecodeError:
            continue

        # Append found parties
        combined['sellers'].extend(page_data.get('sellers', []))
        combined['buyers'].extend(page_data.get('buyers', []))

    doc.close()

    # Build ordered result
    ordered = {}
    for field in [
        'contract_number', 'contract_date', 'project_name', 'developer_name',
        'property_name', 'net_sold_area', 'common_area', 'property_value',
        'property_type', 'land_number', 'area', 'mortgage_status'
    ]:
        if field in combined:
            ordered[field] = combined[field]
    ordered['sellers'] = combined.get('sellers', [])
    ordered['buyers'] = combined.get('buyers', [])

    return ordered
