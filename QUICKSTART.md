# Quick Start Guide

## 🚀 Getting Started in 5 Minutes

### Prerequisites
- Python 3.10+
- Azure subscription with:
  - Azure Cosmos DB account
  - Azure AI Search service
  - Azure OpenAI service with deployments
  - Azure AI Foundry project

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

#### Option C: cURL Example
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

## 📡 API Endpoints

### POST /recommend
Get personalized recommendations based on natural language query.

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
  "thread_id": "thread_abc123",
  "intent": {
    "user_goal": "improve air quality",
    "building_scale": "medium"
  },
  "recommendations": [
    {
      "module_id": "air-quality-monitor",
      "name": "Air Quality Monitor",
      "theme": "health_wellbeing",
      "match_score": 0.92,
      "rationale": "Direct match for air quality monitoring needs",
      "implementation_priority": "high",
      "dependencies": []
    }
  ],
  "implementation_plan": "Step-by-step guidance..."
}
```

### POST /feedback
Record user feedback on recommendations.

**Request:**
```json
{
  "user_id": "user123",
  "interaction_id": "thread_abc123",
  "feedback_type": "deployed",
  "module_id": "air-quality-monitor",
  "rating": 5,
  "comment": "Perfect solution!"
}
```

### GET /history/{user_id}
Get user's recommendation history.

### GET /trending
Get trending modules based on usage.

## 🎯 Example Use Cases

### 1. Energy Management
```python
query = "I need to reduce energy costs in my office building"
user_context = {
    "building_scale": "medium",
    "license_type": "standard"
}
```

Expected recommendations:
- Energy Analyzer
- HVAC Optimizer
- Solar Panel Optimizer

### 2. Predictive Maintenance
```python
query = "Help me prevent equipment failures and reduce downtime"
user_context = {
    "building_scale": "large",
    "license_type": "premium"
}
```

Expected recommendations:
- AI Failure Prediction
- Condition Monitoring

### 3. Sustainability Goals
```python
query = "I want to achieve carbon neutrality and get green certifications"
user_context = {
    "building_scale": "enterprise",
    "goals": ["sustainability", "carbon_reduction"]
}
```

Expected recommendations:
- Carbon Footprint Tracker
- ESG Reporting
- Green Certification

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

### Import errors
Make sure you're running from the project root directory.

## 📚 Architecture Overview

```
┌─────────────┐
│   FastAPI   │  ← HTTP requests
│   Server    │
└──────┬──────┘
       │
       ▼
┌──────────────────────────┐
│ RecommendationEngine     │
│  • Orchestrates workflow │
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
│   Azure Services           │
│  • AI Foundry (Agents)     │
│  • AI Search (Hybrid)      │
│  • OpenAI (Embeddings)     │
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
- Azure AI Foundry: https://learn.microsoft.com/azure/ai-studio/
- Cosmos DB: https://learn.microsoft.com/azure/cosmos-db/

## 💡 Tips

- **Multi-turn conversations**: Use `thread_id` from previous response for follow-up queries
- **Feedback is important**: Record user actions to improve recommendations over time
- **Scale settings**: Adjust Cosmos DB and Search throughput based on load
- **Cost optimization**: Use serverless Cosmos DB for development

Enjoy building with the Eliona Recommendation System! 🎉
