# ------------------------- Prompts -------------------------
LANGUAGE_PROMPT_TABLE_DETECT = (
    """
if you found "power of attorney" in the content of the page then it contains English
Answer with exactly "yes" if it is English, otherwise "no".
"""
)

LANGUAGE_PROMPT_IMAGE_DETECT = (
    """
some pages mix English and Arabic in two columns as the page is split into two columns,
the right one includes Arabic and the left includes English.
if you found power of attorney in the page then it contains English
Check if this page contains the principal/attorney data in English.
Answer with exactly "yes" if it is English, otherwise "no".
You will see the start of the English block after a line of dashes:
-----------------------------------------------
"""
)

POA_PROMPT_ENG = (
    """
Extract the following from the English section of this power-of-attorney document image and return valid JSON.
Roles:
  • Principals: individuals referred to as "The Principal"
  • Attorneys: individuals referred to as "The Attorney"
  • Virtue Attorneys: individuals referred to as "The Virtue Attorney" (if any)

For each person, extract:
  - name: full name (e.g., "Mr. Samuel Dunnachie")
  - nationality: (e.g., "British National")
  - emirates_id: the Emirates ID number  which could be  و يحمل هوية رقم  or empty string if none
  - passport_no: passport number which could be  و يحمل جواز سفر رقم or empty string if none 

Return a single JSON object:
{
  "principals": [ … ],
  "attorneys":  [ … ],
  "virtue_attorneys": [ … ]
}
"""
)

POA_PROMPT_ARABIC = (
    """
extract the text data including the names of persons mentioned and the roles in arabic either principal or attorney
which will be found in the first paragraph in the document so ignore the terms.
- note you will find و يشار اليه بالوكيل after the details of the attorneys
- while you will find "ويشار اليه بالموكل" after the details of the principals
- Note sometimes the data is in tables with header indicating the role, first column name, second nationality,
  third document type, fourth document number; ignore other columns.
- Do not repeat the same person under multiple roles.
"""
)