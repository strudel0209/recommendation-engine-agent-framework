#  Module Recommendation System MVP

An intelligent recommendation engine for Smart Building Block modules using Azure AI services.

## Architecture

This MVP uses the following Azure services:
- **Azure AI Search**: Hybrid vector + keyword search for module retrieval
- **Azure AI Foundry Agents**: Orchestration and RAG-based recommendation
- **Azure Cosmos DB**: Module catalog and metadata storage
- **Azure OpenAI**: Embeddings (text-embedding-3-large) and Chat (GPT-4o)

## Workflow

1. **User Input**: Natural language description of needs
2. **Intent Extraction**: LLM extracts persona, goals, constraints, metrics
3. **Candidate Retrieval**: Hybrid search (vector + keyword) on module catalog
4. **Rules & Compatibility**: Check dependencies, conflicts, licensing
5. **Ranking & Enrichment**: Score modules and generate explanations (RAG)
6. **Structured Output**: Return recommendations with rationale
7. **Feedback Loop**: Log interactions for continuous improvement

## Project Structure

```
recommendations-system/
├── README.md
├── requirements.txt
├── .env.template
├── config/
│   └── settings.py
├── data/
│   ├── sample_modules.json
│   └── sample_themes.json
├── src/
│   ├── __init__.py
│   ├── data_manager.py      # Cosmos DB operations
│   ├── search_manager.py    # Azure AI Search operations
│   ├── agent_manager.py     # Azure AI Foundry Agent
│   ├── embeddings.py        # Vector generation
│   ├── rules_engine.py      # Compatibility checks
│   └── recommendation.py    # Main orchestration
├── api/
│   └── main.py              # FastAPI application
├── scripts/
│   ├── setup_cosmos.py
│   ├── setup_search.py
│   └── seed_data.py
└── tests/
    └── test_recommendation.py
```

## Setup Instructions

### Prerequisites

- Python 3.10+
- Azure Subscription
- Azure CLI installed and configured

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.template` to `.env` and fill in your Azure credentials:

```bash
cp .env.template .env
```

Required environment variables:
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_EMBEDDING_DEPLOYMENT`
- `AZURE_OPENAI_CHAT_DEPLOYMENT`
- `AZURE_SEARCH_ENDPOINT`
- `AZURE_SEARCH_API_KEY`
- `AZURE_COSMOS_ENDPOINT`
- `AZURE_COSMOS_KEY`
- `AZURE_AI_PROJECT_ENDPOINT`

### 3. Set Up Azure Resources

```bash
# Create Cosmos DB and collections
python scripts/setup_cosmos.py

# Create Azure AI Search index
python scripts/setup_search.py

# Seed sample data
python scripts/seed_data.py
```

### 4. Run the API

```bash
cd api
uvicorn main:app --reload --port 8000
```

### 5. Test the System

```bash
# Run tests
pytest tests/

# Or test via API
curl -X POST http://localhost:8000/recommend \
  -H "Content-Type: application/json" \
  -d '{
    "query": "I need a solution for predictive maintenance across multiple buildings with energy savings focus"
  }'
```

## API Endpoints

### POST `/recommend`

Request:
```json
{
  "query": "User's natural language description",
  "max_results": 5,
  "include_explanation": true
}
```

Response:
```json
{
  "recommendations": [
    {
      "module_id": "ai-failure-prediction",
      "module_name": "AI Failure Prediction Engine",
      "theme": "Predictive Maintenance",
      "score": 0.92,
      "explanation": "This module provides...",
      "dependencies": ["asset-health-dashboard"],
      "estimated_effort": "Medium",
      "onboarding_url": "https://..."
    }
  ],
  "extracted_intent": {
    "persona": "Facilities Manager",
    "goal": "Predictive Maintenance",
    "scale": "Multiple Buildings",
    "constraints": ["budget"],
    "metrics": ["energy_savings"]
  },
  "interaction_id": "uuid-here"
}
```

### POST `/feedback`

Log user feedback:
```json
{
  "interaction_id": "uuid",
  "module_id": "ai-failure-prediction",
  "action": "accepted|rejected|clicked"
}
```

## Development

### Adding New Modules

1. Add module definition to `data/sample_modules.json`
2. Run `python scripts/seed_data.py` to update indexes

### Customizing Rules

Edit `src/rules_engine.py` to add custom compatibility logic.

### Modifying Agent Behavior

Update agent instructions in `src/agent_manager.py`.

---

##  Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI REST API                         │
│         /recommend  /feedback  /history  /trending          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              RecommendationEngine (Orchestrator)             │
│  • Workflow                            │
│  • Multi-turn conversation support                           │
│  • Feedback loop integration                                 │
└─────┬──────────┬──────────┬──────────┬─────────────────────┘
      │          │          │          │
      ▼          ▼          ▼          ▼
┌──────────┐ ┌────────┐ ┌─────────┐ ┌─────────────┐
│ Agent    │ │ Rules  │ │ Search  │ │ Embeddings  │
│ Manager  │ │ Engine │ │ Manager │ │ Manager     │
└────┬─────┘ └───┬────┘ └────┬────┘ └──────┬──────┘
     │           │           │              │
     ▼           ▼           ▼              ▼
┌────────────────────────────────────────────────────┐
│              Azure Services                        │
│  ┌──────────────────────────────────────────────┐ │
│  │ Azure AI Foundry                             │ │
│  │  • GPT-4.1-mini for reasoning                      │ │
│  │  • Function calling                          │ │
│  │  • RAG pattern                               │ │
│  └──────────────────────────────────────────────┘ │
│  ┌──────────────────────────────────────────────┐ │
│  │ Azure AI Search                 │ │
│  │  • Hybrid search (vector + keyword)          │ │
│  │  • 1024-dim embeddings                       │ │
│  │  • HNSW algorithm                            │ │
│  │  • Semantic ranking                          │ │
│  └──────────────────────────────────────────────┘ │
│  ┌──────────────────────────────────────────────┐ │
│  │ Azure OpenAI                                 │ │
│  │  • text-embedding-3-large                    │ │
│  │  • Automatic vectorization                   │ │
│  └──────────────────────────────────────────────┘ │
│  ┌──────────────────────────────────────────────┐ │
│  │ Azure Cosmos DB for NoSQL                    │ │
│  │  • Module catalog                            │ │
│  │  • User interactions                         │ │
│  │  • Feedback tracking                         │ │
│  └──────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────┘
```

---

## Architecture Decisions

- **Hybrid Search**: Combines semantic (vector) and keyword search for better recall
- **RAG Pattern**: Grounds LLM responses in retrieved module documents
- **Function Calling**: Agent uses custom functions for rules and compatibility
- **Structured Output**: JSON responses for easy integration
- **Feedback Loop**: Interaction logging for ML improvement

### Workflow

```
1. User Input → Natural language query
2. Intent Extraction → Agent parses goals, scale, constraints
3. Candidate Retrieval → Hybrid search (vector + keyword)
4. Rules & Compatibility → Validate dependencies, conflicts, licenses
5. Ranking & Enrichment → Agent RAG for personalized rationale
6. Structured Output → JSON with recommendations + implementation plan
7. Feedback Loop → Log interactions for improvement
```

## Next Steps

- [ ] Implement A/B testing framework
- [ ] Add personalization based on user history
- [ ] Integrate real  module catalog
- [ ] Deploy to Azure Container Apps
- [ ] Set up CI/CD pipeline
- [ ] Add monitoring and telemetry

## License

MIT License
