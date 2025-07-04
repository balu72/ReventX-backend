from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from ..utils.auth import seller_required, admin_required
from ..models import db, User, UserRole, BuyerProfile, Interest, PropertyType
from ..utils.meeting_utils import calculate_buyer_meeting_quota
# Import helper functions from buyer_utils
from ..utils.buyer_utils import (
    get_nextcloud_connection,
    get_buyer_profile_images,
    convert_image_to_base64_data_url
)
import logging

buyers = Blueprint('buyers', __name__, url_prefix='/api/buyers')

@buyers.route('', methods=['GET'])
@jwt_required()
def get_buyers():
    """Get all buyers with optional filtering"""
    # Get query parameters
    name = request.args.get('name', '')
    operator_type = request.args.get('operator_type', '')
    interest = request.args.get('interest', '')
    property_type = request.args.get('property_type', '')
    country = request.args.get('country', '')
    state = request.args.get('state', '')
    selling_wayanad = request.args.get('selling_wayanad', '')
    
    # Start with a query for all buyers - only include users with buyer role
    query = BuyerProfile.query.join(User).filter(User.role == UserRole.BUYER.value).order_by(BuyerProfile.organization.asc())
    
    # Apply filters if provided
    if name:
        query = query.filter(
            (BuyerProfile.name.ilike(f'%{name}%')) | 
            (BuyerProfile.organization.ilike(f'%{name}%'))
        )
    
    if operator_type:
        query = query.filter(BuyerProfile.operator_type == operator_type)
    
    if interest:
        # For JSONB array fields, use the @> operator to check if array contains element
        query = query.filter(BuyerProfile.interests.op('@>')(f'["{interest}"]'))
    
    if property_type:
        # For JSONB array fields, use the @> operator to check if array contains element
        query = query.filter(BuyerProfile.properties_of_interest.op('@>')(f'["{property_type}"]'))
    
    if country:
        query = query.filter(BuyerProfile.country == country)
    
    if state:
        query = query.filter(BuyerProfile.state == state)
    
    if selling_wayanad:
        selling_wayanad_bool = selling_wayanad.lower() == 'true'
        query = query.filter(BuyerProfile.selling_wayanad == selling_wayanad_bool)
    
    # Execute the query
    buyer_profiles = query.all()
    
    # Convert to dict format without problematic relationships
    buyers_data = []
    for b in buyer_profiles:
        buyer_dict = {
            'id': b.id,
            'user_id': b.user_id,
            'name': b.name,
            'organization': b.organization,
            'designation': b.designation,
            'operator_type': b.operator_type,
            'category_id': b.category_id,
            'salutation': b.salutation,
            'first_name': b.first_name,
            'last_name': b.last_name,
            'vip': b.vip,
            'status': b.status,
            'gst': b.gst,
            'pincode': b.pincode,
           # 'interests': [interest.name for interest in b.interest_relationships] if b.interest_relationships else [],
            'interests': b.interests or [],
            'properties_of_interest': b.properties_of_interest or [],
            'country': b.country,
            'state': b.state,
            'city': b.city,
            'address': b.address,
            'mobile': b.mobile,
            'website': b.website,
            'instagram': b.instagram,
            'year_of_starting_business': b.year_of_starting_business,
            'selling_wayanad': b.selling_wayanad,
            'since_when': b.since_when,
            'bio': b.bio,
            'profile_image': b.profile_image,
            'created_at': b.created_at.isoformat() if b.created_at else None,
            'updated_at': b.updated_at.isoformat() if b.updated_at else None,
            'user': {
                'id': b.user.id,
                'username': b.user.username,
                'email': b.user.email,
                'role': b.user.role,
                'created_at': b.user.created_at.isoformat() if b.user.created_at else None
            }
        }
        
        # Get buyer profile image using helper functions
        try:
            # Get buyer profile images
            image_files = get_buyer_profile_images(b.user_id)
            if image_files:
                # Sort by timestamp (most recent first) and get the latest image
                image_files.sort(key=lambda x: x[0], reverse=True)
                latest_timestamp, latest_filename, latest_file_info = image_files[0]
                
                # Convert image to base64 data URL
                image_data = convert_image_to_base64_data_url(b.user_id, latest_filename)
                buyer_dict['profile_image'] = image_data['image_data_url']
            else:
                # No image found, keep existing profile_image value or set to None
                if not buyer_dict.get('profile_image'):
                    buyer_dict['profile_image'] = None
        except Exception as e:
            # Log error but don't fail the request
            logging.error(f"Error retrieving buyer profile image for user {b.user_id}: {str(e)}")
            # Keep existing profile_image value or set to None
            if not buyer_dict.get('profile_image'):
                buyer_dict['profile_image'] = None

        # Calculate meeting quota information for each buyer
        meeting_quota = calculate_buyer_meeting_quota(b.user_id, b)

        # Add meeting quota information to the buyer dictionary
        buyer_dict.update(meeting_quota)
        
        buyers_data.append(buyer_dict)
     
    return jsonify({
       'buyers': buyers_data
    }), 200

@buyers.route('/<int:buyer_id>', methods=['GET'])
@jwt_required()
def get_buyer(buyer_id):
    """Get a specific buyer's details"""
    # Find the buyer profile
    buyer_profile = BuyerProfile.query.filter_by(user_id=buyer_id).first()
    
    if not buyer_profile:
        return jsonify({
            'error': 'Buyer not found'
        }), 404
    
    # Check if the associated user is actually a buyer
    user = User.query.get(buyer_id)
    if not user or user.role != 'buyer':
        return jsonify({
            'error': 'User is not a buyer'
        }), 400
    
    # Convert to dict format without problematic relationships
    buyer_dict = {
        'id': buyer_profile.id,
        'user_id': buyer_profile.user_id,
        'name': buyer_profile.name,
        'organization': buyer_profile.organization,
        'designation': buyer_profile.designation,
        'operator_type': buyer_profile.operator_type,
        'category_id': buyer_profile.category_id,
        'salutation': buyer_profile.salutation,
        'first_name': buyer_profile.first_name,
        'last_name': buyer_profile.last_name,
        'vip': buyer_profile.vip,
        'status': buyer_profile.status,
        'gst': buyer_profile.gst,
        'pincode': buyer_profile.pincode,
       # 'interests': [interest.name for interest in buyer_profile.interest_relationships] if buyer_profile.interest_relationships else [],
        'interests': buyer_profile.interests or [],
        'properties_of_interest': buyer_profile.properties_of_interest or [],
        'country': buyer_profile.country,
        'state': buyer_profile.state,
        'city': buyer_profile.city,
        'address': buyer_profile.address,
        'mobile': buyer_profile.mobile,
        'website': buyer_profile.website,
        'instagram': buyer_profile.instagram,
        'year_of_starting_business': buyer_profile.year_of_starting_business,
        'selling_wayanad': buyer_profile.selling_wayanad,
        'since_when': buyer_profile.since_when,
        'bio': buyer_profile.bio,
        'profile_image': buyer_profile.profile_image,
        'created_at': buyer_profile.created_at.isoformat() if buyer_profile.created_at else None,
        'updated_at': buyer_profile.updated_at.isoformat() if buyer_profile.updated_at else None,
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'role': user.role,
            'created_at': user.created_at.isoformat() if user.created_at else None
        }
    }
    
    # Get buyer profile image using helper functions
    try:
        # Get buyer profile images
        image_files = get_buyer_profile_images(buyer_id)
        if image_files:
            # Sort by timestamp (most recent first) and get the latest image
            image_files.sort(key=lambda x: x[0], reverse=True)
            latest_timestamp, latest_filename, latest_file_info = image_files[0]
            
            # Convert image to base64 data URL
            image_data = convert_image_to_base64_data_url(buyer_id, latest_filename)
            buyer_dict['profile_image'] = image_data['image_data_url']
        else:
            # No image found, keep existing profile_image value or set to None
            if not buyer_dict.get('profile_image'):
                buyer_dict['profile_image'] = None
    except Exception as e:
        # Log error but don't fail the request
        logging.error(f"Error retrieving buyer profile image: {str(e)}")
        # Keep existing profile_image value or set to None
        if not buyer_dict.get('profile_image'):
            buyer_dict['profile_image'] = None
    
    # Calculate meeting quota information
    meeting_quota = calculate_buyer_meeting_quota(buyer_id, buyer_profile)
    
    # Add meeting quota information to the buyer dictionary
    buyer_dict.update(meeting_quota)
    
    return jsonify({
        'buyer': buyer_dict
    }), 200

@buyers.route('/operator-types', methods=['GET'])
@jwt_required()
def get_operator_types():
    """Get all unique operator types"""
    operator_types = db.session.query(BuyerProfile.operator_type).distinct().all()
    # Filter out None values and extract from tuples
    types = [t[0] for t in operator_types if t[0]]
    
    # If no data exists, return default types
    if not types:
        types = ['Tour Operator', 'Travel Agent', 'Hotel Chain', 'Resort Owner', 'DMC']
    
    return jsonify({
        'operator_types': types
    }), 200

@buyers.route('/interests', methods=['GET'])
@jwt_required()
def get_interests():
    """Read all  interests"""
    # Get all buyer profiles and extract unique interests
    all_interests = Interest.query.all()
    interests = []
    
    for interest in all_interests:
        if (interest.name):
            interests.append(interest.name)

    return jsonify({
        'interests': interests
    }), 200

@buyers.route('/property-types', methods=['GET'])
@jwt_required()
def get_property_types():
    """Get all unique property types"""
    # Get all buyer profiles and extract unique property types
    all_property_types = PropertyType.query.all()
    property_types = []
    
    for property_type in all_property_types:
        if (property_type.name):
            property_types.append(property_type.name)
    
    return jsonify({
        'property_types': property_types
    }), 200

@buyers.route('/countries', methods=['GET'])
@jwt_required()
def get_countries():
    """Get all unique countries"""
    countries = db.session.query(BuyerProfile.country).distinct().all()
    # Filter out None values and extract from tuples
    country_list = [c[0] for c in countries if c[0]]
    
    # If no data exists, return default countries
    if not country_list:
        country_list = ['India', 'USA', 'UK', 'Germany', 'France', 'Australia', 'Canada', 'Singapore']
    
    return jsonify({
        'countries': country_list
    }), 200

@buyers.route('/states', methods=['GET'])
@jwt_required()
def get_states():
    """Get all unique states for a specific country"""
    country = request.args.get('country')
    
    if not country:
        return jsonify({
            'error': 'Country parameter is required'
        }), 400
    
   # states = db.session.query(BuyerProfile.state).filter_by(country=country).distinct().all()
    # Filter out None values and extract from tuples
  #  state_list = [s[0] for s in states if s[0]]
    state_list =[]
    
    # If no data exists, return default states based on country
    if not state_list:
        static_data_states = {
            'India': [
                'Andhra Pradesh', 'Arunachal Pradesh', 'Assam', 'Bihar', 'Chhattisgarh',
                'Goa', 'Gujarat', 'Haryana', 'Himachal Pradesh', 'Jharkhand', 'Karnataka',
                'Kerala', 'Madhya Pradesh', 'Maharashtra', 'Manipur', 'Meghalaya',
                'Mizoram', 'Nagaland', 'Odisha', 'Punjab', 'Rajasthan', 'Sikkim',
                'Tamil Nadu', 'Telangana', 'Tripura', 'Uttar Pradesh', 'Uttarakhand',
                'West Bengal'
            ],
            'USA': [
                'Alabama', 'Alaska', 'Arizona', 'Arkansas', 'California', 'Colorado', 'Connecticut',
                'Delaware', 'Florida', 'Georgia', 'Hawaii', 'Idaho', 'Illinois', 'Indiana', 'Iowa',
                'Kansas', 'Kentucky', 'Louisiana', 'Maine', 'Maryland', 'Massachusetts', 'Michigan',
                'Minnesota', 'Mississippi', 'Missouri', 'Montana', 'Nebraska', 'Nevada', 'New Hampshire',
                'New Jersey', 'New Mexico', 'New York', 'North Carolina', 'North Dakota', 'Ohio',
                'Oklahoma', 'Oregon', 'Pennsylvania', 'Rhode Island', 'South Carolina', 'South Dakota',
                'Tennessee', 'Texas', 'Utah', 'Vermont', 'Virginia', 'Washington', 'West Virginia',
                'Wisconsin', 'Wyoming'
            ],
            'UK': [
                    'England', 'Scotland', 'Wales', 'Northern Ireland'
                ],
            'Germany': [
                'Baden-Württemberg', 'Bavaria', 'Berlin', 'Brandenburg', 'Bremen', 'Hamburg', 'Hesse',
                'Lower Saxony', 'Mecklenburg-Vorpommern', 'North Rhine-Westphalia', 'Rhineland-Palatinate',
                'Saarland', 'Saxony', 'Saxony-Anhalt', 'Schleswig-Holstein', 'Thuringia'
            ],
            'France': [
                'Auvergne-Rhône-Alpes', 'Bourgogne-Franche-Comté', 'Brittany', 'Centre-Val de Loire',
                'Corsica', 'Grand Est', 'Hauts-de-France', 'Île-de-France', 'Normandy', 'Nouvelle-Aquitaine',
                'Occitanie', 'Pays de la Loire', 'Provence-Alpes-Côte d\'Azur'
            ],
            'Australia': [
                'New South Wales', 'Victoria', 'Queensland', 'Western Australia', 'South Australia',
                'Tasmania', 'Northern Territory', 'Australian Capital Territory'
            ],
            'Canada': [
                'Alberta', 'British Columbia', 'Manitoba', 'New Brunswick', 'Newfoundland and Labrador',
                'Nova Scotia', 'Ontario', 'Prince Edward Island', 'Quebec', 'Saskatchewan', 'Northwest Territories',
                'Nunavut', 'Yukon'
            ],
            'Singapore': [
                'Central Region', 'East Region', 'North Region', 'North-East Region', 'West Region'
            ]
        }
        state_list = static_data_states.get(country, [])
    
    return jsonify({
        'states': state_list
    }), 200

def _get_all_valid_buyer_user_ids():
    """Helper function to get all valid buyer user IDs"""
    buyer_user_ids = db.session.query(BuyerProfile.user_id).join(User).filter(
        User.role == UserRole.BUYER.value
    ).order_by(BuyerProfile.user_id.asc()).all()
    
    # Extract user_ids from tuples
    return [uid[0] for uid in buyer_user_ids]

@buyers.route('/by-user-ids', methods=['POST'])
@jwt_required()
def get_buyers_by_user_ids():
    """Get buyers by array of user IDs"""
    try:
        # Get JSON data from request
        data = request.get_json()
        
        if not data:
            return jsonify({
                'error': 'JSON payload required'
            }), 400
        
        user_ids = data.get('user_ids', [])
        
        # Validate input
        if not isinstance(user_ids, list):
            return jsonify({
                'error': 'user_ids must be an array'
            }), 400
        
        if len(user_ids) == 0:
            return jsonify({
                'error': 'user_ids array cannot be empty'
            }), 400
        
        if len(user_ids) > 20:
            return jsonify({
                'error': 'Maximum 20 user IDs allowed'
            }), 400
        
        # Filter to only positive integers
        valid_input_ids = []
        invalid_user_ids = []
        
        for user_id in user_ids:
            if isinstance(user_id, int) and user_id > 0:
                valid_input_ids.append(user_id)
            else:
                invalid_user_ids.append(user_id)
        
        if len(valid_input_ids) == 0:
            return jsonify({
                'error': 'No valid user IDs provided (must be positive integers)'
            }), 400
        
        # Get all valid buyer user IDs from the database
        all_valid_buyer_ids = _get_all_valid_buyer_user_ids()
        
        # Filter input IDs to only include those that are valid buyers
        valid_buyer_ids = [uid for uid in valid_input_ids if uid in all_valid_buyer_ids]
        not_found_user_ids = [uid for uid in valid_input_ids if uid not in all_valid_buyer_ids]
        
        # Add not found IDs to invalid list
        invalid_user_ids.extend(not_found_user_ids)
        
        if len(valid_buyer_ids) == 0:
            return jsonify({
                'buyers': [],
                'invalid_user_ids': invalid_user_ids,
                'summary': {
                    'requested': len(user_ids),
                    'valid': 0,
                    'invalid': len(invalid_user_ids)
                }
            }), 200
        
        # Query for buyer profiles with valid buyer IDs
        buyer_profiles = BuyerProfile.query.join(User).filter(
            User.id.in_(valid_buyer_ids)
        ).order_by(BuyerProfile.organization.asc()).all()
        
        # Convert to dict format without meeting quota information
        buyers_data = []
        for b in buyer_profiles:
            buyer_dict = {
                'id': b.id,
                'user_id': b.user_id,
                'name': b.name,
                'organization': b.organization,
                'designation': b.designation,
                'operator_type': b.operator_type,
                'category_id': b.category_id,
                'salutation': b.salutation,
                'first_name': b.first_name,
                'last_name': b.last_name,
                'vip': b.vip,
                'status': b.status,
                'gst': b.gst,
                'pincode': b.pincode,
                'interests': b.interests or [],
                'properties_of_interest': b.properties_of_interest or [],
                'country': b.country,
                'state': b.state,
                'city': b.city,
                'address': b.address,
                'mobile': b.mobile,
                'website': b.website,
                'instagram': b.instagram,
                'year_of_starting_business': b.year_of_starting_business,
                'selling_wayanad': b.selling_wayanad,
                'since_when': b.since_when,
                'bio': b.bio,
                'profile_image': b.profile_image,
                'created_at': b.created_at.isoformat() if b.created_at else None,
                'updated_at': b.updated_at.isoformat() if b.updated_at else None,
                'user': {
                    'id': b.user.id,
                    'username': b.user.username,
                    'email': b.user.email,
                    'role': b.user.role,
                    'created_at': b.user.created_at.isoformat() if b.user.created_at else None
                }
            }
            
            # Note: Meeting quota information is intentionally omitted for performance
            
            buyers_data.append(buyer_dict)
        
        return jsonify({
            'buyers': buyers_data,
            'invalid_user_ids': invalid_user_ids,
            'summary': {
                'requested': len(user_ids),
                'valid': len(buyers_data),
                'invalid': len(invalid_user_ids)
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'error': f'Internal server error: {str(e)}'
        }), 500

@buyers.route('/user-ids', methods=['GET'])
@jwt_required()
def get_all_buyer_user_ids():
    """Get all valid buyer user IDs with optional filtering"""
    try:
        # Get query parameters for filtering
        name = request.args.get('name', '')
        operator_type = request.args.get('operator_type', '')
        interest = request.args.get('interest', '')
        property_type = request.args.get('property_type', '')
        country = request.args.get('country', '')
        state = request.args.get('state', '')
        
        # If no filters provided, return all buyer user IDs (backward compatibility)
        if not any([name, operator_type, interest, property_type, country, state]):
            user_ids = _get_all_valid_buyer_user_ids()
            return jsonify({
                'user_ids': user_ids
            }), 200
        
        # Start with a query for all buyers - only include users with buyer role
        query = db.session.query(BuyerProfile.user_id).join(User).filter(
            User.role == UserRole.BUYER.value
        )
        
        # Apply filters if provided
        if name:
            query = query.filter(
                (BuyerProfile.name.ilike(f'%{name}%')) | 
                (BuyerProfile.organization.ilike(f'%{name}%'))
            )
        
        if operator_type:
            query = query.filter(BuyerProfile.operator_type == operator_type)
        
        if interest:
            # For JSONB array fields, use the @> operator to check if array contains element
            query = query.filter(BuyerProfile.interests.op('@>')(f'["{interest}"]'))
        
        if property_type:
            # For JSONB array fields, use the @> operator to check if array contains element
            query = query.filter(BuyerProfile.properties_of_interest.op('@>')(f'["{property_type}"]'))
        
        if country:
            query = query.filter(BuyerProfile.country == country)
        
        if state:
            query = query.filter(BuyerProfile.state == state)
        
        # Execute the query and get user IDs
        query = query.order_by(BuyerProfile.user_id.asc())
        user_id_tuples = query.all()
        
        # Extract user_ids from tuples
        user_ids = [uid[0] for uid in user_id_tuples]
        
        return jsonify({
            'user_ids': user_ids
        }), 200
        
    except Exception as e:
        return jsonify({
            'error': f'Internal server error: {str(e)}'
        }), 500
