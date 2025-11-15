"""
Main chatbot service with intelligent tool-based context loading
"""
import logging
import re
from typing import Dict, List, Optional
from datetime import datetime
from ..models import db, ChatConversation, ChatMessage, User
from .llm_service import LLMService
from .chatbot_context import ChatbotContext
from .chatbot_tools import ChatbotTools

logger = logging.getLogger(__name__)

class ChatbotService:
    """Chatbot service with dynamic tool selection"""
    
    def __init__(self):
        self.llm = LLMService()
        self.context_manager = ChatbotContext()
        self.tools = ChatbotTools()
    
    def _extract_company_names(self, message: str) -> List[str]:
        """Extract company names from message (capitalized multi-word phrases)"""
        pattern = r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+(?:\s+(?:Private|Pvt\.?|Limited|Ltd\.?|Inc\.?|Corporation|Corp\.?))?)'
        return re.findall(pattern, message)

    def process_message(
        self,
        user_id: int,
        message: str,
        conversation_id: Optional[int] = None
    ) -> Dict:
        """
        Process user message and generate response using dynamic tool selection
        
        Args:
            user_id: ID of the user sending the message
            message: User's message text
            conversation_id: Optional conversation ID (creates new if not provided)
        
        Returns:
            Dict with conversation_id, message response, metadata
        """
        try:
            # Get or create conversation
            if conversation_id:
                conversation = ChatConversation.query.get(conversation_id)
                if not conversation or conversation.user_id != user_id:
                    raise ValueError("Invalid conversation ID")
            else:
                conversation = self._create_conversation(user_id, message)
            
            # Save user message
            user_message = ChatMessage(
                conversation_id=conversation.id,
                role='user',
                content=message
            )
            db.session.add(user_message)
            db.session.commit()
            
            # Get user
            user = User.query.get(user_id)
            
            # STEP 1: Tool Selection
            logger.info(f"🔍 Starting tool selection for message: {message[:50]}...")
            tool_selection_prompt = self.tools.get_tool_selection_prompt(message, user.role)
            selected_tools = self.llm.select_tools(message, user.role, tool_selection_prompt)
            logger.info(f"✅ Selected tools: {selected_tools}")
            
            # STEP 2: Execute Selected Tools
            enriched_context = {}
            
            # Always include basic user context
            user_context = self.context_manager.get_user_context(user_id)
            enriched_context.update(user_context)
            
            # Execute each selected tool
            if selected_tools and selected_tools != ["general_info"]:
                for tool_name in selected_tools:
                    try:
                        logger.info(f"⚙️ Executing tool: {tool_name}")
                        
                        # Prepare tool parameters
                        tool_params = {}
                        
                        # Handle tools that need extracted parameters from message
                        if tool_name == 'search_sellers':
                            # Extract company/seller name from message
                            company_keywords = self._extract_company_names(message)
                            tool_params['query'] = company_keywords[0] if company_keywords else message
                            tool_params['limit'] = 5
                        elif tool_name == 'search_meetings_by_company':
                            # Extract company name
                            company_keywords = self._extract_company_names(message)
                            if company_keywords:
                                tool_params['company_name'] = company_keywords[0]
                            else:
                                # Try to extract from message (fallback)
                                tool_params['company_name'] = message
                        
                        result = self.tools.execute_tool(tool_name, user_id, user.role, **tool_params)
                        
                        # Map tool name to context key
                        context_key_map = {
                            'get_stall_info': 'stall_info',
                            'get_meeting_statistics': 'meeting_statistics',
                            'get_meeting_details': 'meetings',
                            'get_travel_details': 'travel',
                            'get_ground_transportation': 'ground_transportation',
                            'get_detailed_accommodation': 'detailed_accommodation',
                            'get_financial_status': 'financial_status',
                            'get_attendees_info': 'attendees',
                            'get_category_info': 'category_info',
                            'get_time_slots': 'time_slots',
                            'get_bank_details': 'bank_details',
                            'search_sellers': 'search_results',
                            'search_meetings_by_company': 'meetings'
                        }
                        
                        context_key = context_key_map.get(tool_name, tool_name)
                        
                        # Handle special cases
                        if tool_name == 'get_meeting_details':
                            enriched_context['meetings'] = result.get('meetings', [])
                            enriched_context['meeting_count'] = result.get('count', 0)
                        elif tool_name == 'search_meetings_by_company':
                            enriched_context['meetings'] = result.get('meetings', [])
                            enriched_context['meeting_count'] = len(result.get('meetings', []))
                        else:
                            enriched_context[context_key] = result
                        
                        logger.info(f"✅ Tool {tool_name} completed")
                    except Exception as tool_error:
                        logger.error(f"❌ Error executing tool {tool_name}: {str(tool_error)}")
                        # Continue with other tools
            
            logger.info(f"📦 Context gathered with keys: {enriched_context.keys()}")
            logger.info(f"📊 Context size: {len(str(enriched_context))} characters")
            
            # STEP 3: Generate Response with Focused Context
            history = self._get_conversation_history(conversation.id)
            
            llm_response = self.llm.generate_response(
                messages=history,
                system_prompt=self.llm.get_system_prompt(user.role),
                context=enriched_context
            )
            
            response_text = llm_response['content']
            response_metadata = {
                'provider': llm_response['provider'],
                'model': llm_response['model'],
                'used_llm': True,
                'context_provided': True,
                'selected_tools': selected_tools,
                'tools_executed': len(selected_tools)
            }
            
            # Save assistant response
            assistant_message = ChatMessage(
                conversation_id=conversation.id,
                role='assistant',
                content=response_text,
                metadata=response_metadata
            )
            db.session.add(assistant_message)
            
            # Update conversation timestamp
            conversation.updated_at = datetime.utcnow()
            db.session.commit()
            
            logger.info(f"✅ Response generated successfully")
            
            return {
                'conversation_id': conversation.id,
                'message': {
                    'id': assistant_message.id,
                    'role': 'assistant',
                    'content': response_text,
                    'metadata': response_metadata,
                    'created_at': assistant_message.created_at.isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            db.session.rollback()
            raise
    
    def _create_conversation(self, user_id: int, initial_message: str) -> ChatConversation:
        """Create a new conversation"""
        # Generate title from first message (first 50 chars)
        title = initial_message[:50] + '...' if len(initial_message) > 50 else initial_message
        
        conversation = ChatConversation(
            user_id=user_id,
            title=title
        )
        db.session.add(conversation)
        db.session.commit()
        
        return conversation
    
    def _get_conversation_history(self, conversation_id: int, limit: int = 10) -> List[Dict]:
        """Get conversation history for LLM context"""
        messages = ChatMessage.query.filter_by(conversation_id=conversation_id)\
            .order_by(ChatMessage.created_at.desc())\
            .limit(limit)\
            .all()
        
        # Reverse to get chronological order
        messages.reverse()
        
        return [
            {
                'role': msg.role,
                'content': msg.content
            }
            for msg in messages
            if msg.role in ['user', 'assistant']
        ]
    
    def get_conversation(self, conversation_id: int, user_id: int) -> Optional[Dict]:
        """Get conversation with messages"""
        conversation = ChatConversation.query.get(conversation_id)
        if not conversation or conversation.user_id != user_id:
            return None
        
        return conversation.to_dict(include_messages=True)
    
    def get_user_conversations(self, user_id: int, limit: int = 20) -> List[Dict]:
        """Get user's conversations"""
        conversations = ChatConversation.query.filter_by(user_id=user_id, is_active=True)\
            .order_by(ChatConversation.updated_at.desc())\
            .limit(limit)\
            .all()
        
        return [conv.to_dict() for conv in conversations]
    
    def delete_conversation(self, conversation_id: int, user_id: int) -> bool:
        """Delete (deactivate) a conversation"""
        conversation = ChatConversation.query.get(conversation_id)
        if not conversation or conversation.user_id != user_id:
            return False
        
        conversation.is_active = False
        db.session.commit()
        return True
    
    def submit_feedback(self, message_id: int, user_id: int, feedback_type: str, comment: Optional[str] = None) -> bool:
        """Submit feedback on a message"""
        from ..models import ChatFeedback
        
        message = ChatMessage.query.get(message_id)
        if not message:
            return False
        
        # Check if user has access to this message
        conversation = ChatConversation.query.get(message.conversation_id)
        if not conversation or conversation.user_id != user_id:
            return False
        
        # Check if feedback already exists
        existing = ChatFeedback.query.filter_by(
            message_id=message_id,
            user_id=user_id
        ).first()
        
        if existing:
            # Update existing feedback
            existing.feedback_type = feedback_type
            existing.comment = comment
        else:
            # Create new feedback
            feedback = ChatFeedback(
                message_id=message_id,
                user_id=user_id,
                feedback_type=feedback_type,
                comment=comment
            )
            db.session.add(feedback)
        
        db.session.commit()
        return True
