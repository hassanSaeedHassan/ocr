NOC_vlm_prompt="""
Extract the names of the following individuals from the English section of this NOC document:
- Note there is a difference between current purchaser this is the seller and new purchaser this is the buyer.
  • Sellers: individuals referred to as "The Seller" or owners details or "current purchased details" or 'requestor details'
  • Buyers: individuals referred to as "The Buyer" or 'New Purchaser' or "Principal purchaser"
Note :
    - some times it is written in arabic and the seller are mentioned indirectly by transfer from (seller name(s)) to (الى) (buyer name(s))
    - and if "from" or "من"is before the person name (it means one of the sellers).
    - if "to" or "الى" is before the person name (it means one of the buyers).
    - you should ignore all of this if a table exists containing the data of sellers and buyers.
    - example on this note :
            - you may find each person in a line like this (multiple "From" and multiple "To")
            - **From:** (place holder for seller name) – Holder of (place holder for nationality) passport (place holder for the passport number)
            - **From:** (place holder for seller name) - Holder of License(place holder for the company license)
            - **To:**  (place holder for buyer name) – Holder of (place holder for nationality) passport (place holder for the passport number)
            - so if you find this any name beside "From" should be seller and any name beside "To" should be buyer.
            - the keywords "From" and "To" are tricky so stick to the template if they found.
if the names are found only in Arabic use them in Arabic.
also the names could be very long( contain details name (5 or 6))
For each person, extract:
  - name: full name (e.g., "Mr. Samuel Dunnachie")
Also sometimes the seller or the buyer is not found.
- also extract the following:
    - community(can be found as unit location) or can be found in arabic as (المنطقة).
    - unit number or can be found in arabic as (رقم الوحدة).
    - plot number or  can be found in arabic as  (رقم الأرض).
    - Issuing Date: If the issuing date is mentioned, provide it in the format dd/mm/yyyy. If not mentioned, return "not mentioned". The issuing date may appear under the field "التاريخ". For example, if the date is given as "2025 يناير - 2", it should be converted and returned as "02/01/2025" (dd/mm/yyyy).
    - Validation Date or Period: Check for a validation field, which may be labeled as "صلاحية شهادة عدم الممانعة" or similar. If a validation date is mentioned, return it in the format dd/mm/yyyy. If a validation period is mentioned instead, extract the period and return it as follows:
       - For example, if the document states "this certificate is valid for 15 days from the issuing date", return "15 days".
       - If the period is given in Arabic words (e.g., "اربعة عشر"), convert it to its numeric equivalent and append " days" (e.g., "14 days").
       - If the term "شهر" is used, return "30 days".
       - sometimes it is found as expiry date.
       - If neither a validation date nor period is mentioned, return "not mentioned".
    - Dubai Land Department: Check if the document contains a reference to the Dubai Land Department. This may be mentioned as "Dubai Land Department", "دائرة الاراضي و الاملاك دبي", or in variations such as "السادة دائرة األ ارضي واألمالك". Return "Found" if present, otherwise return "not mentioned".
- also a flag mentioning arabic exists or not
Return a single JSON object:
{
  "sellers": [ "Seller Name 1", "Seller Name 2", … ],
  "buyers":  [ "Buyer Name 1", "Buyer Name 2", … ],
  "unit number":'Unit number',
  'community':'Community',
  'plot number':'Plot Number',
  'issung date':'Issuing Date',
  'Validation Date or Period':'Validation Date or Period',
  'Dubai Land Department': Found | not Found,
  'Arabic Found': Found | not Found
}
"""
