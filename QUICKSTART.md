# Quick Start Guide

## 🚀 Getting Started in 5 Minutes

### Prerequisites
- Python 3.10+
- Azure subscription with:
  - Azure Cosmos DB account
  - Azure AI Search service
  - Azure OpenAI service with deployments
  - Azure AI Foundry project (optional for Foundry features)

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Configure Environment
Copy `.env.template` to `.env` and fill in your Azure resource details:
```bash
cp .env.template .env
```

Edit `.env` with your Azure endpoints and deployment names.

### Step 3: Azure Login
```bash
az login
```

### Step 4: Run Complete Setup
```bash
python scripts/setup_all.py
```

This will:
- ✅ Create Cosmos DB database and containers
- ✅ Create Azure AI Search index with vector configuration
- ✅ Load and index 12 sample building management modules

### Step 5: Start the API Server
```bash
python api/main.py
```

The API will be available at `http://localhost:8000`

### Step 6: Test the System

#### Option A: Interactive API Documentation
Open your browser to `http://localhost:8000/docs` for Swagger UI

#### Option B: Run Tests
```bash
python tests/test_recommendation.py
OR
code api/sample_requests.http
```

#### Option C: cURL Example (Non-streaming)
```bash
curl -X POST http://localhost:8000/recommend \
  -H "Content-Type: application/json" \
  -d '{
    "query": "I need to reduce energy costs in my building",
    "user_id": "user123",
    "user_context": {
      "building_scale": "medium",
      "license_type": "standard"
    }
  }'
```

#### Option D: cURL Example (Streaming with SSE)
```bash
curl -X POST http://localhost:8000/recommend/stream \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -N \
  -d '{
    "query": "I need to reduce energy costs in my building",
    "user_id": "user123",
    "user_context": {
      "building_scale": "medium",
      "license_type": "standard"
    }
  }'
```

## 📡 API Endpoints

### POST /recommend
Get personalized recommendations based on natural language query (non-streaming).

**Request:**
```json
{
  "query": "I want to improve indoor air quality",
  "user_id": "user123",
  "user_context": {
    "building_scale": "medium",
    "existing_modules": ["energy-analyzer"],
    "license_type": "standard"
  }
}
```

**Response:**
```json
{
  "conversation_id": "conv_abc123",
  "intent": {
    "type": "recommendation_request"
  },
  "recommendations": [
    {
      "module_id": "air-quality-monitor",
      "module_name": "Air Quality Monitor",
      "score": 0.92,
      "reason": "Direct match for air quality monitoring needs"
    }
  ],
  "implementation_plan": "Step-by-step guidance...",
  "summary": "Based on your needs...",
  "timestamp": "2025-10-15T10:30:00Z",
  "usage": {
    "prompt_tokens": 150,
    "completion_tokens": 300,
    "total_tokens": 450
  }
}
```

### POST /recommend/stream ✨ NEW
Get personalized recommendations with Server-Sent Events (SSE) streaming.

**Request:** Same as `/recommend`

**Response Stream (text/event-stream):**
```
data: {"type": "start", "conversation_id": "conv_abc123", "timestamp": "2025-10-15T10:30:00Z"}

data: {"type": "text_delta", "text_delta": "Based on ", "accumulated_text": "Based on "}

data: {"type": "text_delta", "text_delta": "your energy", "accumulated_text": "Based on your energy"}

data: {"type": "complete", "conversation_id": "conv_abc123", "recommendations": [...], "usage": {...}}

data: {"type": "done"}
```

**JavaScript Client Example:**
```javascript
const eventSource = new EventSource('/recommend/stream', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    query: 'I need to reduce energy costs',
    user_id: 'user123'
  })
});

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  switch(data.type) {
    case 'start':
      console.log('Stream started:', data.conversation_id);
      break;
    case 'text_delta':
      // Update UI with incremental text
      appendText(data.text_delta);
      break;
    case 'complete':
      // Final recommendations received
      displayRecommendations(data.recommendations);
      break;
    case 'done':
      eventSource.close();
      break;
  }
};
```

### POST /feedback
Record user feedback on recommendations.

**Request:**
```json
{
  "user_id": "user123",
  "interaction_id": "conv_abc123",
  "feedback_type": "deployed",
  "module_id": "air-quality-monitor",
  "rating": 5,
  "comment": "Perfect solution!"
}
```

## 🎯 Example Use Cases

### 1. Energy Management (Non-streaming)
```python
import requests

response = requests.post('http://localhost:8000/recommend', json={
    "query": "I need to reduce energy costs in my office building",
    "user_id": "user123",
    "user_context": {
        "building_scale": "medium",
        "license_type": "standard"
    }
})

print(response.json())
```

### 2. Streaming Recommendations
```python
import requests
import json

response = requests.post(
    'http://localhost:8000/recommend/stream',
    json={
        "query": "I need to reduce energy costs",
        "user_id": "user123"
    },
    stream=True,
    headers={'Accept': 'text/event-stream'}
)

for line in response.iter_lines():
    if line:
        if line.startswith(b'data: '):
            data = json.loads(line[6:])
            print(f"Event type: {data['type']}")
            if data['type'] == 'text_delta':
                print(f"Text: {data['text_delta']}")
            elif data['type'] == 'complete':
                print(f"Recommendations: {data['recommendations']}")
```

## 🔧 Troubleshooting

### "Service not initialized" error
Make sure you ran `python scripts/setup_all.py` successfully.

### Authentication errors
1. Run `az login`
2. Verify you have access to all Azure resources
3. Check `.env` file has correct endpoints

### No recommendations returned
1. Verify data was seeded: Check Cosmos DB and Search index
2. Check Azure OpenAI deployments are active
3. Review logs for detailed errors

### Streaming connection issues
1. Check firewall/proxy settings for SSE
2. Ensure nginx/reverse proxy doesn't buffer responses (`X-Accel-Buffering: no`)
3. Test with simple curl command first

## 📚 Architecture Overview

```
┌─────────────┐
│   FastAPI   │  ← HTTP/SSE requests
│   Server    │
└──────┬──────┘
       │
       ▼
┌──────────────────────────┐
│ RecommendationEngine     │
│  • Orchestrates workflow │
│  • Streaming support ✨  │
└───┬────────┬────────┬────┘
    │        │        │
    ▼        ▼        ▼
┌─────┐  ┌─────┐  ┌─────────┐
│Agent│  │Rules│  │Search   │
│ MGR │  │ ENG │  │Manager  │
└──┬──┘  └──┬──┘  └────┬────┘
   │        │          │
   ▼        ▼          ▼
┌────────────────────────────┐
│   Microsoft Agent SDK      │
│  • AgentRunResponse ✅     │
│  • AgentRunResponseUpdate✅│
│  • Streaming support ✅    │
└────────────────────────────┘
   │
   ▼
┌────────────────────────────┐
│   Azure Services           │
│  • AI Search (Hybrid)      │
│  • OpenAI (Embeddings+LLM) │
│  • Cosmos DB (Catalog)     │
└────────────────────────────┘
```

## 🎓 Next Steps

1. **Customize Sample Data**: Edit `data/sample_modules.json` with your modules
2. **Tune Search**: Adjust `vector_search_k` and `hybrid_search_top` in settings
3. **Enhance Rules**: Add custom business rules in `rules_engine.py`
4. **Production Deploy**: Use Azure Container Apps or App Service
5. **Add Authentication**: Integrate Azure AD or API keys
6. **Monitor**: Enable Application Insights for telemetry

## 📖 Documentation

- Full README: `README.md`
- API Docs: `http://localhost:8000/docs` (when server is running)
- Azure AI Search: https://learn.microsoft.com/azure/search/
- Microsoft Agent Framework: https://github.com/microsoft/agent-framework
- Cosmos DB: https://learn.microsoft.com/azure/cosmos-db/

## 💡 Tips

- **Multi-turn conversations**: Use `conversation_id` from previous response for follow-up queries
- **Streaming for UX**: Use `/recommend/stream` for better user experience with progressive results
- **Feedback is important**: Record user actions to improve recommendations over time
- **Token usage tracking**: Check `usage` field in responses to monitor costs
- **Scale settings**: Adjust Cosmos DB and Search throughput based on load
- **Cost optimization**: Use serverless Cosmos DB for development

Enjoy building with the Recommendation System! 🎉
