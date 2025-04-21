BROAD_CLASSIFICATION_PROMPT ="""
Categories:
Based on the document's visible sections and content structure, please classify the document into one of the following broad categories. Return only the category name in lowercase.

Important Note :any bank letter should be classified as bank document
1. legal – Documents issued by the Dubai government land department (e.g., title deed, pre title deed, title deed (lease to own), title deed (lease finance), initial contract of sale, restrain property certificate, initial contract of usufruct, usufruct right certificate, donation contract, contract f).
2. company – Company related documents (e.g., moa memorandum of association, commercial license, incorporation certificate, company registration, incumbency certificate, translation of legal document) or documents served by jafza and dmcc giving no objection but for company not a property.
3. bank – Bank related documents (e.g., cheques, mortgage contract, mortgage letter, release of mortgage, customer statement, registration tax, receipt).
4. property – Property related documents (e.g., valuation report, noc non objection certificate).
5. personal – Personal documents (e.g., ids, clearance certificate, acknowledgment,power of attorney (POA)).
6. others – Any document that does not clearly match the above categories.

IMPORTANT NOTES:
1.Legal documents should not be from the bank or the developer. If the document header contains the name of a bank, classify it as a bank document.
2.power of attorney (POA) is considered personal document you will find key words like "بيانات الوكيل" or "بيانات الموكل" and you may find them repeated as tables and "توكيل"  in the header.
3. there are two no objection certificates types one related to company (registration,or to own property)and the other is related to property and given by the developper. for example  the document is a non-objection certificate (noc) issued by the jafza (jebel ali freezone authority) to a company,should be company related document so make sure to classify them right.
"""
TD_vlm_prompt = """
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
cheque_vlm_prompt = """
Please extract the following details from each cheque present in the provided image:
- Bank Name
- Cheque Number
- Payer Name
- Amount in AED (or any other currency, if present)
- Account Number
- Issue Date (if available) and should be returned in this format dd/mm/yyyy

Return the data in Json format for each cheque

Please ensure to process all cheques on the document and return the details in a structured format for each cheque, making sure to account for multiple cheques if they exist in the same document.
"""


MORTGAGE_LETTER_EXTRACTION_PROMPT = """
Please extract the following information from the provided mortgage letter document:

1. **Dubai Land Department Mention**: Check if "Dubai Land Department" or "دائرة الاراضي و الاملاك" is found in the document (in either Arabic or English). If found, return "Found", otherwise return "Not found".
   
2. **Issuing Date**: Extract the issuing date from the document. If a date is not mentioned, return "Not mentioned".

3. **Property Details**: Extract the following details about the property:
   - **Property Type**: Extract the type of property mentioned (e.g., residential, commercial).
   - **Property Address**: Extract the full address or location of the property.
   - **Plot Number**: Extract the plot number if mentioned.
   - **Area**: Extract the area in square meters or square feet, if provided.
   - **Building Name**: If mentioned, extract the name of the building or complex.
   - **Unit Number**: Extract the unit number if provided.

Ensure that the extracted information is returned in JSON format, with the following structure:

{
  "dubai_land_department": "<Found or Not found>",
  "issuing_date": "<Date or Not mentioned>",
  "property_details": {
    "property_type": "<Property type or Not mentioned>",
    "property_address": "<Address or Not mentioned>",
    "plot_number": "<Plot number or Not mentioned>",
    "area": "<Area or Not mentioned>",
    "building_name": "<Building name or Not mentioned>",
    "unit_number": "<Unit number or Not mentioned>"
  }
}
"""

NOC_vlm_prompt = """
Please extract the following information from the provided document image:
1. **Issuing Date**: If the issuing date is mentioned, provide it in the format dd/mm/yyyy. If not mentioned, return "not mentioned". The issuing date may appear under the field "التاريخ". For example, if the date is given as "2025 يناير - 2", it should be converted and returned as "02/01/2025" (dd/mm/yyyy).
2. **Developer Name**: Extract the developer name from the top of the document, ensuring that the name is in English only. If not mentioned, return "not mentioned".
3. **Seller**: Extract the names, passport numbers, and nationalities of the sellers. If any of these details are missing, return "not mentioned". This information may be labeled as "current purchaser".
4. **Buyer**: Extract the names, passport numbers, and nationalities of the buyers. If any of these details are missing, return "not mentioned". This information may be labeled as "new purchaser".
5. **Unit Information**: Extract the building name, unit number, unit location & plot number, and land number. If any of these details are missing, return "not mentioned".
6. **Dubai Land Department**: Check if the document contains a reference to the Dubai Land Department. This may be mentioned as "Dubai Land Department", "دائرة الاراضي و الاملاك دبي", or in variations such as "يبد كلاملأاو يضارلأا ةرئاد". Return "Found" if present, otherwise return "not mentioned".
7. **Validation Date or Period**: Check for a validation field, which may be labeled as "صلاحية شهادة عدم الممانعة" or similar. If a validation date is mentioned, return it in the format dd/mm/yyyy. If a validation period is mentioned instead, extract the period and return it as follows:
   - For example, if the document states "this certificate is valid for 15 days from the issuing date", return "15 days".
   - If the period is given in Arabic words (e.g., "اربعة عشر"), convert it to its numeric equivalent and append " days" (e.g., "14 days").
   - If the term "شهر" is used, return "30 days".
   - If neither a validation date nor period is mentioned, return "not mentioned".

Return the extracted information strictly in JSON format with appropriate keys.
"""



TD_vlm_prompt2 = """
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
- Extract values dynamically and return them under `"Title Deed"`:
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
  ```

#### **3. Transaction Details:**
- Extract and return under `"Transaction Details"`:
  - `"Purchased From"` → Extract full English name.
  - `"Land Registration No"`
  - `"Transaction Date"`
  - `"Amount"` → Extract full amount as **numbers only** (ignore text like "Dirhams").

#### **4. Additional Notes:**
- **Names and Companies Handling:**
  - Names may appear in **two lines**, so extract the full name without missing parts.
  - Company names should be extracted in **English only** if both languages are present.
- **Dynamic Field Extraction:**
  - If a field is not explicitly mentioned but present in the document, extract it dynamically and categorize it appropriately.

---

### **Output Requirements:**
- **The extracted information should be well-structured and grouped into sections.**
- **Ensure that Arabic and English text are properly separated as instructed.**
- **Maintain the original structure of the document, ensuring all sections are properly categorized.**
- **Preserve correct numerical formats, special characters, and accurate text encoding.**
"""

BROAD_CLASSIFICATION_PROMPT2 = """
Based on the document's visible sections and content structure, please classify the document into one of the following broad categories. Return only the category in lowercase:


NOTE : Legal documents should not be from the bank or the developper.
if the documents has the name of the bank in the header it should be bank document
1. legal: documents issued by Dubai government land department,These documents should be one of those:
   - title deed: a legal document issued by the Dubai government/land department mentioning property ownership. Header must contain "Title Deed" and "شهادة ملكية عقار", include property details, and must not contain "الموضوع" or "طلب".
   - pre title deed: header contains "شهادة بيع مبدئي" and includes sections for owners and buyers, without "الموضوع" or "طلب".
   - title deed (lease to own): header explicitly contains "title deed(lease to own)" and excludes طلب تسجيل, الموضوع, subject line, letter body, or "استمارة".
   - title deed (lease finance): header includes "title deed lease finance" and excludes طلب تسجيل, الموضوع, subject line, letter body text, or "استمارة".
   - initial contract of sale: issued by a government or land department with header phrases like "initial contract from dubai government", "property sale contract between seller and buyer from dubai government", or "initial contract of usufruct".
   - restrain property certificate: header must contain both "restrain property certificate" and "شهادة تقييد عقار" (unless it contains "إستمارة قيد عقار للبيع", then it is not included).
   - initial contract of usufruct: header must include "initial contract of usufruct".
   - usufruct right certificate: header must contain "شهادة حق منفعة" and include sections for lessors and lessees without "الموضوع" or "طلب".
   - donation contract: must contain "donation contract" in the header.
   - contract f: a contract with details including parties, property, and terms, and must contain "Unified Sell Contract(F)" in the header.

2. company: Company related documents. These include:
   - moa memorandum of association: a legal document outlining company establishment details.
   - commercial license: a legal document for a company's commercial license.
   - incorporation certificate: confirms a company's official registration.
   - company registration: pertains to the registration of a company.
   - incumbency certificate: verifies current officers/directors and their authority.
   - translation of legal document: includes keywords like "ترجمة" indicating a translated document.
   - no objection certificate for a company: where it received from jafza, DMCC

3. bank: Bank related documents. These include:
   - cheques: containing bank check details (bank name, payee, signature, security features).
   - mortgage contract: legal agreement between a borrower and lender with property/mortgage details.
   - mortgage letter: a bank letter detailing mortgage information; subject must include "تسجيل رهن", "طلب تسجيل عقار", "registration of mortgages" or similar.
   - release of mortgage: a letter from a bank indicating the release of a mortgage (may include فك رهن).
   - customer statement: details customer-specific financial transactions or account summaries.
   - registration tax: contains invoice details, procedural info, and a breakdown of taxes/payments.
   - receipt: includes header, receipt number, procedure, and payment details, and must not be a cheque.

4. property: Property related documents. These include:
   - valuation report: contains property valuation details, company information, evaluation results, and certification.
   - noc non objection certificate: contains non objection certificate details with phrases like "non objection certificate", "رسالة عدم ممانعة", etc, also it must be to persons not company related.

5. personal: Personal documents. These include:
   - ids: documents containing personal identification details.
   - power of attorney: legal document granting authority, including keywords like "وكاله", "الوكيل", or "الموكل".
   - clearance certificate: issued by an authorized government agency confirming obligations are fulfilled.
   - acknowledgment: contains words like "إقرار", "بيانات المقر", etc.

6. others: Any document that does not clearly match the above categories.
you should only return the category of the document in lower don't ever give the final type of the document.
"""

# ------------------------- Detailed Prompts -------------------------
# For legal documents issued by Dubai government land department:
LEGAL_PROMPT = """
This document has been identified as a legal document issued by the Dubai government/land department.and they are not from banks Based on its visible sections and content structure, please classify it into one of the following types. Return only the type in lowercase.


1. **title deed**:
   - Issued by Dubai government/land department.
   - Header contains "Title Deed" and "شهادة ملكية عقار".
   - Includes property details like plot number, building name, and area (sqm/ft).
   - Must contain a section with "owners numbers and their shares".
   - Does not contain "الموضوع" or "طلب".
   - No body paragraphs (not a letter).

2. **usufruct right certificate**:
   - Header contains "شهادة حق منفعة".
   - Contains sections for **lessors and their shares** and **lessees and their shares**.
   - Does not contain "الموضوع" or "طلب" or letter body.

3. **title deed lease to own**:
   - Similar to title deed, but header contains "title deed lease to own".
   - Contains **owners numbers and their shares** and **lessees and their shares**.

4. **title deed lease finance**:
   - Similar to title deed, but header contains "title deed lease finance".
   - Contains **owners numbers and their shares** and **lessees and their shares**.

5. **pre title deed**:
   - Issued by Dubai government/land department.
   - the header must  contain "شهادة بيع مبدئي" and logos of Dubai government and land department.
   - Contains sections for **owners and their shares** and **buyers and their shares**.

6. **restrain property certificate**:
   - Issued by Dubai Government, Land Department.
   - Header contains "Restrain Property Certificate" and "شهادة تقييد عقار".
   - Contains the statement: "Real estate registration service department certifies that all transactions against the following property have been blocked in the DLD systems".
   - Does not contain "استمارة".

7. **property restrain procedure**:
   - This document details a **property restrain procedure** (like a blocking property transaction).
   - Contains procedure type, procedure number, procedure date, and buyer/seller details.
   - The key phrase to identify this document is: "PROPERTY RESTRAIN" in the header.
   - Not a certificate, but a **transactional document** related to the property restrain.
   
8.**initial contract of sale**:
    - A document issued by a government or land department that must have in its header one of the following phrases: "initial contract from dubai government", "property sale contract between seller and buyer from dubai government", or "initial contract of usufruct".
9.**initial contract of usufruct**:
    - A legal document issued by the Dubai government whose header must include "initial contract of usufruct".
10.**donation contract**:
    - A legal donation contract which must contain "donation contract" in the header.
11.**contract f**: 
    - A document with contract details including parties, property details, and terms of agreement. It must contain "Unified Sell Contract(F)" in the header or "عقد البيع الموحد".and its first section is contract information.
Note documents containing  the header must  contain "شهادة بيع مبدئي" and logos of Dubai government and land department are pre title deed.
Return the name of the document in Lower and If the document does not clearly match any of these, return "legal".
"""

# For company related documents:
COMPANY_PROMPT = """
This document has been identified as a company related document. Based on its visible sections and content structure, please classify it into one of the following types. Return only the type in lowercase.
- company NOC: is a document given by JAFZA or DMCC to clarify no objection on selling,transfering or owning a property.
- moa memorandum of association: a legal document outlining company establishment details.
- commercial license: a legal document for a company's commercial license.
- incorporation certificate: confirms a company's official registration.
- company registration: pertains to the registration of a company.
- incumbency certificate: verifies current officers/directors and their authority.
- translation of legal document: includes keywords like "ترجمة" indicating a translated document where you will find translation from english to arabic via different translation companies.
- Certificate of good standing: A Certificate of Good Standing confirms a company's legal registration, compliance with regulations, and authorization to operate, issued by a government authority
Return the name of the document and If the document does not clearly match any of these, return "company".
"""

# For bank related documents:
BANK_PROMPT = """
This document has been identified as a bank related document. Based on its visible sections and content structure, please classify it into one of the following types. Return only the type in lowercase.

- cheques: a document containing bank check details such as bank name, payee information, signature, and security features.
- mortgage contract: a legal agreement with property and mortgage details.
- mortgage letter: a bank letter detailing mortgage information; the subject must include "تسجيل رهن", "طلب تسجيل عقار", "تسجيل عقد رهن حق منفعة من الدرجة الاولى","registration of mortgages" or similar.
- release of mortgage: a letter from a bank indicating the release of a mortgage; it may include فك رهن.
- liability letter: A liability letter from the bank confirming the borrower's outstanding debts, payment obligations, and loan terms.
- customer statement: details customer-specific financial transactions or account summaries.
- registration tax: contains invoice details, procedural information, and a breakdown of taxes/payments.
- receipt: includes header, receipt number, procedure, and payment details, and must not be a cheque.
Return the name of the document and If the document does not clearly match any of these, return "bank".
"""

# For property related documents:
PROPERTY_PROMPT = """
This document has been identified as a property related document. Based on its visible sections and content structure, please classify it into one of the following types. Return only the type in lowercase.

- valuation report: contains property valuation details, company information, evaluation results, and certification.
- noc non objection certificate: A document that exclusively contains non objection certificate details. The header and content may include any of the following: "non objection certificate", "رسالة عدم ممانعة", or "شهادة عدم ممانعة" or شهادة لا مانع" ,  "شهادة عدم ممانعة لنقل وحدة","عدم ممانعة تحويل جزئي لملكية عقار","لا مانع من تحويل عقار","شهادة عدم ممانعة من تحويل ملكية عقار","لا مانع من بيع و تسجيل وحدة", "لا مانع من التحويل و التسجيل النهائي و اصدار شهادة حق منفعة", "رسالة لا مانع". It must not be confused with a release mortgage.If the document does not clearly match any of these, return "property".

Return the name of the document and if can't return property"""

# For personal documents:
PERSONAL_PROMPT = """
This document has been identified as a personal document. Based on its visible sections and content structure, please classify it into one of the following types. Return only the type in lowercase.

- ids: contains personal identification details must be issued by UAE.
- passport:contain image of passport and the personal details.
- residence visa:residence visa issued by the government of UAE.
- POA:This document is a legal representation form from the Dubai Courts, detailing the appointment of a power of attorney for an individual, including the names, nationalities, and identification numbers of the principal and the attorney-in-fact.including keywords like "وكاله", "الوكيل", or "الموكل".
- clearance certificate: issued by a government agency confirming all obligations are fulfilled.
- acknowledgment: An acknowledgment document containing words like "إقرار" and "بيانات المقر" , "بيانات ممثل المقر" ,"بيانات المقر له".
If the document does not clearly match any of these, return "personal".
"""
