from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from datetime import datetime
import enum

db = SQLAlchemy()
bcrypt = Bcrypt()

class UserRole(enum.Enum):
    BUYER = "buyer"
    SELLER = "seller"
    ADMIN = "admin"

class MeetingStatus(enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"

class ListingStatus(enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"

# Enhanced Models for the new schema

# Association tables for many-to-many relationships
buyer_profile_interests = db.Table('buyer_profile_interests',
    db.Column('buyer_profile_id', db.Integer, db.ForeignKey('buyer_profiles.id'), primary_key=True),
    db.Column('interest_id', db.Integer, db.ForeignKey('interests.id'), primary_key=True)
)

seller_target_markets = db.Table('seller_target_markets',
    db.Column('seller_profile_id', db.Integer, db.ForeignKey('seller_profiles.id'), primary_key=True),
    db.Column('interest_id', db.Integer, db.ForeignKey('interests.id'), primary_key=True)
)

class BuyerCategory(db.Model):
    __tablename__ = 'buyer_categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    deposit_amount = db.Column(db.Numeric(10, 2))
    entry_fee = db.Column(db.Numeric(10, 2))
    accommodation_hosted = db.Column(db.Boolean, default=False)
    transfers_hosted = db.Column(db.Boolean, default=False)
    max_meetings = db.Column(db.Integer)
    min_meetings = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'deposit_amount': float(self.deposit_amount) if self.deposit_amount else None,
            'entry_fee': float(self.entry_fee) if self.entry_fee else None,
            'accommodation_hosted': self.accommodation_hosted,
            'transfers_hosted': self.transfers_hosted,
            'max_meetings': self.max_meetings,
            'min_meetings': self.min_meetings,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class PropertyType(db.Model):
    __tablename__ = 'property_types'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description
        }

class HostProperty(db.Model):
    __tablename__ = 'host_properties'
    
    property_id = db.Column(db.Integer, primary_key=True)
    property_name = db.Column(db.String(100), nullable=False)
    rooms_allotted = db.Column(db.Integer, nullable=False)
    number_rooms_allocated = db.Column(db.Integer, default=0)
    contact_person_name = db.Column(db.String(100), nullable=True)
    contact_phone = db.Column(db.String(50), nullable=True)
    contact_email = db.Column(db.String(100), nullable=True)
    property_address = db.Column(db.String(200), nullable=True)
    number_current_guests = db.Column(db.Integer, nullable=True)
    
    def to_dict(self):
        return {
            'property_id': self.property_id,
            'property_name': self.property_name,
            'rooms_allotted': self.rooms_allotted,
            'number_rooms_allocated': self.number_rooms_allocated,
            'contact_person_name': self.contact_person_name,
            'contact_phone': self.contact_phone,
            'contact_email': self.contact_email,
            'property_address': self.property_address,
            'number_current_guests': self.number_current_guests
        }

class TransportType(db.Model):
    __tablename__ = 'transport_types'
    
    transport_type_id = db.Column(db.Integer, primary_key=True)
    transport_type = db.Column(db.String(100), nullable=False, unique=True)
    transport_type_description = db.Column(db.String(200), nullable=True)
    capacity = db.Column(db.Integer, nullable=False)
    contact_person_name = db.Column(db.String(100), nullable=True)
    contact_person_phone = db.Column(db.String(50), nullable=True)
    number_available_vehicles = db.Column(db.Integer, default=0, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'transport_type_id': self.transport_type_id,
            'transport_type': self.transport_type,
            'transport_type_description': self.transport_type_description,
            'capacity': self.capacity,
            'contact_person_name': self.contact_person_name,
            'contact_person_phone': self.contact_person_phone,
            'number_available_vehicles': self.number_available_vehicles,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class Interest(db.Model):
    __tablename__ = 'interests'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description
        }

class StallType(db.Model):
    __tablename__ = 'stall_types'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    price = db.Column(db.Numeric(10, 2))
    attendees = db.Column(db.Integer)  # Changed from allowed_attendees to match schema
    max_meetings_per_attendee = db.Column(db.Integer)
    min_meetings_per_attendee = db.Column(db.Integer)
    size = db.Column(db.String(50))
    saleable = db.Column(db.Boolean, default=True)
    inclusions = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    dinner_passes = db.Column(db.Integer, default=1)
    max_additional_seller_passes = db.Column(db.Integer, default=1)
    price_per_additional_pass = db.Column(db.Integer, default=3500)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'price': float(self.price) if self.price else None,
            'size': self.size,
            'attendees': self.attendees,  # Updated field name
            'max_meetings_per_attendee': self.max_meetings_per_attendee,
            'min_meetings_per_attendee': self.min_meetings_per_attendee,
            'inclusions': self.inclusions,
            'saleable': self.saleable,
            'dinner_passes': self.dinner_passes,
            'max_additional_seller_passes': self.max_additional_seller_passes,
            'price_per_additional_pass': self.price_per_additional_pass,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(10), nullable=False, default=UserRole.BUYER.value)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    business_name = db.Column(db.String(120), nullable=True)
    business_description = db.Column(db.Text, nullable=True)
    is_verified = db.Column(db.Boolean, default=False)
    
    def __init__(self, username, email, password, role=UserRole.BUYER, **kwargs):
        self.username = username
        self.email = email
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
        self.role = role.value if isinstance(role, UserRole) else role
        
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)
    
    def is_buyer(self):
        return self.role == UserRole.BUYER.value
    
    def is_seller(self):
        return self.role == UserRole.SELLER.value
    
    def is_admin(self):
        return self.role == UserRole.ADMIN.value
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'created_at': self.created_at.isoformat()
        }

class BuyerProfile(db.Model):
    __tablename__ = 'buyer_profiles'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Core Information (matching database exactly)
    name = db.Column(db.String(100), nullable=False)
    organization = db.Column(db.String(100), nullable=False)
    designation = db.Column(db.String(50), nullable=True)
    operator_type = db.Column(db.String(50), nullable=True)
    
    # Profile Information
    interests = db.Column(db.JSON, nullable=True)  # Note: DB uses JSONB
    properties_of_interest = db.Column(db.JSON, nullable=True)  # Note: DB uses JSONB
    
    # Address Information
    country = db.Column(db.String(50), nullable=True)
    state = db.Column(db.String(50), nullable=True)
    city = db.Column(db.String(50), nullable=True)
    address = db.Column(db.Text, nullable=True)
    mobile = db.Column(db.String(20), nullable=True)
    website = db.Column(db.String(255), nullable=True)
    instagram = db.Column(db.String(100), nullable=True)
    
    # Business Information
    year_of_starting_business = db.Column(db.Integer, nullable=True)
    selling_wayanad = db.Column(db.Boolean, default=False)
    since_when = db.Column(db.Integer, nullable=True)
    bio = db.Column(db.Text, nullable=True)
    profile_image = db.Column(db.String(255), nullable=True)
    
    # Category and Status
    category_id = db.Column(db.Integer, db.ForeignKey('buyer_categories.id'), nullable=True)
    salutation = db.Column(db.String(10), nullable=True)
    first_name = db.Column(db.String(50), nullable=True)
    last_name = db.Column(db.String(50), nullable=True)
    vip = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), default='pending')
    gst = db.Column(db.String(20), nullable=True)
    pincode = db.Column(db.String(10), nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('buyer_profile', uselist=False))
    category = db.relationship('BuyerCategory', backref=db.backref('buyers', lazy=True))
    interest_relationships = db.relationship('Interest', secondary=buyer_profile_interests, 
                                           backref=db.backref('buyer_profiles', lazy=True))
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'organization': self.organization,
            'designation': self.designation,
            'operator_type': self.operator_type,
            'category_id': self.category_id,
            'category': self.category.to_dict() if self.category else None,
            'salutation': self.salutation,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'vip': self.vip,
            'status': self.status,
            'gst': self.gst,
            'pincode': self.pincode,
            'interests': self.interests or [],
            'interest_relationships': [interest.to_dict() for interest in self.interest_relationships],
            'properties_of_interest': self.properties_of_interest or [],
            'country': self.country,
            'state': self.state,
            'city': self.city,
            'address': self.address,
            'mobile': self.mobile,
            'website': self.website,
            'instagram': self.instagram,
            'year_of_starting_business': self.year_of_starting_business,
            'selling_wayanad': self.selling_wayanad,
            'since_when': self.since_when,
            'bio': self.bio,
            'profile_image': self.profile_image,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class SellerProfile(db.Model):
    __tablename__ = 'seller_profiles'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    business_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    seller_type = db.Column(db.String(200), nullable=True)
    target_market = db.Column(db.String(200), nullable=True)
    
    # Contact Information
    contact_email = db.Column(db.String(100), nullable=True)
    contact_phone = db.Column(db.String(20), nullable=True)
    
    # Personal Information (added to match database)
    salutation = db.Column(db.String(10), nullable=True)
    first_name = db.Column(db.String(50), nullable=True)
    last_name = db.Column(db.String(50), nullable=True)
    designation = db.Column(db.String(100), nullable=True)
    company_name = db.Column(db.String(100), nullable=True)
    mobile = db.Column(db.String(15), nullable=True)
    
    # Business Information
    start_year = db.Column(db.Integer, nullable=True)
    
    # Address Information
    address = db.Column(db.Text, nullable=True)
    city = db.Column(db.String(50), nullable=True)
    state = db.Column(db.String(100), nullable=True)
    pincode = db.Column(db.String(10), nullable=True)
    country = db.Column(db.String(50), nullable=True)
    
    # Online Presence
    logo_url = db.Column(db.String(255), nullable=True)
    website = db.Column(db.String(255), nullable=True)
    instagram = db.Column(db.String(100), nullable=True)
    microsite_url = db.Column(db.String(500), nullable=True)
    
    # Business Status
    property_type_id = db.Column(db.Integer, db.ForeignKey('property_types.id'), nullable=True)
    status = db.Column(db.String(20), default='active')
    assn_member = db.Column(db.Boolean, default=False)
    is_verified = db.Column(db.Boolean, default=False)
    gst = db.Column(db.String(20), nullable=True)
    
    # Business Images - Using JSONB to match database
    business_images = db.Column(db.JSON, default=list)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('seller_profile', uselist=False))
    property_type = db.relationship('PropertyType', backref=db.backref('sellers', lazy=True))
    target_market_relationships = db.relationship('Interest', secondary=seller_target_markets,
                                                 backref=db.backref('seller_profiles', lazy=True))
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'business_name': self.business_name,
            'description': self.description,
            'seller_type': self.seller_type,
            'target_market': self.target_market,
            'property_type': self.property_type.to_dict() if self.property_type else None,
            'status': self.status,
            'assn_member': self.assn_member,
            'gst': self.gst,
            'pincode': self.pincode,
            'state': self.state,
            'country': self.country,
            'city': self.city,
            'logo_url': self.logo_url,
            'website': self.website,
            'instagram': self.instagram,
            'microsite_url': self.microsite_url,
            'contact_email': self.contact_email,
            'contact_phone': self.contact_phone,
            'mobile': self.mobile,
            'address': self.address,
            'is_verified': self.is_verified,
            'business_images': self.business_images or [],
            # Personal Information
            'salutation': self.salutation,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'designation': self.designation,
            'company_name': self.company_name,
            'start_year': self.start_year,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'target_market_relationships': [interest.to_dict() for interest in self.target_market_relationships]
        }
class Stall(db.Model):
    __tablename__ = 'stalls'
    
    id = db.Column(db.Integer, primary_key=True)
    seller_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    stall_type_id = db.Column(db.Integer, db.ForeignKey('stall_types.id'), nullable=False)
    number = db.Column(db.String(20), nullable=False)
    
    # Enhanced fields
    allocated_stall_number = db.Column(db.String(20), nullable=True)
    fascia_name = db.Column(db.String(100), nullable=True)
    is_allocated = db.Column(db.Boolean, default=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    # Relationships
    seller = db.relationship('User', backref=db.backref('stalls', lazy=True))
    stall_type_rel = db.relationship('StallType', backref=db.backref('stalls', lazy=True))
    
    def to_dict(self):
        return {
            'id': self.id,
            'seller_id': self.seller_id,
            'stall_type_id': self.stall_type_id,
            'number': self.number,
            'allocated_stall_number': self.allocated_stall_number,
            'fascia_name': self.fascia_name,
            'is_allocated': self.is_allocated,
            'stall_type_info': self.stall_type_rel.to_dict() if self.stall_type_rel else None,
            'price': float(self.stall_type_rel.price) if self.stall_type_rel and self.stall_type_rel.price else None,
            'size': self.stall_type_rel.size if self.stall_type_rel else None,
            'attendees': self.stall_type_rel.attendees if self.stall_type_rel else None,
            'max_meetings_per_attendee': self.stall_type_rel.max_meetings_per_attendee if self.stall_type_rel else None,
            'min_meetings_per_attendee': self.stall_type_rel.min_meetings_per_attendee if self.stall_type_rel else None,
            'inclusions': self.stall_type_rel.inclusions if self.stall_type_rel else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'seller_business_name': self.seller.seller_profile.business_name if self.seller and self.seller.seller_profile else None
        }

# Keep all existing models for backward compatibility

class Meeting(db.Model):
    __tablename__ = 'meetings'
    
    id = db.Column(db.Integer, primary_key=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    seller_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    requestor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # Added requestor_id field
    time_slot_id = db.Column(db.Integer, db.ForeignKey('time_slots.id'), nullable=True)
    attendee_id = db.Column(db.Integer, db.ForeignKey('seller_attendees.id'), nullable=True)  # Added missing field
    notes = db.Column(db.Text, nullable=True)
    status = db.Column(db.Enum(MeetingStatus), nullable=False, default=MeetingStatus.PENDING)
    meeting_date = db.Column(db.Date, nullable=True)  # Added missing field
    meeting_time = db.Column(db.Time, nullable=True)  # Added missing field
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    buyer = db.relationship('User', foreign_keys=[buyer_id], backref=db.backref('buyer_meetings', lazy=True))
    seller = db.relationship('User', foreign_keys=[seller_id], backref=db.backref('seller_meetings', lazy=True))
    requestor = db.relationship('User', foreign_keys=[requestor_id], backref=db.backref('requested_meetings', lazy=True))  # Added requestor relationship
    time_slot = db.relationship('TimeSlot', foreign_keys=[time_slot_id], backref=db.backref('meeting', uselist=False))
    attendee = db.relationship('SellerAttendee', foreign_keys=[attendee_id], backref=db.backref('meetings', lazy=True))  # Added relationship
    
    def to_dict(self):
        return {
            'id': self.id,
            'buyer_id': self.buyer_id,
            'seller_id': self.seller_id,
            'requestor_id': self.requestor_id,  # Added requestor_id field
            'time_slot_id': self.time_slot_id,
            'attendee_id': self.attendee_id,
            'notes': self.notes,
            'status': self.status.value,
            'meeting_date': self.meeting_date.isoformat() if self.meeting_date else None,
            'meeting_time': self.meeting_time.isoformat() if self.meeting_time else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'buyer': {
                'id': self.buyer.id,
                'username': self.buyer.username,
                'email': self.buyer.email,
                'organization': self.buyer.buyer_profile.organization if self.buyer.buyer_profile else 'Unknown Organization'
            },
            'seller': {
                'id': self.seller.id,
                'username': self.seller.username,
                'email': self.seller.email,
                'business_name': self.seller.seller_profile.business_name if self.seller.seller_profile else self.seller.business_name
            },
            'requestor': {  # Added requestor information
                'id': self.requestor.id,
                'username': self.requestor.username,
                'email': self.requestor.email
            } if self.requestor else None,
            'attendee': self.attendee.to_dict() if self.attendee else None,
            'time_slot': self.time_slot.to_dict() if self.time_slot else []
        }

class TimeSlot(db.Model):
    __tablename__ = 'time_slots'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    is_available = db.Column(db.Boolean, default=True)
    meeting_id = db.Column(db.Integer, db.ForeignKey('meetings.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('time_slots', lazy=True))
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat(),
            'is_available': self.is_available,
            'meeting_id': self.meeting_id
        }

class SystemSetting(db.Model):
    __tablename__ = 'system_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.String(255))
    description = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'key': self.key,
            'value': self.value,
            'description': self.description
        }

class TravelPlan(db.Model):
    __tablename__ = 'travel_plans'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    event_name = db.Column(db.String(120), nullable=False)
    event_start_date = db.Column(db.Date, nullable=False)
    event_end_date = db.Column(db.Date, nullable=False)
    venue = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('travel_plans', lazy=True))
    transportation = db.relationship('Transportation', backref='travel_plan', uselist=False, cascade='all, delete-orphan')
    accommodation = db.relationship('Accommodation', backref='travel_plan', uselist=False, cascade='all, delete-orphan')
    ground_transportation = db.relationship('GroundTransportation', backref='travel_plan', uselist=False, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'event_name': self.event_name,
            'event_start_date': self.event_start_date.isoformat() if self.event_start_date else None,
            'event_end_date': self.event_end_date.isoformat() if self.event_end_date else None,
            'venue': self.venue,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'transportation': self.transportation.to_dict() if self.transportation else None,
            'accommodation': self.accommodation.to_dict() if self.accommodation else None,
            'ground_transportation': self.ground_transportation.to_dict() if self.ground_transportation else None
        }

class Transportation(db.Model):
    __tablename__ = 'transportation'
    
    id = db.Column(db.Integer, primary_key=True)
    travel_plan_id = db.Column(db.Integer, db.ForeignKey('travel_plans.id'), nullable=False)
    type = db.Column(db.String(20), nullable=False)  # Primary transportation type
    
    # Individual transportation types for outbound and return journeys
    outbound_type = db.Column(db.String(20), nullable=True)  # Can be different from main type
    return_type = db.Column(db.String(20), nullable=True)    # Can be different from main type
    
    # Outbound journey
    outbound_carrier = db.Column(db.String(100), nullable=False)
    outbound_number = db.Column(db.String(20), nullable=False)
    outbound_departure_location = db.Column(db.String(200), nullable=False)
    outbound_departure_datetime = db.Column(db.DateTime, nullable=False)
    outbound_arrival_location = db.Column(db.String(200), nullable=False)
    outbound_arrival_datetime = db.Column(db.DateTime, nullable=False)
    outbound_booking_reference = db.Column(db.String(50), nullable=False)
    outbound_seat_info = db.Column(db.String(50), nullable=True)
    
    # Return journey
    return_carrier = db.Column(db.String(100), nullable=False)
    return_number = db.Column(db.String(20), nullable=False)
    return_departure_location = db.Column(db.String(200), nullable=False)
    return_departure_datetime = db.Column(db.DateTime, nullable=False)
    return_arrival_location = db.Column(db.String(200), nullable=False)
    return_arrival_datetime = db.Column(db.DateTime, nullable=False)
    return_booking_reference = db.Column(db.String(50), nullable=False)
    return_seat_info = db.Column(db.String(50), nullable=True)
    
    # Ticket uploads
    arrival_ticket = db.Column(db.String(255), nullable=True)
    return_ticket = db.Column(db.String(255), nullable=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'travel_plan_id': self.travel_plan_id,
            'type': self.type,
            'outbound': {
                'type': self.outbound_type or self.type,  # Use individual type or fall back to main type
                'carrier': self.outbound_carrier,
                'number': self.outbound_number,
                'departure_location': self.outbound_departure_location,
                'departure_datetime': self.outbound_departure_datetime.isoformat() if self.outbound_departure_datetime else None,
                'arrival_location': self.outbound_arrival_location,
                'arrival_datetime': self.outbound_arrival_datetime.isoformat() if self.outbound_arrival_datetime else None,
                'booking_reference': self.outbound_booking_reference,
                'seat_info': self.outbound_seat_info,
                'ticket': self.arrival_ticket
            },
            'return': {
                'type': self.return_type or self.type,  # Use individual type or fall back to main type
                'carrier': self.return_carrier,
                'number': self.return_number,
                'departure_location': self.return_departure_location,
                'departure_datetime': self.return_departure_datetime.isoformat() if self.return_departure_datetime else None,
                'arrival_location': self.return_arrival_location,
                'arrival_datetime': self.return_arrival_datetime.isoformat() if self.return_arrival_datetime else None,
                'booking_reference': self.return_booking_reference,
                'seat_info': self.return_seat_info,
                'ticket': self.return_ticket
            }
        }

class Accommodation(db.Model):
    __tablename__ = 'accommodations'
    
    id = db.Column(db.Integer, primary_key=True)
    travel_plan_id = db.Column(db.Integer, db.ForeignKey('travel_plans.id'), nullable=False)
    check_in_datetime = db.Column(db.DateTime, nullable=False)
    check_out_datetime = db.Column(db.DateTime, nullable=False)
    room_type = db.Column(db.String(100), nullable=False)
    booking_reference = db.Column(db.String(50), nullable=False)
    special_notes = db.Column(db.Text, nullable=True)
    
    # New fields added to match database changes
    host_property_id = db.Column(db.Integer, db.ForeignKey('host_properties.property_id'), nullable=False)
    buyer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    host_property = db.relationship('HostProperty', backref=db.backref('accommodations', lazy=True))
    buyer = db.relationship('User', backref=db.backref('accommodations', lazy=True))
    
    def to_dict(self):
        return {
            'id': self.id,
            'travel_plan_id': self.travel_plan_id,
            'host_property_id': self.host_property_id,
            'buyer_id': self.buyer_id,
            'check_in_datetime': self.check_in_datetime.isoformat() if self.check_in_datetime else None,
            'check_out_datetime': self.check_out_datetime.isoformat() if self.check_out_datetime else None,
            'room_type': self.room_type,
            'booking_reference': self.booking_reference,
            'special_notes': self.special_notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            # Include related data for convenience
            'host_property': self.host_property.to_dict() if self.host_property else None,
            'buyer': {
                'id': self.buyer.id,
                'username': self.buyer.username,
                'email': self.buyer.email,
                'name': self.buyer.buyer_profile.name if self.buyer and self.buyer.buyer_profile else None,
                'organization': self.buyer.buyer_profile.organization if self.buyer and self.buyer.buyer_profile else None
            } if self.buyer else None
        }

class GroundTransportation(db.Model):
    __tablename__ = 'ground_transportation'
    
    id = db.Column(db.Integer, primary_key=True)
    travel_plan_id = db.Column(db.Integer, db.ForeignKey('travel_plans.id'), nullable=False)
    
    # Pickup details
    pickup_location = db.Column(db.String(200), nullable=False)
    pickup_datetime = db.Column(db.DateTime, nullable=False)
    pickup_vehicle_type = db.Column(db.Integer, db.ForeignKey('transport_types.transport_type_id'), nullable=True)
    pickup_driver_contact = db.Column(db.String(50), nullable=True)
    
    # Dropoff details
    dropoff_location = db.Column(db.String(200), nullable=False)
    dropoff_datetime = db.Column(db.DateTime, nullable=False)
    dropoff_vehicle_type = db.Column(db.Integer, db.ForeignKey('transport_types.transport_type_id'), nullable=True)
    dropoff_driver_contact = db.Column(db.String(50), nullable=True)
    
    # Relationships
    pickup_transport = db.relationship('TransportType', foreign_keys=[pickup_vehicle_type], backref=db.backref('pickup_ground_transportations', lazy=True))
    dropoff_transport = db.relationship('TransportType', foreign_keys=[dropoff_vehicle_type], backref=db.backref('dropoff_ground_transportations', lazy=True))
    
    def to_dict(self):
        return {
            'id': self.id,
            'travel_plan_id': self.travel_plan_id,
            'pickup': {
                'location': self.pickup_location,
                'datetime': self.pickup_datetime.isoformat() if self.pickup_datetime else None,
                'vehicle_type_id': self.pickup_vehicle_type,
                'vehicle_type': self.pickup_transport.to_dict() if self.pickup_transport else None,
                'driver_contact': self.pickup_driver_contact
            },
            'dropoff': {
                'location': self.dropoff_location,
                'datetime': self.dropoff_datetime.isoformat() if self.dropoff_datetime else None,
                'vehicle_type_id': self.dropoff_vehicle_type,
                'vehicle_type': self.dropoff_transport.to_dict() if self.dropoff_transport else None,
                'driver_contact': self.dropoff_driver_contact
            }
        }

class Listing(db.Model):
    __tablename__ = 'listings'
    
    id = db.Column(db.Integer, primary_key=True)
    seller_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)  # Changed to Numeric for consistency
    duration = db.Column(db.String(50), nullable=False)
    location = db.Column(db.String(200), nullable=False)
    max_participants = db.Column(db.Integer, nullable=False)
    status = db.Column(db.Enum(ListingStatus), nullable=False, default=ListingStatus.ACTIVE)
    image_url = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    views = db.Column(db.Integer, default=0)
    bookings = db.Column(db.Integer, default=0)
    
    seller = db.relationship('User', backref=db.backref('listings', lazy=True))
    available_dates = db.relationship('ListingDate', backref='listing', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'seller_id': self.seller_id,
            'name': self.name,
            'description': self.description,
            'price': float(self.price) if self.price else None,
            'duration': self.duration,
            'location': self.location,
            'max_participants': self.max_participants,
            'status': self.status.value,
            'image_url': self.image_url,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'views': self.views,
            'bookings': self.bookings,
            'available_dates': [date.date.isoformat() for date in self.available_dates]
        }

class ListingDate(db.Model):
    __tablename__ = 'listing_dates'
    
    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(db.Integer, db.ForeignKey('listings.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)

class InvitedBuyer(db.Model):
    __tablename__ = 'invited_buyers'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    invitation_token = db.Column(db.String(255), unique=True, nullable=False)
    is_registered = db.Column(db.Boolean, default=False)
    invited_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    
    admin = db.relationship('User', backref=db.backref('invited_buyers', lazy=True))

class PendingBuyer(db.Model):
    __tablename__ = 'pending_buyers'
    
    id = db.Column(db.Integer, primary_key=True)
    invited_buyer_id = db.Column(db.Integer, db.ForeignKey('invited_buyers.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    designation = db.Column(db.String(30), nullable=False)
    company = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    invited_buyer = db.relationship('InvitedBuyer', backref=db.backref('pending_registration', uselist=False))

class DomainRestriction(db.Model):
    __tablename__ = 'domain_restrictions'
    
    id = db.Column(db.Integer, primary_key=True)
    domain = db.Column(db.String(100), unique=True, nullable=False)
    is_enabled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Missing Models from Clean Schema

class SellerAttendee(db.Model):
    __tablename__ = 'seller_attendees'
    
    id = db.Column(db.Integer, primary_key=True)
    seller_profile_id = db.Column(db.Integer, db.ForeignKey('seller_profiles.id'))
    attendee_number = db.Column(db.Integer)
    name = db.Column(db.String(100))
    designation = db.Column(db.String(100))
    email = db.Column(db.String(100))
    mobile = db.Column(db.String(15))
    is_primary_contact = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    seller_profile = db.relationship('SellerProfile', backref=db.backref('attendees', lazy=True))
    
    def to_dict(self):
        return {
            'id': self.id,
            'seller_profile_id': self.seller_profile_id,
            'attendee_number': self.attendee_number,
            'name': self.name,
            'designation': self.designation,
            'email': self.email,
            'mobile': self.mobile,
            'is_primary_contact': self.is_primary_contact,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class BuyerBusinessInfo(db.Model):
    __tablename__ = 'buyer_business_info'
    
    id = db.Column(db.Integer, primary_key=True)
    buyer_profile_id = db.Column(db.Integer, db.ForeignKey('buyer_profiles.id'))
    start_year = db.Column(db.Integer)
    property_interest_1 = db.Column(db.String(100))
    property_interest_2 = db.Column(db.String(100))
    sell_wayanad = db.Column(db.Boolean, default=False)
    sell_wayanad_year = db.Column(db.Integer)
    previous_visit = db.Column(db.Boolean, default=False)
    previous_stay_property = db.Column(db.String(100))
    why_visit = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    buyer_profile = db.relationship('BuyerProfile', backref=db.backref('business_info', uselist=False))
    
    def to_dict(self):
        return {
            'id': self.id,
            'buyer_profile_id': self.buyer_profile_id,
            'start_year': self.start_year,
            'property_interest_1': self.property_interest_1,
            'property_interest_2': self.property_interest_2,
            'sell_wayanad': self.sell_wayanad,
            'sell_wayanad_year': self.sell_wayanad_year,
            'previous_visit': self.previous_visit,
            'previous_stay_property': self.previous_stay_property,
            'why_visit': self.why_visit,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class BuyerFinancialInfo(db.Model):
    __tablename__ = 'buyer_financial_info'
    
    id = db.Column(db.Integer, primary_key=True)
    buyer_profile_id = db.Column(db.Integer, db.ForeignKey('buyer_profiles.id'))
    deposit_paid = db.Column(db.Boolean, default=False)
    entry_fee_paid = db.Column(db.Boolean, default=False)
    deposit_amount = db.Column(db.Numeric(10, 2))
    entry_fee_amount = db.Column(db.Numeric(10, 2))
    payment_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    buyer_profile = db.relationship('BuyerProfile', backref=db.backref('financial_info', uselist=False))
    
    def to_dict(self):
        return {
            'id': self.id,
            'buyer_profile_id': self.buyer_profile_id,
            'deposit_paid': self.deposit_paid,
            'entry_fee_paid': self.entry_fee_paid,
            'deposit_amount': float(self.deposit_amount) if self.deposit_amount else None,
            'entry_fee_amount': float(self.entry_fee_amount) if self.entry_fee_amount else None,
            'payment_date': self.payment_date.isoformat() if self.payment_date else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class BuyerReferences(db.Model):
    __tablename__ = 'buyer_references'
    
    id = db.Column(db.Integer, primary_key=True)
    buyer_profile_id = db.Column(db.Integer, db.ForeignKey('buyer_profiles.id'))
    ref1_name = db.Column(db.String(100))
    ref1_address = db.Column(db.Text)
    ref2_name = db.Column(db.String(100))
    ref2_address = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    buyer_profile = db.relationship('BuyerProfile', backref=db.backref('references', uselist=False))
    
    def to_dict(self):
        return {
            'id': self.id,
            'buyer_profile_id': self.buyer_profile_id,
            'ref1_name': self.ref1_name,
            'ref1_address': self.ref1_address,
            'ref2_name': self.ref2_name,
            'ref2_address': self.ref2_address,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class SellerBusinessInfo(db.Model):
    __tablename__ = 'seller_business_info'
    
    id = db.Column(db.Integer, primary_key=True)
    seller_profile_id = db.Column(db.Integer, db.ForeignKey('seller_profiles.id'))
    start_year = db.Column(db.BigInteger)
    number_of_rooms = db.Column(db.Integer)
    previous_business = db.Column(db.Boolean, default=False)
    previous_business_year = db.Column(db.BigInteger)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    seller_profile = db.relationship('SellerProfile', backref=db.backref('business_info', uselist=False))
    
    def to_dict(self):
        return {
            'id': self.id,
            'seller_profile_id': self.seller_profile_id,
            'start_year': self.start_year,
            'number_of_rooms': self.number_of_rooms,
            'previous_business': self.previous_business,
            'previous_business_year': self.previous_business_year,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class SellerFinancialInfo(db.Model):
    __tablename__ = 'seller_financial_info'
    
    id = db.Column(db.Integer, primary_key=True)
    seller_profile_id = db.Column(db.Integer, db.ForeignKey('seller_profiles.id'))
    deposit_paid = db.Column(db.Boolean, default=False)
    total_amt_due = db.Column(db.Numeric(10, 2))
    total_amt_paid = db.Column(db.Numeric(10, 2))
    subscription_uptodate = db.Column(db.Boolean, default=False)
    actual_additional_seller_passes = db.Column(db.Integer, default=0, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    seller_profile = db.relationship('SellerProfile', backref=db.backref('financial_info', uselist=False))
    
    def to_dict(self):
        return {
            'id': self.id,
            'seller_profile_id': self.seller_profile_id,
            'deposit_paid': self.deposit_paid,
            'total_amt_due': float(self.total_amt_due) if self.total_amt_due else None,
            'total_amt_paid': float(self.total_amt_paid) if self.total_amt_paid else None,
            'subscription_uptodate': self.subscription_uptodate,
            'actual_additional_seller_passes': self.actual_additional_seller_passes,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class SellerReferences(db.Model):
    __tablename__ = 'seller_references'
    
    id = db.Column(db.Integer, primary_key=True)
    seller_profile_id = db.Column(db.Integer, db.ForeignKey('seller_profiles.id'))
    ref1_name = db.Column(db.String(100))
    ref1_address = db.Column(db.Text)
    ref2_name = db.Column(db.String(100))
    ref2_address = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    seller_profile = db.relationship('SellerProfile', backref=db.backref('references', uselist=False))
    
    def to_dict(self):
        return {
            'id': self.id,
            'seller_profile_id': self.seller_profile_id,
            'ref1_name': self.ref1_name,
            'ref1_address': self.ref1_address,
            'ref2_name': self.ref2_name,
            'ref2_address': self.ref2_address,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class StallInventory(db.Model):
    __tablename__ = 'stall_inventory'
    
    id = db.Column(db.Integer, primary_key=True)
    stall_number = db.Column(db.String(15), nullable=False)
    stall_type_id = db.Column(db.Integer, db.ForeignKey('stall_types.id'))
    allow_seller_selection = db.Column(db.Boolean, default=True)
    is_allocated = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    # Relationships
    stall_type = db.relationship('StallType', backref=db.backref('inventory', lazy=True))
    
    def to_dict(self):
        return {
            'id': self.id,
            'stall_number': self.stall_number,
            'stall_type_id': self.stall_type_id,
            'allow_seller_selection': self.allow_seller_selection,
            'is_allocated': self.is_allocated,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'stall_type': self.stall_type.to_dict() if self.stall_type else None
        }

class MigrationLog(db.Model):
    __tablename__ = 'migration_log'
    
    id = db.Column(db.Integer, primary_key=True)
    step_name = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    message = db.Column(db.Text)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    duration_seconds = db.Column(db.Integer)
    
    def to_dict(self):
        return {
            'id': self.id,
            'step_name': self.step_name,
            'status': self.status,
            'message': self.message,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'duration_seconds': self.duration_seconds
        }

class MigrationMappingBuyers(db.Model):
    __tablename__ = 'migration_mapping_buyers'
    
    id = db.Column(db.Integer, primary_key=True)
    customer_buyer_id = db.Column(db.Integer)
    splash25_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    splash25_buyer_profile_id = db.Column(db.Integer, db.ForeignKey('buyer_profiles.id'))
    migration_status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('buyer_migration_mappings', lazy=True))
    buyer_profile = db.relationship('BuyerProfile', backref=db.backref('migration_mappings', lazy=True))

class MigrationMappingSellers(db.Model):
    __tablename__ = 'migration_mapping_sellers'
    
    id = db.Column(db.Integer, primary_key=True)
    customer_seller_id = db.Column(db.Integer)
    splash25_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    splash25_seller_profile_id = db.Column(db.Integer, db.ForeignKey('seller_profiles.id'))
    migration_status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('seller_migration_mappings', lazy=True))
    seller_profile = db.relationship('SellerProfile', backref=db.backref('migration_mappings', lazy=True))
