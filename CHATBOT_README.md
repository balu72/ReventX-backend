# ReventX Chatbot Implementation

## Overview

The ReventX chatbot is an AI-powered assistant that helps buyers and sellers with event-related queries. It uses LLM-based responses (via Ollama or OpenAI) with rich context from user data to provide intelligent, personalized assistance.

## Features

- **LLM-Powered**: Intelligent AI responses using Ollama or OpenAI
- **Context-Aware**: Accesses user's meetings, travel plans, and profile data
- **Persistent Conversations**: Stores chat history in the database
- **Role-Specific**: Tailored responses for buyers vs sellers
- **Multi-Provider**: Supports Ollama (local) and OpenAI (cloud)

## Architecture

### Backend Components

1. **Database Tables** (`db-migration-add-chatbot.sql`)
   - `chat_conversations`: Conversation sessions
   - `chat_messages`: Individual messages
   - `chat_feedback`: User feedback on responses

2. **Models** (`app/models/models.py`)
   - `ChatConversation`: Conversation model
   - `ChatMessage`: Message model
   - `ChatFeedback`: Feedback model

3. **Services**
   - `llm_service.py`: LLM integration (Ollama/OpenAI)
   - `chatbot_context.py`: User context gathering
   - `chatbot_service.py`: Main orchestration service

4. **API Routes** (`app/routes/chatbot.py`)
   - `POST /api/chat/message`: Send a message
   - `GET /api/chat/conversations`: Get conversation list
   - `GET /api/chat/conversations/:id`: Get conversation with messages
   - `DELETE /api/chat/conversations/:id`: Delete conversation
   - `POST /api/chat/feedback`: Submit feedback
   - `GET /api/chat/health`: Check chatbot health

## Setup Instructions

### 1. Database Migration

Run the migration to create chatbot tables:

```bash
# Connect to your PostgreSQL database
psql -U splash25user -d splash25_core_db -f db-migration-add-chatbot.sql
```

### 2. Install Dependencies

```bash
cd splash25-backend
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Edit `.env` file:

```bash
# Chatbot Configuration
CHATBOT_ENABLED=true
CHATBOT_LLM_PROVIDER=ollama  # or 'openai'
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama2  # or mistral, codellama, etc.
OPENAI_API_KEY=your_key_here  # If using OpenAI
OPENAI_MODEL=gpt-3.5-turbo
CHATBOT_MAX_TOKENS=500
CHATBOT_TEMPERATURE=0.7
```

### 4. Install and Run Ollama (Local AI)

**For macOS:**
```bash
# Install Ollama
brew install ollama

# Start Ollama service
ollama serve

# Pull a model (in another terminal)
ollama pull llama2
```

**For Linux:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama serve
ollama pull llama2
```

**For Windows:**
Download from https://ollama.com/download

### 5. Test the Setup

```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# Check chatbot health
curl http://localhost:5000/api/chat/health
```

## Usage Examples

### Send a Message

```bash
curl -X POST http://localhost:5000/api/chat/message \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "When is the event?"
  }'
```

### Get Conversations

```bash
curl -X GET http://localhost:5000/api/chat/conversations \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Get Specific Conversation

```bash
curl -X GET http://localhost:5000/api/chat/conversations/123 \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## Supported Queries

### Event Information
- "When is the event?"
- "Where is the venue?"
- "What are the event dates?"

### Meetings (Buyer)
- "Show me my meetings"
- "Book a meeting with seller S123"
- "Cancel my meeting"

### Meetings (Seller)
- "Show my meeting schedule"
- "How many pending requests do I have?"
- "Accept meeting request"

### Travel Plans
- "Show my travel plan"
- "Where am I staying?"
- "What are my flight details?"

### Sellers (Buyer)
- "Find sellers"
- "Search for homestays"
- "Show me seller S45"

### Profile Management
- "Update my profile"
- "Change my bank details"

### General Help
- "Help"
- "What can you do?"

## Switching Between Ollama and OpenAI

### Using Ollama (Local - Free)

**Pros:**
- No API costs
- Data stays local
- No rate limits

**Cons:**
- Requires local resources
- Slower on CPU
- Need to download models

```bash
# In .env
CHATBOT_LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama2
```

### Using OpenAI (Cloud - Paid)

**Pros:**
- Faster responses
- Better quality
- No local setup

**Cons:**
- API costs
- Rate limits
- Requires API key

```bash
# In .env
CHATBOT_LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-3.5-turbo
```

### Automatic Fallback

The system automatically falls back to OpenAI if Ollama fails (if OpenAI key is configured):

```python
# This happens automatically in llm_service.py
if ollama_fails and openai_key_exists:
    use_openai()
```

## Ollama Model Recommendations

### For Testing/Development
- `llama2`: Good balance, 7B parameters
- `mistral`: Fast and capable, 7B parameters

### For Production
- `llama2:13b`: Better quality, needs more RAM
- `mixtral`: High quality, 8x7B MoE

### Install a Model
```bash
ollama pull llama2        # ~4GB
ollama pull mistral       # ~4GB
ollama pull llama2:13b    # ~7GB
ollama pull mixtral       # ~26GB
```

## Troubleshooting

### Ollama Connection Error

```
Error: Cannot connect to Ollama
```

**Solution:**
```bash
# Check Ollama is running
ollama serve

# Check port
curl http://localhost:11434/api/tags
```

### Model Not Found

```
Error: Model 'llama2' not found
```

**Solution:**
```bash
ollama pull llama2
ollama list  # Verify model is downloaded
```

### Database Migration Error

```
Error: relation "chat_conversations" does not exist
```

**Solution:**
```bash
psql -U splash25user -d splash25_core_db -f db-migration-add-chatbot.sql
```

### OpenAI API Error

```
Error: OpenAI API key not configured
```

**Solution:**
Add your API key to `.env`:
```bash
OPENAI_API_KEY=sk-your-actual-key-here
```

## Performance Considerations

### Response Times

- **Ollama (llama2)**: 1-3 seconds (CPU), < 1s (GPU)
- **OpenAI**: 500ms - 2 seconds

### Database Queries

The chatbot minimizes database queries:
- Conversations cached per request
- Context gathered once per message
- History limited to last 10 messages

### Memory Usage

- **Backend**: ~100-200MB base
- **Ollama (llama2)**: ~4GB RAM
- **Ollama (llama2:13b)**: ~8GB RAM

## Security

1. **Authentication**: All endpoints require JWT token
2. **Authorization**: Users can only access their own conversations
3. **Data Privacy**: User context never leaves the system
4. **Input Validation**: All inputs sanitized
5. **Rate Limiting**: Recommended for production

## Future Enhancements

- [ ] Real-time WebSocket support
- [ ] Voice input/output
- [ ] Multi-language support
- [ ] Image understanding
- [ ] Meeting booking via chat
- [ ] Export conversation history
- [ ] Admin analytics dashboard

## Support

For issues or questions:
1. Check this README
2. Review logs: `splash25-backend/logs/`
3. Test API health: `GET /api/chat/health`
4. Contact development team

## License

Internal use only - ReventX/Splash25 Event Management System
