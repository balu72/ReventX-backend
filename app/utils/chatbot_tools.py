"""
Tool Registry for Chatbot Context Methods
Maps each context method to a tool that can be dynamically selected by the LLM
"""
from typing import Dict, List, Callable, Any
from .chatbot_context import ChatbotContext

class ChatbotTools:
    """Registry of available tools for dynamic context loading"""
    
    # Tool definitions with descriptions for LLM
    TOOLS = {
        "get_stall_info": {
            "description": "Get seller's stall number, fascia name, type, size, and inclusions. Use when user asks about their stall.",
            "method": ChatbotContext.get_stall_info,
            "params": ["user_id"],
            "roles": ["seller"],
            "keywords": ["stall", "booth", "stand", "number", "location"]
        },
        "get_meeting_statistics": {
            "description": "Get meeting statistics with breakdown by status (pending, accepted, rejected, completed). Use when user asks about meeting counts or statistics.",
            "method": ChatbotContext.get_meeting_statistics,
            "params": ["user_id", "user_role"],
            "roles": ["buyer", "seller"],
            "keywords": ["how many", "statistics", "stats", "count", "total"]
        },
        "get_meeting_details": {
            "description": "Get list of meetings with partner names, dates, times, and status. Use when user wants to see their meetings or meeting schedule.",
            "method": ChatbotContext.get_meeting_details,
            "params": ["user_id", "user_role", "meeting_id"],
            "roles": ["buyer", "seller"],
            "keywords": ["meetings", "schedule", "appointments", "who", "when"]
        },
        "get_travel_details": {
            "description": "Get travel plan including flights (carrier, times), event dates, and venue. Use when user asks about travel or flight information.",
            "method": ChatbotContext.get_travel_details,
            "params": ["user_id"],
            "roles": ["buyer", "seller"],
            "keywords": ["travel", "flight", "airline", "departure", "arrival", "event"]
        },
        "get_ground_transportation": {
            "description": "Get ground transportation details including pickup/dropoff locations, times, and driver contact. Use when user asks about pickup or ground transport.",
            "method": ChatbotContext.get_ground_transportation,
            "params": ["user_id"],
            "roles": ["buyer", "seller"],
            "keywords": ["pickup", "dropoff", "transport", "driver", "car", "vehicle"]
        },
        "get_detailed_accommodation": {
            "description": "Get accommodation details including property name, contact person, phone, check-in/out times, and booking reference. Use when user asks about hotel or accommodation.",
            "method": ChatbotContext.get_detailed_accommodation,
            "params": ["user_id"],
            "roles": ["buyer", "seller"],
            "keywords": ["accommodation", "hotel", "property", "stay", "room", "check-in", "check-out"]
        },
        "get_financial_status": {
            "description": "Get payment status including deposit paid, entry fee, amounts due/paid. Use when user asks about payments or fees.",
            "method": ChatbotContext.get_financial_status,
            "params": ["user_id", "user_role"],
            "roles": ["buyer", "seller"],
            "keywords": ["payment", "deposit", "fee", "paid", "due", "amount", "money"]
        },
        "get_attendees_info": {
            "description": "Get list of team attendees with names, designations, and contact info. Use when user asks about team members or attendees.",
            "method": ChatbotContext.get_attendees_info,
            "params": ["user_id"],
            "roles": ["seller"],
            "keywords": ["team", "attendees", "members", "staff", "who is coming"]
        },
        "get_category_info": {
            "description": "Get buyer category information including max meetings allowed, hosted services. Use when user asks about their category or limits.",
            "method": ChatbotContext.get_category_info,
            "params": ["user_id"],
            "roles": ["buyer"],
            "keywords": ["category", "limit", "max meetings", "hosted", "tier"]
        },
        "get_time_slots": {
            "description": "Get time slots information showing available and booked slots. Use when user asks about availability or free time.",
            "method": ChatbotContext.get_time_slots,
            "params": ["user_id", "user_role", "available_only"],
            "roles": ["buyer", "seller"],
            "keywords": ["time slots", "available", "free", "schedule", "open"]
        },
        "get_bank_details": {
            "description": "Get bank details on file including bank name and account availability. Use when user asks about bank information or refunds.",
            "method": ChatbotContext.get_bank_details,
            "params": ["user_id"],
            "roles": ["buyer"],
            "keywords": ["bank", "account", "refund", "IFSC"]
        },
        "search_sellers": {
            "description": "Search for sellers by name or business name. Use when user wants to find a specific seller or business.",
            "method": ChatbotContext.search_sellers,
            "params": ["query", "limit"],
            "roles": ["buyer", "seller"],
            "keywords": ["search", "find", "look for", "seller", "business"]
        },
        "search_meetings_by_company": {
            "description": "Search meetings by company or organization name. Use when user asks about meetings with a specific company.",
            "method": ChatbotContext.search_meetings_by_company,
            "params": ["user_id", "user_role", "company_name"],
            "roles": ["buyer", "seller"],
            "keywords": ["meetings with", "company", "organization"]
        }
    }
    
    @classmethod
    def get_tool_descriptions(cls, user_role: str) -> str:
        """Generate formatted tool descriptions for LLM prompt"""
        descriptions = []
        for i, (tool_name, tool_info) in enumerate(cls.TOOLS.items(), 1):
            # Only include tools available for user's role
            if user_role in tool_info["roles"]:
                descriptions.append(f"{i}. {tool_name}: {tool_info['description']}")
        return "\n".join(descriptions)
    
    @classmethod
    def get_available_tools(cls, user_role: str) -> List[str]:
        """Get list of tool names available for user's role"""
        return [
            tool_name 
            for tool_name, tool_info in cls.TOOLS.items() 
            if user_role in tool_info["roles"]
        ]
    
    @classmethod
    def execute_tool(cls, tool_name: str, user_id: int, user_role: str, **kwargs) -> Any:
        """
        Execute a tool by name
        
        Args:
            tool_name: Name of the tool to execute
            user_id: User ID
            user_role: User role
            **kwargs: Additional parameters for the tool
        
        Returns:
            Result from the tool execution
        """
        if tool_name not in cls.TOOLS:
            raise ValueError(f"Unknown tool: {tool_name}")
        
        tool_info = cls.TOOLS[tool_name]
        
        # Check if user has access to this tool
        if user_role not in tool_info["roles"]:
            raise PermissionError(f"User role '{user_role}' cannot access tool '{tool_name}'")
        
        # Build parameters based on tool requirements
        params = {}
        if "user_id" in tool_info["params"]:
            params["user_id"] = user_id
        if "user_role" in tool_info["params"]:
            params["user_role"] = user_role
        
        # Add any additional kwargs
        params.update(kwargs)
        
        # Execute the tool
        return tool_info["method"](**params)
    
    @classmethod
    def get_tool_selection_prompt(cls, user_message: str, user_role: str) -> str:
        """Generate prompt for tool selection"""
        tool_list = cls.get_tool_descriptions(user_role)
        
        prompt = f"""You are a tool selector. Analyze the user's question and determine which tools are needed to answer it.

Available tools for {user_role}:
{tool_list}

User question: "{user_message}"

Instructions:
1. Select ONLY the tools needed to answer this specific question
2. Do NOT select tools for information not requested
3. Return a JSON array with tool names
4. If the question is general greeting or unclear, return ["general_info"]

Examples:
- "What is my stall number?" → ["get_stall_info"]
- "Show my meetings" → ["get_meeting_details", "get_meeting_statistics"]
- "When is my flight and where am I staying?" → ["get_travel_details", "get_detailed_accommodation"]
- "How many pending meetings do I have?" → ["get_meeting_statistics"]
- "Hello" or "Help" → ["general_info"]

Return ONLY a valid JSON array, nothing else:"""
        
        return prompt
