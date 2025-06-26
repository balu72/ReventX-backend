from datetime import datetime
from ..models import db, Meeting, MeetingStatus, BuyerCategory, SystemSetting, Stall

def calculate_buyer_meeting_quota(user_id, buyer_profile):
    """
    Calculate meeting quota information for a buyer
    
    Args:
        user_id (int): The user ID of the buyer
        buyer_profile (BuyerProfile): The buyer's profile object
        
    Returns:
        dict: A dictionary containing meeting quota information:
            - buyerMeetingRequestQuota: Total allowed meeting requests
            - buyerMeetingQuotaExceeded: Whether the quota is exceeded
            - currentMeetingRequestCount: Current number of active meeting requests
            - remainingMeetingRequestCount: Remaining meeting requests allowed
    """
    # 1. Get all pending meetings for the current buyer
    pending_meetings = Meeting.query.filter(
        ((Meeting.buyer_id == user_id) | (Meeting.requestor_id == user_id)),
        Meeting.status.in_([MeetingStatus.PENDING.value, MeetingStatus.PENDING.value.upper()])
    ).all()
    
    # 2. Check and update expired meetings
    current_time = datetime.now()
    expired_meetings = []
    
    for meeting in pending_meetings:
        # If created_at is null/empty or if it's more than 48 hours old, mark as expired
        if not meeting.created_at or (current_time - meeting.created_at).total_seconds() > 48 * 3600:
            meeting.status = MeetingStatus.EXPIRED.value
            expired_meetings.append(meeting)
    
    # 3. Commit changes if any meetings were updated
    if expired_meetings:
        db.session.commit()
    
    # 4. Count active meetings (ACCEPTED or PENDING)
    currentMeetingRequestCount = Meeting.query.filter(
        ((Meeting.buyer_id == user_id) | (Meeting.requestor_id == user_id)),
        ((Meeting.status.in_([MeetingStatus.ACCEPTED.value, MeetingStatus.ACCEPTED.value.upper()])) | 
         (Meeting.status.in_([MeetingStatus.PENDING.value, MeetingStatus.PENDING.value.upper()])))
    ).count()
    
    # Count ACCEPTED meetings only
    currentBuyerAcceptedMeetingCount = Meeting.query.filter(
        ((Meeting.buyer_id == user_id) | (Meeting.requestor_id == user_id)),
        (Meeting.status.in_([MeetingStatus.ACCEPTED.value, MeetingStatus.ACCEPTED.value.upper()]))
    ).count()
    
    # 5. Get max meetings allowed based on buyer category
    # Get the buyer's category and its max_meetings value
    if buyer_profile.category_id:
        buyer_category = BuyerCategory.query.get(buyer_profile.category_id)
        max_meetings_per_category = buyer_category.max_meetings if buyer_category else -1
    else:
        max_meetings_per_category = -1
    
    # If category doesn't specify max meetings or value is negative, use system setting
    if max_meetings_per_category is None or max_meetings_per_category < 0:
        max_seller_attendees_setting = SystemSetting.query.filter_by(key='max_seller_attendees_per_day').first()
        max_meetings_per_day = int(max_seller_attendees_setting.value) if max_seller_attendees_setting else 30  # Default to 30
    else:
        max_meetings_per_day = max_meetings_per_category
    
    # 6. Calculate event duration in days
    event_start_date = SystemSetting.query.filter_by(key='event_start_date').first()
    event_end_date = SystemSetting.query.filter_by(key='event_end_date').first()
    
    if event_start_date and event_end_date and event_start_date.value and event_end_date.value:
        try:
            # Parse ISO 8601 format (e.g., 2025-07-11T00:00:00.000Z)
            # First, extract just the date part (YYYY-MM-DD)
            start_date_str = event_start_date.value.split('T')[0]
            end_date_str = event_end_date.value.split('T')[0]
            
            # Then parse with the correct format
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
            
            event_days = (end_date - start_date).days + 1  # +1 to include both start and end days
        except (ValueError, TypeError, IndexError):
            event_days = 3  # Default to 3 days if dates are invalid (typical event duration)
    else:
        event_days = 3  # Default to 3 days if settings are missing (typical event duration)
    
    # 7. Calculate allowed meeting quota (without multiplying by 2)
    buyerAllowedMeetingQuota = max_meetings_per_day * event_days
    
    # Calculate remaining accept count
    buyerRemainingAcceptCount = max(0, buyerAllowedMeetingQuota - currentBuyerAcceptedMeetingCount)
    
    # Determine if buyer can accept more meeting requests
    canBuyerAcceptMeetingRequest = currentBuyerAcceptedMeetingCount < buyerAllowedMeetingQuota
    
    # Calculate total meeting request quota (keep this for backward compatibility)
    buyerMeetingRequestQuota = buyerAllowedMeetingQuota * 2
    
    # 8. Calculate remaining meeting requests
    remainingMeetingRequestCount = max(0, buyerMeetingRequestQuota - currentMeetingRequestCount)
    
    # Return the meeting quota information
    return {
        'buyerMeetingRequestQuota': buyerMeetingRequestQuota,
        'buyerMeetingQuotaExceeded': currentMeetingRequestCount >= buyerMeetingRequestQuota,
        'currentMeetingRequestCount': currentMeetingRequestCount,
        'remainingMeetingRequestCount': remainingMeetingRequestCount,
        'currentBuyerAcceptedMeetingCount': currentBuyerAcceptedMeetingCount,
        'buyerAllowedMeetingQuota': buyerAllowedMeetingQuota,
        'buyerRemainingAcceptCount': buyerRemainingAcceptCount,
        'canBuyerAcceptMeetingRequest': canBuyerAcceptMeetingRequest
    }


def calculate_seller_meeting_quota(seller_id, seller_profile):
    """
    Calculate meeting quota information for a seller
    
    Args:
        seller_id (int): The user ID of the seller
        seller_profile (SellerProfile): The seller's profile object
        
    Returns:
        dict: A dictionary containing meeting quota information:
            - sellerMeetingRequestQuota: Total allowed meeting requests
            - sellerMeetingQuotaExceeded: Whether the quota is exceeded
            - currentMeetingRequestCount: Current number of active meeting requests
            - remainingMeetingRequestCount: Remaining meeting requests allowed
    """
    # 1. Get all pending meetings for the current seller
    pending_meetings = Meeting.query.filter(
        ((Meeting.seller_id == seller_id) | (Meeting.requestor_id == seller_id)),
        Meeting.status.in_([MeetingStatus.PENDING.value, MeetingStatus.PENDING.value.upper()])
    ).all()
    
    # 2. Check and update expired meetings
    current_time = datetime.now()
    expired_meetings = []
    
    for meeting in pending_meetings:
        # If created_at is null/empty or if it's more than 48 hours old, mark as expired
        if not meeting.created_at or (current_time - meeting.created_at).total_seconds() > 48 * 3600:
            meeting.status = MeetingStatus.EXPIRED.value
            expired_meetings.append(meeting)
    
    # 3. Commit changes if any meetings were updated
    if expired_meetings:
        db.session.commit()
    
    # 4. Count active meetings (ACCEPTED or PENDING)
    currentMeetingRequestCount = Meeting.query.filter(
        ((Meeting.seller_id == seller_id) | (Meeting.requestor_id == seller_id)),
        ((Meeting.status.in_([MeetingStatus.ACCEPTED.value, MeetingStatus.ACCEPTED.value.upper()])) | 
         (Meeting.status.in_([MeetingStatus.PENDING.value, MeetingStatus.PENDING.value.upper()])))
    ).count()
    
    # Count ACCEPTED meetings only
    currentSellerAcceptedMeetingCount = Meeting.query.filter(
        ((Meeting.seller_id == seller_id) | (Meeting.requestor_id == seller_id)),
        (Meeting.status.in_([MeetingStatus.ACCEPTED.value, MeetingStatus.ACCEPTED.value.upper()]))
    ).count()
    
    # 5. Calculate event duration in days
    event_start_date = SystemSetting.query.filter_by(key='event_start_date').first()
    event_end_date = SystemSetting.query.filter_by(key='event_end_date').first()
    
    if event_start_date and event_end_date and event_start_date.value and event_end_date.value:
        try:
            # Parse ISO 8601 format (e.g., 2025-07-11T00:00:00.000Z)
            # First, extract just the date part (YYYY-MM-DD)
            start_date_str = event_start_date.value.split('T')[0]
            end_date_str = event_end_date.value.split('T')[0]
            
            # Then parse with the correct format
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
            
            event_days = (end_date - start_date).days + 1  # +1 to include both start and end days
        except (ValueError, TypeError, IndexError):
            event_days = 3  # Default to 3 days if dates are invalid (typical event duration)
    else:
        event_days = 3  # Default to 3 days if settings are missing (typical event duration)
    
    # 6. Calculate sellerMaxMeetingsPerDay
    # Initialize variables
    seller_max_meetings_per_day = 0
    
    # Get default max meetings per attendee per day from system settings or use default
    max_meetings_setting = SystemSetting.query.filter_by(key='max_seller_attendees_per_day').first()
    max_meetings_per_attendee_per_day = int(max_meetings_setting.value) if max_meetings_setting else 30  # Default to 30
    
    # a. Get all stalls allocated to this seller
    seller_stalls = Stall.query.filter_by(seller_id=seller_id).all()
    
    # b & c. For each stall, calculate max meetings
    for stall in seller_stalls:
        stall_type = stall.stall_type_rel
        
        if stall_type and stall_type.attendees is not None and stall_type.max_meetings_per_attendee is not None and stall_type.max_meetings_per_attendee >= 0:
            # Multiply attendees by max_meetings_per_attendee
            seller_max_meetings_per_day += stall_type.attendees * stall_type.max_meetings_per_attendee
        else:
            # If we have stall_type and attendees but no max_meetings_per_attendee
            if stall_type and stall_type.attendees is not None:
                seller_max_meetings_per_day += stall_type.attendees * max_meetings_per_attendee_per_day
            else:
                # Default case - assume 1 attendee
                seller_max_meetings_per_day += 1 * max_meetings_per_attendee_per_day
    
    # 7. Calculate allowed meeting quota (without multiplying by 2)
    sellerAllowedMeetingQuota = event_days * seller_max_meetings_per_day
    
    # Calculate remaining accept count
    sellerRemainingAcceptCount = max(0, sellerAllowedMeetingQuota - currentSellerAcceptedMeetingCount)
    
    # Determine if seller can accept more meeting requests
    canSellerAcceptMeetingRequest = currentSellerAcceptedMeetingCount < sellerAllowedMeetingQuota
    
    # Calculate total meeting request quota (keep this for backward compatibility)
    sellerMeetingRequestQuota = sellerAllowedMeetingQuota * 2
    
    # 8. Calculate remaining meeting requests
    remainingMeetingRequestCount = max(0, sellerMeetingRequestQuota - currentMeetingRequestCount)
    
    # Return the meeting quota information
    return {
        'sellerMeetingRequestQuota': sellerMeetingRequestQuota,
        'sellerMeetingQuotaExceeded': currentMeetingRequestCount >= sellerMeetingRequestQuota,
        'currentMeetingRequestCount': currentMeetingRequestCount,
        'remainingMeetingRequestCount': remainingMeetingRequestCount,
        'currentSellerAcceptedMeetingCount': currentSellerAcceptedMeetingCount,
        'sellerAllowedMeetingQuota': sellerAllowedMeetingQuota,
        'sellerRemainingAcceptCount': sellerRemainingAcceptCount,
        'canSellerAcceptMeetingRequest': canSellerAcceptMeetingRequest
    }
