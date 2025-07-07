import os
import base64
import logging
from datetime import datetime
from io import BytesIO
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from nc_py_api import Nextcloud, NextcloudException
from werkzeug.utils import secure_filename
from ..utils.auth import admin_required

# Constants
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
ALLOWED_EXTENSIONS = {'svg'}
ALLOWED_MIME_TYPES = {'image/svg+xml', 'text/xml', 'application/xml'}
FLOORPLAN_DIRECTORY = '/Photos/splash25_floorplan'
FLOORPLAN_FILENAME = 'splash25_floorplan.svg'

# Blueprint setup
floorplan = Blueprint('floorplan', __name__, url_prefix='/api/floorplan')

def get_nextcloud_connection():
    """
    Helper function to initialize Nextcloud connection.
    
    Returns:
        Nextcloud or None: Nextcloud instance if credentials are available, None otherwise
    """
    storage_url = os.getenv('EXTERNAL_STORAGE_URL')
    storage_user = os.getenv('EXTERNAL_STORAGE_USER')
    storage_password = os.getenv('EXTERNAL_STORAGE_PASSWORD')
    
    if not all([storage_url, storage_user, storage_password]):
        logging.error("Nextcloud credentials not found in environment variables")
        return None
    
    # Ensure storage_url ends with index.php (we know it's not None due to the check above)
    if not storage_url.endswith('index.php'):
        storage_url = storage_url.rstrip('/') + '/index.php'
    
    try:
        return Nextcloud(nextcloud_url=storage_url, nc_auth_user=storage_user, nc_auth_pass=storage_password)
    except Exception as e:
        logging.error(f"Failed to initialize Nextcloud connection: {str(e)}")
        return None

def validate_svg_file(file):
    """
    Helper function to validate SVG file.
    
    Args:
        file: Uploaded file object
        
    Returns:
        dict: Validation result with 'valid' boolean and 'error' message if invalid
    """
    if not file or file.filename == '':
        return {'valid': False, 'error': 'No file selected'}
    
    # Check file extension
    if not '.' in file.filename:
        return {'valid': False, 'error': 'File must have an extension'}
    
    file_extension = file.filename.rsplit('.', 1)[1].lower()
    if file_extension not in ALLOWED_EXTENSIONS:
        return {'valid': False, 'error': 'Invalid file type. Only SVG files are allowed'}
    
    # Check MIME type
    if hasattr(file, 'content_type') and file.content_type:
        if file.content_type not in ALLOWED_MIME_TYPES:
            return {'valid': False, 'error': f'Invalid MIME type. Expected SVG, got {file.content_type}'}
    
    # Check file size
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)  # Reset file pointer
    
    if file_size > MAX_FILE_SIZE:
        return {'valid': False, 'error': f'File size exceeds {MAX_FILE_SIZE // (1024 * 1024)}MB limit'}
    
    if file_size == 0:
        return {'valid': False, 'error': 'File is empty'}
    
    return {'valid': True, 'file_size': file_size}

def ensure_floorplan_directory():
    """
    Helper function to ensure floorplan directory exists.
    
    Returns:
        dict: Result with 'success' boolean and 'error' message if failed
    """
    nc = get_nextcloud_connection()
    if not nc:
        return {'success': False, 'error': 'Nextcloud connection not available'}
    
    try:
        # Check if directory exists
        nc.files.listdir(FLOORPLAN_DIRECTORY)
        logging.debug(f"Found floorplan directory: {FLOORPLAN_DIRECTORY}")
        return {'success': True}
    except NextcloudException as e:
        if e.status_code != 404:
            return {'success': False, 'error': f'Error checking directory: {str(e)}'}
        
        # Directory doesn't exist, create it
        try:
            logging.info(f"Creating floorplan directory: {FLOORPLAN_DIRECTORY}")
            nc.files.mkdir(FLOORPLAN_DIRECTORY)
            logging.info(f"Successfully created directory: {FLOORPLAN_DIRECTORY}")
            return {'success': True}
        except Exception as create_error:
            logging.error(f"Failed to create directory {FLOORPLAN_DIRECTORY}: {str(create_error)}")
            return {'success': False, 'error': f'Failed to create directory: {str(create_error)}'}
    except Exception as e:
        logging.error(f"Unexpected error checking directory: {str(e)}")
        return {'success': False, 'error': f'Unexpected error: {str(e)}'}

def upload_floorplan(file_data):
    """
    Helper function to upload floorplan to storage.
    
    Args:
        file_data: File data bytes
        
    Returns:
        dict: Upload result with success status and details
    """
    nc = get_nextcloud_connection()
    if not nc:
        return {'success': False, 'error': 'Nextcloud connection not available'}
    
    # Ensure directory exists
    dir_result = ensure_floorplan_directory()
    if not dir_result['success']:
        return dir_result
    
    # Upload file
    upload_path = f"{FLOORPLAN_DIRECTORY}/{FLOORPLAN_FILENAME}"
    
    try:
        buf = BytesIO(file_data)
        buf.seek(0)
        logging.info(f"Uploading floorplan to: {upload_path}")
        uploaded_file = nc.files.upload_stream(upload_path, buf)
        logging.info(f"Successfully uploaded floorplan: {uploaded_file.name}")
        
        return {
            'success': True,
            'file_path': upload_path,
            'file_name': FLOORPLAN_FILENAME,
            'file_size': len(file_data),
            'uploaded_at': datetime.utcnow().isoformat() + 'Z'
        }
    except Exception as e:
        logging.error(f"Failed to upload floorplan: {str(e)}")
        return {'success': False, 'error': f'Failed to upload file: {str(e)}'}

def convert_svg_to_base64_data_url(file_path):
    """
    Helper function to convert SVG file to base64 data URL.
    
    Args:
        file_path (str): Path to the SVG file
        
    Returns:
        dict: Dictionary with image data (image_data_url, mime_type, filename) or error
    """
    nc = get_nextcloud_connection()
    if not nc:
        return {'success': False, 'error': 'Nextcloud connection not available'}
    
    try:
        # Get file info for MIME type using find method
        mime_type = 'image/svg+xml'  # Default for SVG
        try:
            # Use find method to get FSNode object
            files = nc.files.find(["eq", "name", FLOORPLAN_FILENAME], path=FLOORPLAN_DIRECTORY)
            if files and len(files) > 0:
                file_node = files[0]
                if hasattr(file_node, 'mime_type') and file_node.mime_type:
                    mime_type = file_node.mime_type
        except Exception as e:
            logging.warning(f"Could not get MIME type from file info for {file_path}: {str(e)}")
        
        # Stream download into memory
        buf = BytesIO()
        nc.files.download2stream(file_path, buf)
        buf.seek(0)
        b64 = base64.b64encode(buf.read()).decode()
        
        # Create data URL
        image_data_url = f'data:{mime_type};base64,{b64}'
        
        return {
            'success': True,
            'image_data_url': image_data_url,
            'mime_type': mime_type,
            'filename': FLOORPLAN_FILENAME
        }
    except Exception as e:
        logging.error(f"Failed to convert SVG to base64: {str(e)}")
        return {'success': False, 'error': f'Failed to process file: {str(e)}'}

def download_floorplan():
    """
    Helper function to download and convert floorplan to base64 data URL.
    
    Returns:
        dict: Dictionary with image data or error information
    """
    nc = get_nextcloud_connection()
    if not nc:
        return {'success': False, 'error': 'Nextcloud connection not available'}
    
    file_path = f"{FLOORPLAN_DIRECTORY}/{FLOORPLAN_FILENAME}"
    
    try:
        # Check if file exists using find method
        files = nc.files.find(["eq", "name", FLOORPLAN_FILENAME], path=FLOORPLAN_DIRECTORY)
        if not files or len(files) == 0:
            return {'success': False, 'error': 'Floorplan not found', 'status_code': 404}
        
        # Convert to base64 data URL
        return convert_svg_to_base64_data_url(file_path)
        
    except NextcloudException as e:
        if e.status_code == 404:
            return {'success': False, 'error': 'Floorplan not found', 'status_code': 404}
        else:
            logging.error(f"Error accessing floorplan: {str(e)}")
            return {'success': False, 'error': f'Error accessing floorplan: {str(e)}'}
    except Exception as e:
        logging.error(f"Unexpected error downloading floorplan: {str(e)}")
        return {'success': False, 'error': f'Unexpected error: {str(e)}'}

# Route handlers

@floorplan.route('/upload', methods=['POST'])
@admin_required
def upload_floorplan_route():
    """
    Endpoint for admin to upload a floor plan (SVG image file)
    """
    try:
        # Check if file is present in request
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        
        # Validate file
        validation_result = validate_svg_file(file)
        if not validation_result['valid']:
            return jsonify({'error': validation_result['error']}), 400
        
        # Read file data
        file.seek(0)
        file_data = file.read()
        
        # Upload file
        upload_result = upload_floorplan(file_data)
        
        if upload_result['success']:
            return jsonify({
                'message': 'Floorplan uploaded successfully',
                'file_info': {
                    'filename': upload_result['file_name'],
                    'file_size': upload_result['file_size'],
                    'uploaded_at': upload_result['uploaded_at']
                }
            }), 200
        else:
            return jsonify({'error': upload_result['error']}), 500
            
    except Exception as e:
        logging.error(f"Error in upload_floorplan_route: {str(e)}")
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

@floorplan.route('', methods=['GET'])
@jwt_required()
def get_floorplan_route():
    """
    Endpoint to get the floorplan for authenticated users
    """
    try:
        # Download and convert floorplan
        download_result = download_floorplan()
        
        if download_result['success']:
            return jsonify({
                'message': 'Floorplan retrieved successfully',
                'floorplan': {
                    'image_data_url': download_result['image_data_url'],
                    'mime_type': download_result['mime_type'],
                    'filename': download_result['filename']
                }
            }), 200
        else:
            status_code = download_result.get('status_code', 500)
            if status_code == 404:
                return jsonify({
                    'error': 'Floorplan not available',
                    'message': 'No floorplan has been uploaded yet'
                }), 404
            else:
                return jsonify({'error': download_result['error']}), status_code
                
    except Exception as e:
        logging.error(f"Error in get_floorplan_route: {str(e)}")
        return jsonify({'error': f'Failed to retrieve floorplan: {str(e)}'}), 500
