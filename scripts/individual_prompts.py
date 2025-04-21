LANGUAGE_PROMPT2 = """
Note: some pages mix English and Arabic in two columns as the page is splitted into two columns the right one include Arabic and the left include English.
and sometimes the line contain arabic and english
Check if this page contains the principal/attorney data in English.
Answer with exactly "yes" if it is English, otherwise "no".
You will see the start of the English block after a line of dashes:
-----------------------------------------------
"""
LANGUAGE_PROMPT = """
if you found "power of attorney" in the content of the page then it contains English
Answer with exactly "yes" if it is English, otherwise "no".
"""

POA_PROMPT_ENG = """
Extract the following from the English section of this power‑of‑attorney document image and return valid JSON.
Roles:
  • Principals: individuals referred to as "The Principal"
  • Attorneys: individuals referred to as "The Attorney"
  • Virtue Attorneys: individuals referred to as "The Virtue Attorney" (if any)

For each person, extract:
  - name: full name (e.g., "Mr. Samuel Dunnachie")
  - nationality: (e.g., "British National")
  - emirates_id: the Emirates ID number or empty string if none
  - passport_no: passport number or empty string if none

Return a single JSON object:
{
  "principals": [ … ],
  "attorneys":  [ … ],
  "virtue_attorneys": [ … ]
}
"""
POA_PROMPT_ENG2 = """
Please extract the following details from the document text and return them as valid JSON. The document may list one or more individuals in each of the following roles. Use the designations provided in the text (e.g., "hereinafter referred as 'The Principal'" and "hereinafter referred as 'The Attorney'") to assign each person to the correct role. Note that some documents might include multiple principals, multiple attorneys, or even multiple virtue attorneys.

For each individual, extract:
- name (e.g., "Mr. Samuel Dunnachie")
- nationality (e.g., "British National")
- Emirates ID (if provided; if not, return an empty string)
- Passport No (if provided; if not, return an empty string)

Group the individuals as follows:
1. principals: All individuals designated as “The Principal” (or similar phrasing) in the text.
2. attorneys: All individuals designated as “The Attorney” (or similar phrasing) in the text.
3. virtue_attorneys: All individuals designated as “The Virtue Attorney” (or similar phrasing) in the text, if any.

Return the output in this JSON format:

{
  "principals": [
    {
      "name": "…",
      "nationality": "…",
      "emirates_id": "…",
      "passport_no": "…"
    },
    ...
  ],
  "attorneys": [
    {
      "name": "…",
      "nationality": "…",
      "emirates_id": "…",
      "passport_no": "…"
    },
    ...
  ],
  "virtue_attorneys": [
    {
      "name": "…",
      "nationality": "…",
      "emirates_id": "…",
      "passport_no": "…"
    },
    ...
  ]
}

Ensure that you:
- Only include the actual details of the individuals, not the role labels.
- Return empty strings for any missing fields.
- Provide all values in English.

Extract the details based on the following example text:

----
* 
We, • Mr. Samuel Dunnachie, British National, holder of Passport No. 537539491, • and Mrs. Moira Janet Dunnachie, British National, holder of Passport No. 563759779 • and Mr. Paul Dunnachie, British National, holder of Passport No. 556662405 • and Mrs. Laura Nicol, British National, holder of Passport No. 122696112 Hereinafter referred as “The Principal” do hereby duly appoint, nominate, and authorize, • Mrs. Helen Elizabeth Haig Kirby, British National, holder of Emirates ID Card No. 784-1972-1694940-0, Hereinafter referred as “The Attorney”, to be our true and lawful attorney...
----

Based on the above text, the correct extraction should group:
- The four individuals as principals.
- The single individual as the attorney.
- No virtue attorneys if none are designated.
"""
    # Arabic extraction prompt.
POA_PROMPT_ARABIC = """
extract the text data including the names of persons mentioned and the roles in arabic either prinicpal or attorney
which will be found in the first paragraph in the document so ignore the terms.
- note you will find و يشار اليه بالوكيل  after the details of the attorneys
- while you will find "ويشار اليه بالموكل" after the details of the prinicpals
- Note sometimes the data represented in tables for each one of them :
    - the header of the table will indicate the role either (prinicpal,attorney or virtue_attorney)
    - the first  column is the name.
    - the second column is the nationality.
    - the third column is document type (passport or emirates id)
    - the fourth column is the document number (passport number or emirates id number)
    - ignore the fifth column
    
the person should be only classified as either one of the roles so don't repeat the same person with different roles.


"""

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


    