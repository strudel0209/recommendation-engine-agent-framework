"""
Recommendation engine orchestration using the Microsoft Agent Framework SDK.

High-level workflow:
1. User Input: Natural language query.
2. Intent Extraction: Handled by ChatAgent (instructions + model reasoning).
3. Candidate Retrieval: Via search_modules tool (hybrid search).
4. Rules & Compatibility: Via validate_compatibility tool.
5. Ranking & Enrichment: Model ranks; engine enriches with local metadata & heuristics.
6. Structured Output: Enforced by AgentManager's response_format (Pydantic).
7. Feedback Loop: Interaction & feedback logged via DataManager.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.agent_manager import AgentManager
from src.data_manager import DataManager
from src.embeddings import EmbeddingsManager
from src.rules_engine import RulesEngine
from src.search_manager import SearchManager

logger = logging.getLogger(__name__)


class RecommendationEngine:
    """
    Orchestrates the recommendation workflow leveraging Agent Framework.

    This class delegates:
      - LLM & tool orchestration to AgentManager (which owns the ChatAgent)
      - Domain data access to DataManager
      - Search logic to SearchManager (exposed to agent as a tool)
      - Rules validation to RulesEngine (exposed to agent as a tool)
    """

    def __init__(
        self,
        *,
        azure_endpoint: str | None = None,
        azure_deployment_name: str | None = None,
        azure_api_version: str | None = None,
    ) -> None:
        """
        Initialize dependencies and create the agent with tools.

        Args:
            azure_endpoint: Optional override for Azure OpenAI endpoint.
            azure_deployment_name: Optional override for deployment name.
            azure_api_version: Optional API version.
        """
        logger.info("Initializing RecommendationEngine")

        # Core managers (keep local domain responsibilities separated)
        self.embeddings_manager = EmbeddingsManager()
        self.data_manager = DataManager()
        self.search_manager = SearchManager()

        # Rules engine needs module catalog
        modules = self.data_manager.list_modules()
        self.rules_engine = RulesEngine(modules)

        # Agent manager (wraps ChatAgent + AzureOpenAIChatClient)
        self.agent_manager = AgentManager(
            endpoint=azure_endpoint,
            deployment_name=azure_deployment_name,
            api_version=azure_api_version,
        )

        # Register tools on the agent
        self._create_agent_with_tools()

        logger.info("RecommendationEngine initialized successfully")

    # --------------------------------------------------------------------- #
    # Agent + tool setup
    # --------------------------------------------------------------------- #
    def _create_agent_with_tools(self) -> None:
        """
        Create ChatAgent via AgentManager with search and rules tools.
        Tools are simple Python callables; Agent Framework inspects signatures.
        """

        def search_function(
            query: str, filters: str | None = None, top: int = 5
        ) -> List[Dict[str, Any]]:
            """
            Hybrid module search (semantic + keyword).

            Args:
                query: Natural language need.
                filters: Optional filter expression (e.g., theme == 'energy_management').
                top: Maximum number of results.
            """
            try:
                return self.search_manager.hybrid_search(
                    query=query, filters=filters, top=top
                )
            except Exception as e:
                logger.error(f"search_function error: {e}")
                return []

        def rules_function(
            module_ids: List[str], user_context: Dict[str, Any] | None = None
        ) -> Dict[str, Any]:
            """
            Validate candidate modules against business & compatibility rules.

            Args:
                module_ids: Candidate module identifiers.
                user_context: Extra context (existing_modules, building_scale, license_type, etc.).
            """
            try:
                result = self.rules_engine.validate_modules(
                    module_ids=module_ids, user_context=user_context
                )
                return {
                    "is_valid": result.is_valid,
                    "errors": result.errors,
                    "warnings": result.warnings,
                    "compatible_modules": result.compatible_modules,
                    "incompatible_modules": result.incompatible_modules,
                }
            except Exception as e:
                logger.error(f"rules_function error: {e}")
                return {
                    "is_valid": False,
                    "errors": [str(e)],
                    "warnings": [],
                    "compatible_modules": [],
                    "incompatible_modules": module_ids,
                }

        self.agent_manager.create_agent(
            search_function=search_function,
            rules_function=rules_function,
        )

    # --------------------------------------------------------------------- #
    # Public API
    # --------------------------------------------------------------------- #
    async def get_recommendations_async(
        self,
        query: str,
        user_id: str,
        user_context: Optional[Dict[str, Any]] = None,
        conversation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate recommendations using agent.
        """
        logger.info(f"[user={user_id}] Processing recommendation request: {query[:80]}")

        try:
            # Agent does ALL the work: search, validation, formatting
            agent_response = await self.agent_manager.process_query(
                user_query=query,
                conversation_id=conversation_id,
                user_context=user_context,
            )

            # Extract what we need
            conv_id = agent_response["conversation_id"]
            recommendations = agent_response["recommendations"]

            # Log interaction for feedback loop
            interaction_payload = {
                "id": conv_id,
                "user_id": user_id,
                "query": query,
                "user_context": user_context or {},
                "recommendations": [r["module_id"] for r in recommendations],
                "conversation_id": conv_id,
                "timestamp": datetime.utcnow().isoformat(),
                "interaction_type": "recommendation_request",
            }
            self.data_manager.log_interaction(interaction_payload)

            logger.info(
                f"[user={user_id}] Generated {len(recommendations)} recommendations"
            )

            # Return agent response as-is (it's already perfect!)
            return {
                "conversation_id": conv_id,
                "intent": agent_response.get("intent", {}),
                "recommendations": recommendations,
                "implementation_plan": agent_response.get("implementation_plan", ""),
                "summary": agent_response.get("summary", ""),
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"[user={user_id}] Error generating recommendations: {e}")
            raise

    def get_recommendations(
        self,
        query: str,
        user_id: str,
        user_context: Optional[Dict[str, Any]] = None,
        conversation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Synchronous wrapper for environments that cannot await.

        Prefer using the async counterpart in async-capable contexts.
        """
        return asyncio.run(
            self.get_recommendations_async(
                query=query,
                user_id=user_id,
                user_context=user_context,
                conversation_id=conversation_id,
            )
        )

    def record_feedback(
        self,
        user_id: str,
        interaction_id: str,
        feedback_type: str,
        feedback_data: Dict[str, Any],
    ) -> None:
        """
        Record user feedback.

        Args:
            user_id: User identifier.
            interaction_id: Original interaction ID logged previously.
            feedback_type: e.g., "clicked", "deployed", "dismissed".
            feedback_data: Additional metadata (e.g., {"module_id": "...", "reason": "..."}).
        """
        try:
            # Bundle feedback_type and feedback_data into a single dict
            feedback = {
                "feedback_type": feedback_type,
                **feedback_data,  # Merge in module_id, comment, rating, etc.
            }

            self.data_manager.log_feedback(
                interaction_id=interaction_id,
                user_id=user_id,
                feedback=feedback,  # ✅ Pass as single dict
            )
            logger.info(f"[user={user_id}] Recorded feedback {feedback_type}")
        except Exception as e:
            logger.error(f"[user={user_id}] Error recording feedback: {e}")
            raise

    def get_user_history(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Retrieve recent interactions for a user.
        """
        try:
            return self.data_manager.get_user_interactions(
                user_id=user_id, max_items=limit
            )
        except Exception as e:
            logger.error(f"[user={user_id}] Error fetching history: {e}")
            raise

    def get_trending_modules(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Basic trending heuristic (example placeholder).
        """
        try:
            all_modules = self.data_manager.list_modules()
            trending = sorted(
                all_modules,
                key=lambda m: len(m.get("personas", [])),
                reverse=True,
            )[:limit]
            return trending
        except Exception as e:
            logger.error(f"Error fetching trending modules: {e}")
            raise

    def cleanup(self) -> None:
        """
        Cleanup resources (logical teardown).
        """
        try:
            if self.agent_manager:
                self.agent_manager.delete_agent()
            logger.info("RecommendationEngine cleanup completed")
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

    # --------------------------------------------------------------------- #
    # Internal enrichment helpers
    # --------------------------------------------------------------------- #
    def _enrich_recommendations(
        self, recommendations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Merge agent-produced recommendation skeletons with full module metadata.

        The agent output (from response_format) includes basic fields; we augment
        with local data + derived value metrics.

        Args:
            recommendations: List of recommendation dicts (module_id required).

        Returns:
            List of enriched recommendation dicts.
        """
        enriched: List[Dict[str, Any]] = []
        for rec in recommendations:
            module_id = rec.get("module_id")
            if not module_id:
                continue
            module = self.data_manager.get_module_by_id(module_id)  # ✅ Changed method
            if not module:
                logger.warning(f"Module {module_id} not found; skipping enrichment.")
                continue

            enriched.append(
                {
                    **module,  # base metadata
                    "module_id": module_id,
                    "name": rec.get("name") or module.get("name"),
                    "theme": rec.get("theme") or module.get("theme"),
                    "match_score": rec.get("match_score") or 0.0,
                    "rationale": rec.get("rationale") or "",
                    "dependencies": rec.get("dependencies")
                    or module.get("dependencies", []),
                    "implementation_priority": rec.get("implementation_priority")
                    or "medium",
                    "estimated_value": self._estimate_value(module),
                }
            )
        return enriched

    def _estimate_value(self, module: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simple heuristic metrics for business value (placeholder logic).
        """
        metrics = module.get("metrics", {})
        return {
            "cost_savings": metrics.get("cost_savings", "Not quantified"),
            "roi_timeline": metrics.get("roi", "12-24 months"),
            "implementation_effort": "Medium",
            "business_impact": (
                "High" if module.get("category") == "analytics" else "Medium"
            ),
        }
