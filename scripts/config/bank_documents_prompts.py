
cheque_vlm_prompt = """
Please extract the following details from each cheque present in the provided image:
- Bank Name
- Cheque Number
- Payer Name
- Amount in AED (or any other currency, if present)
- Account Number
- Issue Date (if available) and should be returned in this format dd/mm/yyyy
- validity period if (available)

Return the data in Json format for each cheque

Please ensure to process all cheques on the document and return the details in a structured format for each cheque, making sure to account for multiple cheques if they exist in the same document.
"""


MORTGAGE_LETTER_EXTRACTION_PROMPT = """
Please extract the following information from the provided mortgage letter document:

1. **Dubai Land Department Mention**: Check if "Dubai Land Department" or "دائرة الاراضي و الاملاك" is found in the document (in either Arabic or English). If found, return "Yes", otherwise return "Not found" to check if itis addressed to dubai land department.
2. **Mortgage Start Date**: Extract the Mortgage Start Date from the document. If a date is not mentioned, return "Not mentioned".
3. **Mortgage End Date**: Extract the Mortgage End date date from the document. If a date is not mentioned, return "Not mentioned".
4. **Property Owners**: Extract the property Owner.
5. **Mortgage Amount**: Extract the Mortgage Amount.
6. **Signed**: check if the letter is signed or not and return Yes or No
7. **Arabic**: check if arabic Exists return Yes or No.
Ensure that the extracted information is returned in JSON format, with the following structure:

{
  "Addressed to DLD": "<Yes or No>",
  "Mortgage_Start_Date": "<Date or Not mentioned>",
  "Mortgage_End_Date": "<Date or Not mentioned>",
  "Owner":"<Property Owner or Not mentioned>",
  "Mortgage_Amount":"<Mortgage_Amount or Not mentioned>",
  "Signed":"<Yes | No>",
  "Arabic":"<Yes | No>"
  
}
"""










