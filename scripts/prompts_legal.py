TD_lease_vlm_prompt = """
The image contains both **Arabic and English text**. Extract the text accurately while following these specific rules:

---

### **General Extraction Rules:**
- The document has fields where the **field name is in English on the left and the value is in Arabic on the right** (or vice versa).
- **Extract only the English values**, which will be found on the **left side after the field name**.
- **Do NOT transliterate Arabic into English** or mix languages.
- **If a field contains both Arabic and English, return only the English value**.
- **If a field does not exist in the image, return `"Not mentioned"`**.
- **Ensure all sections and fields are included, even if they vary based on document type**.
- **Do NOT include any Chinese, Japanese, or non-Arabic/non-English characters.**
- **Ensure numerical values are extracted accurately and formatted correctly.**

---

### **Section-Specific Rules:**

#### **1. Title Deed Lease To Own General Information:**
- Extract values dynamically and return them under `"Title Deed (Lease To Own)"` if exists:
  - `"Issue Date"`
  - `"Mortgage Status"`
  - `"Property Type"`
  - `"Community"`
  - `"Plot No"`
  - `"Municipality No"`
  - `"Building No"`
  - `"Building Name"`
  - `"Property No"`
  - `"Floor No"`
  - `"Parkings"`
  - `"Suite Area"`
  - `"Balcony Area"`
  - `"Area Sq Meter"`
  - `"Area Sq Feet"`
  - `"Common Area"`


#### **2. Owners Numbers and Their Shares:**
- Extract details for **each owner**, ensuring:
  - `"Owner ID"` → Extract the numeric ID.
  - `"Owner Name (English)"` → Extract the **English name**.
  - `"Owner Name (Arabic)"` → Extract the **Arabic name**.
  - `"Share (Sq Meter)"` → Extract numerical value.
- Return the owners' details as an array under `"Owners"`:
  ```json
  "Owners": [
    {
      "Owner ID": "<Extracted ID>",
      "Owner Name (English)": "<Extracted Name>",
      "Owner Name (Arabic)": "<Extracted Name>",
      "Share (Sq Meter)": "<Extracted Value>"
    },
    ...
  ]
#### **3.  Lessees if exists Numbers and Their Shares:**

- Extract details for **each lessees**, ensuring if exists:
  - `"Lessees ID"` → Extract the numeric ID.
  - `"Lessees Name (English)"` → Extract the **English name**.
  - `"Lessees Name (Arabic)"` → Extract the **Arabic name**.
  - `"Share (Sq Meter)"` → Extract numerical value.
- Return the lessees' details as an array under `"Lessees"`:
  ```json
  
      "Lessees": [
    {
      "Lessee ID": "<Extracted ID>",
      "Lessee Name (English)": "<Extracted Name>",
      "Lessee Name (Arabic)": "<Extracted Name>",
      "Share (Sq Meter)": "<Extracted Value>"
    },
    ...
  ]
  ```
#### **3. Transaction Details:**
- Extract and return under `"Transaction Details"`:

  - `"Land Registration No"`
  - `"Transaction Date"`
  - `"Amount"` → Extract full amount as **numbers only** (ignore text like "Dirhams").

---

### **Output Requirements:**
- **The extracted information should be well-structured and grouped into sections.**
- **Ensure that Arabic and English text are properly separated as instructed.**
- **Maintain the original structure of the document, ensuring all sections are properly categorized.**
- **Preserve correct numerical formats, special characters, and accurate text encoding.**
"""

Titledeed__prompt = """
The image contains both **Arabic and English text**. Extract the text accurately while following these specific rules:

---

### **General Extraction Rules:**
- The document has fields where the **field name is in English on the left and the value is in Arabic on the right** (or vice versa).
- **Extract only the English values**, which will be found on the **left side after the field name**.
- **Do NOT transliterate Arabic into English** or mix languages.
- **If a field contains both Arabic and English, return only the English value**.
- **If a field does not exist in the image, return `"Not mentioned"`**.
- **Ensure all sections and fields are included, even if they vary based on document type**.
- **Do NOT include any Chinese, Japanese, or non-Arabic/non-English characters.**
- **Ensure numerical values are extracted accurately and formatted correctly.**

---

### **Section-Specific Rules:**

#### **1. Title Deed General Information:**
- Extract values dynamically and return them under `"Title Deed"` if exists:
  - `"Issue Date"`
  - `"Mortgage Status"`
  - `"Property Type"`
  - `"Community"`
  - `"Plot No"`
  - `"Municipality No"`
  - `"Building No"`
  - `"Building Name"`
  - `"Property No"`
  - `"Floor No"`
  - `"Parkings"`
  - `"Suite Area"`
  - `"Balcony Area"`
  - `"Area Sq Meter"`
  - `"Area Sq Feet"`
  - `"Common Area"`


#### **2. Owners Numbers and Their Shares:**
- Extract details for **each owner**, ensuring:
  - `"Owner ID"` → Extract the numeric ID.
  - `"Owner Name (English)"` → Extract the **English name**.
  - `"Owner Name (Arabic)"` → Extract the **Arabic name**.
  - `"Share (Sq Meter)"` → Extract numerical value.
- Return the owners' details as an array under `"Owners"`:
  ```json
  "Owners": [
    {
      "Owner ID": "<Extracted ID>",
      "Owner Name (English)": "<Extracted Name>",
      "Owner Name (Arabic)": "<Extracted Name>",
      "Share (Sq Meter)": "<Extracted Value>"
    },
    ...
  ]

#### **3. Transaction Details:**
- Extract and return under `"Transaction Details"`:

  - `"Land Registration No"`
  - `"Transaction Date"`
  - `"Amount"` → Extract full amount as **numbers only** (ignore text like "Dirhams").

---

### **Output Requirements:**
- **The extracted information should be well-structured and grouped into sections.**
- **Ensure that Arabic and English text are properly separated as instructed.**
- **Maintain the original structure of the document, ensuring all sections are properly categorized.**
- **Preserve correct numerical formats, special characters, and accurate text encoding.**
"""


usufruct_right_certificate_prompt= """
The image contains both **Arabic and English text**. Extract the text accurately while following these specific rules:

---

### **General Extraction Rules:**
- The document has fields where the **field name is in English on the left and the value is in Arabic on the right** (or vice versa).
- **Extract only the English values**, which will be found on the **left side after the field name**.
- **Do NOT transliterate Arabic into English** or mix languages.
- **If a field contains both Arabic and English, return only the English value**.
- **If a field does not exist in the image, return `"Not mentioned"`**.
- **Ensure all sections and fields are included, even if they vary based on document type**.
- **Do NOT include any Chinese, Japanese, or non-Arabic/non-English characters.**
- **Ensure numerical values are extracted accurately and formatted correctly.**

---

### **Section-Specific Rules:**

#### **1. Usufruct Right Certificate Information:**
- Extract values dynamically and return them under `"Usufruct Right Certificate"` if exists:
  - `"Issue Date"`
  - `"Mortgage Status"`
  - `"Property Type"`
  - `"Community"`
  - `"Plot No"`
  - `"Municipality No"`
  - `"Building No"`
  - `"Building Name"`
  - `"Property No"`
  - `"Floor No"`
  - `"Parkings"`
  - `"Suite Area"`
  - `"Balcony Area"`
  - `"Area Sq Meter"`
  - `"Area Sq Feet"`
  - `"Common Area"`

#### **2. Lessors and lessees if exists Numbers and Their Shares:**

- Extract details for **each lessor**, ensuring if exists:
  - `"Lessor ID"` → Extract the numeric ID.
  - `"Lessor Name (English)"` → Extract the **English name**.
  - `"Lessor Name (Arabic)"` → Extract the **Arabic name**.
  - `"Share (Sq Meter)"` → Extract numerical value.
- Return the lessors' details as an array under `"Lessors"`:
  ```json
  "Lessors": [
    {
      "Lessor ID": "<Extracted ID>",
      "Lessor Name (English)": "<Extracted Name>",
      "Lessor Name (Arabic)": "<Extracted Name>",
      "Share (Sq Meter)": "<Extracted Value>"
    },
      "Lessees": [
    {
      "Lessor ID": "<Extracted ID>",
      "Lessor Name (English)": "<Extracted Name>",
      "Lessor Name (Arabic)": "<Extracted Name>",
      "Share (Sq Meter)": "<Extracted Value>"
    },
    ...
  ]
  ```
#### **3. Transaction Details:**
- Extract and return under `"Transaction Details"`:

  - `"Land Registration No"`
  - `"Transaction Date"`
  - `"Amount"` → Extract full amount as **numbers only** (ignore text like "Dirhams").

---

### **Output Requirements:**
- **The extracted information should be well-structured and grouped into sections.**
- **Ensure that Arabic and English text are properly separated as instructed.**
- **Maintain the original structure of the document, ensuring all sections are properly categorized.**
- **Preserve correct numerical formats, special characters, and accurate text encoding.**
"""

preTitledeed__prompt = """
The image contains both **Arabic and English text**. Extract the text accurately while following these specific rules:

---

### **General Extraction Rules:**
- The document has fields where the **field name is in English on the left and the value is in Arabic on the right** (or vice versa).
- **Extract only the English values**, which will be found on the **left side after the field name**.
- **Do NOT transliterate Arabic into English** or mix languages.
- **If a field contains both Arabic and English, return only the English value**.
- **If a field does not exist in the image, return `"Not mentioned"`**.
- **Ensure all sections and fields are included, even if they vary based on document type**.
- **Do NOT include any Chinese, Japanese, or non-Arabic/non-English characters.**
- **Ensure numerical values are extracted accurately and formatted correctly.**

---

### **Section-Specific Rules:**

#### **1. Pre Title Deed General Information:**
- Extract values dynamically and return them under `"Pre Title Deed"` if exists:
  - `"Issue Date"`
  - `"Mortgage Status"`
  - `"Property Type"`
  - `"Community"`
  - `"Plot No"`
  - `"Municipality No"`
  - `"Building No"`
  - `"Building Name"`
  - `"Property No"`
  - `"Floor No"`
  - `"Parkings"`
  - `"Suite Area"`
  - `"Balcony Area"`
  - `"Area Sq Meter"`
  - `"Area Sq Feet"`
  - `"Common Area"`


#### **2. Owners Numbers and Their Shares:**
- Extract details for **each owner**, ensuring:
  - `"Owner ID"` → Extract the numeric ID.
  - `"Owner Name (English)"` → Extract the **English name**.
  - `"Owner Name (Arabic)"` → Extract the **Arabic name**.
  - `"Share (Sq Meter)"` → Extract numerical value.
- Return the owners' details as an array under `"Owners"`:
  ```json
  "Owners": [
    {
      "Owner ID": "<Extracted ID>",
      "Owner Name (English)": "<Extracted Name>",
      "Owner Name (Arabic)": "<Extracted Name>",
      "Share (Sq Meter)": "<Extracted Value>"
    },
    ...
  ]
  
#### **3. Buyers Numbers and Their Shares:**
- Extract details for **each buyer**, ensuring:
  - `"Buyer ID"` → Extract the numeric ID.
  - `"Buyer Name (English)"` → Extract the **English name** name only not the numbers.
  - `"Buyer Name (Arabic)"` → Extract the **Arabic name** name only not the numbers.
  - `"Share (Sq Meter)"` → Extract numerical value.
- Return the buyers' details as an array under `"Buyers"`:
  ```json
  "Buyers": [
    {
      "Buyer ID": "<Extracted ID>",
      "Buyer Name (English)": "<Extracted Name>",
      "Buyer Name (Arabic)": "<Extracted Name>",
      "Share (Sq Meter)": "<Extracted Value>"
    },
    ...
  ]

#### **4. Transaction Details:**
- Extract and return under `"Transaction Details"`:

  - `"Land Registration No"`
  - `"Transaction Date"`
  - `"Amount"` → Extract full amount as **numbers only** (ignore text like "Dirhams").

---

### **Output Requirements:**
- **The extracted information should be well-structured and grouped into sections.**
- **Ensure that Arabic and English text are properly separated as instructed.**
- **Maintain the original structure of the document, ensuring all sections are properly categorized.**
- **Preserve correct numerical formats, special characters, and accurate text encoding.**
"""

TD_finance_vlm_prompt="""
The image contains both **Arabic and English text**. Extract the text accurately while following these specific rules:

---

### **General Extraction Rules:**
- The document has fields where the **field name is in English on the left and the value is in Arabic on the right** (or vice versa).
- **Extract only the English values**, which will be found on the **left side after the field name**.
- **Do NOT transliterate Arabic into English** or mix languages.
- **If a field contains both Arabic and English, return only the English value**.
- **If a field does not exist in the image, return `"Not mentioned"`**.
- **Ensure all sections and fields are included, even if they vary based on document type**.
- **Do NOT include any Chinese, Japanese, or non-Arabic/non-English characters.**
- **Ensure numerical values are extracted accurately and formatted correctly.**

---

### **Section-Specific Rules:**

#### **1. Title Deed Lease Finance General Information:**
- Extract values dynamically and return them under `"Title Deed (Lease Finance)"` if exists:
  - `"Issue Date"`
  - `"Mortgage Status"`
  - `"Property Type"`
  - `"Community"`
  - `"Plot No"`
  - `"Municipality No"`
  - `"Building No"`
  - `"Building Name"`
  - `"Property No"`
  - `"Floor No"`
  - `"Parkings"`
  - `"Suite Area"`
  - `"Balcony Area"`
  - `"Area Sq Meter"`
  - `"Area Sq Feet"`
  - `"Common Area"`


#### **2. Owners Numbers and Their Shares:**
- Extract details for **each owner**, ensuring:
  - `"Owner ID"` → Extract the numeric ID.
  - `"Owner Name (English)"` → Extract the **English name**.
  - `"Owner Name (Arabic)"` → Extract the **Arabic name**.
  - `"Share (Sq Meter)"` → Extract numerical value.
- Return the owners' details as an array under `"Owners"`:
  ```json
  "Owners": [
    {
      "Owner ID": "<Extracted ID>",
      "Owner Name (English)": "<Extracted Name>",
      "Owner Name (Arabic)": "<Extracted Name>",
      "Share (Sq Meter)": "<Extracted Value>"
    },
    ...
  ]
#### **3.  Lessees if exists Numbers and Their Shares:**

- Extract details for **each lessees**, ensuring if exists:
  - `"Lessees ID"` → Extract the numeric ID.
  - `"Lessees Name (English)"` → Extract the **English name**.
  - `"Lessees Name (Arabic)"` → Extract the **Arabic name**.
  - `"Share (Sq Meter)"` → Extract numerical value.
- Return the lessees' details as an array under `"Lessees"`:
  ```json
  
      "Lessees": [
    {
      "Lessee ID": "<Extracted ID>",
      "Lessee Name (English)": "<Extracted Name>",
      "Lessee Name (Arabic)": "<Extracted Name>",
      "Share (Sq Meter)": "<Extracted Value>"
    },
    ...
  ]
  ```
#### **3. Transaction Details:**
- Extract and return under `"Transaction Details"`:

  - `"Land Registration No"`
  - `"Transaction Date"`
  - `"Amount"` → Extract full amount as **numbers only** (ignore text like "Dirhams").

---

### **Output Requirements:**
- **The extracted information should be well-structured and grouped into sections.**
- **Ensure that Arabic and English text are properly separated as instructed.**
- **Maintain the original structure of the document, ensuring all sections are properly categorized.**
- **Preserve correct numerical formats, special characters, and accurate text encoding.**
"""

CONTRACT_F_PROMPT= """
"Return a valid JSON object with no extra explanation or commentary. "
    "If this page belongs to the Terms and Conditions section, extract the following fields exactly:\n"
    "  - \"contract_date\"\n"
    "  - \"term_payment\"\n"
    "  - \"payment_details\"\n"
    "those information would be found in the first 6 terms so ignore the others. "
    "If the page does not belong to the Terms and Conditions section, you should return the data of each section in json format only the english data. "
    "remember to fetch all the data except for the terms and condition and note the data is listed in two columns left and right "
    "for each section ensure you put the section name in the json. "
    "don't put this ```json  in the response"
   """

# Prompt to extract full contract on page 1
INITIAL_CONTRACT_OF_SALE_PROMPT = '''
You are a document‑understanding assistant. Given the visual contents of an Initial Contract of Sale PDF page, extract **only** the following fields and return exactly one JSON object (no extra text).

— For every numeric field (areas, prices), return digits only (strip any “Sq.M.”, “AED”, etc.).  
— Ignore any “Participant Number” fields entirely.  
— For each party entry:  
    • If `type` is “Company”, include **`license`** (omit `uae_id_number` and `passport_number`).  
    • If `type` is “Person”, include **`uae_id_number`** and, if present, **`passport_number`** (omit `license` and `passport_expiry`).  

Fields to extract:

- `contract_number`  
- `contract_date`  
- `project_name`  
- `developer_name`  
- `property_name`  
- `net_sold_area`  
- `common_area`  
- `property_value`  
- `original_price`
- `property_type`  
- `land_number`  
- `area`  
- `sellers`: array of objects, each with:  
    • `name`  
    • `area`  
    • `uae_id_number` (only if `type` = “Person”)  
    • `passport_number` (if present)  
    • `type`  
    • `nationality` (if present , omit it if not present)
    • `license` (only if `type` = “Company”)  
- `buyers`: array of objects, each with:  
    • `name`  
    • `uae_id_number` (only if `type` = “Person”)  
    • `passport_number` (if present)  
    • `nationality`  
    • `area`  
    • `type`  
- `mortgage_status`

'''

# Prompt to detect presence of PARTIES section on subsequent pages
detect_parties_prompt = '''
You are a document‑understanding assistant. Given an image of one page, respond **only** with 'yes' if this page contains a PARTIES section (the headings SELLER(S) or BUYER(S)), otherwise respond only with 'no'. No extra text.
'''

# Prompt to extract parties and vouchers on pages containing PARTIES
extract_parties_and_vouchers_prompt = '''
You are a document‑understanding assistant. Given the visual contents of an Initial Contract of Sale PDF page containing a PARTIES section, extract **only** these three arrays and output exactly one JSON object (no extra text):
if the parties section contain subsections like SELLER(S) and BUYER(S)
you should get the following:
- sellers: array of objects with keys name, uae_id_number (if present)(only if type “Person”), passport_number (if present), nationality, area, type.
- buyers: array of objects with keys name, uae_id_number (if present)(only if type “Person”), passport_number (if present), nationality, area, type.
- voucher_list: array of objects with keys participant_name, voucher_date, voucher_number_year, voucher_amount, receipt_number_year, receipt_date.
if the parties section contain doesn't contain subsections like SELLER(S) and BUYER(S)
then the data under if is for buyers
you should get the following:
- buyers: array of objects with keys name, uae_id_number (if present)(only if type “Person”), passport_number (if present), nationality, area, type.
- voucher_list: array of objects with keys participant_name, voucher_date, voucher_number_year, voucher_amount, receipt_number_year, receipt_date.
Ignore any 'Participant Number' fields entirely.
'''
