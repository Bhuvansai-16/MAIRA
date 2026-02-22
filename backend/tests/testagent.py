"""
Test middleware with your actual models from config.py
"""

import pytest
from config import gemini_2_5_pro
from deepagents import create_deep_agent
from langchain.agents.middleware import ModelRetryMiddleware
from langchain_core.messages import HumanMessage


def test_real_gemini_retry():
    """Test actual retry for Gemini 2.5 Pro."""
    agent = create_deep_agent(
        model=gemini_2_5_pro,
        tools=[],
        subagents=[],
        middleware=[
            ModelRetryMiddleware(max_retries=2),
        ]
    )
    
    result = agent.invoke({
        "messages": [HumanMessage(content="Test retry behavior")]
    })
    
    assert result["messages"], "Should get response from Gemini"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
