"""FastAPI application for recommendation system."""

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, List, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import json

from config.settings import settings
from src.recommendation import RecommendationEngine

# Configure logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global engine instance
recommendation_engine: Optional[RecommendationEngine] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    global recommendation_engine

    # Startup
    logger.info("Starting recommendation system...")
    recommendation_engine = RecommendationEngine()
    logger.info("Recommendation system started successfully")

    yield

    # Shutdown
    logger.info("Shutting down recommendation system...")


# Create FastAPI app
app = FastAPI(
    title="Recommendation System API",
    description="API for personalized module recommendations based on themes, personas, and goals",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response Models
class UserContext(BaseModel):
    """User context for personalization."""

    building_scale: Optional[str] = Field(
        None, description="Building scale: small, medium, large, enterprise"
    )
    existing_modules: Optional[List[str]] = Field(
        None, description="Already deployed module IDs"
    )
    license_type: Optional[str] = Field(
        None, description="License type: free, standard, premium, enterprise"
    )
    industry: Optional[str] = Field(None, description="Industry vertical")
    goals: Optional[List[str]] = Field(None, description="User's business goals")


class RecommendationRequest(BaseModel):
    """Request for recommendations."""

    query: str = Field(..., description="Natural language query describing needs")
    user_id: str = Field(..., description="User identifier")
    user_context: Optional[UserContext] = Field(
        None, description="User context for personalization"
    )
    conversation_id: Optional[str] = Field(
        None, description="Conversation ID for multi-turn dialogue"
    )


class ModuleRecommendation(BaseModel):
    """Single module recommendation."""

    module_id: str
    module_name: str
    score: float
    reason: str


class UsageInfo(BaseModel):
    """Token usage information."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class RecommendationResponse(BaseModel):
    """Response with recommendations."""

    conversation_id: str
    intent: Dict
    recommendations: List[ModuleRecommendation]
    implementation_plan: str
    summary: Optional[str] = ""
    timestamp: str
    usage: Optional[UsageInfo] = None


class FeedbackRequest(BaseModel):
    """Feedback on recommendations."""

    user_id: str = Field(..., description="User identifier")
    interaction_id: str = Field(..., description="Original interaction/conversation ID")
    feedback_type: str = Field(
        ..., description="Type: clicked, deployed, dismissed, helpful, not_helpful"
    )
    module_id: Optional[str] = Field(None, description="Module ID if applicable")
    comment: Optional[str] = Field(None, description="Optional comment")
    rating: Optional[int] = Field(None, ge=1, le=5, description="Rating 1-5")


# API Endpoints
@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "Recommendation System",
        "status": "running",
        "version": "1.0.0",
    }


@app.get("/health")
async def health():
    """Detailed health check."""
    if not recommendation_engine:
        raise HTTPException(status_code=503, detail="Service not initialized")

    return {
        "status": "healthy",
        "components": {
            "recommendation_engine": "ok",
            "embeddings": "ok",
            "search": "ok",
            "agent": "ok",
            "data_manager": "ok",
        },
    }


@app.post("/recommend", response_model=RecommendationResponse)
async def get_recommendations(request: RecommendationRequest):
    """
    Get personalized module recommendations (non-streaming).

    Steps:
    1. Extract intent from natural language query
    2. Search for relevant modules using hybrid search
    3. Validate compatibility with business rules
    4. Rank and enrich with AI agent (RAG)
    5. Return structured recommendations
    """
    if not recommendation_engine:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        # Convert user_context to dict if provided
        user_context_dict = None
        if request.user_context:
            user_context_dict = request.user_context.model_dump(exclude_none=True)

        # ✅ SDK Pattern: Get recommendations with AgentRunResponse handling
        response = await recommendation_engine.get_recommendations_async(
            query=request.query,
            user_id=request.user_id,
            user_context=user_context_dict,
            conversation_id=request.conversation_id,
        )

        return response
    except Exception as e:
        logger.error(f"Error processing recommendation request: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/recommend/stream")
async def get_recommendations_stream(request: RecommendationRequest):
    """
    Get personalized module recommendations with Server-Sent Events (SSE) streaming.

    This endpoint uses the SDK's streaming capabilities (AgentRunResponseUpdate)
    to provide real-time updates as the agent processes the request.

    Returns:
        StreamingResponse with text/event-stream content type
    """
    if not recommendation_engine:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        # Convert user_context to dict if provided
        user_context_dict = None
        if request.user_context:
            user_context_dict = request.user_context.model_dump(exclude_none=True)

        # ✅ SDK Pattern: Stream with AgentRunResponseUpdate handling
        async def event_generator():
            """Generate SSE events from agent stream."""
            try:
                async for update in recommendation_engine.get_recommendations_stream(
                    query=request.query,
                    user_id=request.user_id,
                    user_context=user_context_dict,
                    conversation_id=request.conversation_id,
                ):
                    # Format as SSE event
                    event_data = json.dumps(update)
                    yield f"data: {event_data}\n\n"

                # Send final event to close stream
                yield "data: {\"type\": \"done\"}\n\n"

            except Exception as e:
                logger.error(f"Error in stream generator: {e}")
                error_event = json.dumps({"type": "error", "error": str(e)})
                yield f"data: {error_event}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            },
        )

    except Exception as e:
        logger.error(f"Error initializing streaming: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/feedback")
async def record_feedback(request: FeedbackRequest):
    """
    Record user feedback on recommendations.

    Feedback types:
    - clicked: User clicked to view module details
    - deployed: User deployed the module
    - dismissed: User dismissed the recommendation
    - helpful: User marked as helpful
    - not_helpful: User marked as not helpful
    """
    if not recommendation_engine:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        feedback_data = {}
        if request.module_id:
            feedback_data["module_id"] = request.module_id
        if request.comment:
            feedback_data["comment"] = request.comment
        if request.rating:
            feedback_data["rating"] = request.rating

        recommendation_engine.record_feedback(
            user_id=request.user_id,
            interaction_id=request.interaction_id,
            feedback_type=request.feedback_type,
            feedback_data=feedback_data,
        )

        return {
            "status": "success",
            "message": "Feedback recorded",
            "feedback_type": request.feedback_type,
        }
    except Exception as e:
        logger.error(f"Error recording feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
