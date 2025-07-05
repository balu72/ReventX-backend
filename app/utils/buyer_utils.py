import os
import base64
import logging
from datetime import datetime, timedelta
from io import BytesIO
from nc_py_api import Nextcloud, NextcloudException
from werkzeug.utils import secure_filename
import requests

def validate_user_id(user_id):
    """
    Helper function to validate and convert user_id to integer.
    
    Args:
        user_id: User ID (string or int)
        
    Returns:
        int: Validated user ID
        
    Raises:
        ValueError: If user_id cannot be converted to int
    """
    if isinstance(user_id, str):
        try:
            return int(user_id)
        except ValueError:
            raise ValueError('Invalid user ID')
    return user_id

def validate_buyer_exists(buyer_id):
    """
    Helper function to check if buyer exists and has buyer role.
    
    Args:
        buyer_id (int): Buyer user ID
        
    Returns:
        bool: True if buyer exists and has correct role, False otherwise
    """
    from ..models import User, UserRole
    
    user = User.query.get(buyer_id)
    return user is not None and user.role == UserRole.BUYER.value

def validate_travel_plan_access(plan_id, user_id):
    """
    Helper function to validate travel plan ownership.
    
    Args:
        plan_id (int): Travel plan ID
        user_id (int): User ID
        
    Returns:
        TravelPlan or None: Travel plan if access is valid, None otherwise
    """
    from ..models import TravelPlan
    
    return TravelPlan.query.filter_by(id=plan_id, user_id=user_id).first()

def get_nextcloud_connection():
    """
    Helper function to initialize Nextcloud connection.
    
    Returns:
        Nextcloud or None: Nextcloud instance if credentials are available, None otherwise
    """
    storage_url = os.getenv('EXTERNAL_STORAGE_URL') + "index.php"
    storage_user = os.getenv('EXTERNAL_STORAGE_USER')
    storage_password = os.getenv('EXTERNAL_STORAGE_PASSWORD')
    
    if not all([storage_url, storage_user, storage_password]):
        return None
    
    return Nextcloud(nextcloud_url=storage_url, nc_auth_user=storage_user, nc_auth_pass=storage_password)

def create_buyer_directories(nc, buyer_id):
    """
    Helper function to create buyer base and profile directories.
    
    Args:
        nc: Nextcloud instance
        buyer_id (int): Buyer user ID
        
    Returns:
        tuple: (buyer_base_dir_available, buyer_image_profile_dir_available)
    """
    storage_user = os.getenv('EXTERNAL_STORAGE_USER')
    storage_password = os.getenv('EXTERNAL_STORAGE_PASSWORD')
    ocs_url = os.getenv("EXTERNAL_STORAGE_URL") + 'ocs/v2.php/apps/files_sharing/api/v1/shares'
    ocs_headers = {'OCS-APIRequest': 'true', "Accept": "application/json"}
    ocs_auth = (storage_user, storage_password)
    
    buyer_dir = f"buyer_{buyer_id}/"
    remote_dir_path = f"/Photos/{buyer_dir}"
    remote_base_profile_images_path = f"/Photos/{buyer_dir}/profile"
    
    buyer_base_dir_available = False
    buyer_image_profile_dir_available = False
    
    # Create base buyer directory
    try:
        nc.files.listdir(remote_dir_path)
        logging.debug(f"Found remote path:: {remote_dir_path}")
        buyer_base_dir_available = True
    except NextcloudException as e:
        if e.status_code != 404:
            raise e
        else:
            try:
                logging.info(f"Could not locate remote directory::: {remote_dir_path}::: Proceeding to create")
                nc.files.mkdir(remote_dir_path)
                logging.debug(f"Created remote directory {remote_dir_path} successfully")
                logging.debug("Now setting sharing permissions...")
                dir_sharing_data = {
                    'path': remote_dir_path,
                    'shareType': 3,  # Public link
                    'permissions': 1  # Read-only
                }
                response = requests.post(ocs_url, headers=ocs_headers, data=dir_sharing_data, auth=ocs_auth)
                
                if response.status_code == 200:
                    logging.info(f"Response Text is:: {response}")
                    share_info = response.json()
                    link = share_info['ocs']['data']['url']
                    logging.debug(f"Public Share URL: {link}")
                    buyer_base_dir_available = True
                else:
                    logging.debug("Failed to create share:", response.text)
            except Exception as e:
                logging.debug(f"Exception while creating buyer base directory:{str(e)}")
                raise Exception(f"Failed to create buyer base directory -- {remote_dir_path} - the error is ::::{str(e)}")
    
    # Create profile images directory if base directory exists
    if buyer_base_dir_available:
        try:
            nc.files.listdir(remote_base_profile_images_path)
            logging.debug(f"Found remote path:: {remote_base_profile_images_path}")
            buyer_image_profile_dir_available = True
        except NextcloudException as e:
            if e.status_code != 404:
                raise e
            else:
                try:
                    logging.info(f"Could not locate buyer profile image directory::: {remote_base_profile_images_path}::: Proceeding to create")
                    nc.files.mkdir(remote_base_profile_images_path)
                    logging.debug(f"Created remote directory {remote_base_profile_images_path} successfully")
                    logging.debug("Now setting sharing permissions...")
                    dir_sharing_data = {
                        'path': remote_base_profile_images_path,
                        'shareType': 3,  # Public link
                        'permissions': 1  # Read-only
                    }
                    response = requests.post(ocs_url, headers=ocs_headers, data=dir_sharing_data, auth=ocs_auth)
                    if response.status_code == 200:
                        logging.info(f"Response Text is:: {response}")
                        share_info = response.json()
                        link = share_info['ocs']['data']['url']
                        logging.debug(f"Public Share URL: {link}")
                        buyer_image_profile_dir_available = True
                    else:
                        logging.debug("Failed to create buyer profile image directory:", response.text)
                except Exception as e:
                    logging.debug(f"Exception while creating buyer profile images directory:{str(e)}")
                    raise Exception(f"Failed to create buyer profile images directory -- {remote_base_profile_images_path} - the error is ::::{str(e)}")
    
    return buyer_base_dir_available, buyer_image_profile_dir_available

def get_buyer_profile_images(buyer_id):
    """
    Helper function to get and filter buyer profile images.
    
    Args:
        buyer_id (int): Buyer user ID
        
    Returns:
        list: List of tuples (timestamp, filename, file_info) sorted by timestamp
    """
    # Get Nextcloud connection
    nc = get_nextcloud_connection()
    if not nc:
        return []  # No connection available
    buyer_profile_dir = f"/Photos/buyer_{buyer_id}/profile"
    
    try:
        files = nc.files.listdir(buyer_profile_dir)
        
        image_files = []
        for file_info in files:
            filename = file_info.name
            # Check if it's an image file with the expected naming pattern
            if (filename.startswith(f'buyer_{buyer_id}_') and 
                filename.lower().endswith(('.jpg', '.jpeg', '.png'))):
                try:
                    # Extract timestamp from filename: buyer_123_1641234567.jpg -> 1641234567
                    timestamp_part = filename.split('_')[2].split('.')[0]
                    timestamp = int(timestamp_part)
                    image_files.append((timestamp, filename, file_info))
                except (IndexError, ValueError):
                    # Skip files that don't match the expected pattern
                    continue
        
        return image_files
        
    except NextcloudException as e:
        if e.status_code == 404:
            return []  # Directory doesn't exist - no images
        else:
            raise e

def get_first_buyer_profile_image(buyer_id, profile_image_path):
    """
    Optimized: Get specific buyer profile image directly by full path
    
    Args:
        buyer_id (int): Buyer user ID
        profile_image_path (str): Full path like "/Photos/buyer_123/profile/buyer_123_1641234567.jpg"
        
    Returns:
        FsNode or None: File info if found, None otherwise
    """
    nc = get_nextcloud_connection()
    if not nc:
        return None
    
    if not profile_image_path:
        return None
    
    # Extract filename from full path
    # "/Photos/buyer_123/profile/buyer_123_1641234567.jpg" -> "buyer_123_1641234567.jpg"
    filename = profile_image_path.split('/')[-1]
    
    # Construct the directory path
    buyer_profile_dir = f"/Photos/buyer_{buyer_id}/profile"
    
    try:
        results = nc.files.find(["eq", "name", filename], path=buyer_profile_dir)
        if results:
            return results[0]  # Return the FsNode directly
        return None
    except NextcloudException as e:
        if e.status_code == 404:
            return None
        else:
            raise e

def convert_image_to_base64_data_url(buyer_id, filename):
    """
    Helper function to convert image to base64 data URL.
    
    Args:
        buyer_id (int): Buyer user ID
        filename (str): Image filename
        
    Returns:
        dict: Dictionary with image data (image_data_url, mime_type, filename)
    """
    # Get Nextcloud connection
    nc = get_nextcloud_connection()
    if not nc:
        raise Exception("Nextcloud connection not available")
    buyer_profile_dir = f"/Photos/buyer_{buyer_id}/profile"
    image_path = f"{buyer_profile_dir}/{filename}"
    
    # Fetch file metadata
    try:
        info = nc.files.file_info(image_path)
        mime = info.mime  # e.g. 'image/jpeg'
    except Exception as e:
        # Fallback: determine MIME type from file extension
        logging.warning(f"Could not get MIME type from file info for {image_path}: {str(e)}")
        
        # Extract file extension
        file_extension = filename.lower().split('.')[-1]
        
        # Map extension to MIME type
        if file_extension == 'png':
            mime = 'image/png'
        elif file_extension in ['jpg', 'jpeg']:
            mime = 'image/jpeg'
        else:
            # This shouldn't happen as we validate file types elsewhere, but just in case
            raise Exception(f"Unsupported image type: {file_extension}")
    
    # Stream download into memory
    buf = BytesIO()
    nc.files.download2stream(image_path, buf)
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode()
    
    # Create data URL
    image_data_url = f'data:{mime};base64,{b64}'
    
    return {
        'image_data_url': image_data_url,
        'mime_type': mime,
        'filename': filename
    }

def validate_image_file(file):
    """
    Helper function to validate image file.
    
    Args:
        file: Uploaded file object
        
    Returns:
        dict: Validation result with 'valid' boolean and 'error' message if invalid
    """
    if file.filename == '':
        return {'valid': False, 'error': 'No file selected'}
    
    # Check file type
    allowed_extensions = {'jpg', 'jpeg', 'png'}
    if not '.' in file.filename or file.filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
        return {'valid': False, 'error': 'Invalid file type. Only JPG, JPEG, and PNG files are allowed'}
    
    # Check file size (1MB limit)
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)  # Reset file pointer
    
    if file_size > 1 * 1024 * 1024:  # 1MB
        return {'valid': False, 'error': 'File size exceeds 1MB limit'}
    
    return {'valid': True}

def generate_buyer_image_filename(buyer_id, original_filename):
    """
    Helper function to generate secure filename for buyer images.
    
    Args:
        buyer_id (int): Buyer user ID
        original_filename (str): Original filename
        
    Returns:
        str: Generated secure filename
    """
    extension = original_filename.rsplit('.', 1)[1].lower()
    return secure_filename(f"buyer_{buyer_id}_{int(datetime.now().timestamp())}.{extension}")

def upload_buyer_image_to_nextcloud(nc, buyer_id, file_data, filename):
    """
    Helper function to upload buyer image to Nextcloud.
    
    Args:
        nc: Nextcloud instance
        buyer_id (int): Buyer user ID
        file_data: File data bytes
        filename (str): Filename to use
        
    Returns:
        str: Upload path on success
        
    Raises:
        Exception: If upload fails
    """
    remote_base_profile_images_path = f"/Photos/buyer_{buyer_id}/profile"
    upload_url = f"{remote_base_profile_images_path}/{filename}"
    
    try:
        buf = BytesIO(file_data)
        buf.seek(0)
        logging.info(f"Uploading file :::: {upload_url}")
        uploaded_file = nc.files.upload_stream(upload_url, buf)
        logging.info(f"The uploaded file data is::: {uploaded_file.name}")
        return upload_url
    except Exception as e:
        logging.debug(f"Exception while uploading file:{e}")
        raise Exception(f'Failed to upload file {upload_url}:::{str(e)}')

def create_buyer_image_response(buyer_id, **kwargs):
    """
    Helper function to create standardized buyer image response structure.
    
    Args:
        buyer_id (int): Buyer user ID
        **kwargs: Additional response fields
        
    Returns:
        dict: Response data structure
    """
    response_data = {
        'buyer_id': buyer_id,
        'has_image': False,
        'image_data_url': None,
        'mime_type': None,
        'filename': None
    }
    response_data.update(kwargs)
    return response_data

def log_buyer_image_response(response_data, context):
    """
    Helper function for centralized logging of buyer image responses.
    
    Args:
        response_data (dict): Response data to log
        context (str): Context description for the log
    """
    logging.info(f"Buyer image response ({context}): {response_data}")

# DateTime helper functions
def get_outbound_departure_datetime(data):
    """
    Helper function to get outbound departure datetime.
    """
    from ..models import SystemSetting
    
    # Check if data is None or empty, or if 'outbound' key is missing
    if data is None or not data or 'outbound' not in data:
        return datetime.now()  # Default to current time
        
    if (not data['outbound'].get('departureDateTime') or 
        data['outbound']['departureDateTime'] == '' or 
        data['outbound']['departureDateTime'] == 'T:00'):
        # Default to current time minus 2 hours (assuming arrival is event time)
        event_start_date = SystemSetting.query.filter_by(key='event_start_date').first()
        if event_start_date and event_start_date.value:
            try:
                # Check for the specific error case
                if event_start_date.value == 'T:00' or event_start_date.value.startswith('T:'):
                    logging.warning(f"Invalid date format 'T:00' detected in event_start_date")
                    return datetime.now()
                
                # Check if the value contains 'T' before splitting
                if 'T' in event_start_date.value:
                    # Extract just the date part (YYYY-MM-DD)
                    start_date_str = event_start_date.value.split('T')[0]
                    
                    # Validate the date string format
                    if len(start_date_str) == 10:  # YYYY-MM-DD is 10 characters
                        # Parse with the correct format
                        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
                        
                        # Set time to 12:00 PM (noon) - assuming arrival is 2pm
                        outbound_date = start_date.replace(hour=12, minute=0, second=0)
                        return outbound_date
                
                # If we reach here, the date format was invalid
                logging.warning(f"Invalid date format in event_start_date: {event_start_date.value}")
                return datetime.now()
                
            except (ValueError, TypeError, IndexError) as e:
                # Log the error for debugging
                logging.error(f"Error parsing event_start_date: {str(e)}")
                # Default to current time if parsing fails
                return datetime.now()
        # Default to current time if setting not found
        return datetime.now()
    else:
        try:
            # Use the provided datetime
            return datetime.fromisoformat(data['outbound']['departureDateTime'])
        except (ValueError, TypeError) as e:
            logging.error(f"Error parsing outbound departure datetime: {str(e)}")
            return datetime.now()

def get_outbound_arrival_datetime(data):
    """
    Helper function to get outbound arrival datetime.
    """
    from ..models import SystemSetting
    
    # Check if data is None or empty, or if 'outbound' key is missing
    if data is None or not data or 'outbound' not in data:
        return datetime.now()  # Default to current time
        
    if (not data['outbound'].get('arrivalDateTime') or 
        data['outbound']['arrivalDateTime'] == '' or 
        data['outbound']['arrivalDateTime'] == 'T:00'):
        # Get event start date from system settings
        event_start_date = SystemSetting.query.filter_by(key='event_start_date').first()
        if event_start_date and event_start_date.value:
            try:
                # Check for the specific error case
                if event_start_date.value == 'T:00' or event_start_date.value.startswith('T:'):
                    logging.warning(f"Invalid date format 'T:00' detected in event_start_date")
                    return datetime.now()
                
                # Check if the value contains 'T' before splitting
                if 'T' in event_start_date.value:
                    # Extract just the date part (YYYY-MM-DD)
                    start_date_str = event_start_date.value.split('T')[0]
                    
                    # Validate the date string format
                    if len(start_date_str) == 10:  # YYYY-MM-DD is 10 characters
                        # Parse with the correct format
                        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
                        
                        # Set time to 02:00 PM (14:00)
                        outbound_date = start_date.replace(hour=14, minute=0, second=0)
                        return outbound_date
                
                # If we reach here, the date format was invalid
                logging.warning(f"Invalid date format in event_start_date: {event_start_date.value}")
                return datetime.now()
                
            except (ValueError, TypeError, IndexError) as e:
                # Log the error for debugging
                logging.error(f"Error parsing event_start_date: {str(e)}")
                # Default to current time if parsing fails
                return datetime.now()
        # Default to current time if setting not found
        return datetime.now()
    else:
        try:
            # Use the provided datetime
            return datetime.fromisoformat(data['outbound']['arrivalDateTime'])
        except (ValueError, TypeError) as e:
            logging.error(f"Error parsing outbound arrival datetime: {str(e)}")
            return datetime.now()

def get_return_departure_datetime(data):
    """
    Helper function to get return departure datetime.
    """
    from ..models import SystemSetting
    
    # Check if data is None or empty, or if 'return' key is missing
    if data is None or not data or 'return' not in data:
        return datetime.now()  # Default to current time
        
    if (not data['return'].get('departureDateTime') or 
        data['return']['departureDateTime'] == '' or 
        data['return']['departureDateTime'] == 'T:00'):
        # Get event end date from system settings
        event_end_date = SystemSetting.query.filter_by(key='event_end_date').first()
        if event_end_date and event_end_date.value:
            try:
                # Check for the specific error case
                if event_end_date.value == 'T:00' or event_end_date.value.startswith('T:'):
                    logging.warning(f"Invalid date format 'T:00' detected in event_end_date")
                    return datetime.now()
                
                # Check if the value contains 'T' before splitting
                if 'T' in event_end_date.value:
                    # Extract just the date part (YYYY-MM-DD)
                    end_date_str = event_end_date.value.split('T')[0]
                    
                    # Validate the date string format
                    if len(end_date_str) == 10:  # YYYY-MM-DD is 10 characters
                        # Parse with the correct format
                        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
                        
                        # Set time to 6:00 PM on the end date
                        return_date = end_date.replace(hour=18, minute=0, second=0)
                        return return_date
                
                # If we reach here, the date format was invalid
                logging.warning(f"Invalid date format in event_end_date: {event_end_date.value}")
                return datetime.now()
                
            except (ValueError, TypeError, IndexError) as e:
                # Log the error for debugging
                logging.error(f"Error parsing event_end_date: {str(e)}")
                # Default to current time if parsing fails
                return datetime.now()
        # Default to current time if setting not found
        return datetime.now()
    else:
        try:
            # Use the provided datetime
            return datetime.fromisoformat(data['return']['departureDateTime'])
        except (ValueError, TypeError) as e:
            logging.error(f"Error parsing return departure datetime: {str(e)}")
            return datetime.now()

def get_return_arrival_datetime(data):
    """
    Helper function to get return arrival datetime.
    """
    from ..models import SystemSetting
    
    # Check if data is None or empty, or if 'return' key is missing
    if data is None or not data or 'return' not in data:
        return datetime.now()  # Default to current time
        
    if (not data['return'].get('arrivalDateTime') or 
        data['return']['arrivalDateTime'] == '' or 
        data['return']['arrivalDateTime'] == 'T:00'):
        # Get event end date from system settings
        event_end_date = SystemSetting.query.filter_by(key='event_end_date').first()
        if event_end_date and event_end_date.value:
            try:
                # Check for the specific error case
                if event_end_date.value == 'T:00' or event_end_date.value.startswith('T:'):
                    logging.warning(f"Invalid date format 'T:00' detected in event_end_date")
                    return datetime.now()
                
                # Check if the value contains 'T' before splitting
                if 'T' in event_end_date.value:
                    # Extract just the date part (YYYY-MM-DD)
                    end_date_str = event_end_date.value.split('T')[0]
                    
                    # Validate the date string format
                    if len(end_date_str) == 10:  # YYYY-MM-DD is 10 characters
                        # Parse with the correct format
                        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
                        
                        # Add 1 day and set time to 12:00 PM
                        return_date = (end_date + timedelta(days=1)).replace(hour=12, minute=0, second=0)
                        return return_date
                
                # If we reach here, the date format was invalid
                logging.warning(f"Invalid date format in event_end_date: {event_end_date.value}")
                return datetime.now()
                
            except (ValueError, TypeError, IndexError) as e:
                # Log the error for debugging
                logging.error(f"Error parsing event_end_date: {str(e)}")
                # Default to current time if parsing fails
                return datetime.now()
        # Default to current time if setting not found
        return datetime.now()
    else:
        try:
            # Use the provided datetime
            return datetime.fromisoformat(data['return']['arrivalDateTime'])
        except (ValueError, TypeError) as e:
            logging.error(f"Error parsing return arrival datetime: {str(e)}")
            return datetime.now()
