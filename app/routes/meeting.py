from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
from ..models import db, Meeting, TimeSlot, User, UserRole, MeetingStatus, SystemSetting
from ..utils.auth import buyer_required, seller_required
import logging

meeting = Blueprint('meeting', __name__, url_prefix='/api/meetings')

@meeting.route('', methods=['GET'])
@jwt_required()
def get_meetings():
    """Get meetings for the current user"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({
            'error': 'User not found'
        }), 404
    
    # Get meetings based on user role
    if user.role == UserRole.BUYER.value:
        meetings = Meeting.query.filter_by(buyer_id=user_id).all()
    elif user.role == UserRole.SELLER.value:
        meetings = Meeting.query.filter_by(seller_id=user_id).all()
    elif user.role == UserRole.ADMIN.value:
        # Admins can see all meetings
        meetings = Meeting.query.all()
    else:
        return jsonify({
            'error': 'Invalid user role'
        }), 400
    
    return jsonify({
        'meetings': [m.to_dict() for m in meetings]
    }), 200

@meeting.route('/<int:meeting_id>', methods=['GET'])
@jwt_required()
def get_meeting(meeting_id):
    """Get a specific meeting"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({
            'error': 'User not found'
        }), 404
    
    meeting = Meeting.query.get(meeting_id)
    
    if not meeting:
        return jsonify({
            'error': 'Meeting not found'
        }), 404
    
    # Check if the user has permission to view this meeting
    if user.role == UserRole.BUYER.value and meeting.buyer_id != user_id:
        return jsonify({
            'error': 'You do not have permission to view this meeting'
        }), 403
    
    if user.role == UserRole.SELLER.value and meeting.seller_id != user_id:
        return jsonify({
            'error': 'You do not have permission to view this meeting'
        }), 403
    
    return jsonify({
        'meeting': meeting.to_dict()
    }), 200

@meeting.route('/buyer/request', methods=['POST'])
@jwt_required()
@buyer_required
def create_buyer_meeting_request():
    """Create a new meeting request by the buyer"""
    data = request.get_json()
    buyer_id = get_jwt_identity()
    
    # Validate required fields
    required_fields = ['requested_id']  
    for field in required_fields:
        if field not in data:
            return jsonify({
                'error': f'Missing required field: {field}'
            }), 400
    
    # Check if meetings are enabled
    meetings_enabled = SystemSetting.query.filter_by(key='meetings_enabled').first()
    if not meetings_enabled or meetings_enabled.value != 'true':
        return jsonify({
            'error': 'Meeting requests are currently disabled'
        }), 400
    
    # ✅ FIX: Convert requested_id to integer to fix data type mismatch
    try:
        seller_id = int(data['requested_id'])
    except (ValueError, TypeError):
        return jsonify({
            'error': 'Invalid seller ID format'
        }), 400
    
    # Check if the seller exists
    seller = User.query.get(seller_id)
    if not seller or seller.role != UserRole.SELLER.value:
        return jsonify({
            'error': 'Invalid seller'
        }), 400
    """
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
    """
    # Check for existing meeting
    meeting = Meeting.query.filter_by(buyer_id=buyer_id, seller_id=seller_id).first()
    if meeting:
        # ✅ ENHANCEMENT: Check if existing meeting status allows new request
        # Get status as lowercase string for case-insensitive comparison
        if hasattr(meeting.status, 'value'):
            status_lower = meeting.status.value.lower()
        else:
            status_lower = str(meeting.status).lower()
        
        # Allow new meeting if previous was cancelled or expired
        if status_lower not in ['cancelled', 'expired']:
            return jsonify({
                'error': f'Meeting request already exists with status: {meeting.status.value if hasattr(meeting.status, "value") else meeting.status}'
            }), 400
        
        # If cancelled or expired, we'll create a new meeting (continue with creation)
    
    # Create the meeting
    meeting = Meeting(
        buyer_id=buyer_id,
        seller_id=seller_id,
        requestor_id=buyer_id,  # Set requestor_id to current buyer
        #time_slot_id=data['time_slot_id'],
        notes=data.get('notes', ''),
        status=MeetingStatus.PENDING
    )
    
    # Mark the time slot as unavailable
    #time_slot.is_available = False
    #time_slot.meeting_id = meeting.id
    
    db.session.add(meeting)
    db.session.commit()
    
    return jsonify({
        'message': 'Meeting request created successfully',
        'meeting': meeting.to_dict()
    }), 201

@meeting.route('/seller/request', methods=['POST'])
@jwt_required()
@seller_required
def create_seller_meeting_request():
    """Create a new meeting request by the seller"""
    data = request.get_json()
    seller_id = get_jwt_identity()
    
    # Validate required fields
    required_fields = ['requested_id']  
    for field in required_fields:
        if field not in data:
            return jsonify({
                'error': f'Missing required field: {field}'
            }), 400
    
    # Check if meetings are enabled
    meetings_enabled = SystemSetting.query.filter_by(key='meetings_enabled').first()
    if not meetings_enabled or meetings_enabled.value != 'true':
        return jsonify({
            'error': 'Meeting requests are currently disabled'
        }), 400
    
    # ✅ FIX: Convert requested_id to integer to fix data type mismatch
    try:
        buyer_id = int(data['requested_id'])
    except (ValueError, TypeError):
        return jsonify({
            'error': 'Invalid buyer ID format'
        }), 400
    
    # Check if the buyer exists
    buyer = User.query.get(buyer_id)
    if not buyer or buyer.role != UserRole.BUYER.value:
        return jsonify({
            'error': 'Invalid buyer'
        }), 400

    # Check for existing meeting
    meeting = Meeting.query.filter_by(buyer_id=buyer_id, seller_id=seller_id).first()
    if meeting:
        # ✅ ENHANCEMENT: Check if existing meeting status allows new request
        # Get status as lowercase string for case-insensitive comparison
        if hasattr(meeting.status, 'value'):
            status_lower = meeting.status.value.lower()
        else:
            status_lower = str(meeting.status).lower()
        
        # Allow new meeting if previous was cancelled or expired
        if status_lower not in ['cancelled', 'expired']:
            return jsonify({
                'error': f'Meeting request already exists with status: {meeting.status.value if hasattr(meeting.status, "value") else meeting.status}'
            }), 400
        
        # If cancelled or expired, we'll create a new meeting (continue with creation)
    
    # Create the meeting
    meeting = Meeting(
        buyer_id=buyer_id,
        seller_id=seller_id,
        requestor_id=seller_id,  # Set requestor_id to current seller
        #time_slot_id=data['time_slot_id'],
        notes=data.get('notes', ''),
        status=MeetingStatus.PENDING
    )
    
    # Mark the time slot as unavailable
    #time_slot.is_available = False
    #time_slot.meeting_id = meeting.id
    
    db.session.add(meeting)
    db.session.commit()
    
    return jsonify({
        'message': 'Meeting request created successfully',
        'meeting': meeting.to_dict()
    }), 201


@meeting.route('/<int:meeting_id>/status', methods=['PUT'])
@jwt_required()
def update_meeting_status(meeting_id):
    """Update the status of a meeting (accept/reject) - available to both buyers and sellers"""
    data = request.get_json()
    user_id = int(get_jwt_identity())
    
    # Validate required fields
    if 'status' not in data:
        return jsonify({
            'error': 'Missing required field: status'
        }), 400
    
    # Validate status value
    try:
        new_status = MeetingStatus(data['status'])
        if new_status not in [MeetingStatus.ACCEPTED, MeetingStatus.REJECTED]:
            return jsonify({
                'error': 'Invalid status. Must be "accepted" or "rejected"'
            }), 400
    except ValueError:
        return jsonify({
            'error': 'Invalid status value'
        }), 400
    
    # Get the meeting
    meeting = Meeting.query.get(meeting_id)
    
    if not meeting:
        return jsonify({
            'error': 'Meeting not found'
        }), 404
    
    # Get the user to check role
    user = User.query.get(user_id)
    if not user:
        return jsonify({
            'error': 'User not found'
        }), 404
    
    # Check if the user has permission to update this meeting
    # Admins can update any meeting, others must be participants
    if user.role != UserRole.ADMIN.value:
        if meeting.buyer_id != user_id and meeting.seller_id != user_id:
            logging.debug(f"User {user_id} does not have permission to update meeting {meeting_id}")
            return jsonify({
                'error': 'You do not have permission to update this meeting'
            }), 403
        
        # Check if the user is the requestor (requestors cannot accept/reject their own requests)
        # This restriction doesn't apply to admins
        if meeting.requestor_id == user_id:
            logging.debug(f"User {user_id} cannot accept/reject their own meeting request")
            return jsonify({
                'error': 'You cannot accept or reject your own meeting request'
            }), 403
    
    # Check if the meeting is in a pending state
    if meeting.status != MeetingStatus.PENDING:
        logging.debug(f"Cannot update meeting {meeting_id}. Current status: {meeting.status.value}")
        return jsonify({
            'error': f'Cannot update meeting status. Current status: {meeting.status.value}'
        }), 400
    
    # Update the meeting status
    meeting.status = new_status
    
    # If rejected, free up the time slot
    if new_status == MeetingStatus.REJECTED and meeting.time_slot:
        meeting.time_slot.is_available = True
        meeting.time_slot.meeting_id = None
    
    db.session.commit()
    
    return jsonify({
        'message': f'Meeting {new_status.value} successfully',
        'meeting': meeting.to_dict()
    }), 200

@meeting.route('/<int:meeting_id>', methods=['DELETE'])
@jwt_required()
def cancel_meeting(meeting_id):
    """Cancel a meeting"""
    user_id = get_jwt_identity()
    
    # Get the meeting
    meeting = Meeting.query.get(meeting_id)
    
    if not meeting:
        return jsonify({
            'error': 'Meeting not found'
        }), 404
    
    # Check if the user has permission to cancel this meeting
    if meeting.buyer_id != user_id and meeting.seller_id != user_id:
        return jsonify({
            'error': 'You do not have permission to cancel this meeting'
        }), 403
    
    # Check if the meeting can be cancelled
    if meeting.status not in [MeetingStatus.PENDING, MeetingStatus.ACCEPTED]:
        return jsonify({
            'error': f'Cannot cancel meeting with status: {meeting.status.value}'
        }), 400
    
    # Update the meeting status
    meeting.status = MeetingStatus.CANCELLED
    
    # Free up the time slot
    if meeting.time_slot:
        meeting.time_slot.is_available = True
        meeting.time_slot.meeting_id = None
    
    db.session.commit()
    
    return jsonify({
        'message': 'Meeting cancelled successfully'
    }), 200

@meeting.route('/export', methods=['GET'])
@jwt_required()
@buyer_required
def export_meetings_for_pdf():
    """Get all meetings for the current buyer for PDF export"""
    buyer_id = get_jwt_identity()
    
    # Get all meetings for this buyer (no pagination, no filters)
    meetings = Meeting.query.filter_by(buyer_id=buyer_id).all()
    
    return jsonify({
        'meetings': [m.to_dict() for m in meetings]
    }), 200

@meeting.route('/export/seller', methods=['GET'])
@jwt_required()
@seller_required
def export_meetings_for_pdf_seller():
    """Get all meetings for the current seller for PDF export"""
    seller_id = get_jwt_identity()
    
    # Get all meetings for this seller (no pagination, no filters)
    meetings = Meeting.query.filter_by(seller_id=seller_id).all()
    
    return jsonify({
        'meetings': [m.to_dict() for m in meetings]
    }), 200

@meeting.route('/<int:meeting_id>/<int:buyer_id>/confirm', methods=['POST'])
@jwt_required()
@seller_required
def confirm_meeting_with_buyer(meeting_id, buyer_id):
    """Confirm meeting with buyer (seller only)"""
    
    # 1. Get seller user ID from JWT
    seller_id = get_jwt_identity()
    
    # 2. Validate seller and buyer exist
    seller = User.query.get(seller_id)
    buyer = User.query.get(buyer_id)
    
    if not seller or seller.role != UserRole.SELLER.value:
        return jsonify({'error': 'Invalid seller'}), 400
        
    if not buyer or buyer.role != UserRole.BUYER.value:
        return jsonify({'error': 'Invalid buyer'}), 400
    
    # 3. Check seller and buyer profiles exist
    if not seller.seller_profile:
        return jsonify({'error': 'Seller profile not found'}), 400
        
    if not buyer.buyer_profile:
        return jsonify({'error': 'Buyer profile not found'}), 400
    
    # 4. Get system settings for date/time validation
    event_start = SystemSetting.query.filter_by(key='event_start_date').first()
    event_end = SystemSetting.query.filter_by(key='event_end_date').first()
    day_start = SystemSetting.query.filter_by(key='day_start_time').first()
    day_end = SystemSetting.query.filter_by(key='day_end_time').first()
    
    if not event_start or not event_end or not day_start or not day_end:
        return jsonify({'error': 'System settings not configured properly'}), 500
    
    # 5. Validate current date/time is within allowed range
    current_datetime = datetime.now()
    current_date = current_datetime.date()
    current_time = current_datetime.time()
    
    # Parse event dates
    try:
        event_start_date = datetime.fromisoformat(event_start.value.replace('Z', '+00:00')).date()
        event_end_date = datetime.fromisoformat(event_end.value.replace('Z', '+00:00')).date()
    except (ValueError, AttributeError):
        return jsonify({'error': 'Invalid event date configuration'}), 500
    
    # Parse day start/end times
    try:
        day_start_time = datetime.strptime(day_start.value, '%I:%M %p').time()
        day_end_time = datetime.strptime(day_end.value, '%I:%M %p').time()
    except (ValueError, AttributeError):
        return jsonify({'error': 'Invalid day time configuration'}), 500
    
    # Check if current date is within event dates
    if not (event_start_date <= current_date <= event_end_date):
        return jsonify({'error': 'You cannot confirm this meeting today'}), 400
    
    # Check if current time is within day hours
    if not (day_start_time <= current_time <= day_end_time):
        return jsonify({'error': 'You cannot confirm this meeting today'}), 400
    
    # 6. Check buyer category
    buyer_category_id = buyer.buyer_profile.category_id
    
    if buyer_category_id == 7:  # Walk-in
        # Check if walk-in meeting already exists and is confirmed
        existing_walkin = Meeting.query.filter_by(
            buyer_id=buyer_id, 
            seller_id=seller_id,
            status=MeetingStatus.UNSCHEDULED_COMPLETED
        ).first()
        
        if existing_walkin:
            return jsonify({'message': 'Meeting is already confirmed'}), 200
        
        # Create new meeting with UNSCHEDULED_COMPLETED status
        new_meeting = Meeting(
            buyer_id=buyer_id,
            seller_id=seller_id,
            requestor_id=seller_id,
            status=MeetingStatus.UNSCHEDULED_COMPLETED,
            meeting_date=current_date,
            notes=f"Walk-in meeting confirmed on {current_datetime.strftime('%Y-%m-%d %H:%M')}"
        )
        db.session.add(new_meeting)
        
    else:  # Scheduled buyer
        existing_meeting = None
        
        # Handle auto-detect meeting (meeting_id < 0)
        if meeting_id < 0:
            # Find existing meeting between seller and buyer
            existing_meeting = Meeting.query.filter_by(
                buyer_id=buyer_id, 
                seller_id=seller_id
            ).filter(
                Meeting.status.in_([MeetingStatus.ACCEPTED, MeetingStatus.COMPLETED])
            ).first()
            
            if not existing_meeting:
                return jsonify({'error': 'You have no meeting with this buyer'}), 400
        else:
            # Get the specific meeting by ID
            existing_meeting = Meeting.query.get(meeting_id)
            
            if not existing_meeting:
                return jsonify({'error': 'Meeting not found'}), 404
            
            # Verify this meeting belongs to the seller and buyer
            if existing_meeting.seller_id != seller_id or existing_meeting.buyer_id != buyer_id:
                return jsonify({'error': 'You have no meeting with this buyer'}), 400
        
        # Check if meeting is already confirmed
        if existing_meeting.status == MeetingStatus.COMPLETED:
            return jsonify({'message': 'Meeting is already confirmed'}), 200
        
        # Check meeting status is accepted
        if existing_meeting.status != MeetingStatus.ACCEPTED:
            return jsonify({'error': 'Meeting must be accepted before it can be confirmed'}), 400
        
        # Check meeting date is today or in the past
        if existing_meeting.meeting_date and existing_meeting.meeting_date > current_date:
            return jsonify({'error': 'Cannot confirm future meetings'}), 400
        
        # Update status to COMPLETED
        existing_meeting.status = MeetingStatus.COMPLETED
    
    try:
        db.session.commit()
        return jsonify({'message': 'Meeting confirmed successfully'}), 200
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error confirming meeting: {str(e)}")
        return jsonify({'error': 'Failed to confirm meeting'}), 500
