import streamlit as st
import pandas as pd
import re
from scripts.vlm_utils import safe_json_loads
from scripts.validation import validate_documents


def clean_name(n: str) -> str:
    """Remove honorifics and trim whitespace."""
    return re.sub(r'^(Mr\.|Mrs\.|Ms\.|Dr\.)\s*', '', n, flags=re.IGNORECASE).strip()


def tokens(name: str) -> set[str]:
    """Split on spaces, lowercase, drop 1–2 character tokens."""
    return {t.lower() for t in name.split() if len(t) > 2}


def infer_role(name: str, sellers: list, buyers: list) -> str:
    """Assign seller/buyer/unknown based on name matching."""
    lname = name.lower()
    for s in sellers:
        if s.lower() in lname:
            return 'seller'
    for b in buyers:
        if b.lower() in lname:
            return 'buyer'
    return 'unknown'


def map_doc_label(doc: str) -> str:
    """Map raw doc codes to display labels."""
    return {
        'ids': 'Emirates ID',
        'passport': 'Passport',
        'residence visa': 'Residence Visa'
    }.get(doc, doc.title())


def render_person_roles_editor(results, key='person_roles_editor'):
    """
    Build and display a consolidated, editable table of persons with their roles and document expiries.
    Also runs document validation and stores outcomes in session state.
    """
    # 1) Reference seller/buyer names from Contract F or NOC
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

    # 2) Collect raw entries including expiries
    raw = []
    for d in results:
        dt = d.get('doc_type','').lower()
        data = safe_json_loads(d.get('extracted_data', {}))
        if dt == 'ids':
            nm = clean_name(data.get('front',{}).get('name_english','Unknown'))
            expiry = data.get('front', {}).get('expiry_date','').strip() or None
            raw.append({'name': nm, 'docs': {'ids'}, 'role': infer_role(nm, sellers, buyers), 'is_pass': False, 'expiry_map': {'ids': expiry}})
        elif dt == 'passport':
            nm = clean_name(data.get('fullname') or data.get('full_name','Unknown'))
            expiry = data.get('Date of Expiry','').strip() or data.get('expiry_date','').strip() or None
            raw.append({'name': nm, 'docs': {'passport'}, 'role': 'unknown', 'is_pass': True, 'expiry_map': {'passport': expiry}})
        elif dt == 'residence visa':
            nm = clean_name(data.get('fullname') or data.get('full_name','Unknown'))
            expiry = data.get('expiry_date','').strip() or None
            raw.append({'name': nm, 'docs': {'residence visa'}, 'role': 'unknown', 'is_pass': False, 'expiry_map': {'residence visa': expiry}})
        elif dt == 'poa':
            poa_data = safe_json_loads(d.get('extracted_data', {}))
            for p in poa_data.get('principals', []):
                nm = clean_name(p.get('name','Unknown'))
                raw.append({'name': nm, 'docs': {'poa'}, 'role': 'poa', 'is_pass': False, 'expiry_map': {}})
            for a in poa_data.get('attorneys', []):
                nm = clean_name(a.get('name','Unknown'))
                raw.append({'name': nm, 'docs': {'poa'}, 'role': 'poa', 'is_pass': False, 'expiry_map': {}})

    # 3) Merge into clusters by token intersection
    clusters = []
    for e in raw:
        e_toks = tokens(e['name'])
        placed = False
        for c in clusters:
            # merge when token sets intersect by smaller set size
            common = e_toks & c['tokens']
            if len(common) == min(len(e_toks), len(c['tokens'])) and common:
                # merge docs
                c['docs'].update(e['docs'])
                # merge expiries
                c['expiry_map'].update(e['expiry_map'])
                # prefer passport display label
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
                'tokens': tokens(e['name']),
                'expiry_map': dict(e['expiry_map'])
            })

    # 4) Build final rows with expiry annotations
    rows = []
    for c in clusters:
        parts = []
        for doc in sorted(c['docs']):
            if doc == 'poa':
                continue
            label = map_doc_label(doc)
            exp = c['expiry_map'].get(doc)
            if exp:
                if doc == 'ids':
                    parts.append(f"{label} (valid until {exp})")
                else:
                    parts.append(f"{label} ({exp})")
            else:
                parts.append(label)
        doc_str = ", ".join(parts) if parts else "none"
        rows.append({'Name': c['label'], 'Provided Documents': doc_str, 'Role': c['role']})

    # 5) Render the data editor
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

    # 6) Run and store validation outcomes
    st.session_state.validation_outcomes = validate_documents(results)
