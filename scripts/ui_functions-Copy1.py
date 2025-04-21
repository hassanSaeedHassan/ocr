import streamlit as st
import pandas as pd
import re
from scripts.vlm_utils import safe_json_loads


def clean_name(n: str) -> str:
    """Remove honorifics and trim whitespace."""
    return re.sub(r'^(Mr\.|Mrs\.|Ms\.|Dr\.)\s*', '', n, flags=re.IGNORECASE).strip()


def tokens(name: str) -> set[str]:
    """Split on spaces, lowercase, drop 1–2 character tokens."""
    return {t.lower() for t in name.split() if len(t) > 2}


def infer_role(name: str, sellers: list, buyers: list) -> str:
    """Assign seller/buyer/unknown based on name matching."""
    l = name.lower()
    for s in sellers:
        if s.lower() in l:
            return 'seller'
    for b in buyers:
        if b.lower() in l:
            return 'buyer'
    return 'unknown'


def map_doc_label(doc: str) -> str:
    return {
        'ids': 'Emirates ID',
        'passport': 'Passport',
        'residence visa': 'Residence Visa'
    }.get(doc, doc.title())


def render_person_roles_editor(results, key='person_roles_editor'):
    """
    Build a consolidated, editable table of persons:
    - Merge entries by token-set intersection equal to smaller set size.
    - Use passport’s full name for display.
    - Exclude 'poa' from Provided Documents.
    - Keep contract roles (seller/buyer) over POA.
    """
    # 1) Reference seller/buyer names
    sellers, buyers = [], []
    contract = next((d for d in results if 'contract f' in d.get('doc_type','').lower()), None)
    if contract:
        cd = safe_json_loads(contract['extracted_data'])
        p1 = cd.get('Page_1', {})
        od = p1.get('Owner Details', {})
        bd = p1.get('Buyers Share Details', {})
        if od.get('Seller Name'): sellers = [od['Seller Name']]
        if bd.get('Buyer Name'): buyers = [bd['Buyer Name']]
    else:
        noc = next((d for d in results if 'noc' in d.get('doc_type','').lower()), None)
        nd = safe_json_loads(noc['extracted_data']) if noc else {}
        sn = (nd.get('seller') or {}).get('name')
        bn = (nd.get('buyer') or {}).get('name')
        if sn: sellers = [sn]
        if bn: buyers = [bn]

    # 2) Collect raw entries
    raw = []
    for d in results:
        dt = d.get('doc_type','').lower()
        data = safe_json_loads(d.get('extracted_data', {}))
        if dt == 'ids':
            nm = clean_name(data.get('front',{}).get('name_english','Unknown'))
            raw.append({'name': nm, 'docs': {'ids'}, 'role': infer_role(nm, sellers, buyers), 'is_pass': False})
        elif dt == 'passport':
            nm = clean_name(data.get('fullname') or data.get('full_name','Unknown'))
            raw.append({'name': nm, 'docs': {'passport'}, 'role': 'unknown', 'is_pass': True})
        elif dt == 'residence visa':
            nm = clean_name(data.get('fullname') or data.get('full_name','Unknown'))
            raw.append({'name': nm, 'docs': {'residence visa'}, 'role': 'unknown', 'is_pass': False})
        elif dt == 'poa':
            poa_data = safe_json_loads(d.get('extracted_data', {}))
            for p in poa_data.get('principals', []):
                nm = clean_name(p.get('name','Unknown'))
                raw.append({'name': nm, 'docs': {'poa'}, 'role': 'poa', 'is_pass': False})
            for a in poa_data.get('attorneys', []):
                nm = clean_name(a.get('name','Unknown'))
                raw.append({'name': nm, 'docs': {'poa'}, 'role': 'poa', 'is_pass': False})

    # 3) Merge into clusters with strict token-set match
    clusters = []
    for e in raw:
        e_toks = tokens(e['name'])
        placed = False
        for c in clusters:
            i = e_toks & c['tokens']
            if len(i) == min(len(e_toks), len(c['tokens'])) and len(i) > 0:
                # merge docs
                c['docs'].update(e['docs'])
                # prefer passport label
                if e['is_pass']:
                    c['label'] = e['name']
                # role priority: seller/buyer > existing > poa
                if e['role'] in ('seller','buyer') and c['role']=='unknown':
                    c['role'] = e['role']
                elif e['role']=='poa' and c['role']=='unknown':
                    c['role'] = 'poa'
                placed = True
                break
        if not placed:
            clusters.append({
                'label': e['name'],
                'docs': set(e['docs']),
                'role': e['role'],
                'tokens': tokens(e['name'])
            })

    # 4) Build final rows
    rows = []
    for c in clusters:
        p_docs = c['docs'] - {'poa'}
        mapped = sorted(map(map_doc_label, p_docs))
        doc_str = ','.join(mapped) if mapped else 'none'
        rows.append({'Name': c['label'], 'Provided Documents': doc_str, 'Role': c['role']})

    # 5) Display
    df = pd.DataFrame(rows)
    edited = st.data_editor(
        df,
        column_config={
            'Name': 'Name',
            'Provided Documents': 'Provided Documents',
            'Role': st.column_config.SelectboxColumn('Role', options=['buyer','seller','poa','unknown'])
        },
        disabled=['Name','Provided Documents'],
        use_container_width=True,
        key=key
    )
    st.session_state.person_roles = edited.to_dict(orient='records')
