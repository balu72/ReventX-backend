from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..utils.auth import admin_required
from ..models import db, Transportation, TravelPlan, BuyerProfile, User, Accommodation, HostProperty, Meeting, TimeSlot, SellerProfile, Stall, MeetingStatus
from sqlalchemy import or_, and_, func, desc, asc
import math

admin_reports = Blueprint('admin_reports', __name__, url_prefix='/api/admin')

@admin_reports.route('/reports/transportation-accommodation', methods=['GET'])
@admin_required
def get_transportation_accommodation_report():
    """
    Get Transportation and Accommodation Report with pagination, filtering, and sorting (admin only)
    """
    try:
        # Get query parameters
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        
        # Filter parameters
        buyer_name = request.args.get('buyer_name', '').strip()
        company_name = request.args.get('company_name', '').strip()
        outbound_details = request.args.get('outbound_details', '').strip()
        return_details = request.args.get('return_details', '').strip()
        property_name = request.args.get('property_name', '').strip()
        
        # Sort parameters
        sort_by = request.args.get('sort_by', '')
        sort_order = request.args.get('sort_order', 'asc')
        
        # Base query
        query = db.session.query(
            Transportation, TravelPlan, BuyerProfile, User, Accommodation, HostProperty
        ).select_from(Transportation)\
        .join(TravelPlan, Transportation.travel_plan_id == TravelPlan.id)\
        .join(BuyerProfile, TravelPlan.user_id == BuyerProfile.user_id)\
        .join(User, BuyerProfile.user_id == User.id)\
        .outerjoin(Accommodation, Accommodation.travel_plan_id == TravelPlan.id)\
        .outerjoin(HostProperty, Accommodation.host_property_id == HostProperty.property_id)
        
        # Apply filters
        filters = []
        if buyer_name:
            filters.append(BuyerProfile.name.ilike(f'%{buyer_name}%'))
        if company_name:
            filters.append(BuyerProfile.organization.ilike(f'%{company_name}%'))
        if outbound_details:
            filters.append(or_(
                Transportation.outbound_carrier.ilike(f'%{outbound_details}%'),
                Transportation.outbound_departure_location.ilike(f'%{outbound_details}%'),
                Transportation.outbound_arrival_location.ilike(f'%{outbound_details}%')
            ))
        if return_details:
            filters.append(or_(
                Transportation.return_carrier.ilike(f'%{return_details}%'),
                Transportation.return_departure_location.ilike(f'%{return_details}%')
            ))
        if property_name:
            filters.append(HostProperty.property_name.ilike(f'%{property_name}%'))
        
        if filters:
            query = query.filter(and_(*filters))
        
        # Get total count before pagination
        total_count = query.count()
        
        # Apply sorting
        if sort_by:
            sort_column = None
            if sort_by == 'buyer_name':
                sort_column = BuyerProfile.name
            elif sort_by == 'company_name':
                sort_column = BuyerProfile.organization
            elif sort_by == 'outbound_departure_date':
                sort_column = Transportation.outbound_departure_datetime
            elif sort_by == 'return_departure_date':
                sort_column = Transportation.return_departure_datetime
            elif sort_by == 'check_in_date':
                sort_column = Accommodation.check_in_datetime
            elif sort_by == 'check_out_date':
                sort_column = Accommodation.check_out_datetime
            
            if sort_column is not None:
                if sort_order.lower() == 'desc':
                    query = query.order_by(desc(sort_column))
                else:
                    query = query.order_by(asc(sort_column))
        
        # Apply pagination
        offset = (page - 1) * per_page
        results = query.offset(offset).limit(per_page).all()
        
        # Process results and format dates in Python
        report_data = []
        for transportation, travel_plan, buyer_profile, user, accommodation, host_property in results:
            row_data = {
                # Transportation ID and Buyer Info
                'transportation_id': transportation.id,
                'buyer_name': buyer_profile.name or '',
                'buyer_company': buyer_profile.organization or '',
                'buyer_email': user.email or '',
                
                # Outbound Transportation Details
                'outbound_type': transportation.outbound_type or '',
                'outbound_carrier': transportation.outbound_carrier or '',
                'outbound_number': transportation.outbound_number or '',
                'outbound_departure_location': transportation.outbound_departure_location or '',
                'outbound_departure_date': transportation.outbound_departure_datetime.strftime('%d/%m/%Y') if transportation.outbound_departure_datetime else '',
                'outbound_departure_time': transportation.outbound_departure_datetime.strftime('%H:%M:%S') if transportation.outbound_departure_datetime else '',
                'outbound_arrival_location': transportation.outbound_arrival_location or '',
                'outbound_booking_reference': transportation.outbound_booking_reference or '',
                'outbound_seat_info': transportation.outbound_seat_info or '',
                
                # Return Transportation Details
                'return_carrier': transportation.return_carrier or '',
                'return_number': transportation.return_number or '',
                'return_departure_location': transportation.return_departure_location or '',
                'return_departure_date': transportation.return_departure_datetime.strftime('%d/%m/%Y') if transportation.return_departure_datetime else '',
                'return_departure_time': transportation.return_departure_datetime.strftime('%H:%M:%S') if transportation.return_departure_datetime else '',
                'return_booking_reference': transportation.return_booking_reference or '',
                'return_seat_info': transportation.return_seat_info or '',
                'return_type': transportation.return_type or '',
                
                # Ticket Information (for View Ticket functionality)
                'arrival_ticket_url': transportation.arrival_ticket or '',
                'return_ticket_url': transportation.return_ticket or '',
                'has_arrival_ticket': bool(transportation.arrival_ticket),
                'has_return_ticket': bool(transportation.return_ticket),
                
                # Accommodation Details (if available)
                'check_in_date': accommodation.check_in_datetime.strftime('%d/%m/%Y') if accommodation and accommodation.check_in_datetime else '',
                'check_in_time': accommodation.check_in_datetime.strftime('%H:%M:%S') if accommodation and accommodation.check_in_datetime else '',
                'check_out_date': accommodation.check_out_datetime.strftime('%d/%m/%Y') if accommodation and accommodation.check_out_datetime else '',
                'check_out_time': accommodation.check_out_datetime.strftime('%H:%M:%S') if accommodation and accommodation.check_out_datetime else '',
                'room_type': accommodation.room_type if accommodation else '',
                'accommodation_booking_reference': accommodation.booking_reference if accommodation else '',
                'special_notes': accommodation.special_notes if accommodation else '',
                
                # Host Property Details (if available)
                'property_name': host_property.property_name if host_property else '',
                'contact_person_name': host_property.contact_person_name if host_property else '',
                'contact_phone': host_property.contact_phone if host_property else '',
                'contact_email': host_property.contact_email if host_property else '',
                'property_address': host_property.property_address if host_property else ''
            }
            
            report_data.append(row_data)
        
        # Calculate pagination metadata
        total_pages = math.ceil(total_count / per_page) if total_count > 0 else 1
        has_next = page < total_pages
        has_previous = page > 1
        
        return jsonify({
            'message': 'Transportation and Accommodation Report generated successfully',
            'data': report_data,
            'pagination': {
                'current_page': page,
                'per_page': per_page,
                'total_records': total_count,
                'total_pages': total_pages,
                'has_next': has_next,
                'has_previous': has_previous
            },
            'filters_applied': {
                'buyer_name': buyer_name,
                'company_name': company_name,
                'outbound_details': outbound_details,
                'return_details': return_details,
                'property_name': property_name
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'error': f'Failed to generate report: {str(e)}',
            'data': [],
            'pagination': {
                'current_page': 1,
                'per_page': per_page,
                'total_records': 0,
                'total_pages': 1,
                'has_next': False,
                'has_previous': False
            },
            'filters_applied': {}
        }), 500

@admin_reports.route('/reports/transportation-accommodation/export', methods=['GET'])
@admin_required
def export_transportation_accommodation_report():
    """
    Export all Transportation and Accommodation Report data (admin only)
    Applies filters but ignores pagination - returns ALL matching records
    """
    try:
        # Filter parameters (same as main endpoint)
        buyer_name = request.args.get('buyer_name', '').strip()
        company_name = request.args.get('company_name', '').strip()
        outbound_details = request.args.get('outbound_details', '').strip()
        return_details = request.args.get('return_details', '').strip()
        property_name = request.args.get('property_name', '').strip()
        
        # Base query (same as main endpoint)
        query = db.session.query(
            Transportation, TravelPlan, BuyerProfile, User, Accommodation, HostProperty
        ).select_from(Transportation)\
        .join(TravelPlan, Transportation.travel_plan_id == TravelPlan.id)\
        .join(BuyerProfile, TravelPlan.user_id == BuyerProfile.user_id)\
        .join(User, BuyerProfile.user_id == User.id)\
        .outerjoin(Accommodation, Accommodation.travel_plan_id == TravelPlan.id)\
        .outerjoin(HostProperty, Accommodation.host_property_id == HostProperty.property_id)
        
        # Apply filters (same as main endpoint)
        filters = []
        if buyer_name:
            filters.append(BuyerProfile.name.ilike(f'%{buyer_name}%'))
        if company_name:
            filters.append(BuyerProfile.organization.ilike(f'%{company_name}%'))
        if outbound_details:
            filters.append(or_(
                Transportation.outbound_carrier.ilike(f'%{outbound_details}%'),
                Transportation.outbound_departure_location.ilike(f'%{outbound_details}%'),
                Transportation.outbound_arrival_location.ilike(f'%{outbound_details}%')
            ))
        if return_details:
            filters.append(or_(
                Transportation.return_carrier.ilike(f'%{return_details}%'),
                Transportation.return_departure_location.ilike(f'%{return_details}%')
            ))
        if property_name:
            filters.append(HostProperty.property_name.ilike(f'%{property_name}%'))
        
        if filters:
            query = query.filter(and_(*filters))
        
        # Get ALL results (no pagination for export)
        results = query.all()
        
        # Process results (same as main endpoint)
        report_data = []
        for transportation, travel_plan, buyer_profile, user, accommodation, host_property in results:
            row_data = {
                # Transportation ID and Buyer Info
                'transportation_id': transportation.id,
                'buyer_name': buyer_profile.name or '',
                'buyer_company': buyer_profile.organization or '',
                'buyer_email': user.email or '',
                
                # Outbound Transportation Details
                'outbound_type': transportation.outbound_type or '',
                'outbound_carrier': transportation.outbound_carrier or '',
                'outbound_number': transportation.outbound_number or '',
                'outbound_departure_location': transportation.outbound_departure_location or '',
                'outbound_departure_date': transportation.outbound_departure_datetime.strftime('%d/%m/%Y') if transportation.outbound_departure_datetime else '',
                'outbound_departure_time': transportation.outbound_departure_datetime.strftime('%H:%M:%S') if transportation.outbound_departure_datetime else '',
                'outbound_arrival_location': transportation.outbound_arrival_location or '',
                'outbound_booking_reference': transportation.outbound_booking_reference or '',
                'outbound_seat_info': transportation.outbound_seat_info or '',
                
                # Return Transportation Details
                'return_carrier': transportation.return_carrier or '',
                'return_number': transportation.return_number or '',
                'return_departure_location': transportation.return_departure_location or '',
                'return_departure_date': transportation.return_departure_datetime.strftime('%d/%m/%Y') if transportation.return_departure_datetime else '',
                'return_departure_time': transportation.return_departure_datetime.strftime('%H:%M:%S') if transportation.return_departure_datetime else '',
                'return_booking_reference': transportation.return_booking_reference or '',
                'return_seat_info': transportation.return_seat_info or '',
                'return_type': transportation.return_type or '',
                
                # Ticket Information (for View Ticket functionality)
                'arrival_ticket_url': transportation.arrival_ticket or '',
                'return_ticket_url': transportation.return_ticket or '',
                'has_arrival_ticket': bool(transportation.arrival_ticket),
                'has_return_ticket': bool(transportation.return_ticket),
                
                # Accommodation Details (if available)
                'check_in_date': accommodation.check_in_datetime.strftime('%d/%m/%Y') if accommodation and accommodation.check_in_datetime else '',
                'check_in_time': accommodation.check_in_datetime.strftime('%H:%M:%S') if accommodation and accommodation.check_in_datetime else '',
                'check_out_date': accommodation.check_out_datetime.strftime('%d/%m/%Y') if accommodation and accommodation.check_out_datetime else '',
                'check_out_time': accommodation.check_out_datetime.strftime('%H:%M:%S') if accommodation and accommodation.check_out_datetime else '',
                'room_type': accommodation.room_type if accommodation else '',
                'accommodation_booking_reference': accommodation.booking_reference if accommodation else '',
                'special_notes': accommodation.special_notes if accommodation else '',
                
                # Host Property Details (if available)
                'property_name': host_property.property_name if host_property else '',
                'contact_person_name': host_property.contact_person_name if host_property else '',
                'contact_phone': host_property.contact_phone if host_property else '',
                'contact_email': host_property.contact_email if host_property else '',
                'property_address': host_property.property_address if host_property else ''
            }
            
            report_data.append(row_data)
        
        return jsonify({
            'message': 'Export data generated successfully',
            'data': report_data,
            'total_records': len(report_data)
        }), 200
        
    except Exception as e:
        return jsonify({
            'error': f'Failed to generate export data: {str(e)}',
            'data': [],
            'total_records': 0
        }), 500

@admin_reports.route('/reports/buyer-meetings-export', methods=['GET'])
@admin_required
def get_buyer_meetings_export():
    """
    Get all buyers with their meetings for bulk PDF export (admin only)
    Returns structured data for frontend PDF generation
    """
    try:
        # Query all buyers with their basic information
        buyers_query = db.session.query(BuyerProfile, User)\
            .join(User, BuyerProfile.user_id == User.id)\
            .filter(User.role == 'buyer')\
            .order_by(BuyerProfile.name)
        
        buyers_data = []
        total_meetings = 0
        
        for buyer_profile, user in buyers_query.all():
            # Get all accepted meetings for this buyer
            meetings_query = db.session.query(Meeting, TimeSlot, SellerProfile, Stall)\
                .outerjoin(TimeSlot, Meeting.time_slot_id == TimeSlot.id)\
                .outerjoin(SellerProfile, SellerProfile.user_id == Meeting.seller_id)\
                .outerjoin(Stall, Stall.seller_id == Meeting.seller_id)\
                .filter(Meeting.buyer_id == user.id)\
                .filter(Meeting.status == MeetingStatus.ACCEPTED)\
                .order_by(TimeSlot.start_time.asc().nullslast())
            
            meetings = []
            for meeting, time_slot, seller_profile, stall in meetings_query.all():
                # Format meeting time
                meeting_time = "Not scheduled"
                if time_slot:
                    start_time = time_slot.start_time.strftime('%I:%M %p') if time_slot.start_time else ""
                    end_time = time_slot.end_time.strftime('%I:%M %p') if time_slot.end_time else ""
                    if start_time and end_time:
                        meeting_time = f"{start_time} - {end_time}"
                elif hasattr(meeting, 'meeting_date') and meeting.meeting_date and hasattr(meeting, 'meeting_time') and meeting.meeting_time:
                    # Use meeting date/time if available
                    meeting_time = f"{meeting.meeting_date.strftime('%d/%m/%Y')} {meeting.meeting_time.strftime('%I:%M %p')}"
                
                # Get seller name
                seller_name = "Unknown Seller"
                if seller_profile:
                    if hasattr(seller_profile, 'business_name') and seller_profile.business_name:
                        seller_name = seller_profile.business_name
                    elif hasattr(seller_profile, 'company_name') and seller_profile.company_name:
                        seller_name = seller_profile.company_name
                
                # Get stall number
                stall_number = "Not assigned"
                if stall:
                    if hasattr(stall, 'allocated_stall_number') and stall.allocated_stall_number:
                        stall_number = stall.allocated_stall_number
                    elif hasattr(stall, 'number') and stall.number:
                        stall_number = stall.number
                
                meetings.append({
                    'meeting_time': meeting_time,
                    'stall_number': stall_number,
                    'seller_name': seller_name,
                    'notes': meeting.notes or "",
                    'status': meeting.status.value if meeting.status else "pending"
                })
            
            # Only add buyers who have accepted meetings
            if meetings:
                buyers_data.append({
                    'buyer_id': user.id,
                    'buyer_name': buyer_profile.name or "Unknown",
                    'buyer_organization': buyer_profile.organization or "Unknown Organization",
                    'meetings': meetings
                })
                
                total_meetings += len(meetings)
        
        return jsonify({
            'message': 'Buyer meetings export data generated successfully',
            'buyers': buyers_data,
            'total_buyers': len(buyers_data),
            'total_meetings': total_meetings
        }), 200
        
    except Exception as e:
        return jsonify({
            'error': f'Failed to generate buyer meetings export data: {str(e)}',
            'buyers': [],
            'total_buyers': 0,
            'total_meetings': 0
        }), 500
