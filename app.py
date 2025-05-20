import streamlit as st
import time
import fitz  # PyMuPDF
import base64
import tempfile
import io
import os
import json
import zipfile
from datetime import datetime,date
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
from scripts.utils.ocr_utils import *
from scripts.procedure_recognition import suggest_procedure
import streamlit.components.v1 as components
import firebase_admin
from firebase_admin import credentials, firestore
import math
import requests
import pandas as pd
from scripts.integrators.integrator import *
from scripts.firebase_connectors.fire_base_connection import (
    init_db,
    login_user,
    signup_user,
    load_appointments,
)


# ----------------- SET AUTHENTICATION & CLIENT IN SESSION ------------------
if "client" not in st.session_state:
    st.session_state.client = OpenAI(
        base_url="https://router.huggingface.co/hyperbolic/v1",
#         base_url = "https://mf32siy1syuf3src.us-east-1.aws.endpoints.huggingface.cloud/v1/",
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

# ─── Initialize Firestore & Session Defaults ───────────────────────────────
db = init_db()
st.set_page_config(page_title="Injaz OCR System", layout="wide")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# ─── LOGIN SCREEN ──────────────────────────────────────────────────────────
if not st.session_state.logged_in:
    st.title("🔒 Injaz OCR Login")

    email = st.text_input("Email")
    pwd   = st.text_input("Password", type="password")
    if st.button("Login"):
        user = login_user(db, email, pwd)
        if user:
            st.session_state.logged_in = True
            st.session_state.user      = user

            # load CSR list and auto-pick exactly as you had before…
            rows = []
            for doc in db.collection("auth").stream():
                u = doc.to_dict()
                if u.get("injaz_id"):
                    rows.append({
                        "injaz_id": u["injaz_id"],
                        "email":    u["email"].strip().lower(),
                        "full_name": u.get("full_name"),
                        "name":     u.get("name"),
                    })
            st.session_state.csr_list = rows

            logged_email = user["email"].strip().lower()
            csr_obj = next((u for u in rows if u["email"] == logged_email), None)
            if csr_obj:
                st.session_state.selected_csr = {
                    "id":        csr_obj["injaz_id"],
                    "email":     csr_obj["email"],
                    "full_name": csr_obj["full_name"],
                    "name":      csr_obj["name"]
                }
            else:
                st.error("⚠️ Your account email isn’t in the CSR list.")

            st.experimental_rerun()
        else:
            st.error("Invalid credentials")

    st.stop()


# ---------- STREAMLIT UI ----------
if "zoho_token" not in st.session_state:
    # this will cache it immediately
    try:
        st.session_state.zoho_token = get_auth_token()
    except Exception as e:
        st.error(f"Could not get Zoho token: {e}")
        st.stop()
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


# initialize pagination & selection
st.session_state.setdefault("page", 1)
st.session_state.setdefault("selected_name", None)
st.session_state.setdefault("selected_pdfs", None)

mode = "Appointment"
uploaded_files = []

if mode == "Appointment":
    if st.session_state.selected_name is None:
        st.header("📋 Select an Appointment")
        df = load_appointments(db)  # already only pending, with Title-Case cols
        if df.empty:
            st.info("No pending appointments.")
            st.stop()

        per_page = 5
        pages   = math.ceil(len(df) / per_page)
        pg      = st.session_state.page
        subset  = df.iloc[(pg-1)*per_page : pg*per_page]

        st.dataframe(subset[[
            'First Name','Last Name','Client Type',
            'Appointment Type','Appointment Date',
            'Time Slot','Email','Phone','Status'
        ]])

        cols = st.columns([1,2,1])
        with cols[0]:
            st.button("Prev", on_click=lambda: st.session_state.update(page=max(1, pg-1)))
        with cols[1]:
            st.write(f"Page {pg}/{pages}")
        with cols[2]:
            st.button("Next", on_click=lambda: st.session_state.update(page=min(pages, pg+1)))

        names = (subset["First Name"] + " " + subset["Last Name"]).tolist()
        sel = st.selectbox("Select by name", names)
        if st.button("Choose Appointment"):
            st.session_state.selected_name = sel
            st.session_state.selected_pdfs = None
        st.stop()

    # user has chosen a name → fetch the row
    df = load_appointments(db)
    full_name = st.session_state.selected_name
    matches = df[(df["First Name"] + " " + df["Last Name"]) == full_name]

    if matches.empty:
        st.error(f"No appointment found for {full_name}. Please re-select.")
        st.stop()

    row = matches.iloc[0]
    st.subheader("Appointment Details")
    st.table(pd.DataFrame([row[[
        "First Name","Last Name","Email","Phone","Appointment Date"
    ]]]))


    pdf_urls = row.get("Document URLs", [])
    # pdf_urls = row.get("Document URLs", [])
    uploaded_files = []

    if pdf_urls:
        if st.session_state.selected_pdfs is None:
            bufs = []
            for i, url in enumerate(pdf_urls, 1):
                r = requests.get(url); r.raise_for_status()
                ext = url.split('.')[-1].lower()
                if ext not in ("pdf","png","jpg","jpeg"):
                    # fallback to content-type header
                    ct = r.headers.get("Content-Type", "")
                    ext = "pdf" if "pdf" in ct else "jpg"

                buf = io.BytesIO(r.content)
                buf.name = f"{row['First Name']}_{row['Last Name']}_doc{i}.{ext}"
                bufs.append(buf)
            st.session_state.selected_pdfs = bufs
        uploaded_files = st.session_state.selected_pdfs

    else:
        st.warning("No PDFs in this appointment.")

    # **ONE** uploader for extra docs
    extra = st.file_uploader(
        "➕ Upload extra documents (optional)",
        type=["png","jpg","jpeg","pdf"],
        accept_multiple_files=True,
        key="extra_docs"
    )
    if extra:
        uploaded_files.extend(extra)




if st.button("Submit") and uploaded_files:
    st.session_state.documents_saved = False
    st.session_state.results = []
    t0 = time.time()
    for f in uploaded_files:
        with st.spinner(f"Processing {f.name}…"):
            name = f.name.lower()
            # 1) Check extension: if it’s an image, convert → PDF first
            if name.endswith((".png", ".jpg", ".jpeg")):
                f.seek(0)
                img = Image.open(f)
                img = ImageOps.exif_transpose(img)   # fix orientation
                if img.mode != "RGB":
                    img = img.convert("RGB")

                pdf_buf = io.BytesIO()
                img.save(pdf_buf, format="PDF")
                pdf_buf.name = f"{f.name.rsplit('.',1)[0]}.pdf"
                pdf_buf.seek(0)

                # Now process this ONE PDF
                try:
                    res = process_document(pdf_buf, pdf_buf.name)
                except Exception as e:
                    st.error(f"Failed to process converted PDF for {f.name}: {e}")
                    continue

            else:
                # Not an image → treat as PDF immediately
                try:
                    res = process_document(f, f.name)
                except RuntimeError as e:
                    st.error(f"Error processing PDF {f.name}: {e}")
                    continue

            # collect into results list
            if isinstance(res, list):
                st.session_state.results.extend(res)
            else:
                st.session_state.results.append(res)

    st.session_state.current_index = 0
    st.success(f"Processing complete in {time.time() - t0:.1f}s")





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
        procedures = [
    "Transfer Sell","Sell Mortgage","Sell + Mortgage Registration","Sell Development",
    "Sell Development Mortgage","Sell Development Registration","Sell Pre Registration",
    "Blocking","Unblocking + Sell","Unblocking + Sell Mortgage","Unblocking + Lease to Own",
    "Sell Pre Registration + Mortgage Registration Pre Registration",
    "Sell Pre Registration + Mortgage Release","Gift/ Grant","Gift/ Grant Delayed Sell",
    "Gift/ Grant Pre Registration","Company Transfer Sell","Company Gifting",
    "Company Registration - Individual","Company Registration - Offshore CO",
    "Company Registration - SolePR","Mortgage Registration","Mortgage Pre Registration",
    "Mortgage Registration on Pre Registration","Mortgage Release on Delayed Sell",
    "Portfolio Mortgage Modification - Amount+Date","Portfolio Mortgage Modification - Date",
    "Portfolio Mortgage Registration","Portfolio Mortgage Release","Delayed Sell",
    "Delayed Sell + Delayed Mortgage","Delayed Sell Mortgage",
    "Delayed Sell Mortgage Registration","Delayed Sell Mortgage Release",
    "Modify Delayed Mortgage - (Price)","Modify Delayed Mortgage - Add note/Extend",
    "Modify Delayed Sell Development - (Price)",
    "Modify Delayed Sell Development - Add note/Extend","Modify Sell Development - Extend only",
    "Modify Sell Development Mortgage - (Price)",
    "Modify Sell Development Mortgage - Add note/Extend","Lease Finance Registration",
    "Lease Finance Modification on Sell Development - Add note/Extend",
    "Lease Finance Modification on Delayed sell - (Price)",
    "Lease Finance Modification on Sell Development - (Price)",
    "Lease Finance Registration on Delayed Sell","Lease Finance Registration on Sell Development",
    "Lease hold Mortgage Registration","Lease hold Mortgage Release","Lease to Own (Ejarah)",
    "Lease to Own Modification on Delayed Sell - (Price)",
    "Lease to Own Modification on Delayed Sell - Add note/Extend",
    "Lease to Own Modification on Sell Development - (Price)",
    "Lease to Own Modification on Sell Development - Add note/Extend",
    "Lease to Own on Delayed Sell","Lease to Own on Pre Registration",
    "Lease to Own on Sell Development","Lease to Own Release",
    "Lease to Own Release + Lease to Own","Lease to Own Release + Sell",
    "Lease to Own Release + Sell Mortgage","Lease to Own Release on Delayed Sell",
    "Lease to Own Release on Sell Development","Release of Mortgage","Release of Mortgage + Sell",
    "Release of Mortgage + Sell + Mortgage","Release of Mortgage + Mortgage Registration",
    "Release of Mortgage + Mortgage","Release of Mortgage + Sell + Mortgage Registration",
    "Release Delayed Mortgage + Delayed Mortgage","Release Delayed Mortgage + Delayed Sell",
    "Release Delayed Mortgage + Delayed Sell + Delayed Mortgage","Release Lease Finance",
    "Release Lease Finance + Mortgage Registration","Release Lease to Own + Mortgage",
    "Release Lease to Own + Sell + Mortgage Pre-Registration",
    "Release Lease to Own Pre + Lease to Own Pre-Registration",
    "Release Lease to Own Pre-Registration + Mortgage Pre-Registration",
    "Release Lease to Own Pre-Registration + Sell-Pre Registration",
    "Release of Mortgage + Gift/ Grant + Mortgage",
    "Release of Mortgage + Gift/ Grant + Mortgage Registration",
    "Release of Mortgage + Lease to own","Release of Mortgage on Sell Development",
    "Release of Mortgage Pre + Pre Sell + Pre Mortgage",
    "Release of Mortgage Pre + Sell Pre Registration",
    "Release of Mortgage Pre Registration + Mortgage Pre Registration",
    "Release of Mortgage Pre Registration + Sell Pre Registration",
    "Release of Mortgage Pre Registration + Sell Pre Registration + Mortgage Registration Pre Registration",
    "Release Sell Development Modification - (Price)",
    "Release Sell Development Modification - Add notes/Extend"
]


        selected_procedure = st.selectbox(
            "Choose procedure:",
            procedures,
            key="proc_selector"
        )

    # ─── Define your allow-lists ─────────────────────────────────────────────────
    valid_trustee_names = {
        "Fatma Al Rahma",
        "Hanaa Albalushi",
        "Khozama Alhumyani",
        "Manal Alnami",
        "Mohammed Althawadi",
        "Nadeen Ali",
        "Ahmed Salah",
    }
    
    valid_csr_names = {
        "Sarrah Mae Antolin",
        "Reda Najjar",
        "Layal Makhlouf",
        "Princess Sibayan",
        "Hena Goyal",
        "Odoo Test",
        "Fatima Kanakri",
        "Zoya Kazmi",
        "Noha Abo ElFadl",
        # note: Marketing Team and any entries containing “@” will simply not match
    }
    
    # ─── Fetch and store in session (only once) ──────────────────────────────────
    if "csr_list" not in st.session_state or "trustee_list" not in st.session_state:
        csr_users, trustee_users = get_csr_and_trustee_users(st.session_state.get("zoho_token"))
    
        # filter by allow-list
        st.session_state.trustee_list = [
            u for u in trustee_users
            if (u.get("full_name") or u.get("name")) in valid_trustee_names
        ]
        st.session_state.csr_list = [
            u for u in csr_users
            if (u.get("full_name") or u.get("name")) in valid_csr_names
        ]
    
    # ─── Prepare the display names ──────────────────────────────────────────────
    csr_names = [u.get("full_name") or u.get("name") for u in st.session_state.csr_list]
    trustee_names = [u.get("full_name") or u.get("name") for u in st.session_state.trustee_list]


    # ─── CSR picker ─────────────────────────────────────────────────────────
    if st.session_state.get("selected_csr"):
        # If we already have a CSR (i.e. the logged-in user), just show it…
        csr = st.session_state.selected_csr
        st.markdown(f"**Assigned CSR Representative:** {csr['full_name']} ({csr['email']})")
    else:
        # …otherwise fall back to your selectbox UI
        selected_csr_name = st.selectbox(
            "Assign CSR Representative",
            ["–– None ––"] + csr_names,
            key="csr_selector"
        )
        if selected_csr_name != "–– None ––":
            csr_obj = next(
                u for u in st.session_state.csr_list
                if (u.get("full_name") or u.get("name")) == selected_csr_name
            )
            st.session_state.selected_csr = {
                "id":        csr_obj["id"],
                "email":     csr_obj.get("email"),
                "full_name": csr_obj.get("full_name"),
                "name":      csr_obj.get("name")
            }
        else:
            st.session_state.selected_csr = None

    # # ─── Trustee picker ─────────────────────────────────────────────────────
    # selected_trustee_name = st.selectbox(
    #     "Assign Trustee Employee",
    #     ["–– None ––"] + trustee_names,
    #     key="trustee_selector"
    # )
    # trustee_obj = next(
    #     (u for u in st.session_state.trustee_list if (u.get("full_name") or u.get("name")) == selected_trustee_name),
    #     None
    # )
    # if trustee_obj:
    #     st.session_state.selected_trustee = {
    #         "id":        trustee_obj["id"],
    #         "email":     trustee_obj.get("email"),
    #         "full_name": trustee_obj.get("full_name"),
    #         "name":      f"{trustee_obj.get('first_name','')} {trustee_obj.get('last_name','')}".strip()
    #     }
    # else:
    #     st.session_state.selected_trustee = None

    # … after you compute trustee_names …
    
    staff_name = row.get("staffName", "").strip()
    
    # Try to find an exact match (case-insensitive)
    match = None
    for u in st.session_state.trustee_list:
        name = (u.get("full_name") or u.get("name") or "").strip()
        if name.lower() == staff_name.lower():
            match = u
            break
    
    if match:
        # Build the dropdown options
        options = ["–– None ––"] + trustee_names
        idx = options.index(match.get("full_name") or match.get("name"))
        # Render a disabled selectbox with the matched index
        selected_trustee_name = st.selectbox(
            "Assign Trustee Employee",
            options,
            index=idx,
            disabled=True,
            key="trustee_selector"
        )
        # Store the matched trustee object
        st.session_state.selected_trustee = {
            "id":        match["id"],
            "email":     match.get("email"),
            "full_name": match.get("full_name"),
            "name":      f"{match.get('first_name','')} {match.get('last_name','')}".strip()
        }
    
    else:
        # No match → regular, editable selectbox
        selected_trustee_name = st.selectbox(
            "Assign Trustee Employee",
            ["–– None ––"] + trustee_names,
            key="trustee_selector"
        )
        trustee_obj = next(
            (u for u in st.session_state.trustee_list
             if (u.get("full_name") or u.get("name")) == selected_trustee_name),
            None
        )
        if trustee_obj:
            st.session_state.selected_trustee = {
                "id":        trustee_obj["id"],
                "email":     trustee_obj.get("email"),
                "full_name": trustee_obj.get("full_name"),
                "name":      f"{trustee_obj.get('first_name','')} {trustee_obj.get('last_name','')}".strip()
            }
        else:
            st.session_state.selected_trustee = None

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
                

                try:
                    st.experimental_rerun()
                except AttributeError:
                    st.rerun()

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
final_roles = st.session_state.get("person_roles", [])
if "results" in st.session_state and st.session_state.results:
    st.markdown("### Ready to send to Zoho CRM")
    if st.button("Submit to Zoho"):
            # 1) Build the Zoho payload
        try:
            appt_date = row["Appointment Date"]  # e.g. "12-05-2025"
            time_slot = row["Time Slot"]         # e.g. "08:15 AM"
            booking_id=row["bookingId"]
        except :
            appt_date=appt_date
            time_slot=time_slot
        payload = build_deal_payload(
            st.session_state.results,
            st.session_state.person_roles,
            selected_procedure,
            appt_date,
            time_slot,
            booking_id,
            owner=st.session_state.selected_csr,
            assigned_trustee=st.session_state.selected_trustee,
            token=st.session_state.get("zoho_token")
        )
#         st.markdown("#### Zoho Payload")
#         st.write(payload)
#         st.write("Current token:", st.session_state.get("zoho_token"))

#         # 2) Post the Deal
        posted = post_booking(st.session_state.get("zoho_token"), payload)
        st.write("Deal posted successfully?", posted)

        if not posted:
            st.error("❌ Failed to create Deal in Zoho. Check logs for details.")
        else:
            # 3) Retrieve Zoho’s internal deal ID by Booking_Id (poll until available)
            booking_id = payload["data"][0]["Booking_Id"]
            st.info(f"Looking up deal for Booking_Id={booking_id}…")

            # refresh token once up front
            token = get_auth_token(st.session_state.get("zoho_token"))
            st.session_state["zoho_token"] = token

            timeout_secs = 120         # overall timeout
            interval_secs = 15        # how often to retry
            deadline = time.time() + timeout_secs
            deal_id = None

            with st.spinner("Waiting for Zoho to index the new deal…"):
                while time.time() < deadline:
                    deal_id = get_deal_id_by_booking_id(token, booking_id)
                    if deal_id:
                        break
                    time.sleep(interval_secs)

            if not deal_id:
                st.error(f"❌ Could not find Deal for Booking_Id={booking_id} after {timeout_secs}s")
            else:
                st.success(f"✅ Zoho Deal ID: {deal_id}")
                try:
                    appointment_id = row["ID"]  # Assuming 'id' is the document ID in Firebase
                    appointment_ref = db.collection("appointments").document(appointment_id)
                    appointment_ref.update({"status": "done"})
                    st.success(f"✅ Appointment status updated to 'done' in Firebase.")
                except Exception as e:
                    st.error(f"❌ Failed to update appointment status in Firebase: {e}")
                # 4) Upload each renamed document
                with st.spinner("Uploading attachments to Zoho..."):
                    for idx, doc in enumerate(st.session_state.results, start=1):
                        dt = doc.get("doc_type", "document").lower().strip()

                        # build human-readable label
                        if dt in ["ids", "passport", "residence visa"]:
                            raw = doc.get("extracted_data", "")
                            if isinstance(raw, str):
                                try:
                                    data = json.loads(raw)
                                except:
                                    data = {"raw_text": raw}
                            else:
                                data = raw
                            if "raw_text" in data and isinstance(data["raw_text"], str):
                                try:
                                    data = json.loads(clean_json_string(data["raw_text"]))
                                except:
                                    pass

                            if dt == "ids":
                                person = data.get("front", {}).get("name_english", "").strip()
                            elif dt == "passport":
                                person = data.get("fullname", "").strip()
                            else:
                                person = (data.get("full_name") or data.get("arabic_name") or "").strip()

                            role = next(
                                (r["Role"] for r in st.session_state.person_roles if r["Name"] == person),
                                None
                            )
                            label = f"{idx}.{role} {dt} — {person}" if role else f"{idx}.{dt} — {person}"
                        else:
                            label = f"{idx}.{dt}"

                        base_name = label.replace(" ", "_").replace("/", "_")
                        file_name = f"{base_name}.pdf"

                        file_bytes = doc.get("pdf_bytes") or doc.get("original_pdf_bytes")
                        if not file_bytes:
                            st.warning(f"No PDF content for {file_name}, skipping.")
                            continue

                        # first upload attempt
                        ok, msg = upload_attachment_to_deal(
                            auth_token   = token,
                            deal_id      = deal_id,
                            file_name    = file_name,
                            file_content = file_bytes,
                            content_type = "application/pdf"
                        )

                        # on 401, refresh and retry once
                        if not ok and "401" in msg:
                            token = get_auth_token(token)
                            st.session_state["zoho_token"] = token
                            ok, msg = upload_attachment_to_deal(
                                auth_token   = token,
                                deal_id      = deal_id,
                                file_name    = file_name,
                                file_content = file_bytes,
                                content_type = "application/pdf"
                            )

                        if ok:
                            st.write(f"✅ Uploaded `{file_name}` → {msg}")
                        else:
                            st.error(f"❌ Failed to upload `{file_name}`: {msg}")
                          
if st.button("🔄 Work on another appointment"):
    # 1) Remove exactly the bits we want reset
    for key in [
        "selected_name",
        "selected_pdfs",
        "results",
        "current_index",
        "selected_csr",
        "selected_trustee",
    ]:
        st.session_state.pop(key, None)

    # 2) Reset pagination
    st.session_state.page = 1

    # 3) Rerun from the top (now selected_name is gone)
    try:
        st.experimental_rerun()
    except AttributeError:
        st.rerun()
