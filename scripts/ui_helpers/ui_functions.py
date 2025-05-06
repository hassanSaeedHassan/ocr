import streamlit as st
import pandas as pd
import re
from scripts.vlm_utils import safe_json_loads
from scripts.validation import validate_documents
from scripts.unifiers.properties_unifiers import unify_noc


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


def render_person_roles_editor(results, key='person_roles_editor'):
    """
    Build and display a consolidated, editable table of persons with their roles and document expiries.
    Clustering is by Emirates ID; passports merge via two-token name match, visas by ID or tokens, POA tags clusters.
    """
    # 1) Reference sellers and buyers
    sellers, buyers = [], []
    contract = next((d for d in results if 'contract f' in d.get('doc_type','').lower()), None)
    if contract:
        cd = safe_json_loads(contract['extracted_data'])
        p1 = cd.get('Page_1', {})
        for v in p1.get('Owner Details', {}).values():
            name = v.get('Seller Name') if isinstance(v, dict) else v
            if name: sellers.append(str(name).strip())
        for v in p1.get('Buyers Share Details', {}).values():
            name = v.get('Buyer Name') if isinstance(v, dict) else v
            if name: buyers.append(str(name).strip())

    else:
        noc_doc = next((d for d in results if 'noc' in d.get('doc_type','').lower()), None)
        if noc_doc:
            # 1) unify & persist back to session_state
            unified = unify_noc(noc_doc['extracted_data'])
            noc_doc['extracted_data'] = unified
            # If you ever reassign results itself, do:
            # st.session_state.results = results

            # 2) parse the unified JSON
            nd = safe_json_loads(unified) or {}

            # 3) helper that handles str / dict / list and splits on commas
            def extract_names(field):
                if isinstance(field, str):
                    return [n.strip() for n in re.split(r'\s*,\s*', field) if n.strip()]
                elif isinstance(field, dict):
                    return extract_names(field.get('name',''))
                elif isinstance(field, list):
                    out = []
                    for item in field:
                        if isinstance(item, dict):
                            out += extract_names(item.get('name',''))
                        else:
                            out += extract_names(str(item))
                    return out
                return []

            # 4) build your sellers/buyers lists
            sellers += extract_names(nd.get('sellers') or nd.get('seller'))
            buyers  += extract_names(nd.get('buyers')  or nd.get('buyer'))

    # 2) Build initial clusters from IDs (merging duplicates)
    clusters = []
    def make_cluster(id_keys, docs, expiry_map, label, role):
        clusters.append({
            'id_keys': set(id_keys),
            'docs': set(docs),
            'expiry_map': dict(expiry_map),
            'label': label,
            'role': role,
            'tokens': tokens(label)
        })

    for d in results:
        if d.get('doc_type','').lower() == 'ids':
            data = safe_json_loads(d['extracted_data'])
            front = data.get('front', {})
            nm = clean_name(front.get('name_english','Unknown'))
            eid = re.sub(r'\D', '', front.get('emirates_id','') or front.get('document_number',''))
            exp = front.get('expiry_date','').strip() or None
            role = infer_role(nm, sellers, buyers)
            if not eid:
                continue
            # merge into existing cluster if ID matches
            merged = False
            for cl in clusters:
                if eid in cl['id_keys']:
                    cl['docs'].add('ids')
                    cl['expiry_map']['ids'] = exp
                    cl['label'] = nm
                    cl['tokens'] = tokens(nm)
                    if cl['role'] == 'unknown' and role in ('seller','buyer'):
                        cl['role'] = role
                    merged = True
                    break
            if not merged:
                make_cluster([eid], ['ids'], {'ids': exp}, nm, role)

    # 3) Merge passports via two-token name match
    for d in results:
        if d.get('doc_type','').lower() == 'passport':
            data = safe_json_loads(d['extracted_data'])
            nm = clean_name(data.get('fullname') or data.get('full_name','Unknown')).replace('-',' ')
            exp = data.get('Date of Expiry','').strip() or data.get('expiry_date','').strip() or None
            p_toks = tokens(nm)
            merged = False
            for cl in clusters:
                common = p_toks & cl['tokens']
                if len(common) >= 2:
                    cl['docs'].add('passport')
                    cl['expiry_map']['passport'] = exp
                    cl['label'] = nm
                    merged = True
                    break
            if not merged:
                make_cluster([], ['passport'], {'passport': exp}, nm, 'unknown')

    # 4) Merge visas by ID or token match
    for d in results:
        if d.get('doc_type','').lower() == 'residence visa':
            data = safe_json_loads(d['extracted_data'])
            nm = clean_name(data.get('fullname') or data.get('full_name','Unknown'))
            exp = data.get('expiry_date','').strip() or None
            vid = ''
            for k in ('emirates_id', 'passport_no'):
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
                v_toks = tokens(nm)
                for cl in clusters:
                    if v_toks & cl['tokens']:
                        cl['docs'].add('residence visa')
                        cl['expiry_map']['residence visa'] = exp
                        merged = True
                        break
            if not merged:
                make_cluster([], ['residence visa'], {'residence visa': exp}, nm, 'unknown')

    # 5) Tag POA entries by ID match
    for d in results:
        if d.get('doc_type','').lower() == 'poa':
            raw = safe_json_loads(d['extracted_data']) or {}
            princs = raw.get('principals')
            base_role = 'unknown'
            if isinstance(princs, dict) and princs:
                first = next(iter(princs.values()))
                key = re.sub(r'\D','', first.get('emirates_id','') or '')
                for cl in clusters:
                    if key in cl['id_keys']:
                        base_role = cl['role']
                        break
            attys = raw.get('attorneys')
            recs = attys.values() if isinstance(attys, dict) else attys if isinstance(attys, list) else []
            for rec in recs:
                if not isinstance(rec, dict): continue
                key = re.sub(r'\D','', rec.get('emirates_id','') or '')
                for cl in clusters:
                    if key in cl['id_keys']:
                        cl['docs'].add('poa')
                        cl['role'] = f'poa_{base_role}'
                        break
    for cl in clusters:
        if cl['role'] == 'unknown':
            cl['role'] = infer_role(cl['label'], sellers, buyers)
    # 6) Build rows
    rows = []
    for cl in clusters:
        parts = []
        for doc in sorted(cl['docs']):
            if doc == 'poa': continue
            lbl = map_doc_label(doc)
            exp = cl['expiry_map'].get(doc)
            if exp:
                suffix = f" (valid until {exp})" if doc == 'ids' else f" ({exp})"
                parts.append(lbl + suffix)
            else:
                parts.append(lbl)
        if 'poa' in cl['docs']:
            parts.append('POA')
        rows.append({'Name': cl['label'], 'Provided Documents': ', '.join(parts) or 'none', 'Role': cl['role']})

    # 7) Render table
    df = pd.DataFrame(rows)
    df.index += 1
    edited = st.data_editor(
        df,
        column_config={
            'Name': 'Name',
            'Provided Documents': 'Provided Documents',
            'Role': st.column_config.SelectboxColumn(
                'Role',
                options=[
                    'seller', 'buyer',
                    'poa_seller', 'poa_buyer',
                    'broker seller', 'broker buyer',
                    'conveyancer seller', 'conveyancer buyer',
                    'unknown'
                ]
            )
        },
        disabled=['Name', 'Provided Documents'],
        num_rows="dynamic",
        hide_index=False,
        use_container_width=True,
        key=key
    )
    st.session_state.person_roles = edited.to_dict(orient='records')
    st.session_state.validation_outcomes = validate_documents(results)