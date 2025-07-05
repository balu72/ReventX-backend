from datetime import datetime
from ..models import db, Meeting, MeetingStatus, BuyerCategory, SystemSetting, Stall
from collections import defaultdict

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
            meeting.status = MeetingStatus.EXPIRED
            expired_meetings.append(meeting)
    
    # 3. Commit changes if any meetings were updated
    if expired_meetings:
        db.session.commit()
    
    # 4. Count pending meetings after expiration cleanup
    currentPendingMeetingCount = Meeting.query.filter(
        ((Meeting.buyer_id == user_id) | (Meeting.requestor_id == user_id)),
        Meeting.status.in_([MeetingStatus.PENDING.value, MeetingStatus.PENDING.value.upper()])
    ).count()
    
    # Count active meetings (ACCEPTED or PENDING)
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
    
    # 7. Calculate allowed meeting quota - A buyer will attend only one day so we don't multiply by event_days
    buyerAllowedMeetingQuota = max_meetings_per_day  # * event_days
    
    # Calculate remaining accept count
    buyerRemainingAcceptCount = max(0, buyerAllowedMeetingQuota - currentBuyerAcceptedMeetingCount)
    
    # Determine if buyer can accept more meeting requests
    canBuyerAcceptMeetingRequest = currentBuyerAcceptedMeetingCount < buyerAllowedMeetingQuota
    
    # Calculate total meeting request quota - Allowed requests is twice the allowed meetings
    buyerMeetingRequestQuota = buyerAllowedMeetingQuota * 2
    
    # 8. Calculate remaining meeting requests using new formula
    remainingMeetingRequestCount = max(0, buyerMeetingRequestQuota - (2 * currentBuyerAcceptedMeetingCount) - currentPendingMeetingCount)
    
    # Return the meeting quota information
    return {
        'buyerMeetingRequestQuota': buyerMeetingRequestQuota,
        'buyerMeetingQuotaExceeded': currentMeetingRequestCount >= buyerMeetingRequestQuota,
        'currentMeetingRequestCount': currentMeetingRequestCount,
        'remainingMeetingRequestCount': remainingMeetingRequestCount,
        'currentBuyerAcceptedMeetingCount': currentBuyerAcceptedMeetingCount,
        'buyerAllowedMeetingQuota': buyerAllowedMeetingQuota,
        'buyerRemainingAcceptCount': buyerRemainingAcceptCount,
        'canBuyerAcceptMeetingRequest': canBuyerAcceptMeetingRequest,
        'buyerPendingMeetingRequestCount': currentPendingMeetingCount
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
            meeting.status = MeetingStatus.EXPIRED
            expired_meetings.append(meeting)
    
    # 3. Commit changes if any meetings were updated
    if expired_meetings:
        db.session.commit()
    
    # 4. Count pending meetings after expiration cleanup
    currentPendingMeetingCount = Meeting.query.filter(
        ((Meeting.seller_id == seller_id) | (Meeting.requestor_id == seller_id)),
        Meeting.status.in_([MeetingStatus.PENDING.value, MeetingStatus.PENDING.value.upper()])
    ).count()
    
    # Count active meetings (ACCEPTED or PENDING)
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
    
    # 8. Calculate remaining meeting requests using new formula
    remainingMeetingRequestCount = max(0, sellerMeetingRequestQuota - (2 * currentSellerAcceptedMeetingCount) - currentPendingMeetingCount)
    
    # Return the meeting quota information
    return {
        'sellerMeetingRequestQuota': sellerMeetingRequestQuota,
        'sellerMeetingQuotaExceeded': currentMeetingRequestCount >= sellerMeetingRequestQuota,
        'currentMeetingRequestCount': currentMeetingRequestCount,
        'remainingMeetingRequestCount': remainingMeetingRequestCount,
        'currentSellerAcceptedMeetingCount': currentSellerAcceptedMeetingCount,
        'sellerAllowedMeetingQuota': sellerAllowedMeetingQuota,
        'sellerRemainingAcceptCount': sellerRemainingAcceptCount,
        'canSellerAcceptMeetingRequest': canSellerAcceptMeetingRequest,
        'sellerPendingMeetingRequestCount': currentPendingMeetingCount
    }


def batch_calculate_buyer_meeting_quota(buyer_profiles):
    """
    Calculate meeting quota information for multiple buyers in a single database query
    
    Args:
        buyer_profiles (list): List of BuyerProfile objects
        
    Returns:
        list: Updated buyer_profiles with quota information added to each profile
    """
    if not buyer_profiles:
        return buyer_profiles
    
    # Extract all user_ids from buyer profiles
    all_user_ids = [profile.user_id for profile in buyer_profiles]
    
    # Single query to get all meetings for all buyers (only buyer_id filter)
    all_meetings = Meeting.query.filter(
        Meeting.buyer_id.in_(all_user_ids)
    ).all()
    
    # Get system settings once (shared across all buyers)
    event_start_date = SystemSetting.query.filter_by(key='event_start_date').first()
    event_end_date = SystemSetting.query.filter_by(key='event_end_date').first()
    max_seller_attendees_setting = SystemSetting.query.filter_by(key='max_seller_attendees_per_day').first()
    
    # Calculate event duration once
    if event_start_date and event_end_date and event_start_date.value and event_end_date.value:
        try:
            start_date_str = event_start_date.value.split('T')[0]
            end_date_str = event_end_date.value.split('T')[0]
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
            event_days = (end_date - start_date).days + 1
        except (ValueError, TypeError, IndexError):
            event_days = 3
    else:
        event_days = 3
    
    # Group meetings by buyer_id for efficient processing
    meetings_by_buyer = defaultdict(list)
    for meeting in all_meetings:
        meetings_by_buyer[meeting.buyer_id].append(meeting)
    
    # Get buyer categories once for all buyers that have category_id
    category_ids = [profile.category_id for profile in buyer_profiles if profile.category_id]
    buyer_categories = {}
    if category_ids:
        categories = BuyerCategory.query.filter(BuyerCategory.id.in_(category_ids)).all()
        buyer_categories = {cat.id: cat for cat in categories}
    
    # Process expired meetings in batch
    current_time = datetime.now()
    expired_meetings = []
    
    for meeting in all_meetings:
        if (meeting.status in [MeetingStatus.PENDING.value, MeetingStatus.PENDING.value.upper()] and
            (not meeting.created_at or (current_time - meeting.created_at).total_seconds() > 48 * 3600)):
            meeting.status = MeetingStatus.EXPIRED
            expired_meetings.append(meeting)
    
    # Commit expired meetings changes if any
    if expired_meetings:
        db.session.commit()
    
    # Process each buyer profile and calculate quota
    for profile in buyer_profiles:
        buyer_meetings = meetings_by_buyer.get(profile.user_id, [])
        
        # Count meetings by status after expiration cleanup
        pending_count = 0
        accepted_count = 0
        active_count = 0
        
        for meeting in buyer_meetings:
            status_upper = meeting.status.upper() if meeting.status else ''
            
            if status_upper == MeetingStatus.PENDING.value.upper():
                pending_count += 1
                active_count += 1
            elif status_upper == MeetingStatus.ACCEPTED.value.upper():
                accepted_count += 1
                active_count += 1
        
        # Get max meetings allowed based on buyer category
        if profile.category_id and profile.category_id in buyer_categories:
            buyer_category = buyer_categories[profile.category_id]
            max_meetings_per_category = buyer_category.max_meetings if buyer_category else -1
        else:
            max_meetings_per_category = -1
        
        # If category doesn't specify max meetings or value is negative, use system setting
        if max_meetings_per_category is None or max_meetings_per_category < 0:
            max_meetings_per_day = int(max_seller_attendees_setting.value) if max_seller_attendees_setting else 30
        else:
            max_meetings_per_day = max_meetings_per_category
        
        # Calculate allowed meeting quota - A buyer will attend only one day so we don't multiply by event_days
        buyerAllowedMeetingQuota = max_meetings_per_day
        
        # Calculate remaining accept count
        buyerRemainingAcceptCount = max(0, buyerAllowedMeetingQuota - accepted_count)
        
        # Determine if buyer can accept more meeting requests
        canBuyerAcceptMeetingRequest = accepted_count < buyerAllowedMeetingQuota
        
        # Calculate total meeting request quota - Allowed requests is twice the allowed meetings
        buyerMeetingRequestQuota = buyerAllowedMeetingQuota * 2
        
        # Calculate remaining meeting requests using new formula
        remainingMeetingRequestCount = max(0, buyerMeetingRequestQuota - (2 * accepted_count) - pending_count)
        
        # Add quota information to the buyer profile
        quota_info = {
            'buyerMeetingRequestQuota': buyerMeetingRequestQuota,
            'buyerMeetingQuotaExceeded': active_count >= buyerMeetingRequestQuota,
            'currentMeetingRequestCount': active_count,
            'remainingMeetingRequestCount': remainingMeetingRequestCount,
            'currentBuyerAcceptedMeetingCount': accepted_count,
            'buyerAllowedMeetingQuota': buyerAllowedMeetingQuota,
            'buyerRemainingAcceptCount': buyerRemainingAcceptCount,
            'canBuyerAcceptMeetingRequest': canBuyerAcceptMeetingRequest,
            'buyerPendingMeetingRequestCount': pending_count
        }
        
        # Store quota info as an attribute on the profile object
        profile.quota_info = quota_info
    
    return buyer_profiles
