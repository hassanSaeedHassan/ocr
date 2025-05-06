import json
import re
from typing import Any, Union

# ─── your existing helpers ───────────────────────────────────────────────────

def clean_json_string(json_str: str) -> str:
    cleaned = json_str.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return cleaned

def remove_single_block_artifacts(txt: str) -> str:
    return re.sub(r"\{[^:{}]*\}", "{}", txt)

def _auto_close(txt: str) -> str:
    stack, in_str, esc = [], False, False
    for ch in txt:
        if in_str:
            if esc: esc = False
            elif ch == "\\": esc = True
            elif ch == '"': in_str = False
        else:
            if ch == '"': in_str = True
            elif ch in "{[": stack.append(ch)
            elif ch == "}" and stack and stack[-1] == "{": stack.pop()
            elif ch == "]" and stack and stack[-1] == "[": stack.pop()
    closers = {"{": "}", "[": "]"}
    for opener in reversed(stack):
        txt += closers[opener]
    return txt

def _clean_and_parse_string(txt: str) -> Any:
    txt = clean_json_string(txt)
    txt = re.sub(r"[\u4e00-\u9fff]+", "", txt)               # strip Chinese
    txt = remove_single_block_artifacts(txt)                  # drop {...} artifacts
    txt = re.sub(r",\s*(?=[\]}])", "", txt)                   # drop trailing commas
    txt = re.sub(r'("([^"]+)"\s*:\s*)"[^"]*$', r'\1""', txt)   # blank trailing unterminated
    txt = _auto_close(txt)                                    # auto‑close braces/brackets
    try:
        return json.loads(txt)
    except:
        return {}

def _blank_long_strings(obj: Any, max_len: int = 200) -> Any:
    if isinstance(obj, dict):
        return {
            k: ("" if isinstance(v, str) and len(v) > max_len 
                 else _blank_long_strings(v, max_len))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_blank_long_strings(v, max_len) for v in obj]
    return obj

# ─── revised post_processing ─────────────────────────────────────────────────

def post_processing(raw: Union[str, dict, list], *, max_str_len: int = 200) -> Any:
    """
    1) If raw is a dict → recurse on its values.
    2) If raw is a list → recurse on its items.
    3) If raw is a string:
       a) Look for `"raw_text": "` via regex; if found, grab everything after that
          (even if truncated), unescape JSON escapes (\n, \", \\), and call that `inner`.
       b) Try plain `json.loads(inner)` → on success set result = parsed.
          On JSONDecodeError → result = _clean_and_parse_string(inner).
       c) If no `"raw_text"` found, then result = _clean_and_parse_string(raw).
    4) Finally, always return `_blank_long_strings(result, max_str_len)`.
    """
    # 1) dict: recurse
    if isinstance(raw, dict):
        return {k: post_processing(v, max_str_len=max_str_len) 
                for k, v in raw.items()}

    # 2) list: recurse
    if isinstance(raw, list):
        return [post_processing(v, max_str_len=max_str_len) 
                for v in raw]

    # 3) string: extract raw_text or clean directly
    if isinstance(raw, str):
        s = raw.strip()
        inner = None

        # 3a) sniff out raw_text key
        m = re.search(r'"raw_text"\s*:\s*"', s, re.DOTALL)
        if m:
            # grab everything after the opening quote
            inner = s[m.end():]
            # unescape JSON escapes
            try:
                inner = bytes(inner, "utf-8").decode("unicode_escape")
            except:
                inner = inner.replace(r"\n", "\n")\
                             .replace(r'\"', '"')\
                             .replace(r"\\", "\\")

        # 3b) choose parsing path
        if inner is not None:
            # try plain JSON
            try:
                parsed = json.loads(inner)
            except json.JSONDecodeError:
                parsed = _clean_and_parse_string(inner)
        else:
            parsed = _clean_and_parse_string(s)

        # 4) blank out any overly-large strings
        return _blank_long_strings(parsed, max_str_len)

    # 4) other types: return as-is
    return raw
