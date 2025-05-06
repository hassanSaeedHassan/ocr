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
# ----------------- SET AUTHENTICATION & CLIENT IN SESSION ------------------
if "client" not in st.session_state:
    st.session_state.client = OpenAI(
        base_url = "https://mf32siy1syuf3src.us-east-1.aws.endpoints.huggingface.cloud/v1/",
        api_key="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",)
if "token" not in st.session_state:
    st.session_state.token='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'
st.set_page_config(
    page_title="Injaz OCR System",
    page_icon="https://bunny-wp-pullzone-x8psmhth4d.b-cdn.net/wp-content/uploads/2022/12/Asset-1.svg",
    layout="wide")
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

    # build an in-memory ZIP of every standalone PDF
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        for idx, result in enumerate(st.session_state.results, start=1):
            pdf_data = result.get("pdf_bytes", result.get("original_pdf_bytes"))
            # give each file a unique name
            name = f"{result['filename']}_{result['doc_type']}_{idx}.pdf"
            zf.writestr(name, pdf_data)
    zip_buffer.seek(0)

    # stream it to the browser
    st.download_button(
        "Download All Documents as ZIP",
        data=zip_buffer,
        file_name="documents.zip",
        mime="application/zip",
    )
    st.session_state.documents_saved = True

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
                # Section header
                st.markdown(f"**{key}:**")
                # If it's a list, render each entry as a bullet
                if isinstance(message, list):
                    for line in message:
                        st.markdown(f"- {line}")
                else:
                    # single‐line message
                    st.markdown(f"- {message}")



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
            key="proc_selector" )
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
        person_name = person.strip() or "Unknown"
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

        # 1) Build a list of Data‑URI strings for each “page”:
        page_imgs = []

        # If it’s just an image, show it as one “page”
        if current.get("image_bytes") and not current.get("original_pdf_bytes"):
            img_bytes = current["image_bytes"]
            # you can detect whether it's PNG or JPEG if you like; here we assume PNG
            b64 = base64.b64encode(img_bytes).decode("utf-8")
            page_imgs = [f"data:image/png;base64,{b64}"]

        # Otherwise if it’s a PDF, render each page to PNG
        elif current.get("pdf_bytes") or current.get("original_pdf_bytes"):
            pdf_bytes = current.get("pdf_bytes", current["original_pdf_bytes"])
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            for page in doc:
                pix = page.get_pixmap(matrix=fitz.Matrix(1, 1))
                b64 = base64.b64encode(pix.tobytes("png")).decode("utf-8")
                page_imgs.append(f"data:image/png;base64,{b64}")
            doc.close()

        else:
            st.warning("No preview available for this document.")
            page_imgs = []

        # 2) If we have at least one “page,” embed the same HTML viewer:
        if page_imgs:
            js_pages = json.dumps(page_imgs)
            n_pages = len(page_imgs)

            html = f"""
            <style>
              .viewer-container {{
                position: relative;
                width:100%; max-width:800px;
                height:1000px; margin:auto;
                border:1px solid #ccc;
                display: flex;
                flex-direction: column;
              }}
              .image-wrapper {{
                flex: 1 1 auto;
                overflow: auto;
              }}
              .image-wrapper img {{
                width:100%;
                object-fit: contain;
                transition: transform 0.2s;
                cursor: zoom-in;
              }}
              .controls {{
                flex: 0 0 auto;
                display:flex;
                justify-content:center;
                gap:6px;
                padding:8px;
                background:rgba(255,255,255,0.9);
                border-top:1px solid #ccc;
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
              <div class="image-wrapper">
                <img id="docImg" src="" />
              </div>
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

              function resetZoom() {{ zoom = 1; img.style.transformOrigin = 'center center'; }}
              function setZoomAt(x, y) {{
                resetZoom();
                zoom = 2;
                const rect = img.getBoundingClientRect();
                const px = ((x - rect.left)/rect.width)*100;
                const py = ((y - rect.top)/rect.height)*100;
                img.style.transformOrigin = `${{px}}% ${{py}}%`;
              }}

              document.getElementById("prevBtn").onclick = () => {{ if(idx>0) idx--; resetZoom(); render(); }};
              document.getElementById("nextBtn").onclick = () => {{ if(idx<pages.length-1) idx++; resetZoom(); render(); }};
              document.getElementById("rotateBtn").onclick = () => {{ rot = (rot + 90) % 360; render(); }};
              document.getElementById("resetBtn").onclick = () => {{ resetZoom(); render(); }};

              img.addEventListener("click", e => {{
                if(zoom===1) setZoomAt(e.clientX, e.clientY);
                else resetZoom();
                render();
              }});

              render();
            }})();
            </script>
            """
            components.html(html, height=1000, scrolling=False)

            if st.button(
                "🗑️ Delete this document",
                key=f"delete_doc_{selected_index}",
                help="Remove this document from the transaction"
            ):
                # Remove it
                st.session_state.results.pop(selected_index)
                # Reset the selection so we don't point at a missing index
                st.session_state.current_index = 0
                # Restart to refresh everything
                st.experimental_rerun()

        else:
            st.warning("No preview available for this document.")
        with col_ocr:
            st.markdown("### Extracted Data")
            raw = current.get("extracted_data", "")
            if "contract f" in current.get("doc_type","").lower():
                raw = unify_contract_f(raw)
            elif "commercial license" in current.get("doc_type","").lower():
                raw = unify_commercial_license(raw)
            elif current.get("doc_type","").lower()=='title deed':
                raw = unify_title_deed(raw)
            elif current.get("doc_type","").lower()=='usufruct right certificate':
                raw = unify_usufruct_right_certificate(raw)
            elif current.get("doc_type","").lower()=='pre title deed':
                raw = unify_pre_title_deed(raw)
            elif current.get("doc_type","").lower() in ['title deed lease finance'] :
                raw = unify_title_deed_lease_finance(raw)
            elif current.get("doc_type","").lower() in ['title deed lease to own'] :
                raw = unify_title_deed_lease_to_own(raw)
            elif current.get("doc_type","").lower() in ['cheques'] :
                raw = unify_cheques(raw)
            elif current.get("doc_type","").lower() =='noc non objection certificate' :
                raw = unify_noc(raw)
            extracted_raw = raw
            display_mode = "Form"
            if display_mode == "Form":
                render_data_form(extracted_raw, selected_index)