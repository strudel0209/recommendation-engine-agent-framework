"""Simple tests and examples for the recommendation system."""
import asyncio
import logging
from typing import Dict

from src.recommendation import RecommendationEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_basic_recommendation():
    """Test basic recommendation workflow."""
    logger.info("="*60)
    logger.info("Test: Basic Recommendation")
    logger.info("="*60)
    
    try:
        # Initialize engine
        engine = RecommendationEngine()
        
        # Test query
        query = "I need to reduce energy costs in my medium-sized office building"
        user_id = "test_user_001"
        user_context = {
            "building_scale": "medium",
            "existing_modules": [],
            "license_type": "standard"
        }
        
        logger.info(f"\nQuery: {query}")
        logger.info(f"User: {user_id}")
        logger.info(f"Context: {user_context}\n")
        
        # Get recommendations
        response = engine.get_recommendations(
            query=query,
            user_id=user_id,
            user_context=user_context
        )
        
        # Display results
        logger.info(f"✅ Got {len(response['recommendations'])} recommendations")
        logger.info(f"Thread ID: {response['thread_id']}\n")
        
        for i, rec in enumerate(response['recommendations'], 1):
            logger.info(f"{i}. {rec['name']} ({rec['theme']})")
            logger.info(f"   Score: {rec['match_score']:.2f}")
            logger.info(f"   Rationale: {rec['rationale']}")
            logger.info(f"   Priority: {rec['implementation_priority']}\n")
        
        if response.get('implementation_plan'):
            logger.info(f"Implementation Plan:\n{response['implementation_plan']}\n")
        
        # Cleanup
        engine.cleanup()
        
        return response
    
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        raise


async def test_multi_turn_conversation():
    """Test multi-turn conversation with thread context."""
    logger.info("="*60)
    logger.info("Test: Multi-turn Conversation")
    logger.info("="*60)
    
    try:
        engine = RecommendationEngine()
        user_id = "test_user_002"
        
        # First query
        query1 = "Show me modules for predictive maintenance"
        logger.info(f"\nQuery 1: {query1}")
        
        response1 = engine.get_recommendations(
            query=query1,
            user_id=user_id
        )
        
        thread_id = response1['thread_id']
        logger.info(f"✅ Got {len(response1['recommendations'])} recommendations")
        logger.info(f"Thread: {thread_id}\n")
        
        # Follow-up query (same thread)
        query2 = "What about modules that work with those for energy optimization?"
        logger.info(f"\nQuery 2 (follow-up): {query2}")
        
        response2 = engine.get_recommendations(
            query=query2,
            user_id=user_id,
            thread_id=thread_id  # Continue conversation
        )
        
        logger.info(f"✅ Got {len(response2['recommendations'])} recommendations")
        logger.info(f"Thread: {response2['thread_id']}\n")
        
        for i, rec in enumerate(response2['recommendations'], 1):
            logger.info(f"{i}. {rec['name']}")
        
        # Cleanup
        engine.cleanup()
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        raise


async def test_feedback_loop():
    """Test feedback recording."""
    logger.info("="*60)
    logger.info("Test: Feedback Loop")
    logger.info("="*60)
    
    try:
        engine = RecommendationEngine()
        user_id = "test_user_003"
        
        # Get recommendation
        query = "I want to improve indoor air quality"
        response = engine.get_recommendations(
            query=query,
            user_id=user_id
        )
        
        thread_id = response['thread_id']
        logger.info(f"✅ Got recommendations (Thread: {thread_id})\n")
        
        # Record feedback
        if response['recommendations']:
            module_id = response['recommendations'][0]['id']
            
            # User clicked on first recommendation
            engine.record_feedback(
                user_id=user_id,
                interaction_id=thread_id,
                feedback_type="clicked",
                feedback_data={
                    "module_id": module_id,
                    "position": 1
                }
            )
            logger.info(f"✅ Recorded 'clicked' feedback for {module_id}")
            
            # User deployed the module
            engine.record_feedback(
                user_id=user_id,
                interaction_id=thread_id,
                feedback_type="deployed",
                feedback_data={
                    "module_id": module_id,
                    "rating": 5,
                    "comment": "Exactly what we needed!"
                }
            )
            logger.info(f"✅ Recorded 'deployed' feedback with rating\n")
        
        # Get user history
        history = engine.get_user_history(user_id=user_id)
        logger.info(f"✅ User has {len(history)} interactions in history\n")
        
        # Cleanup
        engine.cleanup()
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        raise


async def test_rules_validation():
    """Test compatibility rules validation."""
    logger.info("="*60)
    logger.info("Test: Rules Validation")
    logger.info("="*60)
    
    try:
        engine = RecommendationEngine()
        
        # Test with constraints
        query = "I need all energy and maintenance modules for a small building"
        user_id = "test_user_004"
        user_context = {
            "building_scale": "small",
            "license_type": "free"
        }
        
        logger.info(f"\nQuery: {query}")
        logger.info(f"Context: Small building, Free license\n")
        
        response = engine.get_recommendations(
            query=query,
            user_id=user_id,
            user_context=user_context
        )
        
        logger.info(f"✅ Got {len(response['recommendations'])} compatible recommendations")
        
        # Display compatibility info
        for rec in response['recommendations']:
            logger.info(f"\n{rec['name']}:")
            logger.info(f"  - Scale support: {rec.get('scale', [])}")
            logger.info(f"  - License: {rec.get('license', 'standard')}")
            logger.info(f"  - Dependencies: {rec.get('dependencies', [])}")
        
        # Cleanup
        engine.cleanup()
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        raise


async def run_all_tests():
    """Run all tests."""
    logger.info("\n" + "="*60)
    logger.info("RUNNING ALL TESTS")
    logger.info("="*60 + "\n")
    
    tests = [
        ("Basic Recommendation", test_basic_recommendation),
        ("Multi-turn Conversation", test_multi_turn_conversation),
        ("Feedback Loop", test_feedback_loop),
        ("Rules Validation", test_rules_validation)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            await test_func()
            results.append((test_name, "✅ PASSED"))
        except Exception as e:
            results.append((test_name, f"❌ FAILED: {e}"))
        
        logger.info("\n" + "-"*60 + "\n")
    
    # Summary
    logger.info("\n" + "="*60)
    logger.info("TEST SUMMARY")
    logger.info("="*60)
    for test_name, result in results:
        logger.info(f"{test_name}: {result}")
    logger.info("="*60 + "\n")


if __name__ == "__main__":
    # Run specific test
    # asyncio.run(test_basic_recommendation())
    
    # Or run all tests
    asyncio.run(run_all_tests())
