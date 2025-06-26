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
from ..models import db, User, TravelPlan, Transportation, Accommodation, GroundTransportation, Meeting, MeetingStatus, UserRole, TimeSlot, SystemSetting, BuyerProfile, BuyerCategory, PropertyType, Interest, StallType, Stall

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

# Helper functions for datetime handling
def get_outbound_departure_datetime(data):
    """
    Helper function to get outbound departure datetime.
    """
    # Check if data is None or empty, or if 'outbound' key is missing
    if data is None or not data or 'outbound' not in data:
        return datetime.now()  # Default to current time
        
    if (not data['outbound'].get('departureDateTime') or 
        data['outbound']['departureDateTime'] == '' or 
        data['outbound']['departureDateTime'] == 'T:00'):
        # Default to current time minus 2 hours (assuming arrival is event time)
        event_start_date = SystemSetting.query.filter_by(key='event_start_date').first()
        if event_start_date and event_start_date.value:
            try:
                # Check for the specific error case
                if event_start_date.value == 'T:00' or event_start_date.value.startswith('T:'):
                    logging.warning(f"Invalid date format 'T:00' detected in event_start_date")
                    return datetime.now()
                
                # Check if the value contains 'T' before splitting
                if 'T' in event_start_date.value:
                    # Extract just the date part (YYYY-MM-DD)
                    start_date_str = event_start_date.value.split('T')[0]
                    
                    # Validate the date string format
                    if len(start_date_str) == 10:  # YYYY-MM-DD is 10 characters
                        # Parse with the correct format
                        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
                        
                        # Set time to 12:00 PM (noon) - assuming arrival is 2pm
                        from datetime import timedelta
                        outbound_date = start_date.replace(hour=12, minute=0, second=0)
                        return outbound_date
                
                # If we reach here, the date format was invalid
                logging.warning(f"Invalid date format in event_start_date: {event_start_date.value}")
                return datetime.now()
                
            except (ValueError, TypeError, IndexError) as e:
                # Log the error for debugging
                logging.error(f"Error parsing event_start_date: {str(e)}")
                # Default to current time if parsing fails
                return datetime.now()
        # Default to current time if setting not found
        return datetime.now()
    else:
        try:
            # Use the provided datetime
            return datetime.fromisoformat(data['outbound']['departureDateTime'])
        except (ValueError, TypeError) as e:
            logging.error(f"Error parsing outbound departure datetime: {str(e)}")
            return datetime.now()

def get_outbound_arrival_datetime(data):
    """
    Helper function to get outbound arrival datetime.
    """
    # Check if data is None or empty, or if 'outbound' key is missing
    if data is None or not data or 'outbound' not in data:
        return datetime.now()  # Default to current time
        
    if (not data['outbound'].get('arrivalDateTime') or 
        data['outbound']['arrivalDateTime'] == '' or 
        data['outbound']['arrivalDateTime'] == 'T:00'):
        # Get event start date from system settings
        event_start_date = SystemSetting.query.filter_by(key='event_start_date').first()
        if event_start_date and event_start_date.value:
            try:
                # Check for the specific error case
                if event_start_date.value == 'T:00' or event_start_date.value.startswith('T:'):
                    logging.warning(f"Invalid date format 'T:00' detected in event_start_date")
                    return datetime.now()
                
                # Check if the value contains 'T' before splitting
                if 'T' in event_start_date.value:
                    # Extract just the date part (YYYY-MM-DD)
                    start_date_str = event_start_date.value.split('T')[0]
                    
                    # Validate the date string format
                    if len(start_date_str) == 10:  # YYYY-MM-DD is 10 characters
                        # Parse with the correct format
                        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
                        
                        # Set time to 02:00 PM (14:00)
                        outbound_date = start_date.replace(hour=14, minute=0, second=0)
                        return outbound_date
                
                # If we reach here, the date format was invalid
                logging.warning(f"Invalid date format in event_start_date: {event_start_date.value}")
                return datetime.now()
                
            except (ValueError, TypeError, IndexError) as e:
                # Log the error for debugging
                logging.error(f"Error parsing event_start_date: {str(e)}")
                # Default to current time if parsing fails
                return datetime.now()
        # Default to current time if setting not found
        return datetime.now()
    else:
        try:
            # Use the provided datetime
            return datetime.fromisoformat(data['outbound']['arrivalDateTime'])
        except (ValueError, TypeError) as e:
            logging.error(f"Error parsing outbound arrival datetime: {str(e)}")
            return datetime.now()

def get_return_departure_datetime(data):
    """
    Helper function to get return departure datetime.
    """
    # Check if data is None or empty, or if 'return' key is missing
    if data is None or not data or 'return' not in data:
        return datetime.now()  # Default to current time
        
    if (not data['return'].get('departureDateTime') or 
        data['return']['departureDateTime'] == '' or 
        data['return']['departureDateTime'] == 'T:00'):
        # Get event end date from system settings
        event_end_date = SystemSetting.query.filter_by(key='event_end_date').first()
        if event_end_date and event_end_date.value:
            try:
                # Check for the specific error case
                if event_end_date.value == 'T:00' or event_end_date.value.startswith('T:'):
                    logging.warning(f"Invalid date format 'T:00' detected in event_end_date")
                    return datetime.now()
                
                # Check if the value contains 'T' before splitting
                if 'T' in event_end_date.value:
                    # Extract just the date part (YYYY-MM-DD)
                    end_date_str = event_end_date.value.split('T')[0]
                    
                    # Validate the date string format
                    if len(end_date_str) == 10:  # YYYY-MM-DD is 10 characters
                        # Parse with the correct format
                        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
                        
                        # Set time to 6:00 PM on the end date
                        return_date = end_date.replace(hour=18, minute=0, second=0)
                        return return_date
                
                # If we reach here, the date format was invalid
                logging.warning(f"Invalid date format in event_end_date: {event_end_date.value}")
                return datetime.now()
                
            except (ValueError, TypeError, IndexError) as e:
                # Log the error for debugging
                logging.error(f"Error parsing event_end_date: {str(e)}")
                # Default to current time if parsing fails
                return datetime.now()
        # Default to current time if setting not found
        return datetime.now()
    else:
        try:
            # Use the provided datetime
            return datetime.fromisoformat(data['return']['departureDateTime'])
        except (ValueError, TypeError) as e:
            logging.error(f"Error parsing return departure datetime: {str(e)}")
            return datetime.now()

def get_return_arrival_datetime(data):
    """
    Helper function to get return arrival datetime.
    """
    # Check if data is None or empty, or if 'return' key is missing
    if data is None or not data or 'return' not in data:
        return datetime.now()  # Default to current time
        
    if (not data['return'].get('arrivalDateTime') or 
        data['return']['arrivalDateTime'] == '' or 
        data['return']['arrivalDateTime'] == 'T:00'):
        # Get event end date from system settings
        event_end_date = SystemSetting.query.filter_by(key='event_end_date').first()
        if event_end_date and event_end_date.value:
            try:
                # Check for the specific error case
                if event_end_date.value == 'T:00' or event_end_date.value.startswith('T:'):
                    logging.warning(f"Invalid date format 'T:00' detected in event_end_date")
                    return datetime.now()
                
                # Check if the value contains 'T' before splitting
                if 'T' in event_end_date.value:
                    # Extract just the date part (YYYY-MM-DD)
                    end_date_str = event_end_date.value.split('T')[0]
                    
                    # Validate the date string format
                    if len(end_date_str) == 10:  # YYYY-MM-DD is 10 characters
                        # Parse with the correct format
                        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
                        
                        # Add 1 day and set time to 12:00 PM
                        from datetime import timedelta
                        return_date = (end_date + timedelta(days=1)).replace(hour=12, minute=0, second=0)
                        return return_date
                
                # If we reach here, the date format was invalid
                logging.warning(f"Invalid date format in event_end_date: {event_end_date.value}")
                return datetime.now()
                
            except (ValueError, TypeError, IndexError) as e:
                # Log the error for debugging
                logging.error(f"Error parsing event_end_date: {str(e)}")
                # Default to current time if parsing fails
                return datetime.now()
        # Default to current time if setting not found
        return datetime.now()
    else:
        try:
            # Use the provided datetime
            return datetime.fromisoformat(data['return']['arrivalDateTime'])
        except (ValueError, TypeError) as e:
            logging.error(f"Error parsing return arrival datetime: {str(e)}")
            return datetime.now()

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
