import streamlit as st
import pandas as pd
import re
from scripts.vlm_utils import safe_json_loads
from scripts.validation import validate_documents
from scripts.unifiers.properties_unifiers import unify_noc
import difflib


def clean_name(n: str) -> str:
    """Remove honorifics and trim whitespace."""
    return re.sub(r'^(Mr\.|Mrs\.|Ms\.|Dr\.)\s*', '', n or '', flags=re.IGNORECASE).strip()


def tokens(name: str) -> set[str]:
    """Split on spaces, lowercase, drop 1–2 character tokens."""
    return {t.lower() for t in re.split(r"\s+", name) if len(t) > 2}


def infer_role_old(name: str, sellers: list, buyers: list) -> str:
    """Assign seller/buyer/unknown based on name matching."""
    lname = name.lower()
    for s in sellers:
        if s.lower() in lname:
            return 'seller'
    for b in buyers:
        if b.lower() in lname:
            return 'buyer'
    return 'unknown'
def infer_role(name: str, sellers: list, buyers: list) -> str:
    name_toks = tokens(name)
    # seller if at least 2 tokens overlap
    for s in sellers:
        if len(name_toks & tokens(s)) >= 2:
            return 'seller'
    # buyer if at least 2 tokens overlap
    for b in buyers:
        if len(name_toks & tokens(b)) >= 2:
            return 'buyer'
    return 'unknown'



def map_doc_label(doc: str) -> str:
    """Map raw doc codes to display labels."""
    return {
        'ids': 'Emirates ID',
        'passport': 'Passport',
        'residence visa': 'Residence Visa'
    }.get(doc, doc.title())


    
    
    

def _find_contact_info_old(name: str, contact_map: dict, cutoff: float = 0.6):
    """
    Try to match `name` to one of the keys in contact_map:
     1) exact match
     2) all tokens in key appear in name
     3) fuzzy match via difflib.get_close_matches
    """
    # 1) exact
    if name in contact_map:
        return contact_map[name]

    # 2) token‐subset
    name_lower = name.lower()
    for key, info in contact_map.items():
        tok_list = key.lower().split()
        if all(tok in name_lower for tok in tok_list):
            return info

    # 3) fuzzy
    matches = difflib.get_close_matches(name, contact_map.keys(), n=1, cutoff=cutoff)
    if matches:
        return contact_map[matches[0]]

    return {}


# Helper: fuzzy‐and‐token match into contact_map
def _find_contact_info(name: str, contact_map: dict, cutoff: float = 0.6):
    # guard against name=None or empty contact_map
    if not name or not contact_map:
        return {}
    if name in contact_map:
        return contact_map[name]
    name_low = name.lower()
    for key, info in contact_map.items():
        toks = key.lower().split()
        if all(tok in name_low for tok in toks):
            return info
    matches = difflib.get_close_matches(name, contact_map.keys(), n=1, cutoff=cutoff)
    return contact_map[matches[0]] if matches else {}



def render_person_roles_editor_old(results, appt_row=None, key='person_roles_editor'):
    """
    Build and display an editable table of persons with their roles and document expiries,
    clustering documents by ID, passport, visa, and POA. Optionally pre‐fills Email and Phone
    from the appointment’s sellers & buyers (appt_row).
    """


    # Helper: fuzzy‐and‐token match into contact_map
    def _find_contact_info(name: str, contact_map: dict, cutoff: float = 0.6):
        if name in contact_map:
            return contact_map[name]
        name_low = name.lower()
        for key, info in contact_map.items():
            toks = key.lower().split()
            if all(tok in name_low for tok in toks):
                return info
        matches = difflib.get_close_matches(name, contact_map.keys(), n=1, cutoff=cutoff)
        return contact_map[matches[0]] if matches else {}

    # 1) If this was passed as a pandas.Series, convert to dict
    if isinstance(appt_row, pd.Series):
        appt_row = appt_row.to_dict()

    # 2) Extract explicit seller/buyer names from any contract or NOC doc
    sellers, buyers = [], []
    contract = next((d for d in results if 'contract f' in d.get('doc_type','').lower()), None)
    if contract:
        cd = safe_json_loads(contract['extracted_data'])
        p1 = cd.get('Page_1', {})
        for v in p1.get('Owner Details', {}).values():
            n = v.get('Seller Name') if isinstance(v, dict) else v
            if n: sellers.append(n.strip())
        for v in p1.get('Buyers Share Details', {}).values():
            n = v.get('Buyer Name') if isinstance(v, dict) else v
            if n: buyers.append(n.strip())
    else:
        noc = next((d for d in results if 'noc' in d.get('doc_type','').lower()), None)
        if noc:
            unified = unify_noc(noc['extracted_data'])
            noc['extracted_data'] = unified
            nd = safe_json_loads(unified) or {}
            def extract_names(f):
                if isinstance(f, str):
                    return [x.strip() for x in re.split(r'\s*,\s*', f) if x.strip()]
                if isinstance(f, dict):
                    return extract_names(f.get('name',''))
                if isinstance(f, list):
                    out = []
                    for it in f:
                        out += extract_names(it.get('name') if isinstance(it, dict) else str(it))
                    return out
                return []
            sellers += extract_names(nd.get('sellers') or nd.get('seller'))
            buyers  += extract_names(nd.get('buyers')  or nd.get('buyer'))

    # 3) Build clusters by Emirates ID
    clusters = []
    def make_cluster(ids, docs, exp_map, label, role):
        clusters.append({
            'id_keys': set(ids),
            'docs': set(docs),
            'expiry_map': dict(exp_map),
            'label': label,
            'role': role,
            'tokens': set(label.lower().split())
        })

    for d in results:
        if d.get('doc_type','').lower() == 'ids':
            data = safe_json_loads(d['extracted_data'])
            front = data.get('front', {})
            name = front.get('name_english','Unknown').strip()
            eid  = re.sub(r'\D','', front.get('emirates_id','') or '')
            exp  = front.get('expiry_date','').strip() or None
            role = infer_role(name, sellers, buyers)
            if not eid:
                continue
            merged = False
            for cl in clusters:
                if eid in cl['id_keys']:
                    cl['docs'].add('ids')
                    cl['expiry_map']['ids'] = exp
                    cl['label'] = name
                    merged = True
                    break
            if not merged:
                make_cluster([eid], ['ids'], {'ids': exp}, name, role)

    # 4) Merge passports by 2‐token name overlap
    for d in results:
        if d.get('doc_type','').lower() == 'passport':
            data = safe_json_loads(d['extracted_data'])
            name = data.get('fullname','').strip() or data.get('full_name','').strip()
            exp  = data.get('Date of Expiry','').strip() or None
            toks = set(name.lower().split())
            merged = False
            for cl in clusters:
                if len(toks & cl['tokens']) >= 2:
                    cl['docs'].add('passport')
                    cl['expiry_map']['passport'] = exp
                    merged = True
                    break
            if not merged:
                make_cluster([], ['passport'], {'passport': exp}, name, 'unknown')

    # 5) Merge visas by ID or token match
    for d in results:
        if d.get('doc_type','').lower() == 'residence visa':
            data = safe_json_loads(d['extracted_data'])
            name = data.get('full_name','').strip() or data.get('fullname','').strip()
            exp  = data.get('expiry_date','').strip() or None
            vid  = ''
            for k in ('emirates_id','passport_no'):
                vid = re.sub(r'\D','', data.get(k,'') or '')
                if vid: break
            merged = False
            if vid:
                for cl in clusters:
                    if vid in cl['id_keys']:
                        cl['docs'].add('residence visa')
                        cl['expiry_map']['residence visa'] = exp
                        merged = True
                        break
            if not merged:
                toks = set(name.lower().split())
                for cl in clusters:
                    if toks & cl['tokens']:
                        cl['docs'].add('residence visa')
                        cl['expiry_map']['residence visa'] = exp
                        merged = True
                        break
            if not merged:
                make_cluster([], ['residence visa'], {'residence visa': exp}, name, 'unknown')

    # 6) Tag POA entries by ID
    for d in results:
        if d.get('doc_type','').lower() == 'poa':
            raw   = safe_json_loads(d['extracted_data']) or {}
            princ = raw.get('principals', {})
            base  = 'unknown'
            if isinstance(princ, dict) and princ:
                first = next(iter(princ.values()), {})
                key   = re.sub(r'\D','', first.get('emirates_id','') or '')
                for cl in clusters:
                    if key in cl['id_keys']:
                        base = cl['role']
                        break
            attys = raw.get('attorneys', [])
            recs  = attys.values() if isinstance(attys, dict) else attys
            for r in recs:
                if not isinstance(r, dict): continue
                key = re.sub(r'\D','', r.get('emirates_id','') or '')
                for cl in clusters:
                    if key in cl['id_keys']:
                        cl['docs'].add('poa')
                        cl['role'] = f'poa_{base}'
                        break

    # 7) Infer any remaining unknown roles
    for cl in clusters:
        if cl['role'] == 'unknown':
            cl['role'] = infer_role(cl['label'], sellers, buyers)

    # 8) Build contact_map from appointment row
    contact_map = {}
    if appt_row:
        for p in appt_row.get('sellers', []) + appt_row.get('buyers', []):
            nm = p.get('fullName') or p.get('firstName')
            if nm:
                contact_map[nm] = {
                    'email': p.get('email',''),
                    'phone': p.get('phone','')
                }

    # 9) Assemble DataFrame rows
    rows = []
    for cl in clusters:
        docs = []
        for d in sorted(cl['docs']):
            if d == 'poa': continue
            lbl = map_doc_label(d)
            exp = cl['expiry_map'].get(d)
            docs.append(f"{lbl}{f' ({exp})' if exp else ''}")
        if 'poa' in cl['docs']:
            docs.append('POA')

        info = _find_contact_info(cl['label'], contact_map)
        rows.append({
            'Name': cl['label'],
            'Provided Documents': ', '.join(docs) or 'none',
            'Role': cl['role'],
            'Individual/Company': 'Individual',
            'Email': info.get('email',''),
            'Phone': info.get('phone','')
        })

    # 10) Render with streamlit.data_editor
    df = pd.DataFrame(rows, columns=['Name','Provided Documents','Role','Individual/Company','Email','Phone'])
    if df.empty:
        df = pd.DataFrame([{c: '' for c in df.columns}])
    df.index += 1

    edited = st.data_editor(
        df,
        column_config={
            'Role': st.column_config.SelectboxColumn('Role',
                options=['seller','buyer','poa_seller','poa_buyer','unknown']
            ),
            'Individual/Company': st.column_config.SelectboxColumn('Individual/Company',
                options=['Individual','Company']
            )
        },
        disabled=['Provided Documents'],
        num_rows='dynamic',
        hide_index=False,
        use_container_width=True,
        key=key
    )

    st.session_state.person_roles       = edited.to_dict(orient='records')
    st.session_state.validation_outcomes = validate_documents(results)

def render_person_roles_editor(results, appt_row=None, key='person_roles_editor'):
    """
    Build and display an editable table of persons with their roles and document expiries,
    clustering documents by ID, passport, visa, and POA. Optionally pre‐fills Email and Phone
    from the appointment’s sellers & buyers (appt_row).
    """


    # Helper: fuzzy‐and‐token match into contact_map
    def _find_contact_info(name: str, contact_map: dict, cutoff: float = 0.6):
        if name in contact_map:
            return contact_map[name]
        name_low = name.lower()
        for key, info in contact_map.items():
            toks = key.lower().split()
            if all(tok in name_low for tok in toks):
                return info
        matches = difflib.get_close_matches(name, contact_map.keys(), n=1, cutoff=cutoff)
        return contact_map[matches[0]] if matches else {}

    # 1) If this was passed as a pandas.Series, convert to dict
    if isinstance(appt_row, pd.Series):
        appt_row = appt_row.to_dict()

    # 2) Extract explicit seller/buyer names from any contract or NOC doc
    sellers, buyers = [], []
    contract = next((d for d in results if 'contract f' in d.get('doc_type','').lower()), None)
    if contract:
        cd = safe_json_loads(contract['extracted_data'])
        p1 = cd.get('Page_1', {})
        for v in p1.get('Owner Details', {}).values():
            n = v.get('Seller Name') if isinstance(v, dict) else v
            if n: sellers.append(n.strip())
        for v in p1.get('Buyers Share Details', {}).values():
            n = v.get('Buyer Name') if isinstance(v, dict) else v
            if n: buyers.append(n.strip())
    else:
        noc = next((d for d in results if 'noc' in d.get('doc_type','').lower()), None)
        if noc:
            unified = unify_noc(noc['extracted_data'])
            noc['extracted_data'] = unified
            nd = safe_json_loads(unified) or {}
            def extract_names(f):
                if isinstance(f, str):
                    return [x.strip() for x in re.split(r'\s*,\s*', f) if x.strip()]
                if isinstance(f, dict):
                    return extract_names(f.get('name',''))
                if isinstance(f, list):
                    out = []
                    for it in f:
                        out += extract_names(it.get('name') if isinstance(it, dict) else str(it))
                    return out
                return []
            sellers += extract_names(nd.get('sellers') or nd.get('seller'))
            buyers  += extract_names(nd.get('buyers')  or nd.get('buyer'))

    # 3) Build clusters by Emirates ID
    clusters = []
    def make_cluster(ids, docs, exp_map, label, role):
        clusters.append({
            'id_keys': set(ids),
            'docs': set(docs),
            'expiry_map': dict(exp_map),
            'label': label,
            'role': role,
            'tokens': set(label.lower().split())
        })

    for d in results:
        if d.get('doc_type','').lower() == 'ids':
            data = safe_json_loads(d['extracted_data'])
            front = data.get('front', {})
            name = front.get('name_english','Unknown').strip()
            eid  = re.sub(r'\D','', front.get('emirates_id','') or '')
            exp  = front.get('expiry_date','').strip() or None
            role = infer_role(name, sellers, buyers)
            if not eid:
                continue
            merged = False
            for cl in clusters:
                if eid in cl['id_keys']:
                    cl['docs'].add('ids')
                    cl['expiry_map']['ids'] = exp
                    cl['label'] = name
                    merged = True
                    break
            if not merged:
                make_cluster([eid], ['ids'], {'ids': exp}, name, role)

    # 4) Merge passports by 2‐token name overlap
    for d in results:
        if d.get('doc_type','').lower() == 'passport':
            data = safe_json_loads(d['extracted_data'])
            name = data.get('fullname','').strip() or data.get('full_name','').strip()
            exp  = data.get('Date of Expiry','').strip() or None
            toks = set(name.lower().split())
            merged = False
            for cl in clusters:
                if len(toks & cl['tokens']) >= 2:
                    cl['docs'].add('passport')
                    cl['expiry_map']['passport'] = exp
                    merged = True
                    break
            if not merged:
                make_cluster([], ['passport'], {'passport': exp}, name, 'unknown')

    # 5) Merge visas by ID or token match
    for d in results:
        if d.get('doc_type','').lower() == 'residence visa':
            data = safe_json_loads(d['extracted_data'])
            name = data.get('full_name','').strip() or data.get('fullname','').strip()
            exp  = data.get('expiry_date','').strip() or None
            vid  = ''
            for k in ('emirates_id','passport_no'):
                vid = re.sub(r'\D','', data.get(k,'') or '')
                if vid: break
            merged = False
            if vid:
                for cl in clusters:
                    if vid in cl['id_keys']:
                        cl['docs'].add('residence visa')
                        cl['expiry_map']['residence visa'] = exp
                        merged = True
                        break
            if not merged:
                toks = set(name.lower().split())
                for cl in clusters:
                    if toks & cl['tokens']:
                        cl['docs'].add('residence visa')
                        cl['expiry_map']['residence visa'] = exp
                        merged = True
                        break
            if not merged:
                make_cluster([], ['residence visa'], {'residence visa': exp}, name, 'unknown')

    # 6) Tag POA entries by ID
    for d in results:
        if d.get('doc_type','').lower() == 'poa':
            raw   = safe_json_loads(d['extracted_data']) or {}
            princ = raw.get('principals', {})
            base  = 'unknown'
            if isinstance(princ, dict) and princ:
                first = next(iter(princ.values()), {})
                key   = re.sub(r'\D','', first.get('emirates_id','') or '')
                for cl in clusters:
                    if key in cl['id_keys']:
                        base = cl['role']
                        break
            attys = raw.get('attorneys', [])
            recs  = attys.values() if isinstance(attys, dict) else attys
            for r in recs:
                if not isinstance(r, dict): continue
                key = re.sub(r'\D','', r.get('emirates_id','') or '')
                for cl in clusters:
                    if key in cl['id_keys']:
                        cl['docs'].add('poa')
                        cl['role'] = f'poa_{base}'
                        break

    # 7) Infer any remaining unknown roles
    for cl in clusters:
        if cl['role'] == 'unknown':
            cl['role'] = infer_role(cl['label'], sellers, buyers)

    # 8) Build contact_map from appointment row

    contact_map = {}
    if appt_row:
        # normalize sellers/buyers into real lists
        raw_sellers = appt_row.get('sellers')
        raw_buyers  = appt_row.get('buyers')
        sellers_list = raw_sellers if isinstance(raw_sellers, list) else []
        buyers_list  = raw_buyers  if isinstance(raw_buyers, list)  else []

        for p in sellers_list + buyers_list:
            nm = p.get('fullName') or p.get('firstName')
            if nm:
                contact_map[nm] = {
                    'email': p.get('email',''),
                    'phone': p.get('phone','')
                }

    # 9) Assemble DataFrame rows
    rows = []
    for cl in clusters:
        docs = []
        for d in sorted(cl['docs']):
            if d == 'poa': continue
            lbl = map_doc_label(d)
            exp = cl['expiry_map'].get(d)
            docs.append(f"{lbl}{f' ({exp})' if exp else ''}")
        if 'poa' in cl['docs']:
            docs.append('POA')

        info = _find_contact_info(cl['label'], contact_map)
        rows.append({
            'Name': cl['label'],
            'Provided Documents': ', '.join(docs) or 'none',
            'Role': cl['role'],
            'Individual/Company': 'Individual',
            'Email': info.get('email',''),
            'Phone': info.get('phone','')
        })

    # 10) Render with streamlit.data_editor
    df = pd.DataFrame(rows, columns=['Name','Provided Documents','Role','Individual/Company','Email','Phone'])
    if df.empty:
        df = pd.DataFrame([{c: '' for c in df.columns}])
    df.index += 1

    edited = st.data_editor(
        df,
        column_config={
            'Role': st.column_config.SelectboxColumn('Role',
                options=['seller','buyer','poa_seller','poa_buyer','unknown']
            ),
            'Individual/Company': st.column_config.SelectboxColumn('Individual/Company',
                options=['Individual','Company']
            )
        },
        disabled=['Provided Documents'],
        num_rows='dynamic',
        hide_index=False,
        use_container_width=True,
        key=key
    )

    st.session_state.person_roles       = edited.to_dict(orient='records')
    st.session_state.validation_outcomes = validate_documents(results)
