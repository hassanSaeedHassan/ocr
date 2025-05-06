## emirates id prompt

ID_vlm_prompt = """
Please extract the following information from the provided ID document image:
the id could be resident identity card, identity card, golden card,passport or residence from UAE government.
do your best to get the dates accuratly.
NOte don't but the word name in the name in english field nor but the word 'الاسم'in the name in arabic field.
1. **From the Front Side of the ID:**
   - **Name in Arabic**: Extract the name written in Arabic don't put any characters except Arabic in this field.
   - **Name in English**: Extract the name written in English.
   - **Emirates ID**: Extract the Emirates ID number (in English).
   - **Nationality in English**:Extract the Nationality (in English).
   - **Gender**: Extract the gender (in English).
   - **Issuing Date**: Extract the issuing date (in English).
   - **Expiry Date**: Extract the expiry date (in English).
   - **Date of Birth**: Extract the date of birth (in English).
   
2. **From the Back Side of the ID (if present):**
   - **Occupation**: Extract the occupation listed on the back.
   - **Issuing Place**: Extract the issuing place listed on the back.

If any of these fields are not mentioned or are missing, return "not mentioned" for that specific field.

Ensure that the extracted information is returned in JSON format, with the following structure:
{
    "front": {
        "name_arabic": "<name in Arabic or 'not mentioned'>",
        "name_english": "<name in English or 'not mentioned'>",
        "emirates_id": "<Emirates ID or 'not mentioned'>",
        "nationality": "<Nationality In English or 'not mentioned'>"
        "gender": "<gender or 'not mentioned'>",
        "issuing_date": "<issuing date or 'not mentioned'>",
        "expiry_date": "<expiry date or 'not mentioned'>",
        "date_of_birth": "<date of birth or 'not mentioned'>"
    },
    "back": {
        "occupation": "<occupation or 'not mentioned'>",
        "issuing_place": "<issuing place or 'not mentioned'>"
    }
}
"""

# passport Prompt
passport_prompt = """
You are given an image of a passport. Extract the following fields from the image and return them in JSON format:

- combine both the Surname and Given Name to get the full name
- Nationality or Place of Birth or Country (whichever is available and should be returned in English)
- Date of Birth (format: dd/mm/yyyy)
- Gender (M or F)
- Date of Issue (format: dd/mm/yyyy)
- Date of Expiry (format: dd/mm/yyyy)

Instructions:
- All text must be in English, exactly as it appears on the passport.
- All dates must be in the format dd/mm/yyyy.
- If any field is missing or unreadable, set its value to "Not found".
- Do not include any additional text or explanation. Only return the JSON object.

Example output format:
{
  "fullname": "<value>",
  "Nationality or Place of Birth": "<value>",
  "Date of Birth": "dd/mm/yyyy",
  "Gender": "M or F",
  "Date of Issue": "dd/mm/yyyy",
  "Date of Expiry": "dd/mm/yyyy"
}
"""

## Residence visa prompt
VISA_PROMPT= """
You are an intelligent document parser that extracts structured data from official visa documents written in both Arabic and English.

Please extract the following fields and return them as a valid JSON object:

- full_name (English full name of the individual)
- arabic_name (Arabic full name of the individual)
- emirates_id which is رقم الهوية
- visa_number (e.g., "Dubai 201/2023/XXXXXXX")
- passport_number
- designation (e.g., "MANAGER")
- sponsor (e.g., "Self Sponsor")
- issue_date (تاريخ إصدار الإقامة) this date will be found at the bottom right of the image
- expiry_date take care of the year in expire date (تاريخ الانتهاء) this date will be found at the left of the image.

take care of those values 2033,2032,2022,2023
Return the data in json format
"""

