# main classification Prompt
BROAD_CLASSIFICATION_PROMPT ="""
Categories:
Based on the document's visible sections and content structure, please classify the document into one of the following broad categories. Return only the category name in lowercase.

Important Note :any bank letter should be classified as bank document
1. legal – Documents issued by the Dubai government land department (e.g., title deed, pre title deed, title deed (lease to own), title deed (lease finance), initial contract of sale, restrain property certificate, initial contract of usufruct, usufruct right certificate, donation contract, contract f).
2. company – Company related documents (e.g., moa memorandum of association, commercial license, incorporation certificate, company registration, incumbency certificate, translation of legal document) or documents served by jafza and dmcc giving no objection but for company not a property like company noc.
3. bank – Bank related documents (e.g., cheques, mortgage contract, mortgage letter, release of mortgage, customer statement, registration tax, receipt).
4. property – Property related documents (e.g., valuation report, noc non objection certificate).
5. personal – Personal documents (e.g., ids, clearance certificate, acknowledgment,power of attorney (POA), power of attorney for specific property"وكالة" or 'وكالة خاصة بالعقارات' or 'توكيل رسمي' or 'توكيل رسمي خاص بالعقارات' ).
6. others – Any document that does not clearly match the above categories.

IMPORTANT NOTES:
1.Legal documents should not be from the bank or the developer. If the document header contains the name of a bank, classify it as a bank document.
2.power of attorney (POA) is considered personal document you will find key words like "بيانات الوكيل" or "بيانات الموكل" and you may find them repeated as tables and "توكيل"  in the header.
3. there are two no objection certificates types one related to company (registration,or to own property)and the other is related to property and given by the developper. for example  the document is a non-objection certificate (noc) issued by the jafza (jebel ali freezone authority) or other authority to a company to can buy a property,should be company related document so make sure to classify them right
4.if you find 'شهادة عدم ممانعة' in the document it must be either noc or company noc.
5.the legal document must be issued from dubai government.
6.the noc is a property document issued from the developer and contains the new purchaser and old purchaser details and non objection from the developer to transfer the ownership of the property.
7. the company noc document you will find it as a letter given by authority to give the company the right to buy a property and you will find the license number of the company.
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

# Legal Related documents:

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
   - header must contain "title deed lease to own" and in arabic ('شهادة ملكية عقار مقيد بحق الإجازة') or "شهادة ملكية العقار (إجازة) ".
   - Contains **owners numbers and their shares** and **lessees and their shares**.
   - Note lesses and their shares must be found.
   - Note the mortagage status will not be found in the data.

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
NOTE JAFZA is not a developper it is government authority so the documents issued from it would be company noc.
- company noc: a non objection certificate document is given from authority like (JAFZA,DMCC,dubai development authority) to give the company the right to buy or sell or transfer a property so you will find it as a letter given from the authority mentioning the company license number and its right to have a property.
- valuation report: contains property valuation details, company information, evaluation results, and certification.
- noc non objection certificate: A document that exclusively contains non objection certificate details. The header and content may include any of the following: "non objection certificate", "رسالة عدم ممانعة", or "شهادة عدم ممانعة" or شهادة لا مانع" ,  "شهادة عدم ممانعة لنقل وحدة","عدم ممانعة تحويل جزئي لملكية عقار","لا مانع من تحويل عقار","شهادة عدم ممانعة من تحويل ملكية عقار","لا مانع من بيع و تسجيل وحدة", "لا مانع من التحويل و التسجيل النهائي و اصدار شهادة حق منفعة", "رسالة لا مانع" and shouldn't be from JAFZA. 
- soa : statment of accounts from the developer of the property.

It must not be confused with a release mortgage.If the document does not clearly match any of these, return "property".
again if you think the document is noc non objection certificate it should contain the purchaser and seller details so before giving the final classification check also if (JAFZA "jabal ali free zone",DMCC,dubai development authority)logo is found in the top as most of the time this should be company noc.
Return the name of the document and if can't return property"""

# For personal documents:
PERSONAL_PROMPT = """
This document has been identified as a personal document. Based on its visible sections and content structure, please classify it into one of the following types. Return only the type in lowercase.

- ids: contains personal identification details must be issued by UAE sometimes it is the back side of the ids which contain occupation and issuing place and machine readable zone.
- passport:contain image of passport and the personal details.
- residence visa:residence visa issued by the government of UAE which will include residence or إقامة in the header.
- POA:This document is a legal representation form from the Dubai Courts, detailing the appointment of a power of attorney for an individual, including the names, nationalities, and identification numbers of the principal and the attorney-in-fact.including keywords like "وكاله", "الوكيل", or "الموكل".
- clearance certificate: issued by a government agency confirming all obligations are fulfilled.
- acknowledgment: An acknowledgment document containing words like "إقرار" and "بيانات المقر" , "بيانات ممثل المقر" ,"بيانات المقر له".
If the document does not clearly match any of these, return "personal".
"""