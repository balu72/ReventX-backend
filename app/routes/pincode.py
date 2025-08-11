from flask import Blueprint, jsonify, request
import logging

try:
    from pinin import get_pincode_info, get_state, get_states, get_districts
    PYPININDIA_AVAILABLE = True
except ImportError:
    PYPININDIA_AVAILABLE = False
    logging.warning("pypinindia library not available. Pincode services will be limited.")

pincode = Blueprint('pincode', __name__, url_prefix='/api/pincode')


@pincode.route('/<pincode_value>', methods=['GET'])
def get_pincode_details(pincode_value):
    """
    PUBLIC ENDPOINT: Get location details for a specific pincode using pypinindia
    Used for form auto-fill during registration
    """
    if not PYPININDIA_AVAILABLE:
        return jsonify({
            'error': 'Pincode service not available. pypinindia library not installed.'
        }), 503
    
    # Validate pincode format
    if not pincode_value or len(pincode_value) != 6 or not pincode_value.isdigit():
        return jsonify({
            'error': 'Invalid pincode format. Please provide a 6-digit pincode.'
        }), 400
    
    try:
        # Get pincode information
        pincode_info = get_pincode_info(pincode_value)
        
        if not pincode_info or len(pincode_info) == 0:
            return jsonify({
                'error': f'No location found for pincode {pincode_value}'
            }), 404
        
        # Get the first delivery office (usually the main one)
        main_office = None
        for office in pincode_info:
            if office.get('Deliverystatus') == 'Delivery':
                main_office = office
                break
        
        # If no delivery office found, use the first one
        if not main_office:
            main_office = pincode_info[0]
        
        # Extract location details
        pypinindia_state = main_office.get('statename', '').upper()
        district = main_office.get('districtname', '')
        office_name = main_office.get('officename', '')
        
        # Use district as city, but clean it up
        city = district.replace(' District', '').replace(' district', '').strip()
        if not city:
            city = office_name.replace(' H.O', '').replace(' S.O', '').replace(' B.O', '').strip()
        
        return jsonify({
            'pincode': pincode_value,
            'state': pypinindia_state.title(),  # Return pypinindia state as-is, just properly formatted
            'district': district,
            'city': city,
            'country': 'India',
            'office_name': office_name,
            'office_type': main_office.get('officetype', ''),
            'delivery_status': main_office.get('Deliverystatus', ''),
            'division': main_office.get('divisionname', ''),
            'region': main_office.get('regionname', ''),
            'circle': main_office.get('circlename', ''),
            'taluk': main_office.get('taluk', ''),
            'all_offices': len(pincode_info)
        }), 200
        
    except Exception as e:
        logging.error(f"Error fetching pincode details for {pincode_value}: {str(e)}")
        return jsonify({
            'error': f'Failed to fetch pincode details: {str(e)}'
        }), 500

@pincode.route('/validate/<pincode_value>', methods=['GET'])
def validate_pincode(pincode_value):
    """
    PUBLIC ENDPOINT: Validate a pincode and return basic info
    Used for form validation during registration
    """
    if not PYPININDIA_AVAILABLE:
        return jsonify({
            'error': 'Pincode service not available. pypinindia library not installed.'
        }), 503
    
    # Validate pincode format
    if not pincode_value or len(pincode_value) != 6 or not pincode_value.isdigit():
        return jsonify({
            'valid': False,
            'error': 'Invalid pincode format. Please provide a 6-digit pincode.'
        }), 200
    
    try:
        # Get state for pincode
        state = get_state(pincode_value)
        
        if not state:
            return jsonify({
                'valid': False,
                'error': f'Pincode {pincode_value} not found'
            }), 200
        
        return jsonify({
            'valid': True,
            'pincode': pincode_value,
            'state': state.title()
        }), 200
        
    except Exception as e:
        logging.error(f"Error validating pincode {pincode_value}: {str(e)}")
        return jsonify({
            'valid': False,
            'error': f'Failed to validate pincode: {str(e)}'
        }), 200

@pincode.route('/states', methods=['GET'])
def get_all_states():
    """
    PUBLIC ENDPOINT: Get all states available in pypinindia
    Used for dropdown population in registration forms
    """
    if not PYPININDIA_AVAILABLE:
        return jsonify({
            'error': 'Pincode service not available. pypinindia library not installed.'
        }), 503
    
    try:
        # Get all states from pypinindia
        pypinindia_states = get_states()
        
        # Format state names properly
        formatted_states = [state.title() for state in pypinindia_states]
        
        return jsonify({
            'states': sorted(formatted_states),
            'total_count': len(formatted_states)
        }), 200
        
    except Exception as e:
        logging.error(f"Error fetching states: {str(e)}")
        return jsonify({
            'error': f'Failed to fetch states: {str(e)}'
        }), 500

@pincode.route('/districts/<state_name>', methods=['GET'])
def get_districts_for_state(state_name):
    """
    PUBLIC ENDPOINT: Get all districts for a specific state
    Used for district/city dropdown population
    """
    if not PYPININDIA_AVAILABLE:
        return jsonify({
            'error': 'Pincode service not available. pypinindia library not installed.'
        }), 503
    
    try:
        # Use state name as-is, just convert to uppercase for pypinindia
        pypinindia_state = state_name.upper()
        
        # Get districts for the state
        districts = get_districts(pypinindia_state)
        
        if not districts:
            return jsonify({
                'error': f'No districts found for state: {state_name}'
            }), 404
        
        return jsonify({
            'state': state_name,
            'districts': sorted(districts),
            'total_count': len(districts)
        }), 200
        
    except Exception as e:
        logging.error(f"Error fetching districts for state {state_name}: {str(e)}")
        return jsonify({
            'error': f'Failed to fetch districts: {str(e)}'
        }), 500

@pincode.route('/health', methods=['GET'])
def health_check():
    """
    PUBLIC ENDPOINT: Health check endpoint for pincode service
    """
    return jsonify({
        'service': 'pincode',
        'status': 'healthy',
        'pypinindia_available': PYPININDIA_AVAILABLE,
        'version': '1.0.0'
    }), 200
