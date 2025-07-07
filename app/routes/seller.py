from nc_py_api import Nextcloud, NextcloudException
from io import BytesIO
from PIL import Image
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from urllib.parse import urlparse

import logging
import os
from ..models import (
    db, User, UserRole, SellerProfile, SellerAttendee, SellerBusinessInfo, 
    SellerFinancialInfo, SellerReferences, PropertyType, Interest, BuyerCategory,
    StallType, Meeting, TimeSlot, TravelPlan, Transportation, Accommodation,
    GroundTransportation, Listing, ListingDate, InvitedBuyer, PendingBuyer,
    DomainRestriction, BuyerProfile, BuyerBusinessInfo, BuyerFinancialInfo,
    BuyerReferences, Stall, StallInventory, MigrationLog, MigrationMappingBuyers,
    MigrationMappingSellers, SystemSetting
)
from ..utils.auth import seller_required, admin_required
from ..utils.meeting_utils import calculate_seller_meeting_quota

seller = Blueprint('seller', __name__, url_prefix='/api/sellers')

@seller.route('', methods=['GET'])
@jwt_required()
def get_sellers():
    """Get all sellers with optional filtering"""
    # Get query parameters
    name = request.args.get('name', '')
    seller_type = request.args.get('seller_type', '')
    target_market = request.args.get('target_market', '')
    
    # Get all seller profiles and filter by user role in Python to avoid JOIN issues
    all_profiles = SellerProfile.query.all()
    
    # Filter profiles where the associated user has role='seller'
    seller_profiles = []
    for profile in all_profiles:
        user = User.query.get(profile.user_id)
        if user and user.role == 'seller':
            seller_profiles.append(profile)
    
    # Apply filters if provided
    if name:
        seller_profiles = [s for s in seller_profiles if name.lower() in s.business_name.lower()]
    
    if seller_type:
        seller_profiles = [s for s in seller_profiles if s.seller_type == seller_type]
    
    if target_market:
        seller_profiles = [s for s in seller_profiles if s.target_market == target_market]
    
    # Prepare response data with meeting quota information
    sellers_data = []
    for profile in seller_profiles:
        seller_dict = profile.to_dict()
        
        # Calculate meeting quota and add to profile data
        meeting_quota = calculate_seller_meeting_quota(profile.user_id, profile)
        seller_dict.update(meeting_quota)
        
        sellers_data.append(seller_dict)
    
    return jsonify({
        'sellers': sellers_data
    }), 200

@seller.route('/<int:seller_id>', methods=['GET'])
@jwt_required()
def get_seller(seller_id):
    """Get a specific seller's details"""
    # Find the seller profile
    seller_profile = SellerProfile.query.filter_by(user_id=seller_id).first()
    
    if not seller_profile:
        return jsonify({
            'error': 'Seller not found'
        }), 404
    
    # Check if the associated user is actually a seller
    user = User.query.get(seller_id)
    if not user or user.role != 'seller':
        return jsonify({
            'error': 'User is not a seller'
        }), 400
    # Calculate meeting quota for the seller
    meeting_quota = calculate_seller_meeting_quota(seller_id, seller_profile)
    
    # Initialize with the original microsite URL (or empty string if None)
    seller_full_microsite_url = seller_profile.microsite_url or ''

    # Check if we need to add protocol prefix
    if (seller_profile.microsite_url and 
        not seller_profile.microsite_url.startswith(('http://', 'https://'))):
        
        public_site_url = os.getenv('PUBLIC_SITE_URL', '')
        
        # Only modify if PUBLIC_SITE_URL is available
        if public_site_url:
            # Handle URL concatenation properly
            if public_site_url.endswith('/') and seller_profile.microsite_url.startswith('/'):
                seller_full_microsite_url = public_site_url + seller_profile.microsite_url[1:]
            elif not public_site_url.endswith('/') and not seller_profile.microsite_url.startswith('/'):
                seller_full_microsite_url = public_site_url + '/' + seller_profile.microsite_url
            else:
                seller_full_microsite_url = public_site_url + seller_profile.microsite_url
        # If no PUBLIC_SITE_URL, seller_full_microsite_url keeps the original microsite_url
    # Get seller data and add meeting quota information
    seller_data = seller_profile.to_dict()
    seller_data["full_microsite_url"] = seller_full_microsite_url
    seller_data.update(meeting_quota)
    
    return jsonify({
        'seller': seller_data
    }), 200

@seller.route('/profile', methods=['GET'])
@jwt_required()
@seller_required
def get_own_profile():
    """Get the current seller's profile"""
    user_id = get_jwt_identity()
    # Convert to int if it's a string
    if isinstance(user_id, str):
        try:
            user_id = int(user_id)
        except ValueError:
            return jsonify({'error': 'Invalid user ID'}), 400
    
    # Find the seller profile
    seller_profile = SellerProfile.query.filter_by(user_id=user_id).first()

    if not seller_profile:
        # Auto-create profile for new sellers with data from users table
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        

        # Create new profile with pre-populated data from users table
        seller_profile = SellerProfile(
            user_id=user_id,
            business_name=user.business_name or '',  # Pre-populate from users table
            description=user.business_description or '',  # Pre-populate from users table
            contact_email=user.email,  # Pre-populate from users table
            status='active',
            is_verified=False
        )
        try:
            db.session.add(seller_profile)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return jsonify({
                'error': 'Failed to create seller profile',
                'message': str(e)
            }), 500
    # Generate and save a microsite URL for the new profile
    microsite_url = _generate_microsite_url_for_profile(seller_profile)
    seller_profile.microsite_url = microsite_url

    # Calculate meeting quota for the seller
    meeting_quota = calculate_seller_meeting_quota(user_id, seller_profile)
    
    # Initialize with the original microsite URL (or empty string if None)
    seller_full_microsite_url = seller_profile.microsite_url or ''
    
    # Check if we need to add protocol prefix
    if (seller_profile.microsite_url and 
        not seller_profile.microsite_url.startswith(('http://', 'https://'))):
        
        public_site_url = os.getenv('PUBLIC_SITE_URL', '')
        
        # Only modify if PUBLIC_SITE_URL is available
        if public_site_url:
            # Handle URL concatenation properly
            if public_site_url.endswith('/') and seller_profile.microsite_url.startswith('/'):
                seller_full_microsite_url = public_site_url + seller_profile.microsite_url[1:]
            elif not public_site_url.endswith('/') and not seller_profile.microsite_url.startswith('/'):
                seller_full_microsite_url = public_site_url + '/' + seller_profile.microsite_url
            else:
                seller_full_microsite_url = public_site_url + seller_profile.microsite_url
        # If no PUBLIC_SITE_URL, seller_full_microsite_url keeps the original microsite_url
    
    # Get seller data and add meeting quota information
    seller_data = seller_profile.to_dict()
    seller_data["full_microsite_url"] = seller_full_microsite_url
    seller_data.update(meeting_quota)
    
    return jsonify({
        'seller': seller_data
    }), 200

# helper function for creating a URL
def _generate_microsite_url_for_profile(seller_profile):
    """Helper function to generate a microsite URL for a seller profile
    
    Args:
        seller_profile: The SellerProfile object
        
    Returns:
        str: The generated microsite URL
    """
    import uuid
    from urllib.parse import quote
    import os
    
    
    # Combine to create a unique, readable URL
   # base_url = os.getenv('PUBLIC_SITE_URL', 'https://splash25.com')
    microsite_url = f"/seller/{seller_profile.user_id}"
        
    return microsite_url

@seller.route('/profile/generate-microsite', methods=['POST'])
@jwt_required()
@seller_required
def generate_microsite_url():
    """Generate and save a microsite URL for the current seller's profile"""
    user_id = get_jwt_identity()
    # Convert to int if it's a string
    if isinstance(user_id, str):
        try:
            user_id = int(user_id)
        except ValueError:
            return jsonify({'error': 'Invalid user ID'}), 400
    
    # Get seller profile
    seller_profile = SellerProfile.query.filter_by(user_id=user_id).first()
    if not seller_profile:
        return jsonify({'error': 'Seller profile not found'}), 404
    
    # Generate microsite URL using helper function
    microsite_url = _generate_microsite_url_for_profile(seller_profile)
    
    # Save to profile
    seller_profile.microsite_url = microsite_url
    
    try:
        db.session.commit()
        return jsonify({
            'message': 'Microsite URL generated successfully',
            'seller': seller_profile.to_dict()
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'error': 'Failed to generate microsite URL',
            'message': str(e)
        }), 500


@seller.route('/profile/images', methods=['POST'])
@jwt_required()
@seller_required
def upload_seller_images():
    """Upload multiple business images for the current seller"""
    import os
    import requests
    import uuid
    from datetime import datetime
    from werkzeug.utils import secure_filename
    import base64
    
    user_id = get_jwt_identity()
    # Convert to int if it's a string
    if isinstance(user_id, str):
        try:
            user_id = int(user_id)
        except ValueError:
            return jsonify({'error': 'Invalid user ID'}), 400
    
    # Get seller profile
    seller_profile = SellerProfile.query.filter_by(user_id=user_id).first()
    if not seller_profile:
        return jsonify({'error': 'Seller profile not found'}), 404
    
    # Check if files are present in request
    if 'files' not in request.files:
        return jsonify({'error': 'No files provided'}), 400
    
    files = request.files.getlist('files')
    if not files or len(files) == 0:
        return jsonify({'error': 'No files selected'}), 400
    
    # Validate file count (max 5)
    if len(files) > 5:
        return jsonify({'error': 'Maximum 5 images allowed'}), 400
    
    # Get external storage credentials from environment
    storage_url = os.getenv('EXTERNAL_STORAGE_URL')+"index.php"
    storage_user = os.getenv('EXTERNAL_STORAGE_USER')
    storage_password = os.getenv('EXTERNAL_STORAGE_PASSWORD')
    ocs_url = os.getenv("EXTERNAL_STORAGE_URL")+'ocs/v2.php/apps/files_sharing/api/v1/shares'
    ocs_headers = {'OCS-APIRequest': 'true',"Accept": "application/json"}
    ocs_auth = (storage_user, storage_password)  # Use app password or user/pass
    
    if not all([storage_url, storage_user, storage_password]):
        return jsonify({'error': 'External storage configuration missing'}), 500
    
    nc = Nextcloud(nextcloud_url=storage_url, nc_auth_user=storage_user, nc_auth_pass=storage_password)
    
    # Validate files
    allowed_extensions = {'jpg', 'jpeg', 'png'}
    max_size = 2 * 1024 * 1024  # 2MB
    errors = []
    valid_files = []
    
    for file in files:
        if file.filename == '':
            continue
            
        # Check file extension
        file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
        if file_ext not in allowed_extensions:
            errors.append(f"File '{file.filename}' has invalid format. Only JPEG and PNG are allowed.")
            continue
        
        # Check file size
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(0)  # Reset to beginning
        
        if file_size > max_size:
            errors.append(f"File '{file.filename}' exceeds 2MB limit.")
            continue
            
        valid_files.append(file)
    
    if errors:
        return jsonify({'error': 'File validation failed', 'details': errors}), 400
    
    if not valid_files:
        return jsonify({'error': 'No valid files to upload'}), 400
    
    # If total images would exceed 5, replace all existing images
    existing_images = seller_profile.business_images or []
    if len(existing_images) + len(valid_files) > 5:
        # Replace all existing images
        seller_profile.business_images = []
        db.session.commit()
    
    # Upload files to external storage
    uploaded_images = []
    upload_errors = []
    
    # Create seller directory path
    seller_dir = f"seller_{user_id}"
    #remote_dir_path = f"{storage_url}/{seller_dir}"
    remote_dir_path = f"/Photos/{seller_dir}"
    try:
        nc.files.listdir(remote_dir_path)
        logging.debug(f"Found remote path:: {remote_dir_path}")
    except NextcloudException as e:
        if e.status_code != 404:
            raise e
        else:
            try:
                logging.info(f"Could not locate remote directory::: {remote_dir_path}::: Proceeding to create")
                nc.files.mkdir(remote_dir_path)
                logging.debug(f"Created remote directory {remote_dir_path} successfully")
                logging.debug("Now setting sharing permissions...")
                seller_dir_sharing_data = {
                    'path': remote_dir_path,         # Folder you created
                    'shareType': 3,                  # Public link
                    'permissions': 1                 # Read-only
                }
                response = requests.post(ocs_url, headers=ocs_headers, data=seller_dir_sharing_data, auth=ocs_auth)

                if response.status_code == 200:
                    logging.info(f"Response Text is:: {response}")
                    share_info = response.json()
                    link = share_info['ocs']['data']['url']
                    logging.debug(f"Public Share URL: {link}")
                else:
                    logging.debug("Failed to create share:", response.text)
            except Exception as e:
                logging.debug(f"Exception while creating seller directory:{str(e)}")
                return jsonify({"Exception": f"Failed to create seller directory -- {remote_dir_path} - the error is ::::{str(e)}"}), 500

    for file in valid_files:
        try:
            # Generate unique filename
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            unique_id = str(uuid.uuid4())[:8]
            secure_name = secure_filename(file.filename)
            filename = f"{timestamp}{unique_id}{secure_name}"
            
            # Prepare file data for upload
            file_data = file.read()
            file.seek(0)  # Reset for potential retry
            
            # Create basic auth header
            auth_string = f"{storage_user}:{storage_password}"
            auth_bytes = auth_string.encode('ascii')
            auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
            
            # Upload to external storage
            upload_url = f"{remote_dir_path}/{filename}"
            """
            headers = {
                'Authorization': f'Basic {auth_b64}',
                'Content-Type': file.content_type or 'application/octet-stream'
            }
            """
            # Upload file
            try:
                #with open(file, 'rb') as f:
                    #nc.files.upload_stream(upload_url, f)
                buf = BytesIO(file_data)  
                buf.seek(0)
                logging.info(f"Uploading file :::: {upload_url}")
                uploaded_file = nc.files.upload_stream(upload_url, buf)
                logging.info(f"The uploaded file data is::: {(uploaded_file.name)}")
                # Now give it a publicly available link 
                seller_file_sharing_data = {
                    'path': upload_url,              # Uploaded file
                    'shareType': 3,                  # Public link
                    'permissions': 1                 # Read-only
                }
                response = requests.post(ocs_url, headers=ocs_headers, data=seller_file_sharing_data, auth=ocs_auth)
                file_public_url=""
                if response.status_code == 200:
                    result = response.json()
                    if result["ocs"]["meta"]["status"] == "ok":
                        file_public_url = result["ocs"]["data"]["url"]
                        logging.debug(f"Public share URL: {file_public_url}")
                    else:
                        logging.error(f"Share API error: {result['ocs']['meta']['message']}")
                else:
                    print("HTTP error:", response.status_code, response.text)
                image_record = {
                    'id': str(uuid.uuid4()),
                    'filename': file.filename,
                    'url': file_public_url+"/download",
                    'size': len(file_data),
                    'uploaded_at': datetime.utcnow().isoformat(),
                    'mime_type': file.content_type or 'image/jpeg'
                }
                uploaded_images.append(image_record)

            except Exception as e:
                logging.debug(f"Exception while uploading file:{e}")
                return jsonify({'Exception': f'Failed to upload file {upload_url}:::{str(e)}'}), 500

            
        except Exception as e:
            upload_errors.append(f"Error uploading '{file.filename}': {str(e)}")
    
    if not uploaded_images and upload_errors:
        return jsonify({'error': 'All uploads failed', 'details': upload_errors}), 500
    
    # Update seller profile with new images
    current_images = seller_profile.business_images or []
    updated_images = current_images + uploaded_images
    seller_profile.business_images = updated_images
    
    try:
        db.session.commit()
        
        response_data = {
            'message': 'Images uploaded successfully',
            'uploaded_images': uploaded_images,
            'total_images': len(updated_images),
            'replaced_existing': len(existing_images) + len(valid_files) > 5
        }
        
        if upload_errors:
            response_data['warnings'] = upload_errors
            
        return jsonify(response_data), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to save image records', 'message': str(e)}), 500

@seller.route('/profile', methods=['PUT'])
@jwt_required()
@seller_required
def update_profile():
    """Update the current seller's profile"""
    user_id = get_jwt_identity()
    # Convert to int if it's a string
    if isinstance(user_id, str):
        try:
            user_id = int(user_id)
        except ValueError:
            return jsonify({'error': 'Invalid user ID'}), 400
    
    data = request.get_json()
    
    # Validate business name if provided
    if 'business_name' in data:
        business_name = data['business_name'].strip() if data['business_name'] else ''
        if len(business_name) < 5:
            return jsonify({
                'error': 'Business name must be at least 5 characters long'
            }), 400
        data['business_name'] = business_name
    
    # Find the seller profile
    seller_profile = SellerProfile.query.filter_by(user_id=user_id).first()
    
    if not seller_profile:
        # Create a new profile if it doesn't exist
        seller_profile = SellerProfile(user_id=user_id)
        db.session.add(seller_profile)
    
    # Update fields
    updatable_fields = [
        'business_name', 'description', 'seller_type', 'target_market',
        'logo_url', 'website', 'contact_email', 'contact_phone', 'address'
    ]
    
    for field in updatable_fields:
        if field in data:
            setattr(seller_profile, field, data[field])
    
    try:
        db.session.commit()
        return jsonify({
            'message': 'Profile updated successfully',
            'seller': seller_profile.to_dict()
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'error': 'Failed to update profile',
            'message': str(e)
        }), 500

@seller.route('/types', methods=['GET'])
@jwt_required()
def get_seller_types():
    """Get all unique seller types"""
    seller_types = db.session.query(SellerProfile.seller_type).distinct().all()
    # Filter out None values and extract from tuples
    types = [t[0] for t in seller_types if t[0]]
    
    return jsonify({
        'seller_types': types
    }), 200

@seller.route('/target-markets', methods=['GET'])
@jwt_required()
def get_target_markets():
    """Get all unique target markets"""
    target_markets = db.session.query(SellerProfile.target_market).distinct().all()
    # Filter out None values and extract from tuples
    markets = [m[0] for m in target_markets if m[0]]
    
    return jsonify({
        'target_markets': markets
    }), 200

@seller.route('/<int:seller_id>/verify', methods=['PUT'])
@jwt_required()
@admin_required
def verify_seller(seller_id):
    """Verify a seller (admin only)"""
    # Find the seller profile
    seller_profile = SellerProfile.query.filter_by(user_id=seller_id).first()
    
    if not seller_profile:
        return jsonify({
            'error': 'Seller profile not found'
        }), 404
    
    # Check if the associated user is actually a seller
    user = User.query.get(seller_id)
    if not user or user.role != 'seller':
        return jsonify({
            'error': 'User is not a seller'
        }), 400
    
    # Update verification status
    seller_profile.is_verified = True
    db.session.commit()
    
    return jsonify({
        'message': 'Seller verified successfully',
        'seller': seller_profile.to_dict()
    }), 200

# Enhanced Endpoints for New Models

@seller.route('/attendees', methods=['GET'])
@jwt_required()
@seller_required
def get_attendees():
    """Get all attendees for the current seller"""
    user_id = get_jwt_identity()
    # Convert to int if it's a string
    if isinstance(user_id, str):
        try:
            user_id = int(user_id)
        except ValueError:
            return jsonify({'error': 'Invalid user ID'}), 400
    
    # Get seller profile
    seller_profile = SellerProfile.query.filter_by(user_id=user_id).first()
    if not seller_profile:
        return jsonify({'error': 'Seller profile not found'}), 404
    
    # Get attendees ordered by attendee_number
    attendees = SellerAttendee.query.filter_by(seller_profile_id=seller_profile.id).order_by(SellerAttendee.attendee_number).all()
    
    return jsonify({
        'attendees': [attendee.to_dict() for attendee in attendees]
    }), 200

@seller.route('/attendees', methods=['POST'])
@jwt_required()
@seller_required
def create_attendee():
    """Create a new attendee for the current seller"""
    user_id = get_jwt_identity()
    # Convert to int if it's a string
    if isinstance(user_id, str):
        try:
            user_id = int(user_id)
        except ValueError:
            return jsonify({'error': 'Invalid user ID'}), 400
    
    # Get seller profile
    seller_profile = SellerProfile.query.filter_by(user_id=user_id).first()
    if not seller_profile:
        return jsonify({'error': 'Seller profile not found'}), 404
    
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['name', 'designation', 'email', 'mobile']
    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    # Validate email format
    import re
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, data['email']):
        return jsonify({'error': 'Invalid email format'}), 400
    
    # Check if email already exists for this seller
    existing_attendee = SellerAttendee.query.filter_by(
        seller_profile_id=seller_profile.id,
        email=data['email']
    ).first()
    if existing_attendee:
        return jsonify({'error': 'Email already exists for another attendee'}), 400
    
    # Get next attendee number
    max_attendee = SellerAttendee.query.filter_by(seller_profile_id=seller_profile.id).order_by(SellerAttendee.attendee_number.desc()).first()
    next_number = (max_attendee.attendee_number + 1) if max_attendee else 1
    
    # Handle primary contact logic
    is_primary = data.get('is_primary_contact', False)
    if is_primary:
        # Remove primary contact status from other attendees
        SellerAttendee.query.filter_by(seller_profile_id=seller_profile.id, is_primary_contact=True).update({'is_primary_contact': False})
    
    try:
        # Create new attendee
        new_attendee = SellerAttendee(
            seller_profile_id=seller_profile.id,
            attendee_number=next_number,
            name=data['name'].strip(),
            designation=data['designation'].strip(),
            email=data['email'].strip().lower(),
            mobile=data['mobile'].strip(),
            is_primary_contact=is_primary
        )
        
        db.session.add(new_attendee)
        db.session.commit()
        
        return jsonify({
            'message': 'Attendee created successfully',
            'attendee': new_attendee.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'error': 'Failed to create attendee',
            'message': str(e)
        }), 500

@seller.route('/attendees/<int:attendee_id>', methods=['PUT'])
@jwt_required()
@seller_required
def update_attendee(attendee_id):
    """Update an existing attendee"""
    user_id = get_jwt_identity()
    # Convert to int if it's a string
    if isinstance(user_id, str):
        try:
            user_id = int(user_id)
        except ValueError:
            return jsonify({'error': 'Invalid user ID'}), 400
    
    # Get seller profile
    seller_profile = SellerProfile.query.filter_by(user_id=user_id).first()
    if not seller_profile:
        return jsonify({'error': 'Seller profile not found'}), 404
    
    # Find the attendee and verify ownership
    attendee = SellerAttendee.query.filter_by(
        id=attendee_id,
        seller_profile_id=seller_profile.id
    ).first()
    
    if not attendee:
        return jsonify({'error': 'Attendee not found or access denied'}), 404
    
    data = request.get_json()
    
    # Validate email format if provided
    if 'email' in data and data['email']:
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, data['email']):
            return jsonify({'error': 'Invalid email format'}), 400
        
        # Check if email already exists for another attendee
        existing_attendee = SellerAttendee.query.filter_by(
            seller_profile_id=seller_profile.id,
            email=data['email']
        ).filter(SellerAttendee.id != attendee_id).first()
        if existing_attendee:
            return jsonify({'error': 'Email already exists for another attendee'}), 400
    
    # Handle primary contact logic
    if 'is_primary_contact' in data and data['is_primary_contact']:
        # Remove primary contact status from other attendees
        SellerAttendee.query.filter_by(seller_profile_id=seller_profile.id, is_primary_contact=True).update({'is_primary_contact': False})
    
    try:
        # Update fields
        updatable_fields = ['name', 'designation', 'email', 'mobile', 'is_primary_contact']
        for field in updatable_fields:
            if field in data:
                if field in ['name', 'designation', 'email', 'mobile']:
                    setattr(attendee, field, data[field].strip() if data[field] else '')
                    if field == 'email':
                        attendee.email = attendee.email.lower()
                else:
                    setattr(attendee, field, data[field])
        
        db.session.commit()
        
        return jsonify({
            'message': 'Attendee updated successfully',
            'attendee': attendee.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'error': 'Failed to update attendee',
            'message': str(e)
        }), 500

@seller.route('/attendees/<int:attendee_id>', methods=['DELETE'])
@jwt_required()
@seller_required
def delete_attendee(attendee_id):
    """Delete an attendee"""
    user_id = get_jwt_identity()
    # Convert to int if it's a string
    if isinstance(user_id, str):
        try:
            user_id = int(user_id)
        except ValueError:
            return jsonify({'error': 'Invalid user ID'}), 400
    
    # Get seller profile
    seller_profile = SellerProfile.query.filter_by(user_id=user_id).first()
    if not seller_profile:
        return jsonify({'error': 'Seller profile not found'}), 404
    
    # Find the attendee and verify ownership
    attendee = SellerAttendee.query.filter_by(
        id=attendee_id,
        seller_profile_id=seller_profile.id
    ).first()
    
    if not attendee:
        return jsonify({'error': 'Attendee not found or access denied'}), 404
    
    # Check if the attendee being deleted is marked as primary contact
    if attendee.is_primary_contact:
        return jsonify({'error': 'Cannot delete primary contact. Please assign another attendee as primary contact first.'}), 400
    
    # Check if this is the last attendee (count = 1)
    total_attendees = SellerAttendee.query.filter_by(seller_profile_id=seller_profile.id).count()
    if total_attendees <= 1:
        return jsonify({'error': 'Cannot delete the last attendee. At least one attendee must remain.'}), 400
    
    try:
        db.session.delete(attendee)
        db.session.commit()
        
        return jsonify({
            'message': 'Attendee deleted successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'error': 'Failed to delete attendee',
            'message': str(e)
        }), 500

@seller.route('/property-types', methods=['GET'])
@jwt_required()
def get_property_types():
    """Get all property types"""
    try:
        property_types = PropertyType.query.all()
        return jsonify({
            'property_types': [pt.to_dict() for pt in property_types]
        }), 200
    except Exception as e:
        return jsonify({
            'error': f'Failed to fetch property types: {str(e)}'
        }), 500

@seller.route('/interests', methods=['GET'])
@jwt_required()
def get_interests():
    """Get all interests"""
    try:
        interests = Interest.query.all()
        return jsonify({
            'interests': [interest.to_dict() for interest in interests]
        }), 200
    except Exception as e:
        return jsonify({
            'error': f'Failed to fetch interests: {str(e)}'
        }), 500

@seller.route('/financial-info', methods=['GET'])
@jwt_required()
@seller_required
def get_financial_info():
    """Get financial information for the current seller"""
    user_id = get_jwt_identity()
    # Convert to int if it's a string
    if isinstance(user_id, str):
        try:
            user_id = int(user_id)
        except ValueError:
            return jsonify({'error': 'Invalid user ID'}), 400
    
    # Get seller profile
    seller_profile = SellerProfile.query.filter_by(user_id=user_id).first()
    if not seller_profile:
        return jsonify({'error': 'Seller profile not found'}), 404
    
    # Get financial info
    financial_info = SellerFinancialInfo.query.filter_by(seller_profile_id=seller_profile.id).first()
    
    if not financial_info:
        # Return default values if no financial info exists
        return jsonify({
            'financial_info': {
                'actual_additional_seller_passes': 0,
                'deposit_paid': False,
                'total_amt_due': None,
                'total_amt_paid': None,
                'subscription_uptodate': False
            }
        }), 200
    
    return jsonify({
        'financial_info': financial_info.to_dict()
    }), 200
    

@seller.route('/public/<path:microsite_path>', methods=['GET'])
def get_seller_by_microsite(microsite_path):
    """Get a seller profile by its microsite URL path (public, no auth required)"""
    try:
        # Construct the full microsite URL
        #url = "http://splash25.org/seller/pqrs"
       # parsed_url = urlparse(url)
        #path = parsed_url.path
       # base_url = os.getenv('PUBLIC_SITE_URL', 'https://splash25.com')
        full_microsite_url = f"/seller/{microsite_path}"
        logging.info(f"microsite path: {microsite_path}, full_microsite_url: {full_microsite_url}")
        
        # Find the seller profile by microsite URL
        seller_profile = SellerProfile.query.filter_by(microsite_url=full_microsite_url).first()
        
        if not seller_profile:
            return jsonify({
                'error': 'Seller profile not found'
            }), 404
        
        # Check if the associated user is actually a seller
        user = User.query.get(seller_profile.user_id)
        if not user or user.role != 'seller':
            return jsonify({
                'error': 'User is not a seller'
            }), 400
        
        # Return only the specified subset of fields - now all fields exist in the database
        seller_data = {
            'user_id': seller_profile.user_id,
            'company_name': seller_profile.company_name,
            'business_name': seller_profile.business_name,
            'description': seller_profile.description,
            'seller_type': seller_profile.seller_type,
            'target_market': seller_profile.target_market,
            'logo_url': seller_profile.logo_url,
            'website': seller_profile.website,
            'instagram': seller_profile.instagram,
            'business_images': seller_profile.business_images or [],
            'owner_salutation': seller_profile.salutation,
            'owner_first_name': seller_profile.first_name,
            'owner_last_name': seller_profile.last_name,
            'owner_designation': seller_profile.designation,
            'start_year': seller_profile.start_year
        }
        
        return jsonify({
            'seller': seller_data
        }), 200
    except Exception as e:
        return jsonify({
            'error': f'Failed to fetch seller profile: {str(e)}'
        }), 500


@seller.route('/profile/logo', methods=['POST'])
@jwt_required()
@seller_required
def upload_seller_logo():
    """Upload business logo for the current seller"""
    import os
    import requests
    import uuid
    from datetime import datetime
    from werkzeug.utils import secure_filename
    import base64
    import logging
    
    user_id = get_jwt_identity()
    # Convert to int if it's a string
    if isinstance(user_id, str):
        try:
            user_id = int(user_id)
        except ValueError:
            return jsonify({'error': 'Invalid user ID'}), 400
    
    # Get seller profile
    seller_profile = SellerProfile.query.filter_by(user_id=user_id).first()
    if not seller_profile:
        return jsonify({'error': 'Seller profile not found'}), 404
    
    # Check if file is present in request
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if not file or file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Validate file
    allowed_extensions = {'jpg', 'jpeg', 'png', 'ico'}
    file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
    
    if file_ext not in allowed_extensions:
        return jsonify({'error': 'Invalid file type. Only JPEG, PNG, and ICO files are allowed'}), 400
    
    # Check file size (1MB limit)
    file.seek(0, 2)  # Seek to end
    file_size = file.tell()
    file.seek(0)  # Reset to beginning
    
    if file_size > 1 * 1024 * 1024:  # 1MB
        return jsonify({'error': 'File size exceeds 1MB limit'}), 400
    
    # Get external storage credentials from environment
    storage_url = os.getenv('EXTERNAL_STORAGE_URL')+"index.php"
    storage_user = os.getenv('EXTERNAL_STORAGE_USER')
    storage_password = os.getenv('EXTERNAL_STORAGE_PASSWORD')
    ocs_url = os.getenv("EXTERNAL_STORAGE_URL")+'ocs/v2.php/apps/files_sharing/api/v1/shares'
    ocs_headers = {'OCS-APIRequest': 'true',"Accept": "application/json"}
    ocs_auth = (storage_user, storage_password)  # Use app password or user/pass
    
    if not all([storage_url, storage_user, storage_password]):
        return jsonify({'error': 'External storage configuration missing'}), 500
    
    nc = Nextcloud(nextcloud_url=storage_url, nc_auth_user=storage_user, nc_auth_pass=storage_password)
    
    try:
        seller_base_dir_available = False
        seller_logo_dir_available = False
        # Create seller directory path if it doesn't exist
        seller_dir = f"seller_{user_id}"
        remote_dir_path = f"/Photos/{seller_dir}"
        remote_logo_dir_path = f"{remote_dir_path}/logo"
        try:
            nc.files.listdir(remote_dir_path)
            logging.debug(f"Found remote path:: {remote_dir_path}")
            seller_base_dir_available = True
        except NextcloudException as e:
            if e.status_code != 404:
                raise e
            else:
                try:
                    logging.info(f"Could not locate remote directory::: {remote_dir_path}::: Proceeding to create")
                    nc.files.mkdir(remote_dir_path)
                    logging.debug(f"Created remote directory {remote_dir_path} successfully")
                    logging.debug("Now setting sharing permissions...")
                    seller_dir_sharing_data = {
                        'path': remote_dir_path,         # Folder you created
                        'shareType': 3,                  # Public link
                        'permissions': 1                 # Read-only
                    }
                    response = requests.post(ocs_url, headers=ocs_headers, data=seller_dir_sharing_data, auth=ocs_auth)

                    if response.status_code == 200:
                        logging.info(f"Response Text is:: {response}")
                        share_info = response.json()
                        link = share_info['ocs']['data']['url']
                        logging.debug(f"Public Share URL: {link}")
                        seller_base_dir_available = True
                    else:
                        seller_base_dir_available = False
                        logging.debug("Failed to create share:", response.text)
                except Exception as e:
                    logging.debug(f"Exception while creating seller directory:{str(e)}")
                    return jsonify({"Exception": f"Failed to create base seller directory -- {remote_dir_path} - the error is ::::{str(e)}"}), 500
        
        # Now check if logo directory exists and if not, create it
        if seller_base_dir_available: 
            try:
                nc.files.listdir(remote_logo_dir_path)
                logging.debug(f"Found remote logo dir path:: {remote_logo_dir_path}")
                seller_logo_dir_available = True
            except NextcloudException as e:
                if e.status_code != 404:
                    raise e
                else:
                    try:
                        logging.info(f"Could not locate remote logo directory::: {remote_logo_dir_path}::: Proceeding to create")
                        nc.files.mkdir(remote_logo_dir_path)
                        logging.debug(f"Created remote directory {remote_logo_dir_path} successfully")
                        logging.debug("Now setting sharing permissions...")
                        seller_dir_sharing_data = {
                            'path': remote_dir_path,         # Folder you created
                            'shareType': 3,                  # Public link
                            'permissions': 1                 # Read-only
                        }
                        response = requests.post(ocs_url, headers=ocs_headers, data=seller_dir_sharing_data, auth=ocs_auth)

                        if response.status_code == 200:
                            logging.info(f"Response Text is:: {response}")
                            share_info = response.json()
                            link = share_info['ocs']['data']['url']
                            logging.debug(f"Public Share URL: {link}")
                            seller_logo_dir_available = True
                        else:
                            seller_logo_dir_available = False
                            logging.debug("Failed to create share:", response.text)
                    except Exception as e:
                        logging.debug(f"Exception while creating seller logo directory:{str(e)}")
                        return jsonify({"Exception": f"Failed to create seller logo directory -- {remote_logo_dir_path} - the error is ::::{str(e)}"}), 500

        # Generate unique filename for logo
        secure_name = secure_filename(file.filename)
        filename = f"logo_{user_id}_{secure_name}"
        
        # Prepare file data for upload
        file_data = file.read()
        file.seek(0)  # Reset for potential retry
        
        # Upload to external storage
        upload_url = f"{remote_logo_dir_path}/{filename}"
        
        try:
            buf = BytesIO(file_data)  
            buf.seek(0)
            logging.info(f"Uploading logo file :::: {upload_url}")
            uploaded_file = nc.files.upload_stream(upload_url, buf)
            logging.info(f"The uploaded file data is::: {(uploaded_file.name)}")
            
            # Now give it a publicly available link 
            seller_file_sharing_data = {
                'path': upload_url,              # Uploaded file
                'shareType': 3,                  # Public link
                'permissions': 1                 # Read-only
            }
            response = requests.post(ocs_url, headers=ocs_headers, data=seller_file_sharing_data, auth=ocs_auth)
            file_public_url = ""
            
            if response.status_code == 200:
                result = response.json()
                if result["ocs"]["meta"]["status"] == "ok":
                    file_public_url = result["ocs"]["data"]["url"]
                    logging.debug(f"Public share URL: {file_public_url}")
                else:
                    logging.error(f"Share API error: {result['ocs']['meta']['message']}")
                    return jsonify({'error': 'Failed to create public share for logo'}), 500
            else:
                logging.error(f"HTTP error: {response.status_code} {response.text}")
                return jsonify({'error': 'Failed to create public share for logo'}), 500
            
            # Update seller profile with new logo URL
            seller_profile.logo_url = file_public_url + "/download"
            
            try:
                db.session.commit()
                return jsonify({
                    'message': 'Logo uploaded successfully',
                    'seller': seller_profile.to_dict()
                }), 200
            except Exception as e:
                db.session.rollback()
                return jsonify({'error': f'Failed to update profile with logo URL: {str(e)}'}), 500
                
        except Exception as e:
            logging.debug(f"Exception while uploading logo file:{e}")
            return jsonify({'error': f'Failed to upload logo file {upload_url}:::{str(e)}'}), 500
            
    except Exception as e:
        return jsonify({'error': f'Failed to upload logo: {str(e)}'}), 500
