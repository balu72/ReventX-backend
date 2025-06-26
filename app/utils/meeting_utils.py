from datetime import datetime
from ..models import db, Meeting, MeetingStatus, BuyerCategory, SystemSetting

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
        Meeting.status == MeetingStatus.PENDING.value
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
        ((Meeting.status == MeetingStatus.ACCEPTED.value) | (Meeting.status == MeetingStatus.PENDING.value))
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
            start_date = datetime.strptime(event_start_date.value, '%Y-%m-%d')
            end_date = datetime.strptime(event_end_date.value, '%Y-%m-%d')
            event_days = (end_date - start_date).days + 1  # +1 to include both start and end days
        except (ValueError, TypeError):
            event_days = 1  # Default to 1 day if dates are invalid
    else:
        event_days = 1  # Default to 1 day if settings are missing
    
    # 7. Calculate total allowed meeting requests
    buyerMeetingRequestQuota = 2 * max_meetings_per_day * event_days
    
    # 8. Calculate remaining meeting requests
    remainingMeetingRequestCount = max(0, buyerMeetingRequestQuota - currentMeetingRequestCount)
    
    # Return the meeting quota information
    return {
        'buyerMeetingRequestQuota': buyerMeetingRequestQuota,
        'buyerMeetingQuotaExceeded': currentMeetingRequestCount >= buyerMeetingRequestQuota,
        'currentMeetingRequestCount': currentMeetingRequestCount,
        'remainingMeetingRequestCount': remainingMeetingRequestCount
    }
