"""Microsoft Agent Framework for recommendation orchestration and RAG."""

import json
import logging
import uuid
from datetime import datetime
from typing import Annotated, Any, Callable, Dict, List, Optional

from agent_framework import ChatAgent
from agent_framework.azure import AzureOpenAIChatClient
from azure.identity import DefaultAzureCredential
from pydantic import BaseModel, Field

from config.settings import settings

logger = logging.getLogger(__name__)


class ModuleRecommendation(BaseModel):
    """Structured recommendation output."""

    module_id: str
    module_name: str
    reason: str
    score: float = 0.9


class RecommendationResponse(BaseModel):
    """Complete recommendation response structure."""

    recommendations: List[ModuleRecommendation]
    implementation_plan: str
    summary: str


class AgentManager:
    """Manages Microsoft Agent Framework agents for recommendation orchestration."""

    def __init__(
        self,
        endpoint: Optional[str] = None,
        deployment_name: Optional[str] = None,
        api_version: Optional[str] = None,
        credential: Optional[Any] = None,
    ):
        """Initialize Agent Framework client."""
        logger.info("Initializing AgentManager")

        credential = credential or DefaultAzureCredential()

        # Create Azure OpenAI Chat client using Agent Framework
        self.chat_client = AzureOpenAIChatClient(
            credential=credential,
            endpoint=endpoint or settings.azure_openai_endpoint,
            deployment_name=deployment_name or settings.azure_openai_chat_deployment,
            api_version=api_version,
        )

        self.agent: Optional[ChatAgent] = None
        self.search_function: Optional[Callable] = None
        self.rules_function: Optional[Callable] = None

        # Conversation tracking (thread management per official SDK pattern)
        self.conversations: Dict[str, Any] = {}

        logger.info("Initialized AgentManager with Agent Framework")

    def create_agent(
        self, search_function: Callable, rules_function: Callable
    ) -> ChatAgent:
        """
        Create agent with structured output.

        Args:
            search_function: Function to search for Eliona modules
            rules_function: Function to validate compatibility rules

        Returns:
            ChatAgent configured with tools
        """
        self.search_function = search_function
        self.rules_function = rules_function

        instructions = """You are an expert at recommending Eliona building management modules.

When a user asks for recommendations:
1. Call search_modules to find relevant modules
2. Call validate_compatibility to check which modules are compatible
3. Return structured JSON with:
   - List of recommendations (module_id, module_name, reason)
   - Implementation plan
   - Summary

Always use the exact module IDs returned by validate_compatibility."""

        try:
            # Create ChatAgent with Python callable functions as tools
            self.agent = ChatAgent(
                chat_client=self.chat_client,
                name="eliona-recommendation-agent",
                instructions=instructions,
                tools=[
                    self._search_modules,
                    self._validate_compatibility,
                ],
                response_format=RecommendationResponse,  # ✅ Fixed: removed self.
            )

            logger.info(f"Created ChatAgent: {self.agent.name}")
            return self.agent
        except Exception as e:
            logger.error(f"Error creating agent: {e}")
            raise

    def _search_modules(
        self,
        query: Annotated[
            str,
            Field(description="Natural language search query for modules or themes"),
        ],
        filters: Annotated[
            Optional[str],
            Field(
                description="Optional filter expression (e.g., theme == 'energy_management')"
            ),
        ] = None,
        top: Annotated[
            int, Field(description="Maximum number of results to return", ge=1, le=20)
        ] = 5,
    ) -> str:
        """Search for Eliona modules or themes using hybrid search."""
        try:
            logger.info(f"Executing search: query='{query}', top={top}")

            if not self.search_function:
                return json.dumps({"error": "Search function not configured"})

            results = self.search_function(query=query, filters=filters, top=top)
            return json.dumps(results, indent=2)
        except Exception as e:
            logger.error(f"Search execution error: {e}")
            return json.dumps({"error": str(e)})

    def _validate_compatibility(
        self,
        module_ids: Annotated[
            List[str],
            Field(description="List of module IDs to validate for compatibility"),
        ],
        user_context: Annotated[
            Optional[Dict[str, Any]],
            Field(
                description="User context including building_scale, license_type, existing_modules, etc."
            ),
        ] = None,
    ) -> str:
        """Validate module compatibility based on business rules and user context."""
        try:
            logger.info(f"Validating rules for modules: {module_ids}")

            if not self.rules_function:
                return json.dumps({"error": "Rules function not configured"})

            # Agent Framework handles type conversion, but be defensive
            if isinstance(module_ids, str):
                module_ids = [module_ids]

            result = self.rules_function(
                module_ids=module_ids, user_context=user_context or {}
            )
            return json.dumps(result, indent=2)
        except Exception as e:
            logger.error(f"Rules validation error: {e}")
            return json.dumps({"error": str(e), "is_valid": False})

    async def process_query(
        self,
        user_query: str,
        conversation_id: Optional[str] = None,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Process a user query using the Agent Framework agent.
        """
        if not self.agent:
            raise RuntimeError("Agent not created. Call create_agent() first.")

        try:
            # Get or create conversation thread
            if conversation_id and conversation_id in self.conversations:
                thread = self.conversations[conversation_id]
                logger.info(f"Using existing conversation: {conversation_id}")
            else:
                thread = self.agent.get_new_thread()
                conversation_id = conversation_id or str(uuid.uuid4())
                self.conversations[conversation_id] = thread
                logger.info(f"Created new conversation: {conversation_id}")

            # Prepare the message with user context
            message = user_query
            if user_context:
                context_str = json.dumps(user_context, indent=2)
                message = f"User context:\n{context_str}\n\nUser query: {user_query}"

            # Run the agent
            logger.info(f"Running agent for conversation {conversation_id}")
            result = await self.agent.run(message, thread=thread)

            agent_response_text = result.text
            logger.info(f"Agent response received ({len(agent_response_text)} chars)")
            logger.debug(f"Full agent response:\n{agent_response_text}")

            # Parse the response (now synchronous!)
            parsed_response = self._parse_agent_response(agent_response_text)

            logger.info(
                f"Parsed response: {len(parsed_response.get('recommendations', []))} recommendations"
            )

            return {
                "conversation_id": conversation_id,
                "intent": parsed_response.get("intent", {}),
                "recommendations": parsed_response.get("recommendations", []),
                "implementation_plan": parsed_response.get("implementation_plan", ""),
                "summary": parsed_response.get("summary", ""),
                "agent_response": agent_response_text,
            }

        except Exception as e:
            logger.error(f"Error processing query: {e}")
            raise

    def _parse_agent_response(
        self, response_text: str
    ) -> Dict[str, Any]:  # ✅ Removed async
        """
        Parse structured response from agent.

        The agent returns JSON thanks to response_format=RecommendationResponse.
        """
        try:
            # The response_text is already valid JSON
            parsed = json.loads(response_text)

            # Convert to our internal format
            recommendations = [
                {
                    "module_id": rec.get("module_id"),
                    "module_name": rec.get("module_name", ""),
                    "score": rec.get("score", 0.9) / 10.0,  # Normalize score to 0-1
                    "reason": rec.get("reason", "Recommended by agent"),
                }
                for rec in parsed.get("recommendations", [])
            ]

            logger.info(
                f"Parsed {len(recommendations)} recommendations from structured response"
            )

            return {
                "intent": {"type": "recommendation_request"},
                "recommendations": recommendations,
                "implementation_plan": parsed.get("implementation_plan", ""),
                "summary": parsed.get("summary", ""),
            }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.debug(f"Response text: {response_text[:500]}")
            return {
                "intent": {"type": "recommendation_request"},
                "recommendations": [],
                "implementation_plan": response_text,
                "summary": "",
            }
        except Exception as e:
            logger.error(f"Error parsing response: {e}")
            return {
                "intent": {"type": "recommendation_request"},
                "recommendations": [],
                "implementation_plan": response_text,
                "summary": "",
            }

    def get_conversation_history(self, conversation_id: str) -> Optional[Any]:
        """Get the conversation thread for a given conversation ID."""
        return self.conversations.get(conversation_id)

    def clear_conversation(self, conversation_id: str) -> bool:
        """Clear/delete a conversation thread."""
        if conversation_id in self.conversations:
            del self.conversations[conversation_id]
            logger.info(f"Cleared conversation: {conversation_id}")
            return True
        return False

    def cleanup(self):
        """Clean up agent resources."""
        logger.info("Cleaning up AgentManager resources")
        self.agent = None
        self.search_function = None
        self.rules_function = None
        self.conversations.clear()

    async def get_recommendations_async(
        self,
        query: str,
        user_id: str,
        user_context: Optional[Dict[str, Any]] = None,
        conversation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate recommendations using agent."""
        logger.info(f"[user={user_id}] Processing recommendation request: {query[:80]}")

        try:
            # Agent handles everything: search, rules, formatting
            agent_response = await self.agent_manager.process_query(
                user_query=query,
                conversation_id=conversation_id,
                user_context=user_context,
            )

            conv_id = agent_response.get("conversation_id")
            agent_text = agent_response.get("agent_response", "")

            # Log interaction
            interaction_payload = {
                "id": conv_id,
                "user_id": user_id,
                "query": query,
                "user_context": user_context or {},
                "recommendations": [],  # Agent provides text recommendations
                "conversation_id": conv_id,
                "timestamp": datetime.utcnow().isoformat(),
                "interaction_type": "recommendation_request",
            }
            self.data_manager.log_interaction(interaction_payload)

            # Return agent's text response - this is the SDK pattern
            return {
                "conversation_id": conv_id,
                "intent": {"type": "recommendation_request"},
                "recommendations": [],  # Or parse if you must
                "implementation_plan": agent_text,  # The agent's full conversational response
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            raise
