import json
import re
from collections import defaultdict
from datetime import datetime
import streamlit as st
from typing import Any, Union
from scripts.utils.json_utils import post_processing


def clean_not_mentioned(d):
    if isinstance(d, dict):
        return {k: clean_not_mentioned(v) for k, v in d.items() if v != "Not mentioned"}
    elif isinstance(d, list):
        return [clean_not_mentioned(i) for i in d if i != "Not mentioned"]
    else:
        return d

def unify_title_deed(raw_data: Union[str, dict]) -> dict:
    """
    Unify and clean the title deed JSON:
    - Removes "Transaction Details"
    - Removes any fields with the value "Not mentioned"
    - Custom handling for Land vs Flat property types
    """
    data = raw_data.copy()

    # 2) Remove Transaction Details
    if "Transaction Details" in data:
        del data["Transaction Details"]
  
    data = clean_not_mentioned(data)

    # 4) Normalize and unify Title Deed details (e.g. Area, Owners, Property)
    title_deed = data.get("Title Deed", {})
    owners = data.get("Owners", [])

    # 5) Check Property Type and include relevant fields
    property_type = title_deed.get("Property Type", "").lower()
    if property_type == "land":
        # Fields specific to Land property type
        unified_data = {
            "Title Deed": {
                "Issue Date": title_deed.get("Issue Date"),
                "Mortgage Status": title_deed.get("Mortgage Status"),
                "Property Type": title_deed.get("Property Type"),
                "Community": title_deed.get("Community"),
                "Plot No": title_deed.get("Plot No"),
                "Municipality No": title_deed.get("Municipality No"),
                "Area Sq Meter": title_deed.get("Area Sq Meter"),
                "Area Sq Feet": title_deed.get("Area Sq Feet"),
            },
            "Owners": owners
        }
    elif property_type == 'villa':
        # Fields specific to Villa property type
        unified_data = {
            "Title Deed": {
                "Issue Date": title_deed.get("Issue Date"),
                "Mortgage Status": title_deed.get("Mortgage Status"),
                "Property Type": title_deed.get("Property Type"),
                "Community": title_deed.get("Community"),
                "Plot No": title_deed.get("Plot No"),
                "Building No": title_deed.get("Building No"),
                "Municipality No": title_deed.get("Municipality No"),
                "Area Sq Meter": title_deed.get("Area Sq Meter"),
                "Area Sq Feet": title_deed.get("Area Sq Feet"),
            },
            "Owners": owners
        }
    elif property_type == "flat":
        # Fields specific to Flat property type
        unified_data = {
            "Title Deed": {
                "Issue Date": title_deed.get("Issue Date"),
                "Mortgage Status": title_deed.get("Mortgage Status"),
                "Property Type": title_deed.get("Property Type"),
                "Community": title_deed.get("Community"),
                "Plot No": title_deed.get("Plot No"),
                "Municipality No": title_deed.get("Municipality No"),
                "Building No": title_deed.get("Building No"),
                "Building Name": title_deed.get("Building Name"),
                "Property No": title_deed.get("Property No"),
                "Floor No": title_deed.get("Floor No"),
                "Parkings": title_deed.get("Parkings"),
                "Suite Area": title_deed.get("Suite Area"),
                "Balcony Area": title_deed.get("Balcony Area"),
                "Area Sq Meter": title_deed.get("Area Sq Meter"),
                "Area Sq Feet": title_deed.get("Area Sq Feet"),
                "Common Area": title_deed.get("Common Area")
            },
            "Owners": owners
        }
    else:
        # Default case: if Property Type is unknown or missing, we can return an empty structure or handle it differently
        unified_data = {
            "Title Deed": title_deed,  # Returning as is if the Property Type is neither "Land" nor "Flat"
            "Owners": owners
        }

    # 6) Unify Owners
    if owners:
        owner_dict = defaultdict(lambda: {"Owner Name (English)": "", "Owner Name (Arabic)": "", "Share (Sq Meter)": 0.0})

        # Process the owners to merge them based on Owner ID
        for owner in owners:
            owner_id = owner["Owner ID"].strip("()")  # Remove parentheses from Owner ID
            
            # Concatenate names with space if the same Owner ID is found
            if owner_dict[owner_id]["Owner Name (English)"]:
                owner_dict[owner_id]["Owner Name (English)"] += ' '
                owner_dict[owner_id]["Owner Name (English)"] += f" {owner['Owner Name (English)']}".strip()
                owner_dict[owner_id]["Owner Name (Arabic)"] += ' '
                owner_dict[owner_id]["Owner Name (Arabic)"] += f"  {owner['Owner Name (Arabic)']}".strip()
            else:
                # Only assign the name if this is the first occurrence of the Owner ID
                owner_dict[owner_id]["Owner Name (English)"] = owner["Owner Name (English)"]
                owner_dict[owner_id]["Owner Name (Arabic)"] = owner["Owner Name (Arabic)"]
            try:
                # Retain the share for the first owner with that ID
                if owner_dict[owner_id]["Share (Sq Meter)"] == 0.0:
                    owner_dict[owner_id]["Share (Sq Meter)"] = float(owner["Share (Sq Meter)"])
            except:
                pass

        # Prepare the final list of merged owners with the correct format
        merged_owners = []
        for idx, (owner_id, owner_data) in enumerate(owner_dict.items(), start=1):
            # Ensure correct spacing between names in Arabic
            arabic_name = owner_data["Owner Name (Arabic)"].strip()

            merged_owners.append({
                "Owner ID": f"{owner_id}",  # Optional: keep the parentheses if needed
                "Owner Name (English)": owner_data["Owner Name (English)"].strip(),
                "Owner Name (Arabic)": arabic_name,
                "Share (Sq Meter)": f"{owner_data['Share (Sq Meter)']:.2f}"
            })
        
        # Update the owners section with merged data
        unified_data["Owners"] = {f"Owner {idx}": owner for idx, owner in enumerate(merged_owners, start=1)}

    return unified_data




def unify_usufruct_right_certificate(raw_data: Union[str, dict]) -> dict:
    """
    Unify and clean the Usufruct Right Certificate JSON:
    - Removes "Property Type"
    - Removes "Transaction Details"
    - Removes any fields with the value "Not mentioned"
    - Custom handling for Usufruct Right Certificate with Lessors and Lessees
    """

    data = raw_data.copy()

    # 2) Remove "Transaction Details"
    if "Transaction Details" in data:
        del data["Transaction Details"]    
    data = clean_not_mentioned(data)
    # 4) Normalize and unify Usufruct Right Certificate details
    usufruct = data.get("Usufruct Right Certificate", {})
    lessors = data.get("Lessors", [])
    lessees = data.get("Lessees", [])

    # 5) Right Type and other common fields (Remove Property Type and retain the rest)
    unified_data = {
        "Usufruct Right Certificate": {}
    }

    # Add valid fields from Usufruct Right Certificate (skip "Not mentioned" ones)
    for key in ["Issue Date", "Mortgage Status", "Community", "Plot No", "Municipality No", "Building No",
                "Building Name", "Property No", "Floor No", "Parkings", "Suite Area", "Balcony Area",
                "Area Sq Meter", "Area Sq Feet", "Common Area", "Right Type"]:
        value = usufruct.get(key)
        if value != "Not mentioned" and value:
            unified_data["Usufruct Right Certificate"][key] = value

    # 6) Unify Lessors (similar to Owners merging)
    if lessors:
        lessor_dict = defaultdict(lambda: {"Lessor Name (English)": "", "Lessor Name (Arabic)": "", "Share (Sq Meter)": 0.0})

        # Process the lessors to merge them based on Lessor ID
        for lessor in lessors:
            lessor_id = lessor["Lessor ID"].strip("()")  # Remove parentheses from Lessor ID
            
            # Concatenate names with space if the same Lessor ID is found
            if lessor_dict[lessor_id]["Lessor Name (English)"]:
                lessor_dict[lessor_id]["Lessor Name (English)"] += ' '
                lessor_dict[lessor_id]["Lessor Name (English)"] += f" {lessor['Lessor Name (English)']}".strip()
                lessor_dict[lessor_id]["Lessor Name (Arabic)"] += ' '
                lessor_dict[lessor_id]["Lessor Name (Arabic)"] += f" {lessor['Lessor Name (Arabic)']}".strip()
            else:
                # Only assign the name if this is the first occurrence of the Lessor ID
                lessor_dict[lessor_id]["Lessor Name (English)"] = lessor["Lessor Name (English)"]
                lessor_dict[lessor_id]["Lessor Name (Arabic)"] = lessor["Lessor Name (Arabic)"]

            # Retain the share for the first lessor with that ID
            if lessor_dict[lessor_id]["Share (Sq Meter)"] == 0.0:
                lessor_dict[lessor_id]["Share (Sq Meter)"] = float(lessor["Share (Sq Meter)"])

        # Prepare the final list of merged lessors with the correct format
        merged_lessors = []
        for idx, (lessor_id, lessor_data) in enumerate(lessor_dict.items(), start=1):
            merged_lessors.append({
                "Lessor ID": f"{lessor_id}",  # Optional: keep the parentheses if needed
                "Lessor Name (English)": lessor_data["Lessor Name (English)"].strip(),
                "Lessor Name (Arabic)": lessor_data["Lessor Name (Arabic)"].strip(),
                "Share (Sq Meter)": f"{lessor_data['Share (Sq Meter)']:.2f}"
            })
        
        unified_data["Lessors"] = {f"Lessor {idx}": lessor for idx, lessor in enumerate(merged_lessors, start=1)}

    # 7) Unify Lessees (similar to Owners merging)
    if lessees:
        lessee_dict = defaultdict(lambda: {"Lessee Name (English)": "", "Lessee Name (Arabic)": "", "Share (Sq Meter)": 0.0})

        # Process the lessees to merge them based on Lessee ID
        for lessee in lessees:
            lessee_id = lessee["Lessor ID"].strip("()")  # Remove parentheses from Lessee ID (same as lessor)

            # Concatenate names with space if the same Lessee ID is found
            if lessee_dict[lessee_id]["Lessee Name (English)"]:
                lessee_dict[lessee_id]["Lessee Name (English)"] += ' '
                lessee_dict[lessee_id]["Lessee Name (English)"] += f" {lessee['Lessor Name (English)']}".strip()
                lessee_dict[lessee_id]["Lessee Name (Arabic)"] += ' '
                lessee_dict[lessee_id]["Lessee Name (Arabic)"] += f" {lessee['Lessor Name (Arabic)']}".strip()
            else:
                # Only assign the name if this is the first occurrence of the Lessee ID
                lessee_dict[lessee_id]["Lessee Name (English)"] = lessee["Lessor Name (English)"]
                lessee_dict[lessee_id]["Lessee Name (Arabic)"] = lessee["Lessor Name (Arabic)"]

            # Retain the share for the first lessee with that ID
            if lessee_dict[lessee_id]["Share (Sq Meter)"] == 0.0:
                lessee_dict[lessee_id]["Share (Sq Meter)"] = float(lessee["Share (Sq Meter)"])

        # Prepare the final list of merged lessees with the correct format
        merged_lessees = []
        for idx, (lessee_id, lessee_data) in enumerate(lessee_dict.items(), start=1):
            merged_lessees.append({
                "Lessee ID": f"{lessee_id}",  # Optional: keep the parentheses if needed
                "Lessee Name (English)": lessee_data["Lessee Name (English)"].strip(),
                "Lessee Name (Arabic)": lessee_data["Lessee Name (Arabic)"].strip(),
                "Share (Sq Meter)": f"{lessee_data['Share (Sq Meter)']:.2f}"
            })
        
        unified_data["Lessees"] = {f"Lessee {idx}": lessee for idx, lessee in enumerate(merged_lessees, start=1)}

    return unified_data


def unify_pre_title_deed(raw_data: Union[str, dict]) -> dict:
    """
    Unify and clean the Pre Title Deed and Usufruct Right Certificate JSON:
    - Removes "Transaction Details"
    - Removes any fields with the value "Not mentioned"
    - Custom handling for Pre Title Deed and Usufruct Right Certificate with Property Type handling (Land, Villa, Flat)
    - Merges Buyers, Sellers, and Owners
    """
    data = raw_data.copy()
    if "Transaction Details" in data:
        del data["Transaction Details"]
    data = clean_not_mentioned(data)
    # 4) Normalize and unify Pre Title Deed / Usufruct Right Certificate details
    title_deed = data.get("Pre Title Deed", data.get("Usufruct Right Certificate", {}))
    owners = data.get("Owners", [])
    buyers = data.get("Buyers", [])

    # 5) Check Property Type and include relevant fields
    property_type = title_deed.get("Property Type", "").lower()
    
    unified_data = {
        "Title Deed": {}
    }

    if property_type == "land":
        # Fields specific to Land property type
        unified_data["Title Deed"] = {
            "Issue Date": title_deed.get("Issue Date"),
            "Mortgage Status": title_deed.get("Mortgage Status"),
            "Property Type": title_deed.get("Property Type"),
            "Community": title_deed.get("Community"),
            "Plot No": title_deed.get("Plot No"),
            "Municipality No": title_deed.get("Municipality No"),
            "Area Sq Meter": title_deed.get("Area Sq Meter"),
            "Area Sq Feet": title_deed.get("Area Sq Feet"),
        }
    elif property_type == 'villa':
        # Fields specific to Villa property type
        unified_data["Title Deed"] = {
            "Issue Date": title_deed.get("Issue Date"),
            "Mortgage Status": title_deed.get("Mortgage Status"),
            "Property Type": title_deed.get("Property Type"),
            "Community": title_deed.get("Community"),
            "Plot No": title_deed.get("Plot No"),
            "Building No": title_deed.get("Building No"),
            "Municipality No": title_deed.get("Municipality No"),
            "Area Sq Meter": title_deed.get("Area Sq Meter"),
            "Area Sq Feet": title_deed.get("Area Sq Feet"),
        }
    elif property_type == "flat":
        # Fields specific to Flat property type
        unified_data["Title Deed"] = {
            "Issue Date": title_deed.get("Issue Date"),
            "Mortgage Status": title_deed.get("Mortgage Status"),
            "Property Type": title_deed.get("Property Type"),
            "Community": title_deed.get("Community"),
            "Plot No": title_deed.get("Plot No"),
            "Municipality No": title_deed.get("Municipality No"),
            "Building No": title_deed.get("Building No"),
            "Building Name": title_deed.get("Building Name"),
            "Property No": title_deed.get("Property No"),
            "Floor No": title_deed.get("Floor No"),
            "Parkings": title_deed.get("Parkings"),
            "Suite Area": title_deed.get("Suite Area"),
            "Balcony Area": title_deed.get("Balcony Area"),
            "Area Sq Meter": title_deed.get("Area Sq Meter"),
            "Area Sq Feet": title_deed.get("Area Sq Feet"),
            "Common Area": title_deed.get("Common Area")
        }
    else:
        # Default case: if Property Type is unknown or missing
        unified_data["Title Deed"] = title_deed  # Returning as is if the Property Type is neither "Land" nor "Flat"

    # 6) Unify Owners (similar to Title Deed merging)
    if owners:
        owner_dict = defaultdict(lambda: {"Owner Name (English)": "", "Owner Name (Arabic)": "", "Share (Sq Meter)": 0.0})

        # Process the owners to merge them based on Owner ID
        for owner in owners:
            owner_id = owner["Owner ID"].strip("()")  # Remove parentheses from Owner ID
            
            # Concatenate names with space if the same Owner ID is found
            if owner_dict[owner_id]["Owner Name (English)"]:
                owner_dict[owner_id]["Owner Name (English)"] += ' '
                owner_dict[owner_id]["Owner Name (English)"] += f" {owner['Owner Name (English)']}".strip()
                owner_dict[owner_id]["Owner Name (Arabic)"] += ' '
                owner_dict[owner_id]["Owner Name (Arabic)"] += f" {owner['Owner Name (Arabic)']}".strip()
            else:
                # Only assign the name if this is the first occurrence of the Owner ID
                owner_dict[owner_id]["Owner Name (English)"] = owner["Owner Name (English)"]
                owner_dict[owner_id]["Owner Name (Arabic)"] = owner["Owner Name (Arabic)"]

            # Retain the share for the first owner with that ID
            if owner_dict[owner_id]["Share (Sq Meter)"] == 0.0:
                owner_dict[owner_id]["Share (Sq Meter)"] = float(owner["Share (Sq Meter)"])

        # Prepare the final list of merged owners with the correct format
        merged_owners = []
        for idx, (owner_id, owner_data) in enumerate(owner_dict.items(), start=1):
            merged_owners.append({
                "Owner ID": f"{owner_id}",  # Optional: keep the parentheses if needed
                "Owner Name (English)": owner_data["Owner Name (English)"].strip(),
                "Owner Name (Arabic)": owner_data["Owner Name (Arabic)"].strip(),
                "Share (Sq Meter)": f"{owner_data['Share (Sq Meter)']:.2f}"
            })
        
        unified_data["Owners"] = {f"Owner {idx}": owner for idx, owner in enumerate(merged_owners, start=1)}

    # 7) Unify Buyers (similar to Owners merging)
    if buyers:
        buyer_dict = defaultdict(lambda: {"Buyer Name (English)": "", "Buyer Name (Arabic)": "", "Share (Sq Meter)": 0.0})

        # Process the buyers to merge them based on Buyer ID
        for buyer in buyers:
            buyer_id = buyer["Buyer ID"].strip("()")  # Remove parentheses from Buyer ID
            
            # Concatenate names with space if the same Buyer ID is found
            if buyer_dict[buyer_id]["Buyer Name (English)"]:
                buyer_dict[buyer_id]["Buyer Name (English)"] += ' '
                buyer_dict[buyer_id]["Buyer Name (English)"] += f" {buyer['Buyer Name (English)']}".strip()
                buyer_dict[buyer_id]["Buyer Name (Arabic)"] += ' '
                buyer_dict[buyer_id]["Buyer Name (Arabic)"] += f" {buyer['Buyer Name (Arabic)']}".strip()
            else:
                # Only assign the name if this is the first occurrence of the Buyer ID
                buyer_dict[buyer_id]["Buyer Name (English)"] = buyer["Buyer Name (English)"]
                buyer_dict[buyer_id]["Buyer Name (Arabic)"] = buyer["Buyer Name (Arabic)"]

            # Retain the share for the first buyer with that ID
            if buyer_dict[buyer_id]["Share (Sq Meter)"] == 0.0:
                buyer_dict[buyer_id]["Share (Sq Meter)"] = float(buyer["Share (Sq Meter)"])

        # Prepare the final list of merged buyers with the correct format
        merged_buyers = []
        for idx, (buyer_id, buyer_data) in enumerate(buyer_dict.items(), start=1):
            merged_buyers.append({
                "Buyer ID": f"{buyer_id}",  # Optional: keep the parentheses if needed
                "Buyer Name (English)": buyer_data["Buyer Name (English)"].strip(),
                "Buyer Name (Arabic)": buyer_data["Buyer Name (Arabic)"].strip(),
                "Share (Sq Meter)": f"{buyer_data['Share (Sq Meter)']:.2f}"
            })
        
        unified_data["Buyers"] = {f"Buyer {idx}": buyer for idx, buyer in enumerate(merged_buyers, start=1)}

    return unified_data

def unify_title_deed_lease_finance(raw_data: Union[str, dict]) -> dict:
    """
    Unify and clean the Title Deed (Lease Finance) JSON:
    - Removes "Transaction Details"
    - Removes any fields with the value "Not mentioned"
    - Custom handling for Title Deed (Lease Finance) with Owners and Lessees
    - Handles Property Type (Land, Villa, Flat)
    """
    data = raw_data.copy()
    if "Transaction Details" in data:
        del data["Transaction Details"]
    data = clean_not_mentioned(data)
    # 4) Normalize and unify Title Deed (Lease Finance) details
    title_deed = data.get("Title Deed (Lease Finance)",  {})
    owners = data.get("Owners", [])
    lessees = data.get("Lessees", [])

    # 5) Property Type is "Flat", "Villa", or "Land" — apply relevant fields
    property_type = title_deed.get("Property Type", "").lower()
    
    unified_data = {
        "Title Deed (Lease Finance)": {}
    }

    if property_type == "land":
        # Fields specific to Land property type
        unified_data["Title Deed (Lease Finance)"] = {
            "Issue Date": title_deed.get("Issue Date"),
            "Property Type": title_deed.get("Property Type"),
            "Community": title_deed.get("Community"),
            "Plot No": title_deed.get("Plot No"),
            "Municipality No": title_deed.get("Municipality No"),
            "Area Sq Meter": title_deed.get("Area Sq Meter"),
            "Area Sq Feet": title_deed.get("Area Sq Feet"),
        }
    elif property_type == 'villa':
        # Fields specific to Villa property type
        unified_data["Title Deed (Lease Finance)"] = {
            "Issue Date": title_deed.get("Issue Date"),
            "Property Type": title_deed.get("Property Type"),
            "Community": title_deed.get("Community"),
            "Plot No": title_deed.get("Plot No"),
            "Building No": title_deed.get("Building No"),
            "Municipality No": title_deed.get("Municipality No"),
            "Area Sq Meter": title_deed.get("Area Sq Meter"),
            "Area Sq Feet": title_deed.get("Area Sq Feet"),
        }
    elif property_type == "flat":
        # Fields specific to Flat property type
        unified_data["Title Deed (Lease Finance)"] = {
            "Issue Date": title_deed.get("Issue Date"),
            "Property Type": title_deed.get("Property Type"),
            "Community": title_deed.get("Community"),
            "Plot No": title_deed.get("Plot No"),
            "Municipality No": title_deed.get("Municipality No"),
            "Building No": title_deed.get("Building No"),
            "Building Name": title_deed.get("Building Name"),
            "Property No": title_deed.get("Property No"),
            "Floor No": title_deed.get("Floor No"),
            "Parkings": title_deed.get("Parkings"),
            "Suite Area": title_deed.get("Suite Area"),
            "Balcony Area": title_deed.get("Balcony Area"),
            "Area Sq Meter": title_deed.get("Area Sq Meter"),
            "Area Sq Feet": title_deed.get("Area Sq Feet"),
            "Common Area": title_deed.get("Common Area")
        }
    else:
        # Default case: if Property Type is unknown or missing, we can return an empty structure or handle it differently
        unified_data["Title Deed (Lease Finance)"] = title_deed  # Returning as is if the Property Type is neither "Land" nor "Flat"

    # 6) Unify Owners (similar to Title Deed merging)
    if owners:
        owner_dict = defaultdict(lambda: {"Owner Name (English)": "", "Owner Name (Arabic)": "", "Share (Sq Meter)": 0.0})

        # Process the owners to merge them based on Owner ID
        for owner in owners:
            owner_id = owner["Owner ID"].strip("()")  # Remove parentheses from Owner ID
            
            # Concatenate names with space if the same Owner ID is found
            if owner_dict[owner_id]["Owner Name (English)"]:
                owner_dict[owner_id]["Owner Name (English)"] += ' '
                owner_dict[owner_id]["Owner Name (English)"] += f" {owner['Owner Name (English)']}".strip()
                owner_dict[owner_id]["Owner Name (Arabic)"] += ' '
                owner_dict[owner_id]["Owner Name (Arabic)"] += f" {owner['Owner Name (Arabic)']}".strip()
            else:
                # Only assign the name if this is the first occurrence of the Owner ID
                owner_dict[owner_id]["Owner Name (English)"] = owner["Owner Name (English)"]
                owner_dict[owner_id]["Owner Name (Arabic)"] = owner["Owner Name (Arabic)"]

            # Retain the share for the first owner with that ID
            if owner_dict[owner_id]["Share (Sq Meter)"] == 0.0:
                owner_dict[owner_id]["Share (Sq Meter)"] = float(owner["Share (Sq Meter)"])

        # Prepare the final list of merged owners with the correct format
        merged_owners = []
        for idx, (owner_id, owner_data) in enumerate(owner_dict.items(), start=1):
            merged_owners.append({
                "Owner ID": f"{owner_id}",  # Optional: keep the parentheses if needed
                "Owner Name (English)": owner_data["Owner Name (English)"].strip(),
                "Owner Name (Arabic)": owner_data["Owner Name (Arabic)"].strip(),
                "Share (Sq Meter)": f"{owner_data['Share (Sq Meter)']:.2f}"
            })
        
        unified_data["Owners"] = {f"Owner {idx}": owner for idx, owner in enumerate(merged_owners, start=1)}

    # 7) Unify Lessees (similar to Owners merging)
    if lessees:
        lessee_dict = defaultdict(lambda: {"Lessee Name (English)": "", "Lessee Name (Arabic)": "", "Share (Sq Meter)": 0.0})

        # Process the lessees to merge them based on Lessee ID
        for lessee in lessees:
            lessee_id = lessee["Lessee ID"].strip("()")  # Remove parentheses from Lessee ID
            
            # Concatenate names with space if the same Lessee ID is found
            if lessee_dict[lessee_id]["Lessee Name (English)"]:
                lessee_dict[lessee_id]["Lessee Name (English)"] += ' '
                lessee_dict[lessee_id]["Lessee Name (English)"] += f" {lessee['Lessee Name (English)']}".strip()
                lessee_dict[lessee_id]["Lessee Name (Arabic)"] += ' '
                lessee_dict[lessee_id]["Lessee Name (Arabic)"] += f" {lessee['Lessee Name (Arabic)']}".strip()
            else:
                # Only assign the name if this is the first occurrence of the Lessee ID
                lessee_dict[lessee_id]["Lessee Name (English)"] = lessee["Lessee Name (English)"]
                lessee_dict[lessee_id]["Lessee Name (Arabic)"] = lessee["Lessee Name (Arabic)"]

            # Retain the share for the first lessee with that ID
            if lessee_dict[lessee_id]["Share (Sq Meter)"] == 0.0:
                lessee_dict[lessee_id]["Share (Sq Meter)"] = float(lessee["Share (Sq Meter)"])

        # Prepare the final list of merged lessees with the correct format
        merged_lessees = []
        for idx, (lessee_id, lessee_data) in enumerate(lessee_dict.items(), start=1):
            merged_lessees.append({
                "Lessee ID": f"{lessee_id}",  # Optional: keep the parentheses if needed
                "Lessee Name (English)": lessee_data["Lessee Name (English)"].strip(),
                "Lessee Name (Arabic)": lessee_data["Lessee Name (Arabic)"].strip(),
                "Share (Sq Meter)": f"{lessee_data['Share (Sq Meter)']:.2f}"
            })
        
        unified_data["Lessees"] = {f"Lessee {idx}": lessee for idx, lessee in enumerate(merged_lessees, start=1)}

    return unified_data


def unify_title_deed_lease_to_own(raw_data: Union[str, dict]) -> dict:
    """
    Unify and clean the Title Deed (Lease To Own) JSON:
    - Removes "Transaction Details"
    - Removes any fields with the value "Not mentioned"
    - Custom handling for Title Deed (Lease To Own) with Owners and Lessees
    - Handles Property Type (Flat)
    """
    data = raw_data.copy()
    # 2) Remove "Transaction Details"
    if "Transaction Details" in data:
        del data["Transaction Details"]
    data = clean_not_mentioned(data)

    # 4) Normalize and unify Title Deed (Lease To Own) details
    title_deed = data.get("Title Deed (Lease To Own)", {})
    owners = data.get("Owners", [])
    lessees = data.get("Lessees", [])

    # 5) Property Type is "Flat", apply relevant fields for Flat
    property_type = title_deed.get("Property Type", "").lower()

    unified_data = {
        "Title Deed (Lease To Own)": {}
    }

    if property_type == "land":
        # Fields specific to Land property type
        unified_data["Title Deed (Lease To Own)"] = {
            "Issue Date": title_deed.get("Issue Date"),
            "Property Type": title_deed.get("Property Type"),
            "Community": title_deed.get("Community"),
            "Plot No": title_deed.get("Plot No"),
            "Municipality No": title_deed.get("Municipality No"),
            "Area Sq Meter": title_deed.get("Area Sq Meter"),
            "Area Sq Feet": title_deed.get("Area Sq Feet"),
        }
    elif property_type == 'villa':
        # Fields specific to Villa property type
        unified_data["Title Deed (Lease To Own)"] = {
            "Issue Date": title_deed.get("Issue Date"),
            "Property Type": title_deed.get("Property Type"),
            "Community": title_deed.get("Community"),
            "Plot No": title_deed.get("Plot No"),
            "Building No": title_deed.get("Building No"),
            "Municipality No": title_deed.get("Municipality No"),
            "Area Sq Meter": title_deed.get("Area Sq Meter"),
            "Area Sq Feet": title_deed.get("Area Sq Feet"),
        }
    elif property_type == "flat":
        # Fields specific to Flat property type
        unified_data["Title Deed (Lease To Own)"] = {
            "Issue Date": title_deed.get("Issue Date"),
            "Property Type": title_deed.get("Property Type"),
            "Community": title_deed.get("Community"),
            "Plot No": title_deed.get("Plot No"),
            "Municipality No": title_deed.get("Municipality No"),
            "Building No": title_deed.get("Building No"),
            "Building Name": title_deed.get("Building Name"),
            "Property No": title_deed.get("Property No"),
            "Floor No": title_deed.get("Floor No"),
            "Parkings": title_deed.get("Parkings"),
            "Suite Area": title_deed.get("Suite Area"),
            "Balcony Area": title_deed.get("Balcony Area"),
            "Area Sq Meter": title_deed.get("Area Sq Meter"),
            "Area Sq Feet": title_deed.get("Area Sq Feet"),
            "Common Area": title_deed.get("Common Area")
        }
    else:
        # Default case: if Property Type is unknown or missing
        unified_data["Title Deed (Lease To Own)"] = title_deed  # Returning as is if the Property Type is neither "Land" nor "Flat"

    # 6) Unify Owners (similar to Title Deed merging)
    if owners:
        owner_dict = defaultdict(lambda: {"Owner Name (English)": "", "Owner Name (Arabic)": "", "Share (Sq Meter)": 0.0})

        # Process the owners to merge them based on Owner ID
        for owner in owners:
            owner_id = owner["Owner ID"].strip("()")  # Remove parentheses from Owner ID
            
            # Concatenate names with space if the same Owner ID is found
            if owner_dict[owner_id]["Owner Name (English)"]:
                owner_dict[owner_id]["Owner Name (English)"] += ' '
                owner_dict[owner_id]["Owner Name (English)"] += f" {owner['Owner Name (English)']}".strip()
                owner_dict[owner_id]["Owner Name (Arabic)"] += ' '
                owner_dict[owner_id]["Owner Name (Arabic)"] += f" {owner['Owner Name (Arabic)']}".strip()
            else:
                # Only assign the name if this is the first occurrence of the Owner ID
                owner_dict[owner_id]["Owner Name (English)"] = owner["Owner Name (English)"]
                owner_dict[owner_id]["Owner Name (Arabic)"] = owner["Owner Name (Arabic)"]

            # Retain the share for the first owner with that ID
            if owner_dict[owner_id]["Share (Sq Meter)"] == 0.0:
                owner_dict[owner_id]["Share (Sq Meter)"] = float(owner["Share (Sq Meter)"])

        # Prepare the final list of merged owners with the correct format
        merged_owners = []
        for idx, (owner_id, owner_data) in enumerate(owner_dict.items(), start=1):
            merged_owners.append({
                "Owner ID": f"{owner_id}",  # Optional: keep the parentheses if needed
                "Owner Name (English)": owner_data["Owner Name (English)"].strip(),
                "Owner Name (Arabic)": owner_data["Owner Name (Arabic)"].strip(),
                "Share (Sq Meter)": f"{owner_data['Share (Sq Meter)']:.2f}"
            })
        
        unified_data["Owners"] = {f"Owner {idx}": owner for idx, owner in enumerate(merged_owners, start=1)}

    # 7) Unify Lessees (similar to Owners merging)
    if lessees:
        lessee_dict = defaultdict(lambda: {"Lessee Name (English)": "", "Lessee Name (Arabic)": "", "Share (Sq Meter)": 0.0})

        # Process the lessees to merge them based on Lessee ID
        for lessee in lessees:
            lessee_id = lessee["Lessee ID"].strip("()")  # Remove parentheses from Lessee ID
            
            # Concatenate names with space if the same Lessee ID is found
            if lessee_dict[lessee_id]["Lessee Name (English)"]:
                lessee_dict[lessee_id]["Lessee Name (English)"] += ' '
                lessee_dict[lessee_id]["Lessee Name (English)"] += f" {lessee['Lessee Name (English)']}".strip()
                lessee_dict[lessee_id]["Lessee Name (Arabic)"] += ' '
                lessee_dict[lessee_id]["Lessee Name (Arabic)"] += f" {lessee['Lessee Name (Arabic)']}".strip()
            else:
                # Only assign the name if this is the first occurrence of the Lessee ID
                lessee_dict[lessee_id]["Lessee Name (English)"] = lessee["Lessee Name (English)"]
                lessee_dict[lessee_id]["Lessee Name (Arabic)"] = lessee["Lessee Name (Arabic)"]

            # Retain the share for the first lessee with that ID
            if lessee_dict[lessee_id]["Share (Sq Meter)"] == 0.0:
                lessee_dict[lessee_id]["Share (Sq Meter)"] = float(lessee["Share (Sq Meter)"])

        # Prepare the final list of merged lessees with the correct format
        merged_lessees = []
        for idx, (lessee_id, lessee_data) in enumerate(lessee_dict.items(), start=1):
            merged_lessees.append({
                "Lessee ID": f"{lessee_id}",  # Optional: keep the parentheses if needed
                "Lessee Name (English)": lessee_data["Lessee Name (English)"].strip(),
                "Lessee Name (Arabic)": lessee_data["Lessee Name (Arabic)"].strip(),
                "Share (Sq Meter)": f"{lessee_data['Share (Sq Meter)']:.2f}"
            })
        
        unified_data["Lessees"] = {f"Lessee {idx}": lessee for idx, lessee in enumerate(merged_lessees, start=1)}

    return unified_data
