from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
import logging
from nc_py_api import Nextcloud, NextcloudException
from io import BytesIO
from PIL import Image
import base64
import requests
from urllib.parse import urlparse
from werkzeug.utils import secure_filename
import os
import logging
from ..utils.auth import buyer_required
from ..models import db, User, TravelPlan, Transportation, Accommodation, GroundTransportation, Meeting, MeetingStatus, UserRole, TimeSlot, SystemSetting, BuyerProfile, BuyerCategory, PropertyType, Interest, StallType, Stall, BuyerBankDetails
# Import helper functions from buyer_utils
from ..utils.buyer_utils import (
    get_outbound_departure_datetime,
    get_outbound_arrival_datetime, 
    get_return_departure_datetime,
    get_return_arrival_datetime,
    validate_user_id,
    validate_buyer_exists,
    validate_travel_plan_access,
    get_nextcloud_connection,
    create_buyer_directories,
    get_buyer_profile_images,
    get_first_buyer_profile_image,
    convert_image_to_base64_data_url,
    validate_image_file,
    generate_buyer_image_filename,
    upload_buyer_image_to_nextcloud,
    create_buyer_image_response,
    log_buyer_image_response
)
from ..utils.payment_utils import get_bank_details_from_ifsc, validate_ifsc_format

buyer = Blueprint('buyer', __name__, url_prefix='/api/buyer')

@buyer.route('/dashboard', methods=['GET'])
@buyer_required
def dashboard():
    """
    Endpoint for buyer dashboard data
    """
    user_id = get_jwt_identity()
    
    # Convert to int if it's a string
    if isinstance(user_id, str):
        try:
            user_id = int(user_id)
        except ValueError:
            return jsonify({'error': 'Invalid user ID'}), 400
    
    # Get featured destinations from verified sellers
    try:
        from ..models.models import SellerProfile
        featured_sellers = SellerProfile.query.join(User).filter(
            User.role == UserRole.SELLER.value,
            SellerProfile.is_verified == True,
            SellerProfile.status == 'active'
        ).limit(3).all()
        
        featured_destinations = []
        for seller in featured_sellers:
            featured_destinations.append({
                'id': seller.id,
                'name': seller.business_name or 'Kerala Experience',
                'description': seller.description or 'Experience authentic Kerala hospitality',
                'image_url': seller.logo_url or '/images/destinations/default.jpg'
            })
        
        # Fallback if no sellers found
        if not featured_destinations:
            featured_destinations = [
                {
                    'id': 1,
                    'name': 'Discover Kerala',
                    'description': 'Connect with local businesses and experiences',
                    'image_url': '/images/destinations/kerala-default.jpg'
                }
            ]
    except Exception as e:
        # Fallback in case of database error
        featured_destinations = []
    
    # Get upcoming events from buyer's meetings
    try:
        upcoming_meetings = Meeting.query.filter_by(
            buyer_id=user_id,
            status=MeetingStatus.ACCEPTED
        ).join(TimeSlot).filter(
            TimeSlot.start_time > datetime.now()
        ).order_by(TimeSlot.start_time).limit(2).all()
        
        upcoming_events = []
        for meeting in upcoming_meetings:
            seller_name = 'Business Partner'
            if meeting.seller and meeting.seller.seller_profile:
                seller_name = meeting.seller.seller_profile.business_name
            elif meeting.seller:
                seller_name = meeting.seller.business_name or meeting.seller.username
            
            upcoming_events.append({
                'id': meeting.id,
                'name': f'Meeting with {seller_name}',
                'date': meeting.time_slot.start_time.strftime('%Y-%m-%d'),
                'location': 'Event Venue'
            })
        
        # If no upcoming meetings, show general event info
        if not upcoming_events:
            # Check system settings for event info
            event_start = SystemSetting.query.filter_by(key='event_start_date').first()
            venue_name = SystemSetting.query.filter_by(key='venue_name').first()
            
            if event_start and venue_name:
                upcoming_events.append({
                    'id': 1,
                    'name': 'Splash25 Event',
                    'date': event_start.value,
                    'location': venue_name.value
                })
    except Exception as e:
        # Fallback in case of database error
        upcoming_events = []
    
    return jsonify({
        'message': 'Welcome to the Buyer Dashboard',
        'featured_destinations': featured_destinations,
        'upcoming_events': upcoming_events
    }), 200

@buyer.route('/profile', methods=['GET'])
@buyer_required
def get_profile():
    """
    Endpoint to get buyer profile information
    """
    from ..utils.meeting_utils import calculate_buyer_meeting_quota
    
    user_id = get_jwt_identity()
    
    # Convert to int if it's a string
    if isinstance(user_id, str):
        try:
            user_id = int(user_id)
        except ValueError:
            return jsonify({'error': 'Invalid user ID'}), 400
    
    # Get buyer profile
    buyer_profile = BuyerProfile.query.filter_by(user_id=user_id).first()
    
    if not buyer_profile:
        return jsonify({
            'error': 'Buyer profile not found'
        }), 404
    
    # Get the profile as a dictionary
    profile_dict = buyer_profile.to_dict()
    
    # Get buyer profile image using optimized helper function
    try:
        # Use optimized direct image lookup if profile_image path exists
        if buyer_profile.profile_image:
            file_info = get_first_buyer_profile_image(user_id, buyer_profile.profile_image)
            if file_info:
                # Extract filename from the stored path
                filename = buyer_profile.profile_image.split('/')[-1]
                
                # Convert image to base64 data URL
                image_data = convert_image_to_base64_data_url(user_id, filename)
                profile_dict['profile_image'] = image_data['image_data_url']
            else:
                # File not found in Nextcloud, but path exists in DB
                logging.warning(f"Profile image not found in Nextcloud for buyer {user_id}: {buyer_profile.profile_image}")
                profile_dict['profile_image'] = None
        else:
            # No profile image path stored
            profile_dict['profile_image'] = None
    except Exception as e:
        # Log error but don't fail the request
        logging.error(f"Error retrieving buyer profile image for user {user_id}: {str(e)}")
        profile_dict['profile_image'] = None
    
    # Calculate meeting quota information
    meeting_quota = calculate_buyer_meeting_quota(user_id, buyer_profile)
    
    # Add meeting quota information to the profile dictionary
    profile_dict.update(meeting_quota)
    
    # Return the enhanced profile
    return jsonify({
        'profile': profile_dict
    }), 200

@buyer.route('/profile', methods=['PUT'])
@buyer_required
def update_profile():
    """
    Endpoint to update buyer profile information
    """
    user_id = get_jwt_identity()
    
    # Convert to int if it's a string
    if isinstance(user_id, str):
        try:
            user_id = int(user_id)
        except ValueError:
            return jsonify({'error': 'Invalid user ID'}), 400
    
    data = request.get_json()
    
    # Get or create buyer profile
    buyer_profile = BuyerProfile.query.filter_by(user_id=user_id).first()
    
    if not buyer_profile:
        # Create new profile
        buyer_profile = BuyerProfile(user_id=user_id)
        db.session.add(buyer_profile)
    
    # Update profile fields (including enhanced fields)
    updatable_fields = [
        # Legacy fields
        'name', 'organization', 'designation', 'operator_type', 
        'interests', 'properties_of_interest', 'country', 'state', 
        'city', 'address', 'mobile', 'website', 'instagram', 
        'year_of_starting_business', 'bio', 'profile_image',
        # Enhanced fields
        'category_id', 'salutation', 'first_name', 'last_name', 
        'vip', 'status', 'gst', 'pincode'
    ]
    
    for field in updatable_fields:
        if field in data:
            setattr(buyer_profile, field, data[field])
    
    try:
        db.session.commit()
        return jsonify({
            'message': 'Profile updated successfully',
            'profile': buyer_profile.to_dict()
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'error': f'Failed to update profile: {str(e)}'
        }), 500

@buyer.route('/profile', methods=['POST'])
@buyer_required
def create_profile():
    """
    Endpoint to create buyer profile information
    """
    user_id = get_jwt_identity()
    
    # Convert to int if it's a string
    if isinstance(user_id, str):
        try:
            user_id = int(user_id)
        except ValueError:
            return jsonify({'error': 'Invalid user ID'}), 400
    
    data = request.get_json()
    
    # Check if profile already exists
    existing_profile = BuyerProfile.query.filter_by(user_id=user_id).first()
    if existing_profile:
        return jsonify({
            'error': 'Profile already exists. Use PUT to update.'
        }), 400
    
    # Validate required fields
    required_fields = ['name', 'organization']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    # Create new profile with enhanced fields support
    buyer_profile = BuyerProfile(
        user_id=user_id,
        # Legacy fields
        name=data['name'],
        organization=data['organization'],
        designation=data.get('designation'),
        operator_type=data.get('operator_type'),
        interests=data.get('interests', []),
        properties_of_interest=data.get('properties_of_interest', []),
        country=data.get('country'),
        state=data.get('state'),
        city=data.get('city'),
        address=data.get('address'),
        mobile=data.get('mobile'),
        website=data.get('website'),
        instagram=data.get('instagram'),
        year_of_starting_business=data.get('year_of_starting_business'),
        bio=data.get('bio'),
        profile_image=data.get('profile_image'),
        # Enhanced fields
        category_id=data.get('category_id'),
        salutation=data.get('salutation'),
        first_name=data.get('first_name'),
        last_name=data.get('last_name'),
        vip=data.get('vip', False),
        status=data.get('status', 'pending'),
        gst=data.get('gst'),
        pincode=data.get('pincode')
    )
    
    try:
        db.session.add(buyer_profile)
        db.session.commit()
        return jsonify({
            'message': 'Profile created successfully',
            'profile': buyer_profile.to_dict()
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'error': f'Failed to create profile: {str(e)}'
        }), 500

# Enhanced Model Endpoints

@buyer.route('/categories', methods=['GET'])
@buyer_required
def get_buyer_categories():
    """
    Endpoint to get all buyer categories
    """
    try:
        categories = BuyerCategory.query.all()
        return jsonify({
            'categories': [category.to_dict() for category in categories]
        }), 200
    except Exception as e:
        return jsonify({
            'error': f'Failed to fetch categories: {str(e)}'
        }), 500

@buyer.route('/categories/<int:category_id>', methods=['GET'])
@buyer_required
def get_buyer_category(category_id):
    """
    Endpoint to get a specific buyer category
    """
    try:
        category = BuyerCategory.query.get(category_id)
        if not category:
            return jsonify({'error': 'Category not found'}), 404
        
        return jsonify({
            'category': category.to_dict()
        }), 200
    except Exception as e:
        return jsonify({
            'error': f'Failed to fetch category: {str(e)}'
        }), 500

@buyer.route('/interests', methods=['GET'])
@buyer_required
def get_interests():
    """
    Endpoint to get all available interests
    """
    try:
        interests = Interest.query.all()
        return jsonify({
            'interests': [interest.to_dict() for interest in interests]
        }), 200
    except Exception as e:
        return jsonify({
            'error': f'Failed to fetch interests: {str(e)}'
        }), 500

@buyer.route('/travel-plans', methods=['GET'])
@buyer_required
def get_travel_plans():
    """
    Endpoint to get buyer's travel plans
    """
    user_id = get_jwt_identity()
    
    # Convert to int if it's a string
    if isinstance(user_id, str):
        try:
            user_id = int(user_id)
        except ValueError:
            return jsonify({'error': 'Invalid user ID'}), 400
    
    # Fetch travel plans for the user
    travel_plans = TravelPlan.query.filter_by(user_id=user_id).all()
    
    if not travel_plans:
        # if no travel plan found, create a new one 
        travel_plan = TravelPlan(
            user_id=user_id,
            event_name='Wayanad Splash 2025',
            event_start_date=datetime(2025, 7, 11),
            event_end_date=datetime(2025, 7, 13),
            venue="Wayanad Tourism organization",
            status="Planned",
            created_at=datetime.now()
        )
        db.session.add(travel_plan)
        db.session.commit()

        # Refetch the details
        travel_plans = TravelPlan.query.filter_by(user_id=user_id).all()
    
    return jsonify({
        'travel_plans': [plan.to_dict() for plan in travel_plans]
    }), 200

@buyer.route('/travel-plans/<int:plan_id>/outbound', methods=['PUT'])
@buyer_required
def update_outbound(plan_id):
    """
    Endpoint to update outbound journey details
    """
    user_id = get_jwt_identity()
    
    # Convert to int if it's a string
    if isinstance(user_id, str):
        try:
            user_id = int(user_id)
        except ValueError:
            return jsonify({'error': 'Invalid user ID'}), 400
    
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['carrier', 'number', 'departureLocation', 'departureDateTime', 
                       'arrivalLocation', 'arrivalDateTime', 'bookingReference']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    # Fetch travel plan
    travel_plan = TravelPlan.query.filter_by(id=plan_id, user_id=user_id).first()
    if not travel_plan:
        return jsonify({'error': 'Travel plan not found or access denied'}), 404
    
    # Determine transportation type from data - preserve existing type if not provided
    transport_type = data.get('type', travel_plan.transportation.type if travel_plan.transportation else 'flight').lower()
    outbound_type = data.get('outbound_type', transport_type).lower()  # Individual outbound type
    
    # Prepare data for helper functions
    wrapped_data = {
        'outbound': data
    }
    
    # Update outbound journey details
    if not travel_plan.transportation:
        # Create new transportation record if it doesn't exist
        transportation = Transportation(
            travel_plan_id=plan_id,
            type=transport_type,
            outbound_type=outbound_type,  # Set individual outbound type
            outbound_carrier=data['carrier'],
            outbound_number=data['number'],
            outbound_departure_location=data['departureLocation'],
            outbound_departure_datetime=get_outbound_departure_datetime(wrapped_data),
            outbound_arrival_location=data['arrivalLocation'],
            outbound_arrival_datetime=get_outbound_arrival_datetime(wrapped_data),
            outbound_booking_reference=data['bookingReference'],
            outbound_seat_info=data.get('seatInfo', ''),
            # Set default values for return journey
            return_carrier='',
            return_number='',
            return_departure_location='',
            return_departure_datetime=datetime.now(),
            return_arrival_location='',
            return_arrival_datetime=datetime.now(),
            return_booking_reference=''
        )
        db.session.add(transportation)
    else:
        # Update existing transportation record
        travel_plan.transportation.type = transport_type
        travel_plan.transportation.outbound_type = outbound_type  # Update individual outbound type
        travel_plan.transportation.outbound_carrier = data['carrier']
        travel_plan.transportation.outbound_number = data['number']
        travel_plan.transportation.outbound_departure_location = data['departureLocation']
        travel_plan.transportation.outbound_departure_datetime = get_outbound_departure_datetime(wrapped_data)
        travel_plan.transportation.outbound_arrival_location = data['arrivalLocation']
        travel_plan.transportation.outbound_arrival_datetime = get_outbound_arrival_datetime(wrapped_data)
        travel_plan.transportation.outbound_booking_reference = data['bookingReference']
        travel_plan.transportation.outbound_seat_info = data.get('seatInfo', '')
    
    db.session.commit()
    
    return jsonify({
        'message': 'Outbound journey updated successfully',
        'travel_plan': travel_plan.to_dict()
    }), 200

@buyer.route('/travel-plans/<int:plan_id>/return', methods=['PUT'])
@buyer_required
def update_return(plan_id):
    """
    Endpoint to update return journey details
    """
    user_id = get_jwt_identity()
    
    # Convert to int if it's a string
    if isinstance(user_id, str):
        try:
            user_id = int(user_id)
        except ValueError:
            return jsonify({'error': 'Invalid user ID'}), 400
    
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['carrier', 'number', 'departureLocation', 'departureDateTime', 
                       'arrivalLocation', 'arrivalDateTime', 'bookingReference']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    # Fetch travel plan
    travel_plan = TravelPlan.query.filter_by(id=plan_id, user_id=user_id).first()
    if not travel_plan:
        return jsonify({'error': 'Travel plan not found or access denied'}), 404
    
    # Determine transportation type from data - preserve existing type if not provided
    transport_type = data.get('type', travel_plan.transportation.type if travel_plan.transportation else 'flight').lower()
    return_type = data.get('return_type', transport_type).lower()  # Individual return type
    
    # Prepare data for helper functions
    wrapped_data = {
        'return': data
    }
    
    # Update return journey details
    if not travel_plan.transportation:
        # Create new transportation record if it doesn't exist
        transportation = Transportation(
            travel_plan_id=plan_id,
            type=transport_type,
            return_type=return_type,  # Set individual return type
            # Set default values for outbound journey
            outbound_carrier='',
            outbound_number='',
            outbound_departure_location='',
            outbound_departure_datetime=datetime.now(),
            outbound_arrival_location='',
            outbound_arrival_datetime=datetime.now(),
            outbound_booking_reference='',
            # Return journey details
            return_carrier=data['carrier'],
            return_number=data['number'],
            return_departure_location=data['departureLocation'],
            return_departure_datetime=get_return_departure_datetime(wrapped_data),
            return_arrival_location=data['arrivalLocation'],
            return_arrival_datetime=get_return_arrival_datetime(wrapped_data),
            return_booking_reference=data['bookingReference'],
            return_seat_info=data.get('seatInfo', '')
        )
        db.session.add(transportation)
    else:
        # Update existing transportation record
        travel_plan.transportation.type = transport_type
        travel_plan.transportation.return_type = return_type  # Update individual return type
        travel_plan.transportation.return_carrier = data['carrier']
        travel_plan.transportation.return_number = data['number']
        travel_plan.transportation.return_departure_location = data['departureLocation']
        travel_plan.transportation.return_departure_datetime = get_return_departure_datetime(wrapped_data)
        travel_plan.transportation.return_arrival_location = data['arrivalLocation']
        travel_plan.transportation.return_arrival_datetime = get_return_arrival_datetime(wrapped_data)
        travel_plan.transportation.return_booking_reference = data['bookingReference']
        travel_plan.transportation.return_seat_info = data.get('seatInfo', '')
    
    db.session.commit()
    
    return jsonify({
        'message': 'Return journey updated successfully',
        'travel_plan': travel_plan.to_dict()
    }), 200

@buyer.route('/travel-plans/<int:plan_id>/transportation', methods=['PUT'])
@buyer_required
def update_transportation(plan_id):
    """
    Endpoint to update both outbound and return transportation details in a single transaction
    """
    user_id = get_jwt_identity()
    
    # Convert to int if it's a string
    if isinstance(user_id, str):
        try:
            user_id = int(user_id)
        except ValueError:
            return jsonify({'error': 'Invalid user ID'}), 400
    
    data = request.get_json()
    
    # Validate required fields for both outbound and return
    required_outbound_fields = ['outbound.carrier', 'outbound.number', 'outbound.departureLocation', 
                               'outbound.departureDateTime', 'outbound.arrivalLocation', 
                               'outbound.arrivalDateTime', 'outbound.bookingReference']
    required_return_fields = ['return.carrier', 'return.number', 'return.departureLocation', 
                             'return.departureDateTime', 'return.arrivalLocation', 
                             'return.arrivalDateTime', 'return.bookingReference']
    
    # Check outbound fields
    for field in required_outbound_fields:
        keys = field.split('.')
        if keys[0] not in data or keys[1] not in data[keys[0]]:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    # Check return fields
    for field in required_return_fields:
        keys = field.split('.')
        if keys[0] not in data or keys[1] not in data[keys[0]]:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    # Fetch travel plan
    travel_plan = TravelPlan.query.filter_by(id=plan_id, user_id=user_id).first()
    if not travel_plan:
        return jsonify({'error': 'Travel plan not found or access denied'}), 404
    
    # Get transportation type from data
    transport_type = data.get('type', 'flight').lower()
    
    try:
        # Update transportation details in a single transaction
        if not travel_plan.transportation:
            # Create new transportation record if it doesn't exist
            transportation = Transportation(
                travel_plan_id=plan_id,
                type=transport_type,
                # Individual transportation types
                outbound_type=data['outbound'].get('type', transport_type).lower(),
                return_type=data['return'].get('type', transport_type).lower(),
                # Outbound journey
                outbound_carrier=data['outbound']['carrier'],
                outbound_number=data['outbound']['number'],
                outbound_departure_location=data['outbound']['departureLocation'],
                outbound_departure_datetime=get_outbound_departure_datetime(data),
                outbound_arrival_location=data['outbound']['arrivalLocation'],
                outbound_arrival_datetime=get_outbound_arrival_datetime(data),
                outbound_booking_reference=data['outbound']['bookingReference'],
                outbound_seat_info=data['outbound'].get('seatInfo', ''),
                # Return journey
                return_carrier=data['return']['carrier'],
                return_number=data['return']['number'],
                return_departure_location=data['return']['departureLocation'],
                return_departure_datetime=get_return_departure_datetime(data),
                return_arrival_location=data['return']['arrivalLocation'],
                return_arrival_datetime=get_return_arrival_datetime(data),
                return_booking_reference=data['return']['bookingReference'],
                return_seat_info=data['return'].get('seatInfo', '')
            )
            db.session.add(transportation)
        else:
            # Update existing transportation record (SINGLE UPDATE - FIXES DUPLICATE ISSUE)
            travel_plan.transportation.type = transport_type
            # Individual transportation types
            travel_plan.transportation.outbound_type = data['outbound'].get('type', transport_type).lower()
            travel_plan.transportation.return_type = data['return'].get('type', transport_type).lower()
            # Outbound journey
            travel_plan.transportation.outbound_carrier = data['outbound']['carrier']
            travel_plan.transportation.outbound_number = data['outbound']['number']
            travel_plan.transportation.outbound_departure_location = data['outbound']['departureLocation']
            travel_plan.transportation.outbound_departure_datetime = get_outbound_departure_datetime(data)
            travel_plan.transportation.outbound_arrival_location = data['outbound']['arrivalLocation']
            travel_plan.transportation.outbound_arrival_datetime = get_outbound_arrival_datetime(data)
            travel_plan.transportation.outbound_booking_reference = data['outbound']['bookingReference']
            travel_plan.transportation.outbound_seat_info = data['outbound'].get('seatInfo', '')
            # Return journey
            travel_plan.transportation.return_carrier = data['return']['carrier']
            travel_plan.transportation.return_number = data['return']['number']
            travel_plan.transportation.return_departure_location = data['return']['departureLocation']
            travel_plan.transportation.return_departure_datetime = get_return_departure_datetime(data)
            travel_plan.transportation.return_arrival_location = data['return']['arrivalLocation']
            travel_plan.transportation.return_arrival_datetime = get_return_arrival_datetime(data)
            travel_plan.transportation.return_booking_reference = data['return']['bookingReference']
            travel_plan.transportation.return_seat_info = data['return'].get('seatInfo', '')
        
        db.session.commit()
        
        return jsonify({
            'message': 'Transportation updated successfully',
            'travel_plan': travel_plan.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'error': f'Failed to update transportation: {str(e)}'
        }), 500

@buyer.route('/travel-plans/<int:plan_id>/accommodation', methods=['PUT'])
@buyer_required
def update_accommodation(plan_id):
    """
    Endpoint to update accommodation details
    """
    user_id = get_jwt_identity()
    
    # Convert to int if it's a string
    if isinstance(user_id, str):
        try:
            user_id = int(user_id)
        except ValueError:
            return jsonify({'error': 'Invalid user ID'}), 400
    
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['name', 'address', 'checkInDateTime', 'checkOutDateTime', 
                       'roomType', 'bookingReference']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    # Fetch travel plan
    travel_plan = TravelPlan.query.filter_by(id=plan_id, user_id=user_id).first()
    if not travel_plan:
        return jsonify({'error': 'Travel plan not found or access denied'}), 404
    
    # Update accommodation details
    if not travel_plan.accommodation:
        # Create new accommodation record if it doesn't exist
        accommodation = Accommodation(
            travel_plan_id=plan_id,
            name=data['name'],
            address=data['address'],
            check_in_datetime=datetime.fromisoformat(data['checkInDateTime']),
            check_out_datetime=datetime.fromisoformat(data['checkOutDateTime']),
            room_type=data['roomType'],
            booking_reference=data['bookingReference'],
            special_notes=data.get('specialNotes', '')
        )
        db.session.add(accommodation)
    else:
        # Update existing accommodation record
        travel_plan.accommodation.name = data['name']
        travel_plan.accommodation.address = data['address']
        travel_plan.accommodation.check_in_datetime = datetime.fromisoformat(data['checkInDateTime'])
        travel_plan.accommodation.check_out_datetime = datetime.fromisoformat(data['checkOutDateTime'])
        travel_plan.accommodation.room_type = data['roomType']
        travel_plan.accommodation.booking_reference = data['bookingReference']
        travel_plan.accommodation.special_notes = data.get('specialNotes', '')
    
    db.session.commit()
    
    return jsonify({
        'message': 'Accommodation updated successfully',
        'travel_plan': travel_plan.to_dict()
    }), 200

@buyer.route('/travel-plans/<int:plan_id>/pickup', methods=['PUT'])
@buyer_required
def update_pickup(plan_id):
    """
    Endpoint to update pickup details
    """
    user_id = get_jwt_identity()
    
    # Convert to int if it's a string
    if isinstance(user_id, str):
        try:
            user_id = int(user_id)
        except ValueError:
            return jsonify({'error': 'Invalid user ID'}), 400
    
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['location', 'dateTime']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    # Fetch travel plan
    travel_plan = TravelPlan.query.filter_by(id=plan_id, user_id=user_id).first()
    if not travel_plan:
        return jsonify({'error': 'Travel plan not found or access denied'}), 404
    
    # Update pickup details
    if not travel_plan.ground_transportation:
        # Create new ground transportation record if it doesn't exist
        ground_transportation = GroundTransportation(
            travel_plan_id=plan_id,
            pickup_location=data['location'],
            pickup_datetime=datetime.fromisoformat(data['dateTime']),
            pickup_vehicle_type=data.get('vehicleType', ''),
            pickup_driver_contact=data.get('driverContact', ''),
            # Set default values for dropoff
            dropoff_location='',
            dropoff_datetime=datetime.now(),
            dropoff_vehicle_type='',
            dropoff_driver_contact=''
        )
        db.session.add(ground_transportation)
    else:
        # Update existing ground transportation record
        travel_plan.ground_transportation.pickup_location = data['location']
        travel_plan.ground_transportation.pickup_datetime = datetime.fromisoformat(data['dateTime'])
        travel_plan.ground_transportation.pickup_vehicle_type = data.get('vehicleTypeId', None)
        travel_plan.ground_transportation.pickup_driver_contact = data.get('driverContact', '')
    
    db.session.commit()
    
    return jsonify({
        'message': 'Pickup details updated successfully',
        'travel_plan': travel_plan.to_dict()
    }), 200

@buyer.route('/travel-plans/<int:plan_id>/dropoff', methods=['PUT'])
@buyer_required
def update_dropoff(plan_id):
    """
    Endpoint to update dropoff details
    """
    user_id = get_jwt_identity()
    
    # Convert to int if it's a string
    if isinstance(user_id, str):
        try:
            user_id = int(user_id)
        except ValueError:
            return jsonify({'error': 'Invalid user ID'}), 400
    
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['location', 'dateTime']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    # Fetch travel plan
    travel_plan = TravelPlan.query.filter_by(id=plan_id, user_id=user_id).first()
    if not travel_plan:
        return jsonify({'error': 'Travel plan not found or access denied'}), 404
    
    # Update dropoff details
    if not travel_plan.ground_transportation:
        # Create new ground transportation record if it doesn't exist
        ground_transportation = GroundTransportation(
            travel_plan_id=plan_id,
            # Set default values for pickup
            pickup_location='',
            pickup_datetime=datetime.now(),
            pickup_vehicle_type='',
            pickup_driver_contact='',
            # Dropoff details
            dropoff_location=data['location'],
            dropoff_datetime=datetime.fromisoformat(data['dateTime']),
            dropoff_vehicle_type=data.get('vehicleType', ''),
            dropoff_driver_contact=data.get('driverContact', '')
        )
        db.session.add(ground_transportation)
    else:
        # Update existing ground transportation record
        travel_plan.ground_transportation.dropoff_location = data['location']
        travel_plan.ground_transportation.dropoff_datetime = datetime.fromisoformat(data['dateTime'])
        travel_plan.ground_transportation.dropoff_vehicle_type = data.get('vehicleTypeId', None)
        travel_plan.ground_transportation.dropoff_driver_contact = data.get('driverContact', '')
    
    db.session.commit()
    
    return jsonify({
        'message': 'Dropoff details updated successfully',
        'travel_plan': travel_plan.to_dict()
    }), 200

@buyer.route('/meetings', methods=['GET'])
@buyer_required
def get_meetings():
    """
    Endpoint to get buyer's meetings
    """
    user_id = get_jwt_identity()
    
    # Convert to int if it's a string
    if isinstance(user_id, str):
        try:
            user_id = int(user_id)
        except ValueError:
            return jsonify({'error': 'Invalid user ID'}), 400
    
    # Get query parameters for filtering
    status = request.args.get('status')
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')
    
    # Build query
    query = Meeting.query.filter_by(buyer_id=user_id)
    
    # Apply filters if provided
    if status:
        try:
            meeting_status = MeetingStatus(status)
            query = query.filter_by(status=meeting_status)
        except ValueError:
            return jsonify({'error': f'Invalid status: {status}'}), 400
    
    # Execute query
    meetings = query.all()
    
    return jsonify({
        'meetings': [meeting.to_dict() for meeting in meetings]
    }), 200

@buyer.route('/meetings', methods=['POST'])
@buyer_required
def create_meeting():
    """
    Endpoint to create a new meeting request
    """
    user_id = get_jwt_identity()
    
    # Convert to int if it's a string
    if isinstance(user_id, str):
        try:
            user_id = int(user_id)
        except ValueError:
            return jsonify({'error': 'Invalid user ID'}), 400
    
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['seller_id', 'time_slot_id']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    # Check if meetings are enabled
    meetings_enabled = SystemSetting.query.filter_by(key='meetings_enabled').first()
    if not meetings_enabled or meetings_enabled.value != 'true':
        return jsonify({
            'error': 'Meeting requests are currently disabled'
        }), 400

    # Check if the seller exists
    seller = User.query.get(data['seller_id'])
    if not seller or seller.role != UserRole.SELLER:
        return jsonify({
            'error': 'Invalid seller'
        }), 400
    
    # Check if the time slot exists and is available
    time_slot = TimeSlot.query.get(data['time_slot_id'])
    if not time_slot:
        return jsonify({
            'error': 'Time slot not found'
        }), 404
    
    if not time_slot.is_available:
        return jsonify({
            'error': 'Time slot is not available'
        }), 400
    
    # Check if the time slot belongs to the seller
    if time_slot.user_id != data['seller_id']:
        return jsonify({
            'error': 'Time slot does not belong to the specified seller'
        }), 400

    # Create the meeting
    meeting = Meeting(
        buyer_id=user_id,
        seller_id=data['seller_id'],
        time_slot_id=data['time_slot_id'],
        notes=data.get('notes', ''),
        status=MeetingStatus.PENDING
    )
    
    # Mark the time slot as unavailable
    time_slot.is_available = False
    
    db.session.add(meeting)
    db.session.commit()

    # Link meeting_id to time_slot if supported
    if hasattr(time_slot, 'meeting_id'):
        time_slot.meeting_id = meeting.id
        db.session.commit()
    
    return jsonify({
        'message': 'Meeting request created successfully',
        'meeting': meeting.to_dict()
    }), 201

@buyer.route('/meetings/<int:meeting_id>', methods=['PUT'])
@buyer_required
def update_meeting(meeting_id):
    """
    Endpoint to update meeting status
    """
    user_id = get_jwt_identity()
    
    # Convert to int if it's a string
    if isinstance(user_id, str):
        try:
            user_id = int(user_id)
        except ValueError:
            return jsonify({'error': 'Invalid user ID'}), 400
    
    data = request.get_json()
    
    # Validate required fields
    if 'status' not in data:
        return jsonify({'error': 'Missing required field: status'}), 400
    
    # Check if meeting exists and belongs to the user
    meeting = Meeting.query.filter_by(id=meeting_id, buyer_id=user_id).first()
    if not meeting:
        return jsonify({'error': 'Meeting not found or access denied'}), 404
    
    # Update meeting status
    try:
        meeting.status = MeetingStatus(data['status'])
        db.session.commit()
    except ValueError:
        return jsonify({'error': f'Invalid status: {data["status"]}'}), 400
    
    return jsonify({
        'message': 'Meeting updated successfully',
        'meeting': meeting.to_dict()
    }), 200

@buyer.route('/profile/image', methods=['POST'])
@buyer_required
def upload_profile_image():
    """
    Endpoint to upload buyer profile image
    """
    user_id = get_jwt_identity()
    
    # Convert to int if it's a string using helper function
    try:
        user_id = validate_user_id(user_id)
    except ValueError:
        return jsonify({'error': 'Invalid user ID'}), 400
    
    # Check if file was uploaded
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    # Validate file using helper function
    validation_result = validate_image_file(file)
    if not validation_result['valid']:
        return jsonify({'error': validation_result['error']}), 400
    
    try:
        # Get buyer profile
        buyer_profile = BuyerProfile.query.filter_by(user_id=user_id).first()
        if not buyer_profile:
            return jsonify({'error': 'Buyer profile not found'}), 404
        
        # Get Nextcloud connection using helper function
        nc = get_nextcloud_connection()
        if not nc:
            return jsonify({'error': 'External storage configuration missing'}), 500
        
        # Create buyer directories using helper function
        buyer_base_dir_available, buyer_image_profile_dir_available = create_buyer_directories(nc, user_id)
        
        if not buyer_image_profile_dir_available:
            return jsonify({'error': 'Failed to create buyer profile image directory'}), 500
        
        # Generate unique filename using helper function
        filename = generate_buyer_image_filename(user_id, file.filename)
        
        # Prepare file data for upload
        file_data = file.read()
        file.seek(0)  # Reset for potential retry
        
        # Upload file using helper function
        upload_path = upload_buyer_image_to_nextcloud(nc, user_id, file_data, filename)
        
        # Update profile with image URL
        buyer_profile.profile_image = upload_path  # Store as /Photos/...
        
        db.session.commit()
        
        return jsonify({
            'message': 'Profile image uploaded successfully',
            'profile': buyer_profile.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'error': f'Failed to upload profile image: {str(e)}'
        }), 500

@buyer.route('/travel-plans/<int:plan_id>/upload-ticket', methods=['POST'])
@buyer_required
def upload_ticket(plan_id):
    """
    Endpoint to upload a ticket for a travel plan
    """
    user_id = get_jwt_identity()
    
    # Convert to int if it's a string
    if isinstance(user_id, str):
        try:
            user_id = int(user_id)
        except ValueError:
            return jsonify({'error': 'Invalid user ID'}), 400
    
    # Check if file was uploaded
    if 'ticket' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    # Get section parameter
    section = request.form.get('section')
    if section not in ['arrival', 'departure']:
        return jsonify({'error': 'Invalid section. Must be "arrival" or "departure"'}), 400
    
    file = request.files['ticket']
    
    # Validate file
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Check file type (PDF only)
    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'Invalid file type. Only PDF files are allowed'}), 400
    
    # Check file size (2MB limit)
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)  # Reset file pointer
    
    if file_size > 2 * 1024 * 1024:  # 2MB
        return jsonify({'error': 'File size exceeds 2MB limit'}), 400
    
    # Fetch travel plan
    travel_plan = TravelPlan.query.filter_by(id=plan_id, user_id=user_id).first()
    if not travel_plan:
        return jsonify({'error': 'Travel plan not found or access denied'}), 404
    
    # Check if transportation record exists
    if not travel_plan.transportation:
        return jsonify({'error': 'Transportation record not found'}), 404
    
    try:
        # Get NextCloud credentials
        storage_url = os.getenv('EXTERNAL_STORAGE_URL')+"index.php"
        storage_user = os.getenv('EXTERNAL_STORAGE_USER')
        storage_password = os.getenv('EXTERNAL_STORAGE_PASSWORD')
        ocs_url = os.getenv("EXTERNAL_STORAGE_URL")+'ocs/v2.php/apps/files_sharing/api/v1/shares'
        ocs_headers = {'OCS-APIRequest': 'true',"Accept": "application/json"}
        ocs_auth = (storage_user, storage_password)
        
        if not all([storage_url, storage_user, storage_password]):
            return jsonify({'error': 'External storage configuration missing'}), 500
        
        nc = Nextcloud(nextcloud_url=storage_url, nc_auth_user=storage_user, nc_auth_pass=storage_password)
        
        # Create directory structure if needed
        buyer_dir = f"buyer_{user_id}"
        buyer_base_doc_dir = f"/Documents/{buyer_dir}"
        tickets_dir = f"{buyer_base_doc_dir}/tickets"
        
        # Create base directory if it doesn't exist
        try:
            nc.files.listdir(buyer_base_doc_dir)
        except NextcloudException as e:
            if e.status_code == 404:
                nc.files.mkdir(buyer_base_doc_dir)
                # Set sharing permissions
                dir_sharing_data = {
                    'path': buyer_base_doc_dir,
                    'shareType': 3,  # Public link
                    'permissions': 1  # Read-only
                }
                requests.post(ocs_url, headers=ocs_headers, data=dir_sharing_data, auth=ocs_auth)
        
        # Create tickets directory if it doesn't exist
        try:
            nc.files.listdir(tickets_dir)
        except NextcloudException as e:
            if e.status_code == 404:
                nc.files.mkdir(tickets_dir)
                # Set sharing permissions
                dir_sharing_data = {
                    'path': tickets_dir,
                    'shareType': 3,  # Public link
                    'permissions': 1  # Read-only
                }
                requests.post(ocs_url, headers=ocs_headers, data=dir_sharing_data, auth=ocs_auth)
        
        # Generate unique filename
        filename = secure_filename(f"{section}_ticket.pdf")
        
        # Upload file
        upload_path = f"{tickets_dir}/{filename}"
        file_data = file.read()
        file.seek(0)
        
        buf = BytesIO(file_data)
        buf.seek(0)
        uploaded_file = nc.files.upload_stream(upload_path, buf)
        
        # Create public share
        file_sharing_data = {
            'path': upload_path,
            'shareType': 3,  # Public link
            'permissions': 1  # Read-only
        }
        response = requests.post(ocs_url, headers=ocs_headers, data=file_sharing_data, auth=ocs_auth)
        
        if response.status_code != 200:
            return jsonify({'error': 'Failed to create public share for ticket'}), 500
        
        result = response.json()
        if result["ocs"]["meta"]["status"] != "ok":
            return jsonify({'error': 'Failed to create public share for ticket'}), 500
        
        # Get public URL
        file_public_url = result["ocs"]["data"]["url"] + "/download"
        
        # Update transportation record based on section
        if section == 'arrival':
            travel_plan.transportation.arrival_ticket = file_public_url
        else:  # departure
            travel_plan.transportation.return_ticket = file_public_url
        
        db.session.commit()
        
        return jsonify({
            'message': f'{section.capitalize()} ticket uploaded successfully',
            'travel_plan': travel_plan.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'error': f'Failed to upload ticket: {str(e)}'
        }), 500

@buyer.route('/sellers', methods=['GET'])
@buyer_required
def get_sellers():
    """
    Endpoint to get list of sellers with proper profile data including state and country
    """
    import os
    from ..models.models import SellerProfile
    
    # Get query parameters for filtering
    search = request.args.get('search', '')
    specialty = request.args.get('specialty', '')
    
    # Build query to join users with seller_profiles
    query = db.session.query(User, SellerProfile).join(
        SellerProfile, User.id == SellerProfile.user_id
    ).filter(User.role == UserRole.SELLER.value).order_by(SellerProfile.business_name.asc())
    
    # Apply search filter if provided
    if search:
        query = query.filter(
            (User.username.ilike(f'%{search}%')) | 
            (User.business_name.ilike(f'%{search}%')) |
            (SellerProfile.business_name.ilike(f'%{search}%'))
        )
    
    # Execute query
    results = query.all()
    
    # Get PUBLIC_SITE_URL from environment
    public_site_url = os.getenv('PUBLIC_SITE_URL', 'http://localhost:3000')
    
    # Convert to response format
    seller_list = []
    for user, profile in results:
        # Handle full_microsite_url construction - same logic as in seller.py
        seller_full_microsite_url = profile.microsite_url or ''
        
        # Check if we need to add protocol prefix
        if (profile.microsite_url and 
            not profile.microsite_url.startswith(('http://', 'https://'))):
            
            public_site_url_env = os.getenv('PUBLIC_SITE_URL', '')
            
            # Only modify if PUBLIC_SITE_URL is available
            if public_site_url_env:
                # Handle URL concatenation properly
                if public_site_url_env.endswith('/') and profile.microsite_url.startswith('/'):
                    seller_full_microsite_url = public_site_url_env + profile.microsite_url[1:]
                elif not public_site_url_env.endswith('/') and not profile.microsite_url.startswith('/'):
                    seller_full_microsite_url = public_site_url_env + '/' + profile.microsite_url
                else:
                    seller_full_microsite_url = public_site_url_env + profile.microsite_url
        
        # Construct contact person name from available fields
        contact_person_name = ''
        if profile.first_name or profile.last_name:
            # Build name from first_name and last_name
            name_parts = []
            if profile.salutation:
                name_parts.append(profile.salutation)
            if profile.first_name:
                name_parts.append(profile.first_name)
            if profile.last_name:
                name_parts.append(profile.last_name)
            contact_person_name = ' '.join(name_parts)
        else:
            # Fall back to business name if personal name not available
            contact_person_name = profile.business_name or user.business_name or user.username

        seller_data = {
            'id': user.id,
            'name': user.username,
            'businessName': profile.business_name or user.business_name or '',
            'description': profile.description or user.business_description or '',
            'location': profile.state or 'Unknown',  # Display state instead of pincode
            'country': profile.country or 'Unknown',
            'address': profile.address or '',
            'pincode': profile.pincode or '',
            'seller_type': profile.seller_type or 'Not Specified',  # Include seller type
            'rating': 4.8,  # Placeholder - could be calculated from reviews
            'specialties': [interest.name for interest in profile.target_market_relationships],  # Dynamic specialties from database
            'image_url': profile.logo_url or '/images/sellers/default.jpg',
            'isVerified': profile.is_verified,
            # Get actual stall number from Stall table
            'stallNo': 'Not Allocated Yet',  # Default to Not Allocated
            'website': profile.website or '',
            'full_microsite_url': seller_full_microsite_url,
            'contactEmail': profile.contact_email or user.email,
            'contactPhone': profile.contact_phone or '',
            # Add contact person and designation fields
            'contactPersonName': contact_person_name,
            'designation': profile.designation or ''
        }
        
        # Filter by specialty if provided (placeholder logic)
        if specialty and specialty not in seller_data['specialties']:
            continue
        
        # Get all allocated stall numbers for this seller
        stalls = Stall.query.filter_by(seller_id=user.id).all()
        stall_numbers = []
        for stall in stalls:
            if stall.allocated_stall_number:
                stall_numbers.append(stall.allocated_stall_number)
                
        if stall_numbers:
            seller_data['stallNo'] = ', '.join(stall_numbers)
        
        # Check meeting status
        user_id = get_jwt_identity()
        if isinstance(user_id, str):
            try:
                user_id = int(user_id)
            except ValueError:
                user_id = None
        
        if user_id:
            meeting = Meeting.query.filter_by(buyer_id=user_id, seller_id=user.id).order_by(Meeting.created_at.desc()).first()
            if meeting:
                seller_data['meetingStatus'] = meeting.status.value
            else:
                seller_data['meetingStatus'] = 'none'
        else:
            seller_data['meetingStatus'] = 'none'
        
        seller_list.append(seller_data)
    
    return jsonify({
        'sellers': seller_list
    }), 200

@buyer.route('/image/<int:buyer_id>', methods=['GET'])
def get_buyer_image(buyer_id):
    """
    Endpoint to retrieve buyer image URL given a buyer user ID
    No authentication required - public access
    """
    # Initialize default response structure using helper function
    response_data = create_buyer_image_response(buyer_id)
    
    try:
        # Check if buyer exists and has buyer role using helper function
        if not validate_buyer_exists(buyer_id):
            response_data['error'] = 'Buyer not found'
            log_buyer_image_response(response_data, 'buyer not found')
            return jsonify(response_data), 404
        
        # Get Nextcloud connection using helper function
        nc = get_nextcloud_connection()
        if not nc:
            response_data['error'] = 'External storage configuration missing'
            log_buyer_image_response(response_data, 'config missing')
            return jsonify(response_data), 200
        
        # Get buyer profile images using helper function
        image_files = get_buyer_profile_images(buyer_id)
        if not image_files:
            log_buyer_image_response(response_data, 'no images found')
            return jsonify(response_data), 200
        
        # Sort by timestamp (most recent first) and get the latest image
        image_files.sort(key=lambda x: x[0], reverse=True)
        latest_timestamp, latest_filename, latest_file_info = image_files[0]
        
        # Convert image to base64 data URL using helper function
        image_data = convert_image_to_base64_data_url(buyer_id, latest_filename)
        response_data.update({
            'has_image': True,
            **image_data
        })
        
        log_buyer_image_response(response_data, 'image found')
        return jsonify(response_data), 200
        
    except Exception as e:
        response_data['error'] = f'Failed to retrieve buyer image: {str(e)}'
        logging.error(f"Error retrieving buyer image: {str(e)}")
        log_buyer_image_response(response_data, 'general error')
        return jsonify(response_data), 200

@buyer.route('/public/<buyer_slug>', methods=['GET'])
def get_buyer_public_profile(buyer_slug):
    """Get a buyer profile by its slug (public, no auth required)"""
    try:
        # Extract buyer_id from slug (format: BXXX where XXX are digits)
        if not buyer_slug.startswith('B') or len(buyer_slug) < 2:
            return jsonify({
                'error': 'Invalid buyer slug format. Expected format: BXXX'
            }), 400
        
        # Extract numeric part
        try:
            buyer_id = int(buyer_slug[1:])  # Remove 'B' and convert to int
        except ValueError:
            return jsonify({
                'error': 'Invalid buyer slug format. Expected format: BXXX'
            }), 400
        
        # Check if user exists and has buyer role
        user = User.query.get(buyer_id)
        if not user or user.role != UserRole.BUYER.value:
            return jsonify({
                'error': 'Buyer not found'
            }), 404
        
        # Get buyer profile
        buyer_profile = BuyerProfile.query.filter_by(user_id=buyer_id).first()
        if not buyer_profile:
            return jsonify({
                'error': 'Buyer profile not found'
            }), 404
        
        # Get buyer profile image using helper function
        profile_image_data = None
        try:
            if buyer_profile.profile_image:
                # Extract filename from the stored path
                filename = buyer_profile.profile_image.split('/')[-1]
                
                # Convert image to base64 data URL using helper function
                image_data = convert_image_to_base64_data_url(buyer_id, filename)
                profile_image_data = image_data['image_data_url']
            else:
                # No profile image path stored
                profile_image_data = None
        except Exception as e:
            # Log error but don't fail the request
            logging.error(f"Error retrieving buyer profile image for user {buyer_id}: {str(e)}")
            profile_image_data = None

        # Return only public-safe subset of data
        buyer_data = {
            'user_id': buyer_profile.user_id,
            'name': buyer_profile.name,
            'organization': buyer_profile.organization,
            'designation': buyer_profile.designation,
            'city': buyer_profile.city,
            'state': buyer_profile.state,
            'country': buyer_profile.country,
            'address': buyer_profile.address,
            'profile_image': profile_image_data,
            'status': buyer_profile.status,
            'vip': buyer_profile.vip,
            'category': buyer_profile.category.name if buyer_profile.category else None,
            'website': buyer_profile.website
        }
        
        return jsonify({
            'buyer': buyer_data
        }), 200
        
    except Exception as e:
        return jsonify({
            'error': f'Failed to fetch buyer profile: {str(e)}'
        }), 500

@buyer.route('/bank_details', methods=['POST'])
@buyer_required
def create_bank_details():
    """
    Endpoint to create buyer bank details
    """
    user_id = get_jwt_identity()
    
    # Step 1: Validate user_id and convert to int
    if isinstance(user_id, str):
        try:
            user_id = int(user_id)
        except ValueError:
            return jsonify({'error': 'Invalid user ID'}), 400
    
    # Step 2: Check that buyer is valid user (exists in users.id)
    user = User.query.get(user_id)
    if not user or user.role != UserRole.BUYER.value:
        return jsonify({'error': 'Invalid buyer user'}), 400
    
    # Step 3: Check that buyer has a profile (buyer_id = buyer_profile.user_id)
    buyer_profile = BuyerProfile.query.filter_by(user_id=user_id).first()
    if not buyer_profile:
        return jsonify({'error': 'Buyer profile not found. Please create profile first.'}), 400
    
    # Step 4: Check no existing record for this buyer_id in buyer_bank_details
    existing_bank_details = BuyerBankDetails.query.filter_by(buyer_id=user_id).first()
    if existing_bank_details:
        return jsonify({'error': 'Bank details already exist for this buyer'}), 400
    
    # Step 5: Get and validate input data
    data = request.get_json()
    
    # Step 6: Validate all required (non-null) fields are present
    required_fields = [
        'ifsc_code', 'bank_name', 'bank_branch', 'bank_city',
        'account_holder_name', 'account_number', 'account_type'
    ]
    
    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    # Step 7: Create new BuyerBankDetails record
    try:
        bank_details = BuyerBankDetails(
            buyer_id=user_id,
            # Required fields
            ifsc_code=data['ifsc_code'],
            bank_name=data['bank_name'],
            bank_branch=data['bank_branch'],
            bank_city=data['bank_city'],
            account_holder_name=data['account_holder_name'],
            account_number=data['account_number'],
            account_type=data['account_type'],
            # Optional fields (will be None if not provided)
            bank_centre=data.get('bank_centre'),
            bank_district=data.get('bank_district'),
            bank_state=data.get('bank_state'),
            bank_address=data.get('bank_address'),
            bank_phone=data.get('bank_phone'),
            bank_micr=data.get('bank_micr'),
            # Payment capabilities - default to True if not provided
            imps_enabled=data.get('imps_enabled', True),
            neft_enabled=data.get('neft_enabled', True),
            rtgs_enabled=data.get('rtgs_enabled', True),
            upi_enabled=data.get('upi_enabled', True),
            # Timestamps
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.session.add(bank_details)
        db.session.commit()
        
        return jsonify({
            'message': 'Bank details created successfully',
            'bank_details': bank_details.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'error': f'Failed to create bank details: {str(e)}'
        }), 500

@buyer.route('/bank_details', methods=['PUT'])
@buyer_required
def update_bank_details():
    """
    Endpoint to update buyer bank details
    """
    user_id = get_jwt_identity()
    
    # Step 1: Validate user_id and convert to int
    if isinstance(user_id, str):
        try:
            user_id = int(user_id)
        except ValueError:
            return jsonify({'error': 'Invalid user ID'}), 400
    
    # Step 2: Check that buyer is valid user (exists in users.id)
    user = User.query.get(user_id)
    if not user or user.role != UserRole.BUYER.value:
        return jsonify({'error': 'Invalid buyer user'}), 400
    
    # Step 3: Check that buyer has a profile (buyer_id = buyer_profile.user_id)
    buyer_profile = BuyerProfile.query.filter_by(user_id=user_id).first()
    if not buyer_profile:
        return jsonify({'error': 'Buyer profile not found. Please create profile first.'}), 400
    
    # Step 4: Check that existing record EXISTS for this buyer_id in buyer_bank_details
    existing_bank_details = BuyerBankDetails.query.filter_by(buyer_id=user_id).first()
    if not existing_bank_details:
        return jsonify({'error': 'Bank details not found. Please create bank details first.'}), 404
    
    # Step 5: Get and validate input data
    data = request.get_json()
    
    # Step 6: Validate all required (non-null) fields are present
    required_fields = [
        'ifsc_code', 'bank_name', 'bank_branch', 'bank_city',
        'account_holder_name', 'account_number', 'account_type'
    ]
    
    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    # Step 7: Update existing BuyerBankDetails record
    try:
        # Update required fields
        existing_bank_details.ifsc_code = data['ifsc_code']
        existing_bank_details.bank_name = data['bank_name']
        existing_bank_details.bank_branch = data['bank_branch']
        existing_bank_details.bank_city = data['bank_city']
        existing_bank_details.account_holder_name = data['account_holder_name']
        existing_bank_details.account_number = data['account_number']
        existing_bank_details.account_type = data['account_type']
        
        # Update optional fields
        existing_bank_details.bank_centre = data.get('bank_centre')
        existing_bank_details.bank_district = data.get('bank_district')
        existing_bank_details.bank_state = data.get('bank_state')
        existing_bank_details.bank_address = data.get('bank_address')
        existing_bank_details.bank_phone = data.get('bank_phone')
        existing_bank_details.bank_micr = data.get('bank_micr')
        
        # Update payment capabilities - default to True if not provided
        existing_bank_details.imps_enabled = data.get('imps_enabled', True)
        existing_bank_details.neft_enabled = data.get('neft_enabled', True)
        existing_bank_details.rtgs_enabled = data.get('rtgs_enabled', True)
        existing_bank_details.upi_enabled = data.get('upi_enabled', True)
        
        # Update only the updated_at timestamp (preserve created_at)
        existing_bank_details.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'message': 'Bank details updated successfully',
            'bank_details': existing_bank_details.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'error': f'Failed to update bank details: {str(e)}'
        }), 500

@buyer.route('/bank_details', methods=['GET'])
@buyer_required
def get_bank_details():
    """
    Endpoint to get buyer's existing bank details
    """
    user_id = get_jwt_identity()
    
    # Convert to int if it's a string
    if isinstance(user_id, str):
        try:
            user_id = int(user_id)
        except ValueError:
            return jsonify({'error': 'Invalid user ID'}), 400
    
    # Get existing bank details for this buyer
    bank_details = BuyerBankDetails.query.filter_by(buyer_id=user_id).first()
    
    if not bank_details:
        return jsonify({
            'error': 'No bank details found for this buyer'
        }), 404
    
    return jsonify({
        'bank_details': bank_details.to_dict()
    }), 200

@buyer.route('/bank_details_ifsc/<ifsc>', methods=['GET'])
@buyer_required
def get_ifsc_bank_details(ifsc):
    """
    Endpoint to get bank details from IFSC code using Razorpay API
    """
    try:
        # Validate IFSC format first
        if not validate_ifsc_format(ifsc):
            return jsonify({
                'error': 'Invalid IFSC code format'
            }), 400
        
        # Get bank details from IFSC
        bank_details = get_bank_details_from_ifsc(ifsc)
        
        if bank_details:
            # Transform uppercase field names to lowercase for better JSON practices
            transformed_details = {
                'ifsc': bank_details.get('IFSC', ''),
                'bank_name': bank_details.get('BANK', ''),
                'branch': bank_details.get('BRANCH', ''),
                'centre': bank_details.get('CENTRE', ''),
                'city': bank_details.get('CITY', ''),
                'district': bank_details.get('DISTRICT', ''),
                'state': bank_details.get('STATE', ''),
                'address': bank_details.get('ADDRESS', ''),
                'contact': bank_details.get('CONTACT', ''),
                'micr': bank_details.get('MICR', ''),
                'imps': bank_details.get('IMPS', True),
                'neft': bank_details.get('NEFT', True),
                'rtgs': bank_details.get('RTGS', True),
                'upi': bank_details.get('UPI', True)
            }
            return jsonify(transformed_details), 200
        else:
            return jsonify({
                'error': 'IFSC code not found or invalid'
            }), 404
            
    except Exception as e:
        return jsonify({
            'error': f'Failed to fetch bank details: {str(e)}'
        }), 500
