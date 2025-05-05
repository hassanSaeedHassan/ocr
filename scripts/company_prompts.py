company_license_prompt = """
Extract the following details from the **Dubai Commercial License** document. If a field is missing, return "Not Mentioned".

### **1. License Details**
- License Number  
- Main License Number (if different)  
- Account Number (if available)  
- Registration Number (DCCI or Commercial Register No.)  
- Company Name (Licensee)  
- Business Name / Operating Name (if different)  
- Legal Type (e.g., Private Joint Stock Company, LLC, etc.)  
- License Category (e.g., Department of Economic Development)  
- Country of Origin  
- Issue Date  
- Expiry Date  
- DUNS Number (if available)  

### **2. Authorized Signatory / Manager**
- Name of Authorized Signatory  
- Position / Role  
- Nationality  
- Person ID / Employee ID  

### **3. License Primary Address**
- Office / Suite / Unit Number (if available)  
- Building Name / Tower Name  
- Plot Number (if mentioned)  
- PO Box  
- Parcel ID (if available)  
- Full Address (including area, city, country)  

### **4. Company Contact Details**
- Phone Number  
- Fax Number (if available)  
- Mobile Number  
- Email  

### **5. Business Activities**
- List all business activities mentioned in the document  

### **6. Additional Remarks (if present)**
- Extract any additional remarks or comments  

Ensure the extracted data is in the following **JSON format**, marking missing fields explicitly as `"Not Mentioned"`:

```json
{
  "LicenseDetails": {
    "LicenseNumber": "Not Mentioned",
    "MainLicenseNumber": "Not Mentioned",
    "AccountNumber": "Not Mentioned",
    "RegistrationNumber": "Not Mentioned",
    "CompanyName": "Not Mentioned",
    "BusinessName": "Not Mentioned",
    "LegalType": "Not Mentioned",
    "LicenseCategory": "Not Mentioned",
    "CountryOfOrigin": "Not Mentioned",
    "IssueDate": "Not Mentioned",
    "ExpiryDate": "Not Mentioned",
    "DUNSNumber": "Not Mentioned"
  },
  "AuthorizedSignatory": {
    "Name": "Not Mentioned",
    "Role": "Not Mentioned",
    "Nationality": "Not Mentioned",
    "PersonID": "Not Mentioned"
  },
  "LicensePrimaryAddress": {
    "OfficeNumber": "Not Mentioned",
    "BuildingName": "Not Mentioned",
    "PlotNumber": "Not Mentioned",
    "POBox": "Not Mentioned",
    "ParcelID": "Not Mentioned",
    "FullAddress": "Not Mentioned"
  },
  "CompanyContactDetails": {
    "PhoneNumber": "Not Mentioned",
    "FaxNumber": "Not Mentioned",
    "MobileNumber": "Not Mentioned",
    "Email": "Not Mentioned"
  },
  "BusinessActivities": [
    "Not Mentioned"
  ],
  "Remarks": "Not Mentioned"
}
"""

incumbency_prompt = """
Extract the following details from the **Certificate of Incumbency** document. If a field is missing, return "Not Mentioned".

### **1. Company Details**
- **Company Name**  
- **Registration Number** (if found)  

### **2. Directors**
For each director mentioned in the document:
- **Name**  
- **Nationality** (if available)  

### **3. Shareholders**
For each shareholder mentioned in the document:
- **Name**  
- **Nationality** (if available)  
- **Share Held** (if available)  

### **4. Financial Information**
- **Total Share Capital** (if mentioned)  

### **5. Certificate Details**
- **Issue Date** (format: dd/mm/yyyy)  
- **Validity Duration** (e.g., "6 months")  

Ensure the extracted data is returned in the following **JSON format**, marking missing fields explicitly as `"Not Mentioned"`:

```json
{
  "CompanyDetails": {
    "CompanyName": "Not Mentioned",
    "RegistrationNumber": "Not Mentioned"
  },
  "Directors": [
    {
      "Name": "Not Mentioned",
      "Nationality": "Not Mentioned"
    }
  ],
  "Shareholders": [
    {
      "Name": "Not Mentioned",
      "Nationality": "Not Mentioned",
      "ShareHeld": "Not Mentioned"
    }
  ],
  "FinancialInformation": {
    "TotalShareCapital": "Not Mentioned"
  },
  "CertificateDetails": {
    "IssueDate": "Not Mentioned",
    "ValidityDuration": "Not Mentioned"
  }
}

"""
Incorporation_Certificate_prompt = """
Extract the following details from the **Incorporation Certificate** document. If a field is missing, return "Not Mentioned".

Return the data in the following **JSON format**, ensuring proper structure:

```json
{
  "CompanyName": "Not Mentioned",
  "DateOfIncorporation": "Not Mentioned",
  "LimitedLiabilityNumber": "Not Mentioned",
  "RegistrationNumber": "Not Mentioned"
}
"""
certificate_good_stand_prompt="""
Extract the following details from the **Certificate of good stand** document. If a field is missing, return "Not Mentioned".
Note the dates should be in this format dd/mm/yyyy
Return the data in the following **JSON format**, ensuring proper structure:

```json
{
  "CompanyName": "Not Mentioned",
  "RegisterationDate": "Not Mentioned",
  "LimitedLiabilityNumber or RegistrationNumber": "Not Mentioned",
  "IssuingDate": "Not Mentioned",
  "validity":"Not Mentioned"
}
"""