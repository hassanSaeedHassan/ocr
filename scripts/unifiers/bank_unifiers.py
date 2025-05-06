import json
import re
from collections import defaultdict
from datetime import datetime
import streamlit as st
from typing import Any, Union
from scripts.utils.json_utils import post_processing

def unify_cheques(raw_data: Union[str, dict]) -> dict:
    """
    Unify and clean the Cheque JSON:
    - Remove 'AED' from 'Amount in AED'
    - Create an indexed structure for each cheque
    - Keep only relevant fields: Bank Name, Payer Name, Amount, Issue Date, Cheque Number, Validity Period
    - Normalize dates to dd/mm/yyyy format
    """
    # Helper function to clean and normalize dates
    def clean_date(date_str):
        """Normalize and format dates to DD/MM/YYYY where possible."""
        if not date_str or date_str.lower() in {"not mentioned", "n/a"}:
            return None

        # try common known formats
        for fmt in ("%d/%m/%Y", "%d-%b-%Y", "%d %B %Y", "%d/%b/%Y"):
            try:
                return datetime.strptime(date_str, fmt).strftime("%d/%m/%Y")
            except:
                pass

        # fallback: return original string if not matched
        return date_str
    data = raw_data.copy()

    # 2) Prepare the unified cheques structure
    unified_data = {}

    for idx, cheque in enumerate(data, start=1):
        unified_data[f"Cheque {idx}"] = {
            "Bank Name": cheque.get("Bank Name"),
            "Cheque Number": cheque.get("Cheque Number"),
            "Payer Name": cheque.get("Payer Name").replace('*', ''),
            "Amount": cheque.get("Amount in AED", "").replace(" AED", "").strip(),
            "Issue Date": clean_date(cheque.get("Issue Date", "")),
            "Validity Period": cheque.get("Validity Period")
        }

    return unified_data