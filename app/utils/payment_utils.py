import requests
import json
from typing import Dict, Optional


def get_bank_details_from_ifsc(ifsc: str) -> Optional[Dict]:
    """
    Fetch bank details from IFSC code using Razorpay's IFSC API.
    
    Args:
        ifsc (str): The IFSC code to lookup
        
    Returns:
        Dict: JSON response containing bank details, or None if error occurs
        
    Example response structure:
    {
        "BRANCH": "SARJAPURA MAIN ROAD BRANCH",
        "NEFT": true,
        "MICR": "560485027",
        "ISO3166": "IN-KA",
        "STATE": "KARNATAKA",
        "DISTRICT": "BANGALORE",
        "CONTACT": "+9118602662666",
        "RTGS": true,
        "CITY": "BANGALORE URBAN",
        "CENTRE": "BANGALORE",
        "IMPS": true,
        "ADDRESS": "GROUND AND MEZZANNIE FLOOR 359 39 BREN MERCURY...",
        "UPI": true,
        "SWIFT": null,
        "BANK": "Kotak Mahindra Bank",
        "BANKCODE": "KKBK",
        "IFSC": "KKBK0008107"
    }
    """
    if not ifsc or not isinstance(ifsc, str):
        return None
    
    # Clean and validate IFSC format (11 characters, alphanumeric)
    ifsc = ifsc.strip().upper()
    if len(ifsc) != 11 or not ifsc.isalnum():
        return None
    
    try:
        # Make API request to Razorpay IFSC API
        url = f"https://ifsc.razorpay.com/{ifsc}"
        response = requests.get(url, timeout=10)
        
        # Check if request was successful
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            # IFSC not found
            return None
        else:
            # Other HTTP errors
            print(f"Error fetching IFSC details: HTTP {response.status_code}")
            return None
            
    except requests.exceptions.RequestException as e:
        # Network or request errors
        print(f"Error fetching IFSC details: {str(e)}")
        return None
    except json.JSONDecodeError as e:
        # JSON parsing errors
        print(f"Error parsing IFSC response: {str(e)}")
        return None
    except Exception as e:
        # Any other unexpected errors
        print(f"Unexpected error fetching IFSC details: {str(e)}")
        return None


def validate_ifsc_format(ifsc: str) -> bool:
    """
    Validate IFSC code format.
    
    Args:
        ifsc (str): The IFSC code to validate
        
    Returns:
        bool: True if format is valid, False otherwise
    """
    if not ifsc or not isinstance(ifsc, str):
        return False
    
    ifsc = ifsc.strip().upper()
    
    # IFSC should be 11 characters long and alphanumeric
    if len(ifsc) != 11 or not ifsc.isalnum():
        return False
    
    # First 4 characters should be alphabetic (bank code)
    if not ifsc[:4].isalpha():
        return False
    
    # 5th character should be 0
    if ifsc[4] != '0':
        return False
    
    # Last 6 characters should be alphanumeric (branch code)
    if not ifsc[5:].isalnum():
        return False
    
    return True


def extract_bank_details_for_model(ifsc_data: Dict) -> Dict:
    """
    Extract and format bank details from IFSC API response for BuyerBankDetails model.
    
    Args:
        ifsc_data (Dict): Raw response from IFSC API
        
    Returns:
        Dict: Formatted data suitable for BuyerBankDetails model
    """
    if not ifsc_data:
        return {}
    
    return {
        'ifsc_code': ifsc_data.get('IFSC', ''),
        'bank_name': ifsc_data.get('BANK', ''),
        'bank_branch': ifsc_data.get('BRANCH', ''),
        'bank_centre': ifsc_data.get('CENTRE', ''),
        'bank_city': ifsc_data.get('CITY', ''),
        'bank_district': ifsc_data.get('DISTRICT', ''),
        'bank_state': ifsc_data.get('STATE', ''),
        'bank_address': ifsc_data.get('ADDRESS', ''),
        'bank_phone': ifsc_data.get('CONTACT', ''),
        'bank_micr': ifsc_data.get('MICR', ''),
        'imps_enabled': ifsc_data.get('IMPS', False),
        'neft_enabled': ifsc_data.get('NEFT', False),
        'rtgs_enabled': ifsc_data.get('RTGS', False),
        'upi_enabled': ifsc_data.get('UPI', False)
    }
