"""
Chatbot API Routes
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import logging
from ..utils.chatbot_service import ChatbotService

chatbot_bp = Blueprint('chatbot', __name__, url_prefix='/api/chat')
logger = logging.getLogger(__name__)

# Initialize chatbot service
chatbot_service = ChatbotService()

@chatbot_bp.route('/message', methods=['POST'])
@jwt_required()
def send_message():
    """
    Send a message to the chatbot
    
    Request body:
        {
            "message": "User's message text",
            "conversation_id": 123  // Optional
        }
    
    Response:
        {
            "conversation_id": 123,
            "message": {
                "id": 456,
                "role": "assistant",
                "content": "Response text",
                "metadata": {...},
                "created_at": "2025-01-12T..."
            }
        }
    """
    try:
        current_user_id = get_jwt_identity()
        if isinstance(current_user_id, str):
            current_user_id = int(current_user_id)
        
        data = request.get_json()
        
        if not data or 'message' not in data:
            return jsonify({'error': 'Message is required'}), 400
        
        message = data['message'].strip()
        if not message:
            return jsonify({'error': 'Message cannot be empty'}), 400
        
        conversation_id = data.get('conversation_id')
        
        # Process message
        response = chatbot_service.process_message(
            user_id=current_user_id,
            message=message,
            conversation_id=conversation_id
        )
        
        return jsonify(response), 200
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error processing chat message: {str(e)}")
        return jsonify({'error': 'Failed to process message'}), 500

@chatbot_bp.route('/conversations', methods=['GET'])
@jwt_required()
def get_conversations():
    """
    Get user's chat conversations
    
    Query params:
        limit: Number of conversations to return (default: 20)
    
    Response:
        {
            "conversations": [
                {
                    "id": 123,
                    "title": "First message...",
                    "created_at": "...",
                    "updated_at": "...",
                    "message_count": 10
                }
            ]
        }
    """
    try:
        current_user_id = get_jwt_identity()
        if isinstance(current_user_id, str):
            current_user_id = int(current_user_id)
        
        limit = request.args.get('limit', 20, type=int)
        limit = min(limit, 100)  # Cap at 100
        
        conversations = chatbot_service.get_user_conversations(
            user_id=current_user_id,
            limit=limit
        )
        
        return jsonify({'conversations': conversations}), 200
        
    except Exception as e:
        logger.error(f"Error fetching conversations: {str(e)}")
        return jsonify({'error': 'Failed to fetch conversations'}), 500

@chatbot_bp.route('/conversations/<int:conversation_id>', methods=['GET'])
@jwt_required()
def get_conversation(conversation_id):
    """
    Get a specific conversation with messages
    
    Response:
        {
            "id": 123,
            "title": "...",
            "created_at": "...",
            "updated_at": "...",
            "messages": [
                {
                    "id": 456,
                    "role": "user",
                    "content": "...",
                    "created_at": "..."
                },
                ...
            ]
        }
    """
    try:
        current_user_id = get_jwt_identity()
        if isinstance(current_user_id, str):
            current_user_id = int(current_user_id)
        
        conversation = chatbot_service.get_conversation(
            conversation_id=conversation_id,
            user_id=current_user_id
        )
        
        if not conversation:
            return jsonify({'error': 'Conversation not found'}), 404
        
        return jsonify(conversation), 200
        
    except Exception as e:
        logger.error(f"Error fetching conversation: {str(e)}")
        return jsonify({'error': 'Failed to fetch conversation'}), 500

@chatbot_bp.route('/conversations/<int:conversation_id>', methods=['DELETE'])
@jwt_required()
def delete_conversation(conversation_id):
    """
    Delete a conversation
    
    Response:
        {
            "message": "Conversation deleted successfully"
        }
    """
    try:
        current_user_id = get_jwt_identity()
        if isinstance(current_user_id, str):
            current_user_id = int(current_user_id)
        
        success = chatbot_service.delete_conversation(
            conversation_id=conversation_id,
            user_id=current_user_id
        )
        
        if not success:
            return jsonify({'error': 'Conversation not found'}), 404
        
        return jsonify({'message': 'Conversation deleted successfully'}), 200
        
    except Exception as e:
        logger.error(f"Error deleting conversation: {str(e)}")
        return jsonify({'error': 'Failed to delete conversation'}), 500

@chatbot_bp.route('/feedback', methods=['POST'])
@jwt_required()
def submit_feedback():
    """
    Submit feedback on a chat message
    
    Request body:
        {
            "message_id": 456,
            "feedback_type": "helpful" | "not_helpful" | "inappropriate",
            "comment": "Optional comment"
        }
    
    Response:
        {
            "message": "Feedback submitted successfully"
        }
    """
    try:
        current_user_id = get_jwt_identity()
        if isinstance(current_user_id, str):
            current_user_id = int(current_user_id)
        
        data = request.get_json()
        
        if not data or 'message_id' not in data or 'feedback_type' not in data:
            return jsonify({'error': 'message_id and feedback_type are required'}), 400
        
        message_id = data['message_id']
        feedback_type = data['feedback_type']
        comment = data.get('comment')
        
        # Validate feedback type
        valid_types = ['helpful', 'not_helpful', 'inappropriate']
        if feedback_type not in valid_types:
            return jsonify({'error': f'feedback_type must be one of: {", ".join(valid_types)}'}), 400
        
        success = chatbot_service.submit_feedback(
            message_id=message_id,
            user_id=current_user_id,
            feedback_type=feedback_type,
            comment=comment
        )
        
        if not success:
            return jsonify({'error': 'Message not found or access denied'}), 404
        
        return jsonify({'message': 'Feedback submitted successfully'}), 200
        
    except Exception as e:
        logger.error(f"Error submitting feedback: {str(e)}")
        return jsonify({'error': 'Failed to submit feedback'}), 500

@chatbot_bp.route('/health', methods=['GET'])
def health_check():
    """
    Check chatbot health status
    
    Response:
        {
            "status": "ok",
            "chatbot_enabled": true,
            "llm_available": true,
            "llm_provider": "ollama",
            "version": "1.0.0"
        }
    """
    try:
        llm_available = chatbot_service.llm.is_available()
        llm_provider = chatbot_service.llm.provider
        
        return jsonify({
            'status': 'ok',
            'chatbot_enabled': True,  # Chatbot is always enabled (has rule-based fallback)
            'llm_available': llm_available,
            'llm_provider': llm_provider,
            'version': '1.0.0'
        }), 200
        
    except Exception as e:
        logger.error(f"Error checking chatbot health: {str(e)}")
        return jsonify({
            'status': 'error',
            'chatbot_enabled': False,
            'error': str(e)
        }), 500
