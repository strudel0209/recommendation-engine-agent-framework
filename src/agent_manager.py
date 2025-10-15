"""Microsoft Agent Framework for recommendation orchestration and RAG."""

import json
import logging
import uuid
from datetime import datetime
from typing import Annotated, Any, AsyncIterator, Callable, Dict, List, Optional

from agent_framework import AgentRunResponse, AgentRunResponseUpdate, ChatAgent
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
            search_function: Function to search for company X modules
            rules_function: Function to validate compatibility rules

        Returns:
            ChatAgent configured with tools
        """
        self.search_function = search_function
        self.rules_function = rules_function

        instructions = """You are an expert at recommending company X building management modules.

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
                response_format=RecommendationResponse,
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
        Returns structured response using SDK's AgentRunResponse.
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

            # ✅ SDK Pattern: Use AgentRunResponse
            logger.info(f"Running agent for conversation {conversation_id}")
            response: AgentRunResponse = await self.agent.run(message, thread=thread)

            # ✅ FIXED: Check attributes safely
            logger.info(
                f"Agent response received: text_len={len(response.text)}, "
                f"has_value={response.value is not None}"
            )

            # ✅ SDK Pattern: Use structured .value for Pydantic models
            parsed_response = self._extract_structured_data(response)

            # ✅ FIXED: Extract usage safely (may not be available on all response types)
            usage_info = None
            if hasattr(response, 'usage') and response.usage:
                usage_info = {
                    "prompt_tokens": getattr(response.usage, 'prompt_tokens', 0),
                    "completion_tokens": getattr(response.usage, 'completion_tokens', 0),
                    "total_tokens": getattr(response.usage, 'total_tokens', 0),
                }

            return {
                "conversation_id": conversation_id,
                "intent": parsed_response.get("intent", {}),
                "recommendations": parsed_response.get("recommendations", []),
                "implementation_plan": parsed_response.get("implementation_plan", ""),
                "summary": parsed_response.get("summary", ""),
                "agent_response_text": response.text,
                "usage": usage_info,
            }

        except Exception as e:
            logger.error(f"Error processing query: {e}", exc_info=True)
            raise

    async def process_query_stream(
        self,
        user_query: str,
        conversation_id: Optional[str] = None,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Process a user query with streaming using SDK's AgentRunResponseUpdate.
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

            # ✅ SDK Pattern: Use run_stream for streaming
            logger.info(f"Streaming agent response for conversation {conversation_id}")
            
            # Yield initial event
            yield {
                "type": "start",
                "conversation_id": conversation_id,
                "timestamp": datetime.utcnow().isoformat(),
            }

            accumulated_text = ""
            final_value = None
            final_usage = None  # ✅ Track usage from final update

            async for update in self.agent.run_stream(message, thread=thread):
                # ✅ SDK Pattern: Handle AgentRunResponseUpdate
                if update.text_delta:
                    accumulated_text += update.text_delta
                    yield {
                        "type": "text_delta",
                        "text_delta": update.text_delta,
                        "accumulated_text": accumulated_text,
                    }

                # ✅ FIXED: Check for .value instead of .data
                if hasattr(update, 'value') and update.value:
                    final_value = update.value
                    yield {
                        "type": "value",
                        "value": update.value,
                    }

                # ✅ Track usage if available
                if hasattr(update, 'usage') and update.usage:
                    final_usage = update.usage

                if update.done:
                    # Extract structured data
                    parsed_response = self._extract_structured_data_from_text(
                        accumulated_text, final_value
                    )
                    
                    # ✅ FIXED: Extract usage safely
                    usage_info = None
                    if final_usage:
                        usage_info = {
                            "prompt_tokens": getattr(final_usage, 'prompt_tokens', 0),
                            "completion_tokens": getattr(final_usage, 'completion_tokens', 0),
                            "total_tokens": getattr(final_usage, 'total_tokens', 0),
                        }
                    
                    yield {
                        "type": "complete",
                        "conversation_id": conversation_id,
                        "recommendations": parsed_response.get("recommendations", []),
                        "implementation_plan": parsed_response.get("implementation_plan", ""),
                        "summary": parsed_response.get("summary", ""),
                        "usage": usage_info,
                    }

        except Exception as e:
            logger.error(f"Error in streaming query: {e}", exc_info=True)
            yield {
                "type": "error",
                "error": str(e),
                "conversation_id": conversation_id,
            }

    def _extract_structured_data(self, response: AgentRunResponse) -> Dict[str, Any]:
        """
        Extract structured data from AgentRunResponse.
        Prefers .value (structured Pydantic model) over text parsing.

        Args:
            response: AgentRunResponse from SDK

        Returns:
            Dict with structured recommendations and metadata
        """
        try:
            # ✅ FIXED: Use .value instead of .data
            if response.value:
                if isinstance(response.value, RecommendationResponse):
                    # Direct Pydantic model access
                    recommendations = [
                        {
                            "module_id": rec.module_id,
                            "module_name": rec.module_name,
                            "score": rec.score / 10.0,  # Normalize to 0-1
                            "reason": rec.reason,
                        }
                        for rec in response.value.recommendations
                    ]

                    logger.info(
                        f"Extracted {len(recommendations)} recommendations from structured .value"
                    )

                    return {
                        "intent": {"type": "recommendation_request"},
                        "recommendations": recommendations,
                        "implementation_plan": response.value.implementation_plan,
                        "summary": response.value.summary,
                    }

            # Fallback: Parse from text if no structured data
            return self._extract_structured_data_from_text(response.text, None)

        except Exception as e:
            logger.error(f"Error extracting structured data: {e}")
            # Fallback to text parsing
            return self._extract_structured_data_from_text(response.text, None)

    def _extract_structured_data_from_text(
        self, text: str, value: Optional[Any] = None  # ✅ FIXED: Renamed parameter
    ) -> Dict[str, Any]:
        """
        Fallback method to extract structured data by parsing text.
        Used when response_format was not specified or parsing structured output.

        Args:
            text: Raw text response from agent
            value: Optional structured value from SDK

        Returns:
            Dict with parsed recommendations and metadata
        """
        try:
            # ✅ FIXED: Check value instead of data
            if value and isinstance(value, RecommendationResponse):
                recommendations = [
                    {
                        "module_id": rec.module_id,
                        "module_name": rec.module_name,
                        "score": rec.score / 10.0,
                        "reason": rec.reason,
                    }
                    for rec in value.recommendations
                ]

                return {
                    "intent": {"type": "recommendation_request"},
                    "recommendations": recommendations,
                    "implementation_plan": value.implementation_plan,
                    "summary": value.summary,
                }

            # Fallback: Try to parse JSON from text
            # Look for JSON blocks in markdown code blocks
            import re

            json_match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                parsed = json.loads(json_str)
                return {
                    "intent": parsed.get("intent", {"type": "recommendation_request"}),
                    "recommendations": parsed.get("recommendations", []),
                    "implementation_plan": parsed.get("implementation_plan", ""),
                    "summary": parsed.get("summary", text),
                }

            # Fallback: Return text as summary
            logger.warning("No structured data found, returning text as summary")
            return {
                "intent": {"type": "recommendation_request"},
                "recommendations": [],
                "implementation_plan": "",
                "summary": text,
            }

        except Exception as e:
            logger.error(f"Error parsing structured data from text: {e}")
            return {
                "intent": {"type": "recommendation_request"},
                "recommendations": [],
                "implementation_plan": "",
                "summary": text,
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
