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

def process_pdf_file(file_data, target_size=None):
    """
    Converts the first page of a PDF (provided as a file-like object) into an image using PyMuPDF.
    Ensures that the PDF is processed like an image. Returns a data URI and the image bytes.
    """
    try:
        # Read PDF bytes and reset pointer if needed
        pdf_bytes = file_data.read()
        if not pdf_bytes:
            raise Exception("PDF file is empty or could not be read.")
        
        # Open the PDF from bytes
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        # Load the first page
        page = doc.load_page(0)
        # Render page to a pixmap (PNG format)
        pix = page.get_pixmap()
        image_bytes = pix.tobytes("png")
        
        # If a target size is provided, resize the image using PIL.
        if target_size:
            img = Image.open(BytesIO(image_bytes))
            img = img.resize(target_size)
            buffered = BytesIO()
            img.save(buffered, format="PNG")
            image_bytes = buffered.getvalue()
        
        # Downscale if image is larger than the maximum allowed size.
        MAX_IMAGE_SIZE = int(1 * 1024 * 1024)  # Adjust threshold as needed.
        if len(image_bytes) > MAX_IMAGE_SIZE:
            data_uri, image_bytes, _ = downscale_until(image_bytes, threshold=MAX_IMAGE_SIZE)
        else:
            encoded_image = base64.b64encode(image_bytes).decode("utf-8")
            data_uri = f"data:image/png;base64,{encoded_image}"
        
        return data_uri, image_bytes
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

def process_multipage_document(file_data, extraction_prompt, max_page=5):
    """
    Extracts text data from the first few pages of a PDF by converting them to images and sending each
    to the VLM. Returns a JSON string of combined results.
    """
    combined_results = {}
    doc = fitz.open(stream=file_data.read(), filetype="pdf")
    for page_num in range(min(max_page, len(doc))):
        page = doc.load_page(page_num)
        pix = page.get_pixmap(matrix=fitz.Matrix(1.75, 1.75))
        page_image_bytes = pix.tobytes("png")
        encoded_image = base64.b64encode(page_image_bytes).decode("utf-8")
        page_data_uri = f"data:image/png;base64,{encoded_image}"

        messages_extraction = [
            {"type": "image_url", "image_url": {"url": page_data_uri}},
            {"type": "text", "text": extraction_prompt}
        ]

        with st.spinner(f"Extracting data from page {page_num + 1}/{max_page}..."):
            client = OpenAI(
                base_url="https://mf32siy1syuf3src.us-east-1.aws.endpoints.huggingface.cloud/v1/",
                api_key="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"
            )
            extracted_data, _ = call_vlm(messages_extraction, client)
            cleaned_data = extracted_data.replace('```json', '').replace('```', '').strip()
            try:
                page_data_json = json.loads(cleaned_data)
            except json.JSONDecodeError:
                page_data_json = {"raw_text": cleaned_data}

            combined_results[f"Page_{page_num + 1}"] = page_data_json

    return json.dumps(combined_results, indent=2)

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
    Returns an empty dict if parsing fails.
    """
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

def extract_data_from_pdf_pages_poa(pdf_path, language_prompt, extraction_prompt_eng, extraction_prompt_arabic, max_pages=None):
    """
    Loops through PDF pages (up to max_pages if provided) to determine which page contains
    the required English data. If found, it uses the English extraction prompt; otherwise,
    it falls back to Arabic extraction on page 1.
    """
    # Open the PDF document.
    doc = fitz.open(stream=pdf_path.read(), filetype="pdf")
    total_pages = doc.page_count
    pages_to_check = total_pages if max_pages is None else min(max_pages, total_pages)

    # Initialize the VLM client.
    client = OpenAI(
        base_url="https://mf32siy1syuf3src.us-east-1.aws.endpoints.huggingface.cloud/v1/",
        api_key="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"
    )

    english_found = False
    extracted_data = ""

    # Loop through the pages to check for English data.
    for page_num in range(pages_to_check):
        st.write(f"Processing page {page_num + 1} of {pages_to_check} for English check...")
        image_bytes = pdf_page_to_png(doc, page_num)

        # Downscale if the image is larger than the threshold.
        if len(image_bytes) > THRESHOLD_BYTES:
            data_uri, image_bytes, downsized = downscale_until(image_bytes)
        else:
            encoded = base64.b64encode(image_bytes).decode("utf-8")
            data_uri = f"data:image/png;base64,{encoded}"

        # Build messages for language detection.
        messages_lang = [
            {"type": "image_url", "image_url": {"url": data_uri}},
            {"type": "text", "text": language_prompt}
        ]
        lang_response, _ = call_vlm(messages_lang, client)

        # Check if the language response indicates English.
        if "yes" in lang_response.lower():
            st.write(f"Page {page_num + 1} is in English. Proceeding with English extraction.")
            messages_extract = [
                {"type": "image_url", "image_url": {"url": data_uri}},
                {"type": "text", "text": extraction_prompt_eng}
            ]
            extracted_data, _ = call_vlm(messages_extract, client)
            english_found = True
            break
        else:
            st.write(f"Page {page_num + 1} does not have the data in English.")

    # If no English page is found, perform Arabic extraction on page 1.
    if not english_found:
        st.write("No English data found. Proceeding with Arabic extraction on page 1.")
        image_bytes = pdf_page_to_png(doc, 0)
        if len(image_bytes) > THRESHOLD_BYTES:
            data_uri, image_bytes, downsized = downscale_until(image_bytes)
        else:
            encoded = base64.b64encode(image_bytes).decode("utf-8")
            data_uri = f"data:image/png;base64,{encoded}"
        messages_extract = [
            {"type": "image_url", "image_url": {"url": data_uri}},
            {"type": "text", "text": extraction_prompt_arabic}
        ]
        extracted_data, _ = call_vlm(messages_extract, client)

    return extracted_data

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
