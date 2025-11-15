"""
Context management for chatbot - gathers user-specific data
"""
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from ..models import (
    db, User, BuyerProfile, SellerProfile, Meeting, TravelPlan, Stall,
    BuyerCategory, SellerAttendee, GroundTransportation, 
    BuyerFinancialInfo, SellerFinancialInfo, Accommodation,
    TimeSlot, BuyerBankDetails
)

class ChatbotContext:
    """Manages context for chatbot conversations"""
    
    @staticmethod
    def get_user_context(user_id: int) -> Dict:
        user = User.query.get(user_id)
        if not user:
            return {}
        
        context = {
            'user_id': user.id,
            'user_role': user.role,
            'username': user.username,
            'email': user.email
        }
        
        if user.role == 'buyer':
            context.update(ChatbotContext._get_buyer_context(user))
        elif user.role == 'seller':
            context.update(ChatbotContext._get_seller_context(user))
        
        return context
    
    @staticmethod
    def _get_buyer_context(user: User) -> Dict:
        context = {}
        buyer_profile = user.buyer_profile
        if buyer_profile:
            context['user_name'] = buyer_profile.name
            context['organization'] = buyer_profile.organization
        return context
    
    @staticmethod
    def _get_seller_context(user: User) -> Dict:
        context = {}
        seller_profile = user.seller_profile
        if seller_profile:
            context['user_name'] = f"{seller_profile.first_name or ''} {seller_profile.last_name or ''}".strip()
            context['business_name'] = seller_profile.business_name
            context['organization'] = seller_profile.business_name
        return context
    
    @staticmethod
    def get_meeting_details(user_id: int, user_role: str, meeting_id: Optional[int] = None) -> Dict:
        query = Meeting.query
        if user_role == 'buyer':
            query = query.filter_by(buyer_id=user_id)
        elif user_role == 'seller':
            query = query.filter_by(seller_id=user_id)
        
        total_count = query.count()
        
        if meeting_id:
            meeting = query.filter_by(id=meeting_id).first()
            meetings = [meeting] if meeting else []
        else:
            meetings = query.order_by(Meeting.meeting_date.desc(), Meeting.meeting_time.desc()).all()
        
        return {
            'count': total_count,
            'meetings': [
                {
                    'id': m.id,
                    'partner_name': (m.buyer.buyer_profile.organization if user_role == 'seller' and m.buyer and m.buyer.buyer_profile 
                                   else m.seller.seller_profile.business_name if user_role == 'buyer' and m.seller and m.seller.seller_profile 
                                   else 'Unknown'),
                    'status': m.status.value,
                    'date': m.meeting_date.isoformat() if m.meeting_date else None,
                    'time': m.meeting_time.isoformat() if m.meeting_time else None,
                    'notes': m.notes
                }
                for m in meetings
            ]
        }
    
    @staticmethod
    def get_time_slots(user_id: int, user_role: str, available_only: bool = False) -> Dict:
        """Get time slots for a user (for scheduling meetings)"""
        query = TimeSlot.query.filter_by(user_id=user_id)
        
        if available_only:
            query = query.filter_by(is_available=True)
        
        # Get slots ordered by start time
        slots = query.order_by(TimeSlot.start_time).all()
        
        # Separate into available and booked
        available_slots = []
        booked_slots = []
        now = datetime.now()
        
        for slot in slots:
            slot_data = {
                'id': slot.id,
                'start_time': slot.start_time.isoformat() if slot.start_time else None,
                'end_time': slot.end_time.isoformat() if slot.end_time else None,
                'is_available': slot.is_available,
                'meeting_id': slot.meeting_id,
                'is_past': slot.start_time < now if slot.start_time else False
            }
            
            if slot.is_available:
                available_slots.append(slot_data)
            else:
                booked_slots.append(slot_data)
        
        return {
            'total_slots': len(slots),
            'available_count': len(available_slots),
            'booked_count': len(booked_slots),
            'available_slots': available_slots,
            'booked_slots': booked_slots
        }
    
    @staticmethod
    def get_detailed_accommodation(user_id: int) -> Optional[Dict]:
        """Get detailed accommodation information with property contacts"""
        travel_plan = TravelPlan.query.filter_by(user_id=user_id).first()
        
        if not travel_plan or not travel_plan.accommodation:
            return None
        
        acc = travel_plan.accommodation
        host_property = acc.host_property if acc else None
        
        return {
            'property_name': host_property.property_name if host_property else None,
            'property_address': host_property.property_address if host_property else None,
            'contact_person': host_property.contact_person_name if host_property else None,
            'contact_phone': host_property.contact_phone if host_property else None,
            'contact_email': host_property.contact_email if host_property else None,
            'check_in_datetime': acc.check_in_datetime.isoformat() if acc.check_in_datetime else None,
            'check_out_datetime': acc.check_out_datetime.isoformat() if acc.check_out_datetime else None,
            'room_type': acc.room_type if acc else None,
            'booking_reference': acc.booking_reference if acc else None,
            'special_notes': acc.special_notes if acc else None,
            'rooms_allotted': host_property.rooms_allotted if host_property else None,
            'property_id': host_property.property_id if host_property else None
        }
    
    @staticmethod
    def get_bank_details(user_id: int) -> Optional[Dict]:
        """Get bank details for a buyer (for refund/payment queries)"""
        bank_details = BuyerBankDetails.query.filter_by(buyer_id=user_id).first()
        
        if not bank_details:
            return None
        
        return {
            'bank_name': bank_details.bank_name,
            'bank_branch': bank_details.bank_branch,
            'bank_city': bank_details.bank_city,
            'bank_state': bank_details.bank_state,
            'bank_address': bank_details.bank_address,
            'ifsc_code': bank_details.ifsc_code,
            'account_holder_name': bank_details.account_holder_name,
            'account_type': bank_details.account_type,
            # Don't expose full account number for security - only show last 4 digits
            'account_number_last4': bank_details.account_number[-4:] if bank_details.account_number else None,
            'account_number_available': bool(bank_details.account_number),
            'payment_methods': {
                'imps_enabled': bank_details.imps_enabled,
                'neft_enabled': bank_details.neft_enabled,
                'rtgs_enabled': bank_details.rtgs_enabled,
                'upi_enabled': bank_details.upi_enabled
            }
        }
    
    @staticmethod
    def get_stall_info(user_id: int) -> Optional[Dict]:
        """Get stall information for a seller"""
        stall = Stall.query.filter_by(seller_id=user_id).first()
        
        if not stall:
            return None
        
        return {
            'id': stall.id,
            'number': stall.number,
            'allocated_stall_number': stall.allocated_stall_number,
            'fascia_name': stall.fascia_name,
            'is_allocated': stall.is_allocated,
            'stall_type': {
                'name': stall.stall_type_rel.name if stall.stall_type_rel else None,
                'size': stall.stall_type_rel.size if stall.stall_type_rel else None,
                'price': float(stall.stall_type_rel.price) if stall.stall_type_rel and stall.stall_type_rel.price else None,
                'attendees': stall.stall_type_rel.attendees if stall.stall_type_rel else None,
                'max_meetings_per_attendee': stall.stall_type_rel.max_meetings_per_attendee if stall.stall_type_rel else None,
                'min_meetings_per_attendee': stall.stall_type_rel.min_meetings_per_attendee if stall.stall_type_rel else None,
                'inclusions': stall.stall_type_rel.inclusions if stall.stall_type_rel else None,
                'dinner_passes': stall.stall_type_rel.dinner_passes if stall.stall_type_rel else None
            } if stall.stall_type_rel else None
        }
    
    @staticmethod
    def get_meeting_statistics(user_id: int, user_role: str) -> Dict:
        """Get meeting statistics broken down by status"""
        from ..models import MeetingStatus
        
        query = Meeting.query
        if user_role == 'buyer':
            query = query.filter_by(buyer_id=user_id)
        elif user_role == 'seller':
            query = query.filter_by(seller_id=user_id)
        
        all_meetings = query.all()
        
        # Count by status
        status_counts = {
            'pending': 0,
            'accepted': 0,
            'rejected': 0,
            'completed': 0,
            'cancelled': 0,
            'expired': 0,
            'unscheduled_completed': 0
        }
        
        upcoming_meetings = []
        past_meetings = []
        now = datetime.now()
        
        for meeting in all_meetings:
            status_counts[meeting.status.value] += 1
            
            # Categorize as upcoming or past
            if meeting.meeting_date:
                meeting_datetime = datetime.combine(meeting.meeting_date, meeting.meeting_time) if meeting.meeting_time else datetime.combine(meeting.meeting_date, datetime.min.time())
                if meeting_datetime >= now and meeting.status.value not in ['cancelled', 'rejected', 'completed']:
                    upcoming_meetings.append(meeting)
                elif meeting_datetime < now or meeting.status.value in ['completed', 'cancelled']:
                    past_meetings.append(meeting)
        
        return {
            'total': len(all_meetings),
            'by_status': status_counts,
            'upcoming_count': len(upcoming_meetings),
            'past_count': len(past_meetings),
            'action_required': status_counts['pending'] if user_role == 'seller' else 0
        }
    
    @staticmethod
    def get_category_info(user_id: int) -> Optional[Dict]:
        """Get buyer category information"""
        user = User.query.get(user_id)
        if not user or not user.buyer_profile or not user.buyer_profile.category:
            return None
        
        category = user.buyer_profile.category
        
        return {
            'name': category.name,
            'deposit_amount': float(category.deposit_amount) if category.deposit_amount else None,
            'entry_fee': float(category.entry_fee) if category.entry_fee else None,
            'accommodation_hosted': category.accommodation_hosted,
            'transfers_hosted': category.transfers_hosted,
            'max_meetings': category.max_meetings,
            'min_meetings': category.min_meetings
        }
    
    @staticmethod
    def get_ground_transportation(user_id: int) -> Optional[Dict]:
        """Get ground transportation details"""
        travel_plan = TravelPlan.query.filter_by(user_id=user_id).first()
        
        if not travel_plan or not travel_plan.ground_transportation:
            return None
        
        gt = travel_plan.ground_transportation
        
        return {
            'pickup': {
                'location': gt.pickup_location,
                'datetime': gt.pickup_datetime.isoformat() if gt.pickup_datetime else None,
                'vehicle_type': gt.pickup_transport.transport_type if gt.pickup_transport else None,
                'vehicle_capacity': gt.pickup_transport.capacity if gt.pickup_transport else None,
                'driver_contact': gt.pickup_driver_contact
            },
            'dropoff': {
                'location': gt.dropoff_location,
                'datetime': gt.dropoff_datetime.isoformat() if gt.dropoff_datetime else None,
                'vehicle_type': gt.dropoff_transport.transport_type if gt.dropoff_transport else None,
                'vehicle_capacity': gt.dropoff_transport.capacity if gt.dropoff_transport else None,
                'driver_contact': gt.dropoff_driver_contact
            }
        }
    
    @staticmethod
    def get_financial_status(user_id: int, user_role: str) -> Optional[Dict]:
        """Get payment/financial status"""
        if user_role == 'buyer':
            user = User.query.get(user_id)
            if not user or not user.buyer_profile:
                return None
            
            financial_info = BuyerFinancialInfo.query.filter_by(
                buyer_profile_id=user.buyer_profile.id
            ).first()
            
            if not financial_info:
                return None
            
            return {
                'deposit_paid': financial_info.deposit_paid,
                'entry_fee_paid': financial_info.entry_fee_paid,
                'deposit_amount': float(financial_info.deposit_amount) if financial_info.deposit_amount else None,
                'entry_fee_amount': float(financial_info.entry_fee_amount) if financial_info.entry_fee_amount else None,
                'payment_date': financial_info.payment_date.isoformat() if financial_info.payment_date else None
            }
        
        elif user_role == 'seller':
            user = User.query.get(user_id)
            if not user or not user.seller_profile:
                return None
            
            financial_info = SellerFinancialInfo.query.filter_by(
                seller_profile_id=user.seller_profile.id
            ).first()
            
            if not financial_info:
                return None
            
            return {
                'deposit_paid': financial_info.deposit_paid,
                'total_amt_due': float(financial_info.total_amt_due) if financial_info.total_amt_due else None,
                'total_amt_paid': float(financial_info.total_amt_paid) if financial_info.total_amt_paid else None,
                'subscription_uptodate': financial_info.subscription_uptodate,
                'additional_seller_passes': financial_info.actual_additional_seller_passes
            }
        
        return None
    
    @staticmethod
    def get_attendees_info(user_id: int) -> List[Dict]:
        """Get seller attendee information"""
        user = User.query.get(user_id)
        if not user or not user.seller_profile:
            return []
        
        attendees = SellerAttendee.query.filter_by(
            seller_profile_id=user.seller_profile.id
        ).all()
        
        return [
            {
                'attendee_number': a.attendee_number,
                'name': a.name,
                'designation': a.designation,
                'email': a.email,
                'mobile': a.mobile,
                'is_primary_contact': a.is_primary_contact
            }
            for a in attendees
        ]
    
    @staticmethod
    def get_travel_details(user_id: int) -> Optional[Dict]:
        """Get travel plan details for a user"""
        travel_plan = TravelPlan.query.filter_by(user_id=user_id).first()
        
        if not travel_plan:
            return None
        
        return {
            'event_name': travel_plan.event_name,
            'event_dates': {
                'start': travel_plan.event_start_date.isoformat() if travel_plan.event_start_date else None,
                'end': travel_plan.event_end_date.isoformat() if travel_plan.event_end_date else None
            },
            'venue': travel_plan.venue,
            'status': travel_plan.status,
            'transportation': {
                'outbound': {
                    'carrier': travel_plan.transportation.outbound_carrier,
                    'number': travel_plan.transportation.outbound_number,
                    'departure_location': travel_plan.transportation.outbound_departure_location,
                    'departure_datetime': travel_plan.transportation.outbound_departure_datetime.isoformat() if travel_plan.transportation.outbound_departure_datetime else None,
                    'arrival_location': travel_plan.transportation.outbound_arrival_location,
                    'arrival_datetime': travel_plan.transportation.outbound_arrival_datetime.isoformat() if travel_plan.transportation.outbound_arrival_datetime else None
                },
                'return': {
                    'carrier': travel_plan.transportation.return_carrier,
                    'number': travel_plan.transportation.return_number,
                    'departure_location': travel_plan.transportation.return_departure_location,
                    'departure_datetime': travel_plan.transportation.return_departure_datetime.isoformat() if travel_plan.transportation.return_departure_datetime else None,
                    'arrival_location': travel_plan.transportation.return_arrival_location,
                    'arrival_datetime': travel_plan.transportation.return_arrival_datetime.isoformat() if travel_plan.transportation.return_arrival_datetime else None
                }
            } if travel_plan.transportation else None,
            'accommodation': {
                'property_name': travel_plan.accommodation.host_property.property_name if travel_plan.accommodation and travel_plan.accommodation.host_property else None,
                'check_in': travel_plan.accommodation.check_in_datetime.isoformat() if travel_plan.accommodation and travel_plan.accommodation.check_in_datetime else None,
                'check_out': travel_plan.accommodation.check_out_datetime.isoformat() if travel_plan.accommodation and travel_plan.accommodation.check_out_datetime else None,
                'room_type': travel_plan.accommodation.room_type if travel_plan.accommodation else None
            } if travel_plan.accommodation else None
        }
    
    @staticmethod
    def search_sellers(query: str, limit: int = 5) -> Dict:
        """Search for sellers by name or business name"""
        search_pattern = f"%{query}%"
        
        sellers = SellerProfile.query.filter(
            db.or_(
                SellerProfile.business_name.ilike(search_pattern),
                SellerProfile.first_name.ilike(search_pattern),
                SellerProfile.last_name.ilike(search_pattern),
                SellerProfile.description.ilike(search_pattern)
            )
        ).filter_by(status='active').limit(limit).all()
        
        return {
            'count': len(sellers),
            'sellers': [
                {
                    'id': s.id,
                    'user_id': s.user_id,
                    'business_name': s.business_name,
                    'description': s.description,
                    'seller_type': s.seller_type,
                    'property_type': s.property_type.name if s.property_type else None,
                    'website': s.website,
                    'instagram': s.instagram
                }
                for s in sellers
            ]
        }

    @staticmethod
    def search_meetings_by_company(user_id: int, user_role: str, company_name: str) -> Dict:
        """Search meetings by company/organization name"""
        from ..models import BuyerProfile, SellerProfile
        
        search_pattern = f"%{company_name}%"
        query = Meeting.query
        
        if user_role == 'seller':
            query = query.join(User, Meeting.buyer_id == User.id).join(BuyerProfile, User.id == BuyerProfile.user_id).filter(Meeting.seller_id == user_id).filter(BuyerProfile.organization.ilike(search_pattern))
        elif user_role == 'buyer':
            query = query.join(User, Meeting.seller_id == User.id).join(SellerProfile, User.id == SellerProfile.user_id).filter(Meeting.buyer_id == user_id).filter(SellerProfile.business_name.ilike(search_pattern))
        
        meetings = query.all()
        
        return {
            'count': len(meetings),
            'meetings': [
                {
                    'id': m.id,
                    'partner_name': (m.buyer.buyer_profile.organization if user_role == 'seller' and m.buyer and m.buyer.buyer_profile else m.seller.seller_profile.business_name if user_role == 'buyer' and m.seller and m.seller.seller_profile else 'Unknown'),
                    'status': m.status.value,
                    'date': m.meeting_date.isoformat() if m.meeting_date else None,
                    'time': m.meeting_time.isoformat() if m.meeting_time else None,
                    'notes': m.notes
                }
                for m in meetings
            ]
        }
