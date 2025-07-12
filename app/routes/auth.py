from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token, 
    create_refresh_token,
    jwt_required, 
    get_jwt_identity,
    get_jwt
)
from datetime import datetime, timedelta
import re
import logging
from ..models import db, User, UserRole, InvitedBuyer, PendingBuyer, DomainRestriction, BuyerProfile, SellerProfile, SellerAttendee, AccessLog
from ..utils.email_service import send_registration_confirmation_email

auth = Blueprint('auth', __name__, url_prefix='/api/auth')

# Token blacklist for logout functionality
# In a production environment, this should be stored in Redis or another persistent store
token_blacklist = set()

@auth.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['username', 'email', 'password', 'role']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    # Check if username or email already exists
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'Username already exists'}), 409
    
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email already exists'}), 409
    
    # Validate role
    try:
        role = UserRole(data['role'])
    except ValueError:
        return jsonify({'error': f'Invalid role. Must be one of: {[r.value for r in UserRole]}'}), 400
    
    # Don't allow direct registration as admin
    if role == UserRole.ADMIN:
        return jsonify({'error': 'Cannot register as admin'}), 403
    
    # Additional fields for sellers
    kwargs = {}
    if role == UserRole.SELLER:
        if 'business_name' not in data:
            return jsonify({'error': 'Business name is required for sellers'}), 400
        kwargs['business_name'] = data['business_name']
        kwargs['business_description'] = data.get('business_description', '')
    
    # Create new user
    user = User(
        username=data['username'],
        email=data['email'],
        password=data['password'],
        role=role,
        **kwargs
    )
    
    db.session.add(user)
    db.session.commit()
    
    return jsonify({
        'message': 'User registered successfully',
        'user': user.to_dict()
    }), 201

@auth.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    
    # Validate required fields
    if not data.get('username') or not data.get('password'):
        return jsonify({'error': 'Username and password are required'}), 400
    
    # Find user by username
    user = User.query.filter_by(username=data['username']).first()
    
    # Check if user exists and password is correct
    if not user or not user.check_password(data['password']):
        return jsonify({'error': 'Invalid username or password'}), 401
    
    # Create tokens
    access_token = create_access_token(
        identity=str(user.id),  # Convert to string to avoid JWT issues
        additional_claims={'role': user.role},
        expires_delta=timedelta(hours=1)
    )
    refresh_token = create_refresh_token(
        identity=str(user.id),  # Convert to string to avoid JWT issues
        additional_claims={'role': user.role},
        expires_delta=timedelta(days=30)
    )
    
    return jsonify({
        'access_token': access_token,
        'refresh_token': refresh_token,
        'user': user.to_dict()
    }), 200

@auth.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    current_user_id = get_jwt_identity()
    # Convert to int if it's a string
    if isinstance(current_user_id, str):
        try:
            current_user_id = int(current_user_id)
        except ValueError:
            return jsonify({'error': 'Invalid user ID'}), 400
    
    user = User.query.get(current_user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Create new access token
    access_token = create_access_token(
        identity=str(user.id),  # Convert to string to avoid JWT issues
        additional_claims={'role': user.role},
        expires_delta=timedelta(hours=1)
    )
    
    return jsonify({
        'access_token': access_token,
        'user': user.to_dict()
    }), 200

@auth.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    current_user_id = get_jwt_identity()
    # Convert to int if it's a string
    if isinstance(current_user_id, str):
        try:
            current_user_id = int(current_user_id)
        except ValueError:
            return jsonify({'error': 'Invalid user ID'}), 400
    
    user = User.query.get(current_user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    return jsonify(user.to_dict()), 200

@auth.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    jti = get_jwt()['jti']
    token_blacklist.add(jti)
    return jsonify({'message': 'Successfully logged out'}), 200

# Helper function to check if a token is blacklisted
def is_token_blacklisted(jwt_header, jwt_payload):
    jti = jwt_payload['jti']
    return jti in token_blacklist

@auth.route('/validate-invite/<token>', methods=['GET'])
def validate_invite(token):
    """Validate an invitation token"""
    invited_buyer = InvitedBuyer.query.filter_by(invitation_token=token).first()
    
    if not invited_buyer:
        return jsonify({'error': 'Invalid invitation token'}), 404
    
    if invited_buyer.is_registered:
        return jsonify({'error': 'Invitation already used'}), 400
    
    if invited_buyer.expires_at < datetime.utcnow():
        return jsonify({'error': 'Invitation expired'}), 400
    
    return jsonify({
        'message': 'Invitation valid',
        'invited_buyer': {
            'name': invited_buyer.name,
            'email': invited_buyer.email
        }
    }), 200

@auth.route('/register-invited', methods=['POST'])
def register_invited():
    """Register an invited buyer"""
    data = request.get_json()
    
    # Validate required fields
    required_fields = [
        'token', 'name', 'designation', 'company', 'address', 'city', 'state', 
        'pin', 'mobile', 'email', 'year_of_starting_business', 'type_of_operator',
        'already_sell_wayanad', 'opinion_about_previous_splash', 
        'reference_property1_name', 'reference_property1_address',
        'interests', 'properties_of_interest', 'why_attend_splash2025'
    ]
    
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    # Validate invitation token
    invited_buyer = InvitedBuyer.query.filter_by(invitation_token=data['token']).first()
    
    if not invited_buyer:
        return jsonify({'error': 'Invalid invitation token'}), 404
    
    if invited_buyer.is_registered:
        return jsonify({'error': 'Invitation already used'}), 400
    
    if invited_buyer.expires_at < datetime.utcnow():
        return jsonify({'error': 'Invitation expired'}), 400
    
    # Validate email matches invitation
    if data['email'].lower() != invited_buyer.email.lower():
        return jsonify({'error': 'Email does not match invitation'}), 400
    
    # Check domain restriction if enabled
    domain_restrictions = DomainRestriction.query.filter_by(is_enabled=True).all()
    if domain_restrictions:
        email_domain = data['email'].split('@')[-1].lower()
        allowed_domains = [r.domain.lower() for r in domain_restrictions]
        
        if email_domain not in allowed_domains:
            return jsonify({'error': 'Email domain not allowed'}), 400
    
    # Validate mobile number format
    if not re.match(r'^\+\d{12}$', data['mobile']):
        return jsonify({'error': 'Invalid mobile number format. Must be in format: +XXXXXXXXXXXX (12 digits after +)'}), 400
    
    # Create pending buyer
    pending_buyer = PendingBuyer(
        invited_buyer_id=invited_buyer.id,
        name=data['name'],
        designation=data['designation'],
        company=data['company'],
        gst=data.get('gst'),
        address=data['address'],
        city=data['city'],
        state=data['state'],
        pin=data['pin'],
        mobile=data['mobile'],
        email=data['email'],
        website=data.get('website'),
        instagram=data.get('instagram'),
        year_of_starting_business=data['year_of_starting_business'],
        type_of_operator=data['type_of_operator'],
        already_sell_wayanad=data['already_sell_wayanad'],
        since_when=data.get('since_when'),
        opinion_about_previous_splash=data['opinion_about_previous_splash'],
        property_stayed_in=data.get('property_stayed_in'),
        reference_property1_name=data['reference_property1_name'],
        reference_property1_address=data['reference_property1_address'],
        reference_property2_name=data.get('reference_property2_name'),
        reference_property2_address=data.get('reference_property2_address'),
        interests=','.join(data['interests']),
        properties_of_interest=','.join(data['properties_of_interest']),
        why_attend_splash2025=data['why_attend_splash2025']
    )
    
    db.session.add(pending_buyer)
    db.session.commit()
    
    # Send confirmation email
    send_registration_confirmation_email(pending_buyer)
    
    return jsonify({
        'message': 'Registration submitted successfully',
        'pending_buyer': pending_buyer.to_dict()
    }), 201

@auth.route('/check_user_access/<user_slug>', methods=['GET'])
def check_user_access(user_slug):
    """Check user access information by user slug (public endpoint)"""
    try:
        # Trim the user_slug first
        user_slug = user_slug.strip()
        
        # Check for seller-attendee pattern: S{1-3digits}SA{1-2digits}
        seller_attendee_pattern = r'^S(\d{1,3})SA(\d{1,2})$'
        match = re.match(seller_attendee_pattern, user_slug)
        
        if match:
            seller_id = int(match.group(1).strip())  # Convert to int after trimming
            attendee_number = int(match.group(2).strip())  # Convert to int after trimming
            
            # Validate seller exists in users table
            seller_user = User.query.get(seller_id)
            if not seller_user or seller_user.role != UserRole.SELLER.value:
                return jsonify({'error': 'User not found'}), 404
            
            # Check if seller exists in seller_profiles table
            seller_profile = SellerProfile.query.filter_by(user_id=seller_id).first()
            if not seller_profile:
                return jsonify({'error': 'Unable to locate seller details'}), 404
            
            # Call new helper function
            return get_seller_attendee_info(seller_profile.id, attendee_number)
        
        # Extract user ID from slug (handle both "123" and "B123"/"S123" formats)
        if user_slug.startswith(('B', 'S')):
            user_id = int(user_slug[1:])  # Remove prefix
        else:
            user_id = int(user_slug)  # Direct numeric ID
        
        # Find user by ID
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Based on user role, fetch appropriate profile
        if user.role == UserRole.BUYER.value:
            return get_buyer_access_info(user)
        elif user.role == UserRole.SELLER.value:
            return get_seller_access_info(user)
        else:
            return jsonify({'error': 'Invalid user type'}), 400
            
    except ValueError:
        return jsonify({'error': 'Invalid user slug format'}), 400
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

def get_buyer_access_info(user):
    """Get access information for a buyer"""
    buyer_profile = user.buyer_profile
    if not buyer_profile:
        return jsonify({'error': 'Unable to locate buyer details'}), 404
    
    # Name priority: use 'name' if available, else combine first_name + last_name
    full_name = buyer_profile.name
    if not full_name and (buyer_profile.first_name or buyer_profile.last_name):
        full_name = f"{buyer_profile.first_name or ''} {buyer_profile.last_name or ''}".strip()
    
    # Get buyer profile image using the same helper function as in buyer.py
    profile_image_data = None
    try:
        if buyer_profile.profile_image:
            # Extract filename from the stored path
            filename = buyer_profile.profile_image.split('/')[-1]
            
            # Convert image to base64 data URL using helper function
            from ..utils.buyer_utils import convert_image_to_base64_data_url
            image_data = convert_image_to_base64_data_url(user.id, filename)
            profile_image_data = image_data['image_data_url']
        else:
            # No profile image path stored
            profile_image_data = None
    except Exception as e:
        # Log error but don't fail the request
        logging.error(f"Error retrieving buyer profile image for user {user.id}: {str(e)}")
        profile_image_data = None
    
    # Log successful buyer access
    try:
        log_access_event(
            scanned_id=f"B{user.id}",
            scan_type="BUYER_ACCESS"
        )
    except Exception as e:
        # Log error but don't fail the request
        logging.error(f"Error logging access event for buyer {user.id}: {str(e)}")
    
    return jsonify({
        'fullName': full_name or '',
        'company': buyer_profile.organization or '',
        'designation': buyer_profile.designation or '',
        'contactPhone': buyer_profile.mobile or '',
        'contactEmail': user.email or '',
        'profileImage': profile_image_data
    })

def get_seller_access_info(user):
    """Get access information for a seller"""
    seller_profile = user.seller_profile
    if not seller_profile:
        return jsonify({'error': 'Unable to locate seller details'}), 404
    
    # Name priority: use 'name' if available, else combine first_name + last_name
    full_name = getattr(seller_profile, 'name', None)  # Check if name field exists
    if not full_name and (seller_profile.first_name or seller_profile.last_name):
        full_name = f"{seller_profile.first_name or ''} {seller_profile.last_name or ''}".strip()
    
    # Log successful seller access
    try:
        log_access_event(
            scanned_id=f"S{user.id}",
            scan_type="SELLER_ACCESS"
        )
    except Exception as e:
        # Log error but don't fail the request
        logging.error(f"Error logging access event for buyer {user.id}: {str(e)}")

    return jsonify({
        'fullName': full_name or '',
        'company': seller_profile.business_name or '',
        'designation': seller_profile.designation or '',
        'contactPhone': seller_profile.mobile or '',
        'contactEmail': user.email or '',
        'profileImage': None  # Always None for sellers as requested
    })

def get_seller_attendee_info(seller_profile_id, attendee_number):
    """Get access information for a seller attendee"""
    # Get the seller profile
    seller_profile = SellerProfile.query.get(seller_profile_id)
    if not seller_profile:
        return jsonify({'error': 'Unable to locate seller details'}), 404
    
    # Get the specific attendee
    attendee = SellerAttendee.query.filter_by(
        seller_profile_id=seller_profile_id,
        attendee_number=attendee_number
    ).first()
    
    if not attendee:
        return jsonify({'error': 'Unable to locate attendee details'}), 404
    
    # Log successful seller attendee access
    try:
        log_access_event(
            scanned_id=f"S{seller_profile.user_id}SA{attendee_number}",
            scan_type="SELLER_ATTENDEE_ACCESS"
        )
    except Exception as e:
            # Log error but don't fail the request
        logging.error(f"Error logging access event for buyer {user.id}: {str(e)}")
    
    return jsonify({
        'fullName': (attendee.name or '').strip(),
        'company': (seller_profile.business_name or '').strip(),
        'designation': (attendee.designation or '').strip(),
        'contactPhone': (attendee.mobile or '').strip(),
        'contactEmail': (attendee.email or '').strip(),
        'profileImage': None
    })

@auth.route('/register-walkin-buyer', methods=['POST'])
def register_walkin_buyer():
    """Register a new walk-in buyer"""
    data = request.get_json()
    
    # Validate required fields
    required_fields = [
        'salutation', 'firstName', 'lastName', 'organization', 
        'phone', 'email', 'state', 'city', 'pincode'
    ]
    
    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    # Validate email format
    import re
    email_regex = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
    if not re.match(email_regex, data['email']):
        return jsonify({'error': 'Invalid email format'}), 400
    
    # Check if email already exists
    existing_user = User.query.filter_by(email=data['email']).first()
    if existing_user:
        return jsonify({'error': 'Email already exists'}), 409
    
    # Generate username from email (use email prefix)
    username = data['email'].split('@')[0]
    
    # Ensure username is unique by appending numbers if needed
    base_username = username
    counter = 1
    while User.query.filter_by(username=username).first():
        username = f"{base_username}{counter}"
        counter += 1
    
    try:
        # Create new user with default password "Splash123"
        user = User(
            username=username,
            email=data['email'],
            password="Splash123",  # This will be hashed automatically in the User.__init__ method
            role=UserRole.BUYER
        )
        
        db.session.add(user)
        db.session.flush()  # Get the user ID
        
        # Create buyer profile with walk-in category (ID 7)
        buyer_profile = BuyerProfile(
            user_id=user.id,
            salutation=data['salutation'],
            first_name=data['firstName'],
            last_name=data['lastName'],
            name=f"{data['firstName']} {data['lastName']}",  # Full name
            organization=data['organization'],
            designation=data.get('designation', ''),
            mobile=data['phone'],
            operator_type=data.get('operatorType', 'Domestic'),
            state=data['state'],
            city=data['city'],
            pincode=data['pincode'],
            gst=data.get('gst', ''),
            category_id=7,  # Walk-in buyer category
            status='active'  # Set as active immediately
        )
        
        db.session.add(buyer_profile)
        db.session.commit()
        
        return jsonify({
            'message': 'Walk-in buyer registered successfully',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.role
            },
            'buyer_profile': {
                'id': buyer_profile.id,
                'name': buyer_profile.name,
                'organization': buyer_profile.organization,
                'category_id': buyer_profile.category_id
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        print(f"Error creating walk-in buyer: {str(e)}")
        return jsonify({'error': 'Failed to register walk-in buyer. Please try again.'}), 500

def log_access_event(scanned_id, scan_type=None, scan_date_time=None):
    """
    Log an access event to the access_log table
    
    Args:
        scanned_id (str): The ID that was scanned/accessed
        scan_type (str, optional): Type of scan/access event
        scan_date_time (datetime, optional): When the event occurred (defaults to now)
    
    Returns:
        dict: {'success': bool, 'message': str, 'log_id': int}
    """
    try:
        # Validate required parameters
        if not scanned_id:
            return {
                'success': False,
                'message': 'scanned_id is required',
                'log_id': None
            }
        
        # Convert scanned_id to string and ensure it's not longer than 100 characters
        scanned_id_str = str(scanned_id)[:100]
        
        # Use current time if scan_date_time is not provided
        if scan_date_time is None:
            scan_date_time = datetime.utcnow()
        
        # Truncate scan_type if it's too long
        if scan_type and len(scan_type) > 100:
            scan_type = scan_type[:100]
        
        # Create new access log entry
        access_log = AccessLog(
            scanned_id=scanned_id_str,
            scan_date_time=scan_date_time,
            scan_type=scan_type,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        # Add to database session
        db.session.add(access_log)
        db.session.commit()
        
        logging.info(f"Access event logged: ID={scanned_id_str}, Type={scan_type}, Time={scan_date_time}")
        
        return {
            'success': True,
            'message': 'Access event logged successfully',
            'log_id': access_log.id
        }
        
    except Exception as e:
        # Rollback the session in case of error
        db.session.rollback()
        
        # Log the error
        error_msg = f"Failed to log access event: {str(e)}"
        logging.error(error_msg)
        
        return {
            'success': False,
            'message': error_msg,
            'log_id': None
        }
