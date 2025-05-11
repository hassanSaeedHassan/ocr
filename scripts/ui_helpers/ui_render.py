import json
import streamlit as st

def clean_json_string(json_str):
    """
    Remove markdown/code-fence markers if present and extra whitespace.
    For example, remove leading and trailing ```json and ``` markers.
    """
    cleaned = json_str.strip()
    # If the string starts with a code fence, remove the first and last lines if they are fences.
    if cleaned.startswith("```"):
        # Split by lines.
        lines = cleaned.splitlines()
        # Remove first line if it starts with ```
        if lines[0].strip().startswith("```"):
            lines = lines[1:]
        # Remove last line if it is a code fence.
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return cleaned
def render_dict(d, indent_level=0, parent_key="", use_expander=True):
    """
    Recursively render a dict:
      - Unwrap any {"raw_text": "<json>"} at every nesting level.
      - Keys become static markdown labels (indented).
      - Values become st.text_input fields (or nested render_dict calls).
    """
    inputs = {}
    simple_fields = []
    indent = "  " * indent_level  # two non-breaking spaces per level

    for key, value in d.items():
        # ——— Unwrap raw_text if it's valid JSON ———
        if (
            isinstance(value, dict)
            and set(value.keys()) == {"raw_text"}
            and isinstance(value["raw_text"], str)
        ):
            inner = clean_json_string(value["raw_text"])
            try:
                value = json.loads(inner)
            except json.JSONDecodeError:
                pass  # leave as-is if not valid JSON

        raw_label = key.replace("_", " ")
        widget_key = f"{parent_key}_{key}" if parent_key else key

        # ——— Nested dict ———
        if isinstance(value, dict):
            # Inline if only one child or same as parent
            if len(value) == 1 or (parent_key and key.lower() == parent_key.lower()):
                st.markdown(f"{indent}**{raw_label}:**")
                inputs[key] = render_dict(
                    value,
                    indent_level=indent_level + 1,
                    parent_key=widget_key,
                    use_expander=False,
                )
            else:
                # flush pending simple fields first
                for i in range(0, len(simple_fields), 2):
                    cols = st.columns(2)
                    k1, v1, lbl1, wkey1 = simple_fields[i]
                    with cols[0]:
                        inputs[k1] = st.text_input(lbl1, value=str(v1), key=wkey1)
                    if i + 1 < len(simple_fields):
                        k2, v2, lbl2, wkey2 = simple_fields[i + 1]
                        with cols[1]:
                            inputs[k2] = st.text_input(lbl2, value=str(v2), key=wkey2)
                simple_fields.clear()

                if use_expander:
                    with st.expander(f"{indent}{raw_label}", expanded=True):
                        inputs[key] = render_dict(
                            value,
                            indent_level=indent_level + 1,
                            parent_key=widget_key,
                            use_expander=False,
                        )
                else:
                    st.markdown(f"{indent}**{raw_label}:**")
                    inputs[key] = render_dict(
                        value,
                        indent_level=indent_level + 1,
                        parent_key=widget_key,
                        use_expander=False,
                    )

        # ——— List ———
        elif isinstance(value, list):
            # flush any pending simple fields
            for i in range(0, len(simple_fields), 2):
                cols = st.columns(2)
                k1, v1, lbl1, wkey1 = simple_fields[i]
                with cols[0]:
                    inputs[k1] = st.text_input(lbl1, value=str(v1), key=wkey1)
                if i + 1 < len(simple_fields):
                    k2, v2, lbl2, wkey2 = simple_fields[i + 1]
                    with cols[1]:
                        inputs[k2] = st.text_input(lbl2, value=str(v2), key=wkey2)
            simple_fields.clear()

            st.markdown(f"{indent}**{raw_label}:**")
            if value and isinstance(value[0], dict):
                inputs[key] = []
                for idx, item in enumerate(value):
                    st.markdown(f"{indent}- Item {idx+1}")
                    inputs[key].append(
                        render_dict(
                            item,
                            indent_level=indent_level + 1,
                            parent_key=f"{widget_key}_{idx}",
                            use_expander=False,
                        )
                    )
            else:
                inputs[key] = st.text_input(raw_label, value=str(value), key=widget_key)

        # ——— Simple fields ———
        else:
            simple_fields.append((key, value, raw_label, widget_key))

    # flush any remaining simple fields
    for i in range(0, len(simple_fields), 2):
        cols = st.columns(2)
        k1, v1, lbl1, wkey1 = simple_fields[i]
        with cols[0]:
            inputs[k1] = st.text_input(lbl1, value=str(v1), key=wkey1)
        if i + 1 < len(simple_fields):
            k2, v2, lbl2, wkey2 = simple_fields[i + 1]
            with cols[1]:
                inputs[k2] = st.text_input(lbl2, value=str(v2), key=wkey2)

    return inputs

def render_data_form(extracted_data, form_key):
    """
    Renders a Streamlit form for extracted_data:
      - If it's a flat dict (only primitive values), show plain inputs.
      - Otherwise, use a collapsed expander per top‑level key.
    """
    # Step 1: Normalize into a dict
    if isinstance(extracted_data, str):
        cleaned = clean_json_string(extracted_data)
        try:
            extracted_data = json.loads(cleaned)
        except json.JSONDecodeError:
            extracted_data = {"raw_text": cleaned}

    if isinstance(extracted_data, list):
        if extracted_data and isinstance(extracted_data[0], dict):
            extracted_data = {"Documents": extracted_data}
        else:
            extracted_data = {"raw_text": str(extracted_data)}

    if not isinstance(extracted_data, dict):
        extracted_data = {"raw_text": str(extracted_data)}

    # Step 2: Detect flat‑dict case
    is_flat = all(
        not isinstance(v, (dict, list))
        for v in extracted_data.values()
    )

    with st.form(key=f"ocr_data_form_{form_key}"):
        form_inputs = {}

        if is_flat:
            # Render each key/value directly
            for key, value in extracted_data.items():
                widget_key = f"form{form_key}_{key}"
                form_inputs[key] = st.text_input(
                    label=key,
                    value=str(value),
                    key=widget_key
                )

        else:
            # Fall back to per‑section accordions
            for section_label, section_value in extracted_data.items():
                with st.expander(section_label, expanded=False):
                    widget_prefix = f"form{form_key}_{section_label}"

                    if isinstance(section_value, dict):
                        form_inputs[section_label] = render_dict(
                            section_value,
                            indent_level=1,
                            parent_key=widget_prefix,
                            use_expander=False
                        )

                    elif isinstance(section_value, list):
                        if all(not isinstance(i, dict) for i in section_value):
                            form_inputs[section_label] = st.text_input(
                                section_label,
                                value=str(section_value),
                                key=widget_prefix
                            )
                        else:
                            items = []
                            for idx, item in enumerate(section_value):
                                st.markdown(f"**Item {idx+1}**")
                                items.append(render_dict(
                                    item,
                                    indent_level=1,
                                    parent_key=f"{widget_prefix}_{idx}",
                                    use_expander=False
                                ))
                            form_inputs[section_label] = items

                    else:
                        form_inputs[section_label] = st.text_input(
                            section_label,
                            value=str(section_value),
                            key=widget_prefix
                        )

        submitted = st.form_submit_button("Save Changes")
        if submitted:
            st.session_state.results[form_key]["extracted_data"] = form_inputs
            st.success("Changes saved!")
            try:
                st.experimental_rerun()
            except AttributeError:
                st.rerun()
