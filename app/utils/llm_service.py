"""
LLM Service for AI-powered chatbot responses
Supports both Ollama (local) and OpenAI (cloud)
"""
import os
import logging
from typing import Dict, List, Optional
import requests
import json

logger = logging.getLogger(__name__)

class LLMService:
    """Service for interacting with LLMs (Ollama/OpenAI)"""
    
    def __init__(self):
        self.provider = os.getenv('CHATBOT_LLM_PROVIDER', 'ollama').lower()
        self.ollama_base_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
        self.ollama_model = os.getenv('OLLAMA_MODEL', 'llama2')
        self.openai_api_key = os.getenv('OPENAI_API_KEY', '')
        self.openai_model = os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo')
        self.max_tokens = int(os.getenv('CHATBOT_MAX_TOKENS', '500'))
        self.temperature = float(os.getenv('CHATBOT_TEMPERATURE', '0.7'))
    
    def generate_response(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        context: Optional[Dict] = None
    ) -> Dict:
        """
        Generate AI response using configured LLM
        
        Args:
            messages: List of conversation messages [{'role': 'user'|'assistant', 'content': str}]
            system_prompt: Optional system prompt for context
            context: Additional context data
        
        Returns:
            Dict with 'content', 'provider', 'model'
        """
        try:
            if self.provider == 'ollama':
                return self._ollama_generate(messages, system_prompt, context)
            elif self.provider == 'openai':
                return self._openai_generate(messages, system_prompt, context)
            else:
                raise ValueError(f"Unsupported LLM provider: {self.provider}")
        except Exception as e:
            logger.error(f"Error generating LLM response: {str(e)}")
            # Try fallback provider
            if self.provider == 'ollama' and self.openai_api_key:
                logger.info("Ollama failed, falling back to OpenAI")
                try:
                    return self._openai_generate(messages, system_prompt, context)
                except Exception as openai_error:
                    logger.error(f"OpenAI fallback also failed: {str(openai_error)}")
            
            # Return error response
            return {
                'content': "I'm having trouble processing your request right now. Please try asking in a different way or contact support if the issue persists.",
                'provider': 'error',
                'model': 'none',
                'error': str(e)
            }
    
    def _ollama_generate(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str],
        context: Optional[Dict]
    ) -> Dict:
        """Generate response using Ollama"""
        # Build prompt
        prompt = self._build_prompt(messages, system_prompt, context)
        
        # Call Ollama API
        url = f"{self.ollama_base_url}/api/generate"
        payload = {
            'model': self.ollama_model,
            'prompt': prompt,
            'stream': False,
            'options': {
                'temperature': self.temperature,
                'num_predict': self.max_tokens
            }
        }
        
        try:
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            return {
                'content': result.get('response', '').strip(),
                'provider': 'ollama',
                'model': self.ollama_model,
                'tokens': result.get('eval_count', 0)
            }
        except requests.exceptions.ConnectionError:
            raise Exception("Cannot connect to Ollama. Please ensure Ollama is running on " + self.ollama_base_url)
        except requests.exceptions.Timeout:
            raise Exception("Ollama request timed out. The model might be loading or the server is slow.")
        except Exception as e:
            raise Exception(f"Ollama error: {str(e)}")
    
    def _openai_generate(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str],
        context: Optional[Dict]
    ) -> Dict:
        """Generate response using OpenAI"""
        if not self.openai_api_key:
            raise Exception("OpenAI API key not configured")
        
        try:
            from openai import OpenAI
        except ImportError:
            raise Exception("OpenAI library not installed. Run: pip install openai")
        
        # Initialize OpenAI client (new API v1.0+)
        client = OpenAI(api_key=self.openai_api_key)
        
        # Build messages for OpenAI format
        openai_messages = []
        
        if system_prompt:
            openai_messages.append({
                'role': 'system',
                'content': system_prompt
            })
        
        # Add context to system message if provided
        if context:
            context_message = self._format_context(context)
            if context_message:
                openai_messages.append({
                    'role': 'system',
                    'content': f"User Context:\n{context_message}"
                })
        
        # Add conversation history
        openai_messages.extend(messages)
        
        try:
            # Use new OpenAI API v1.0+ syntax
            response = client.chat.completions.create(
                model=self.openai_model,
                messages=openai_messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )
            
            return {
                'content': response.choices[0].message.content.strip(),
                'provider': 'openai',
                'model': self.openai_model,
                'tokens': response.usage.total_tokens
            }
        except Exception as e:
            raise Exception(f"OpenAI error: {str(e)}")
    
    def _build_prompt(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str],
        context: Optional[Dict]
    ) -> str:
        """Build a single prompt string for Ollama"""
        prompt_parts = []
        
        # Add system prompt
        if system_prompt:
            prompt_parts.append(f"System: {system_prompt}\n")
        
        # Add context
        if context:
            context_str = self._format_context(context)
            logger.info(f"Formatted context length: {len(context_str) if context_str else 0}")
            logger.info(f"Formatted context preview: {context_str[:500] if context_str else 'EMPTY'}")
            if context_str:
                prompt_parts.append(f"User Context:\n{context_str}\n")
        
        # Add conversation history
        for msg in messages:
            role = "User" if msg['role'] == 'user' else "Assistant"
            prompt_parts.append(f"{role}: {msg['content']}")
        
        # Add final prompt for assistant
        prompt_parts.append("Assistant:")
        
        full_prompt = "\n".join(prompt_parts)
        logger.info(f"Full prompt length: {len(full_prompt)}")
        
        return full_prompt
    
    def _format_context(self, context: Dict) -> str:
        """Format context dictionary into readable string"""
        context_parts = []
        
        if context.get('user_role'):
            context_parts.append(f"- User Role: {context['user_role'].title()}")
        
        if context.get('user_name'):
            context_parts.append(f"- Name: {context['user_name']}")
        
        if context.get('organization'):
            context_parts.append(f"- Organization: {context['organization']}")
        
        # Format STALL INFO (for sellers)
        if context.get('stall_info'):
            stall = context['stall_info']
            context_parts.append(f"\n**Stall Information:**")
            context_parts.append(f"- Stall Number: {stall.get('allocated_stall_number') or stall.get('number')}")
            context_parts.append(f"- Fascia Name: {stall.get('fascia_name')}")
            if stall.get('stall_type'):
                st = stall['stall_type']
                context_parts.append(f"- Stall Type: {st.get('name')} ({st.get('size')})")
                context_parts.append(f"- Max Meetings Per Attendee: {st.get('max_meetings_per_attendee')}")
                context_parts.append(f"- Inclusions: {st.get('inclusions')}")
        
        # Format meeting statistics
        if context.get('meeting_statistics'):
            stats = context['meeting_statistics']
            context_parts.append(f"\n**Meeting Statistics:**")
            context_parts.append(f"- Total Meetings: {stats.get('total')}")
            context_parts.append(f"- Pending: {stats.get('by_status', {}).get('pending')}")
            context_parts.append(f"- Accepted: {stats.get('by_status', {}).get('accepted')}")
            context_parts.append(f"- Upcoming: {stats.get('upcoming_count')}")
            context_parts.append(f"- Past: {stats.get('past_count')}")
        
        # Format meeting data (detailed)
        if context.get('meetings'):
            meetings = context['meetings']
            if meetings:
                context_parts.append(f"\n**Recent Meetings:**")
                for m in meetings[:5]:  # Show up to 5 meetings
                    context_parts.append(f"  • Meeting #{m.get('id')}: {m.get('partner_name')}")
                    context_parts.append(f"    Status: {m.get('status')}, Date: {m.get('date') or 'Not scheduled'}, Time: {m.get('time') or 'TBD'}")
        
        # Format attendees (for sellers)
        if context.get('attendees') and len(context['attendees']) > 0:
            context_parts.append(f"\n**Team Attendees:**")
            for att in context['attendees']:
                context_parts.append(f"  • {att.get('name')} ({att.get('designation')})")
        
        # Format category info (for buyers)
        if context.get('category_info'):
            cat = context['category_info']
            context_parts.append(f"\n**Buyer Category:**")
            context_parts.append(f"- Category: {cat.get('name')}")
            context_parts.append(f"- Max Meetings Allowed: {cat.get('max_meetings')}")
            context_parts.append(f"- Accommodation Hosted: {cat.get('accommodation_hosted')}")
        
        # Format travel data
        if context.get('travel'):
            travel = context['travel']
            context_parts.append(f"\n**Travel Plan:**")
            if travel:
                context_parts.append(f"- Event: {travel.get('event_name', 'Splash25')}")
                if travel.get('transportation'):
                    trans = travel['transportation']
                    context_parts.append(f"- Transportation: {trans.get('outbound', {}).get('carrier', 'N/A')} (outbound)")
                if travel.get('accommodation'):
                    acc = travel['accommodation']
                    context_parts.append(f"- Accommodation: {acc.get('property_name', 'N/A')}")
        
        # Format ground transportation
        if context.get('ground_transportation'):
            gt = context['ground_transportation']
            context_parts.append(f"\n**Ground Transportation:**")
            if gt.get('pickup'):
                context_parts.append(f"- Pickup: {gt['pickup'].get('location')} at {gt['pickup'].get('datetime')}")
            if gt.get('dropoff'):
                context_parts.append(f"- Dropoff: {gt['dropoff'].get('location')} at {gt['dropoff'].get('datetime')}")
        
        # Format financial status
        if context.get('financial_status'):
            fin = context['financial_status']
            context_parts.append(f"\n**Payment Status:**")
            if fin.get('deposit_paid') is not None:
                context_parts.append(f"- Deposit Paid: {'Yes' if fin.get('deposit_paid') else 'No'}")
            if fin.get('entry_fee_paid') is not None:
                context_parts.append(f"- Entry Fee Paid: {'Yes' if fin.get('entry_fee_paid') else 'No'}")
            if fin.get('total_amt_due') is not None:
                context_parts.append(f"- Total Amount Due: {fin.get('total_amt_due')}")
            if fin.get('total_amt_paid') is not None:
                context_parts.append(f"- Total Amount Paid: {fin.get('total_amt_paid')}")
        
        # Format time slots
        if context.get('time_slots'):
            slots = context['time_slots']
            context_parts.append(f"\n**Time Slots:**")
            context_parts.append(f"- Total Slots: {slots.get('total_slots')}")
            context_parts.append(f"- Available: {slots.get('available_count')}")
            context_parts.append(f"- Booked: {slots.get('booked_count')}")
        
        # Format detailed accommodation
        if context.get('detailed_accommodation'):
            acc = context['detailed_accommodation']
            context_parts.append(f"\n**Accommodation Details:**")
            context_parts.append(f"- Property: {acc.get('property_name')}")
            if acc.get('contact_person'):
                context_parts.append(f"- Contact Person: {acc.get('contact_person')}")
            if acc.get('contact_phone'):
                context_parts.append(f"- Contact Phone: {acc.get('contact_phone')}")
            context_parts.append(f"- Check-in: {acc.get('check_in_datetime')}")
            context_parts.append(f"- Check-out: {acc.get('check_out_datetime')}")
            if acc.get('booking_reference'):
                context_parts.append(f"- Booking Reference: {acc.get('booking_reference')}")
        
        # Format bank details (for buyers - only show that it's available)
        if context.get('bank_details'):
            bank = context['bank_details']
            context_parts.append(f"\n**Bank Details on File:**")
            context_parts.append(f"- Bank: {bank.get('bank_name')}")
            context_parts.append(f"- Account Available: {'Yes' if bank.get('account_number_available') else 'No'}")
            context_parts.append(f"- IFSC Code: {bank.get('ifsc_code')}")
        
        return "\n".join(context_parts)
    
    def get_system_prompt(self, user_role: str) -> str:
        """Get system prompt based on user role"""
        base_prompt = """You are a helpful assistant for the Splash25 event management system.

IMPORTANT: You will receive detailed user context with their ACTUAL meeting schedule and travel plans. 
ALWAYS use this specific data to answer questions. DO NOT make assumptions or provide generic guidance.

When user asks about meetings:
- Check the "Meeting Schedule" section in User Context
- If it says "NO meetings scheduled", tell them they have no meetings
- If meetings are listed, show the actual meeting details
- Be specific and use the actual data provided

When user asks about travel:
- Check the "Travel Plan" section in User Context
- Show their actual travel arrangements
- Be specific about their transportation and accommodation

Event Information:
- Dates: January 10-12, 2025
- Venue: Wayanad, Kerala

Always be concise, helpful, and professional. Use ONLY the data provided in User Context."""
        
        role_specific = {
            'buyer': """
The user is a BUYER (event participant) who can:
- Browse and connect with sellers
- Schedule meetings with sellers
- Manage their travel plans
- View event information""",
            'seller': """
The user is a SELLER (exhibitor) who can:
- View and manage meeting requests
- See buyer information
- Update their stall and business information
- Manage their schedule"""
        }
        
        return f"{base_prompt}\n\n{role_specific.get(user_role, '')}"
    
    def select_tools(self, user_message: str, user_role: str, tool_prompt: str) -> List[str]:
        """
        Select which tools to use based on user message
        
        Args:
            user_message: User's question
            user_role: User's role
            tool_prompt: Tool selection prompt
        
        Returns:
            List of tool names to execute
        """
        try:
            # Use a lightweight call for tool selection
            if self.provider == 'ollama':
                url = f"{self.ollama_base_url}/api/generate"
                payload = {
                    'model': self.ollama_model,
                    'prompt': tool_prompt,
                    'stream': False,
                    'options': {
                        'temperature': 0.1,  # Low temperature for consistent selection
                        'num_predict': 100  # Short response
                    }
                }
                response = requests.post(url, json=payload, timeout=10)
                response.raise_for_status()
                result = response.json()
                response_text = result.get('response', '').strip()
            
            elif self.provider == 'openai':
                from openai import OpenAI
                client = OpenAI(api_key=self.openai_api_key)
                response = client.chat.completions.create(
                    model=self.openai_model,
                    messages=[{"role": "user", "content": tool_prompt}],
                    max_tokens=100,
                    temperature=0.1
                )
                response_text = response.choices[0].message.content.strip()
            
            # Parse JSON response
            import re
            # Extract JSON array from response
            json_match = re.search(r'\[.*?\]', response_text, re.DOTALL)
            if json_match:
                tools_json = json.loads(json_match.group())
                logger.info(f"Selected tools: {tools_json}")
                return tools_json
            else:
                logger.warning(f"Could not parse tool selection: {response_text}")
                return ["general_info"]  # Fallback
        
        except Exception as e:
            logger.error(f"Tool selection error: {str(e)}")
            return ["general_info"]  # Fallback to basic context
    
    def is_available(self) -> bool:
        """Check if LLM service is available"""
        try:
            if self.provider == 'ollama':
                response = requests.get(f"{self.ollama_base_url}/api/tags", timeout=5)
                return response.status_code == 200
            elif self.provider == 'openai':
                return bool(self.openai_api_key)
            return False
        except:
            return False
