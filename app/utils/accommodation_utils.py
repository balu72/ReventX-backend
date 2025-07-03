from ..models import db, Accommodation, HostProperty


def calculate_host_property_statistics(host_property_id):
    """
    Calculate host property statistics based on current accommodation allocations
    and update the host property model in memory (without committing to database)
    
    Args:
        host_property_id (int): The ID of the host property to calculate statistics for
        
    Returns:
        dict: Success response with calculated statistics or error response
    """
    try:
        # Validate host property exists
        host_property = HostProperty.query.get(host_property_id)
        if not host_property:
            return {
                'error': f'Host property with ID {host_property_id} not found',
                'status_code': 404
            }
        
        # Get all accommodations for this host property in one query
        accommodations = Accommodation.query.filter_by(host_property_id=host_property_id).all()
        
        if not accommodations or len(accommodations) == 0:
            # No accommodations found - set both to 0
            host_property.number_rooms_allocated = 0
            host_property.number_current_guests = 0
            shared_count = 0
            single_count = 0
        else:
            # Accommodations exist - count from the already fetched results
            shared_count = len([acc for acc in accommodations if acc.room_type == 'shared'])
            single_count = len([acc for acc in accommodations if acc.room_type == 'single'])
            
            # Calculate number_rooms_allocated using new formula
            # Formula: (shared_count // 2) + single_count
            host_property.number_rooms_allocated = (shared_count // 2) + single_count
            
            # Validation: Check if allocated rooms exceed available rooms
            if host_property.number_rooms_allocated > host_property.rooms_allotted:
                return {
                    'error': 'Cannot allocate room: exceeds available room capacity',
                    'status_code': 400
                }
            
            # Update number_current_guests using the specified formula
            # Formula: (1 * shared_count) + (2 * single_count)
            host_property.number_current_guests = (1 * shared_count) + (2 * single_count)
        
        return {
            'success': True,
            'message': 'Host property statistics calculated successfully',
            'host_property': host_property,
            'statistics': {
                'shared_count': shared_count,
                'single_count': single_count,
                'number_rooms_allocated': host_property.number_rooms_allocated,
                'number_current_guests': host_property.number_current_guests
            }
        }
        
    except Exception as e:
        return {
            'error': f'Failed to calculate host property statistics: {str(e)}',
            'status_code': 500
        }
