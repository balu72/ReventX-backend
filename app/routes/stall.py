from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
from ..models import db, User, Stall, SellerProfile, StallInventory
from ..utils.auth import seller_required, admin_required

stall = Blueprint('stall', __name__, url_prefix='/api/stalls')

@stall.route('', methods=['GET'])
@jwt_required()
@seller_required
def get_stalls():
    """Get all stalls for the current seller"""
    current_user_id = get_jwt_identity()
    # Convert to int if it's a string
    if isinstance(current_user_id, str):
        try:
            current_user_id = int(current_user_id)
        except ValueError:
            return jsonify({'error': 'Invalid user ID'}), 400
    
    try:
        # Get stalls for the current seller with seller profile info
        stalls = db.session.query(Stall, SellerProfile).join(
            SellerProfile, Stall.seller_id == SellerProfile.user_id
        ).filter(Stall.seller_id == current_user_id).all()
        
        stall_list = []
        for stall, seller_profile in stalls:
            stall_dict = stall.to_dict()
            # Use actual stall fascia_name, fallback to business_name if empty
            stall_dict['fascia_name'] = stall.fascia_name or seller_profile.business_name
            # Include complete stall type information for attendee calculations
            if stall.stall_type_rel:
                stall_dict['stall_type_info'] = stall.stall_type_rel.to_dict()
                # Map the stall type fields to the stall for backward compatibility
                stall_dict['allowed_attendees'] = stall.stall_type_rel.attendees
                stall_dict['max_additional_seller_passes'] = stall.stall_type_rel.max_additional_seller_passes
            stall_list.append(stall_dict)
        
        return jsonify({
            'stalls': stall_list
        }), 200
        
    except Exception as e:
        return jsonify({
            'error': 'Failed to fetch stalls',
            'message': str(e)
        }), 500


@stall.route('/<int:stall_id>', methods=['PUT'])
@jwt_required()
@admin_required
def update_stall(stall_id):
    """Update an existing stall (admin only)"""
    try:
        # Find the stall (admin can update any stall)
        stall = Stall.query.get(stall_id)
        
        if not stall:
            return jsonify({
                'error': 'Stall not found'
            }), 404
        
        data = request.get_json()
        
        # Update fields if provided
        if 'number' in data:
            # Check if new number conflicts with existing stalls for the same seller
            existing_stall = Stall.query.filter_by(
                seller_id=stall.seller_id, 
                number=data['number']
            ).filter(Stall.id != stall_id).first()
            
            if existing_stall:
                return jsonify({
                    'error': 'Stall number already exists for this seller'
                }), 400
            
            stall.number = data['number']
        
        if 'stall_type_id' in data:
            # Verify stall type exists
            from ..models import StallType
            stall_type = StallType.query.get(data['stall_type_id'])
            if not stall_type:
                return jsonify({
                    'error': 'Invalid stall type ID'
                }), 400
            stall.stall_type_id = data['stall_type_id']
        
        if 'fascia_name' in data:
            stall.fascia_name = data['fascia_name']
        
        if 'allocated_stall_number' in data:
            stall.allocated_stall_number = data['allocated_stall_number']
        
        if 'is_allocated' in data:
            stall.is_allocated = bool(data['is_allocated'])
        
        db.session.commit()
        
        # Get the updated stall with seller profile info
        stall_with_profile = db.session.query(Stall, SellerProfile).join(
            SellerProfile, Stall.seller_id == SellerProfile.user_id
        ).filter(Stall.id == stall.id).first()
        
        if stall_with_profile:
            stall, seller_profile = stall_with_profile
            stall_dict = stall.to_dict()
            stall_dict['fascia_name'] = stall.fascia_name or seller_profile.business_name
        else:
            stall_dict = stall.to_dict()
        
        return jsonify({
            'message': 'Stall updated successfully',
            'stall': stall_dict
        }), 200
        
    except ValueError as e:
        return jsonify({
            'error': 'Invalid data type',
            'message': str(e)
        }), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'error': 'Failed to update stall',
            'message': str(e)
        }), 500

@stall.route('/<int:stall_id>/fascia-name', methods=['PUT'])
@jwt_required()
@seller_required
def update_stall_fascia_name(stall_id):
    """Update fascia name for a specific stall"""
    current_user_id = get_jwt_identity()
    if isinstance(current_user_id, str):
        try:
            current_user_id = int(current_user_id)
        except ValueError:
            return jsonify({'error': 'Invalid user ID'}), 400
    
    try:
        # Find the stall and verify ownership
        stall = Stall.query.filter_by(id=stall_id, seller_id=current_user_id).first()
        
        if not stall:
            return jsonify({'error': 'Stall not found or access denied'}), 404
        
        data = request.get_json()
        fascia_name = data.get('fascia_name', '').strip()
        
        # Validation: 20-80 characters
        if len(fascia_name) < 20:
            return jsonify({'error': 'Fascia name must be at least 20 characters long'}), 400
        elif len(fascia_name) > 80:
            return jsonify({'error': 'Fascia name cannot exceed 80 characters'}), 400
        
        # Update the stall's fascia name
        stall.fascia_name = fascia_name
        db.session.commit()
        
        # Return updated stall with seller profile info
        stall_with_profile = db.session.query(Stall, SellerProfile).join(
            SellerProfile, Stall.seller_id == SellerProfile.user_id
        ).filter(Stall.id == stall.id).first()
        
        if stall_with_profile:
            stall, seller_profile = stall_with_profile
            stall_dict = stall.to_dict()
            stall_dict['fascia_name'] = stall.fascia_name or seller_profile.business_name
            if stall.stall_type_rel:
                stall_dict['stall_type_info'] = stall.stall_type_rel.to_dict()
                stall_dict['allowed_attendees'] = stall.stall_type_rel.attendees
                stall_dict['max_additional_seller_passes'] = stall.stall_type_rel.max_additional_seller_passes
        else:
            stall_dict = stall.to_dict()
        
        return jsonify({
            'message': 'Fascia name updated successfully',
            'stall': stall_dict
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'error': 'Failed to update fascia name',
            'message': str(e)
        }), 500

@stall.route('/<int:stall_id>/select_stall_number', methods=['PUT'])
@jwt_required()
@seller_required
def select_stall_number(stall_id):
    """Select a specific stall number from inventory for the seller's stall"""
    current_user_id = get_jwt_identity()
    if isinstance(current_user_id, str):
        try:
            current_user_id = int(current_user_id)
        except ValueError:
            return jsonify({'error': 'Invalid user ID'}), 400
    
    try:
        data = request.get_json()
        allocated_stall_number_id = data.get('allocated_stall_number_id')
        
        if not allocated_stall_number_id:
            return jsonify({'error': 'allocated_stall_number_id is required'}), 400
        
        # 1. Check if the stall belongs to the current seller
        stall = Stall.query.filter_by(id=stall_id, seller_id=current_user_id).first()
        if not stall:
            return jsonify({'error': 'Stall not found or access denied'}), 404
        
        # 2. Check if the allocated_stall_number_id exists in stall_inventory
        inventory_stall = StallInventory.query.get(allocated_stall_number_id)
        if not inventory_stall:
            return jsonify({'error': 'Invalid allocated_stall_number_id - stall not found in inventory'}), 400
        
        # 3. Check if stall type matches between stalls and stall_inventory
        if stall.stall_type_id != inventory_stall.stall_type_id:
            return jsonify({
                'error': f'Stall type mismatch. Your stall requires type {stall.stall_type_id} but selected inventory stall is type {inventory_stall.stall_type_id}'
            }), 400
        
        # 4. Check if seller selection is allowed
        if not inventory_stall.allow_seller_selection:
            return jsonify({'error': 'This stall does not allow seller selection'}), 400
        
        # 5. Check if the stall is already allocated
        if inventory_stall.is_allocated:
            return jsonify({'error': 'This stall has already been allocated to another seller'}), 400
        
        # If stall was previously allocated to a different inventory stall, free that one
        if stall.stall_id:
            previous_inventory = StallInventory.query.get(stall.stall_id)
            if previous_inventory:
                previous_inventory.is_allocated = False
                previous_inventory.updated_at = datetime.utcnow()
        
        # Update the stalls table
        stall.stall_id = allocated_stall_number_id  # Update stalls.stall_id with allocated_stall_number_id
        stall.allocated_stall_number = inventory_stall.stall_number  # Copy stall_number from inventory
        stall.updated_at = datetime.utcnow()
        
        # Update the stall_inventory table
        inventory_stall.is_allocated = True
        inventory_stall.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        # Return updated stall with seller profile info
        stall_with_profile = db.session.query(Stall, SellerProfile).join(
            SellerProfile, Stall.seller_id == SellerProfile.user_id
        ).filter(Stall.id == stall.id).first()
        
        if stall_with_profile:
            stall, seller_profile = stall_with_profile
            stall_dict = stall.to_dict()
            stall_dict['fascia_name'] = stall.fascia_name or seller_profile.business_name
            if stall.stall_type_rel:
                stall_dict['stall_type_info'] = stall.stall_type_rel.to_dict()
                stall_dict['allowed_attendees'] = stall.stall_type_rel.attendees
                stall_dict['max_additional_seller_passes'] = stall.stall_type_rel.max_additional_seller_passes
        else:
            stall_dict = stall.to_dict()
        
        return jsonify({
            'message': 'Stall number selected successfully',
            'stall': stall_dict,
            'selected_inventory_stall': inventory_stall.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'error': 'Failed to select stall number',
            'message': str(e)
        }), 500
