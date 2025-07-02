from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..models import db, StallType, StallInventory
from ..utils.auth import admin_required

stall_types = Blueprint('stall_types', __name__, url_prefix='/api/stall-types')

@stall_types.route('', methods=['GET'])
@jwt_required()
def get_stall_types():
    """Get all stall types"""
    try:
        stall_types_list = StallType.query.all()
        return jsonify({
            'stall_types': [st.to_dict() for st in stall_types_list]
        }), 200
    except Exception as e:
        return jsonify({
            'error': f'Failed to fetch stall types: {str(e)}'
        }), 500

@stall_types.route('/<int:stall_type_id>', methods=['GET'])
@jwt_required()
def get_stall_type(stall_type_id):
    """Get a specific stall type"""
    try:
        stall_type = StallType.query.get(stall_type_id)
        if not stall_type:
            return jsonify({'error': 'Stall type not found'}), 404
        
        return jsonify({
            'stall_type': stall_type.to_dict()
        }), 200
    except Exception as e:
        return jsonify({
            'error': f'Failed to fetch stall type: {str(e)}'
        }), 500

@stall_types.route('', methods=['POST'])
@jwt_required()
@admin_required
def create_stall_type():
    """Create a new stall type (admin only)"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['name', 'price', 'attendees', 'size']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Check if stall type name already exists
        existing_stall_type = StallType.query.filter_by(name=data['name']).first()
        if existing_stall_type:
            return jsonify({'error': 'Stall type name already exists'}), 400
        
        # Create new stall type
        stall_type = StallType(
            name=data['name'],
            price=float(data['price']),
            attendees=int(data['attendees']),
            max_meetings_per_attendee=int(data.get('max_meetings_per_attendee', 30)),
            min_meetings_per_attendee=int(data.get('min_meetings_per_attendee', 0)),
            size=data['size'],
            saleable=data.get('saleable', True),
            inclusions=data.get('inclusions', ''),
            dinner_passes=int(data.get('dinner_passes', 1)),
            max_additional_seller_passes=int(data.get('max_additional_seller_passes', 1)),
            price_per_additional_pass=int(data.get('price_per_additional_pass', 3500))
        )
        
        db.session.add(stall_type)
        db.session.commit()
        
        return jsonify({
            'message': 'Stall type created successfully',
            'stall_type': stall_type.to_dict()
        }), 201
        
    except ValueError as e:
        return jsonify({
            'error': 'Invalid data type',
            'message': str(e)
        }), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'error': f'Failed to create stall type: {str(e)}'
        }), 500

@stall_types.route('/<int:stall_type_id>', methods=['PUT'])
@jwt_required()
@admin_required
def update_stall_type(stall_type_id):
    """Update a stall type (admin only)"""
    try:
        stall_type = StallType.query.get(stall_type_id)
        if not stall_type:
            return jsonify({'error': 'Stall type not found'}), 404
        
        data = request.get_json()
        
        # Update fields if provided and not null (but allow 0 values)
        if 'name' in data:
            # Check if new name conflicts with existing stall types
            existing_stall_type = StallType.query.filter_by(name=data['name']).filter(StallType.id != stall_type_id).first()
            if existing_stall_type:
                return jsonify({'error': 'Stall type name already exists'}), 400
            stall_type.name = data['name']
        
        if 'price' in data and data['price'] is not None:
            stall_type.price = float(data['price'])
        
        if 'attendees' in data and data['attendees'] is not None:
            stall_type.attendees = int(data['attendees'])
        
        if 'max_meetings_per_attendee' in data and data['max_meetings_per_attendee'] is not None:
            stall_type.max_meetings_per_attendee = int(data['max_meetings_per_attendee'])
        
        if 'min_meetings_per_attendee' in data and data['min_meetings_per_attendee'] is not None:
            stall_type.min_meetings_per_attendee = int(data['min_meetings_per_attendee'])
        
        if 'size' in data:
            stall_type.size = data['size']
        
        if 'saleable' in data and data['saleable'] is not None:
            stall_type.saleable = bool(data['saleable'])
        
        if 'inclusions' in data:
            stall_type.inclusions = data['inclusions']
        
        if 'dinner_passes' in data and data['dinner_passes'] is not None:
            stall_type.dinner_passes = int(data['dinner_passes'])
        
        if 'max_additional_seller_passes' in data and data['max_additional_seller_passes'] is not None:
            stall_type.max_additional_seller_passes = int(data['max_additional_seller_passes'])
        
        if 'price_per_additional_pass' in data and data['price_per_additional_pass'] is not None:
            stall_type.price_per_additional_pass = int(data['price_per_additional_pass'])
        
        db.session.commit()
        
        return jsonify({
            'message': 'Stall type updated successfully',
            'stall_type': stall_type.to_dict()
        }), 200
        
    except ValueError as e:
        return jsonify({
            'error': 'Invalid data type',
            'message': str(e)
        }), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'error': f'Failed to update stall type: {str(e)}'
        }), 500

@stall_types.route('/<int:stall_type_id>', methods=['DELETE'])
@jwt_required()
@admin_required
def delete_stall_type(stall_type_id):
    """Delete a stall type (admin only)"""
    try:
        stall_type = StallType.query.get(stall_type_id)
        if not stall_type:
            return jsonify({'error': 'Stall type not found'}), 404
        
        # Check if stall type is being used by any stalls
        from ..models import Stall
        stalls_using_type = Stall.query.filter_by(stall_type_id=stall_type_id).count()
        if stalls_using_type > 0:
            return jsonify({
                'error': f'Cannot delete stall type. It is being used by {stalls_using_type} stall(s)'
            }), 400
        
        db.session.delete(stall_type)
        db.session.commit()
        
        return jsonify({
            'message': 'Stall type deleted successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'error': f'Failed to delete stall type: {str(e)}'
        }), 500

@stall_types.route('/inventory', methods=['GET'])
@jwt_required()
def get_stall_inventory():
    """Get stall inventory with availability status"""
    try:
        inventory = StallInventory.query.all()
        return jsonify({
            'inventory': [item.to_dict() for item in inventory]
        }), 200
    except Exception as e:
        return jsonify({
            'error': f'Failed to fetch stall inventory: {str(e)}'
        }), 500

@stall_types.route('/inventory', methods=['POST'])
@jwt_required()
@admin_required
def create_stall_inventory():
    """Create stall inventory item (admin only)"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['stall_number', 'stall_type_id']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Check if stall number already exists
        existing_inventory = StallInventory.query.filter_by(stall_number=data['stall_number']).first()
        if existing_inventory:
            return jsonify({'error': 'Stall number already exists in inventory'}), 400
        
        # Verify stall type exists
        stall_type = StallType.query.get(data['stall_type_id'])
        if not stall_type:
            return jsonify({'error': 'Invalid stall type ID'}), 400
        
        # Create inventory item
        inventory_item = StallInventory(
            stall_number=data['stall_number'],
            stall_type_id=data['stall_type_id'],
            is_allocated=data.get('is_allocated', False)
        )
        
        db.session.add(inventory_item)
        db.session.commit()
        
        return jsonify({
            'message': 'Stall inventory item created successfully',
            'inventory_item': inventory_item.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'error': f'Failed to create stall inventory item: {str(e)}'
        }), 500

@stall_types.route('/inventory/<int:inventory_id>', methods=['PUT'])
@jwt_required()
@admin_required
def update_stall_inventory(inventory_id):
    """Update stall inventory item (admin only)"""
    try:
        inventory_item = StallInventory.query.get(inventory_id)
        if not inventory_item:
            return jsonify({'error': 'Inventory item not found'}), 404
        
        data = request.get_json()
        
        # Update fields if provided
        if 'stall_number' in data:
            # Check if new stall number conflicts
            existing_inventory = StallInventory.query.filter_by(stall_number=data['stall_number']).filter(StallInventory.id != inventory_id).first()
            if existing_inventory:
                return jsonify({'error': 'Stall number already exists in inventory'}), 400
            inventory_item.stall_number = data['stall_number']
        
        if 'stall_type_id' in data:
            # Verify stall type exists
            stall_type = StallType.query.get(data['stall_type_id'])
            if not stall_type:
                return jsonify({'error': 'Invalid stall type ID'}), 400
            inventory_item.stall_type_id = data['stall_type_id']
        
        if 'is_allocated' in data:
            inventory_item.is_allocated = bool(data['is_allocated'])
        
        db.session.commit()
        
        return jsonify({
            'message': 'Stall inventory item updated successfully',
            'inventory_item': inventory_item.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'error': f'Failed to update stall inventory item: {str(e)}'
        }), 500

@stall_types.route('/available', methods=['GET'])
@jwt_required()
def get_available_stall_types():
    """Get only saleable stall types"""
    try:
        available_types = StallType.query.filter_by(saleable=True).all()
        return jsonify({
            'stall_types': [st.to_dict() for st in available_types]
        }), 200
    except Exception as e:
        return jsonify({
            'error': f'Failed to fetch available stall types: {str(e)}'
        }), 500
