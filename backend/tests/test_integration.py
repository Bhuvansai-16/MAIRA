"""
Test script to verify the deep reasoning agent integration
"""
import sys
import os

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all modules can be imported"""
    print("🔍 Testing imports...")
    
    try:
        from main_agent import agent, subagents
        print("✅ Main agent imported successfully")
        print(f"   Total subagents: {len(subagents)}")
        
        # Verify deep reasoning agent is in subagents
        subagent_names = [sa.get('name', 'unknown') for sa in subagents]
        print(f"   Subagent names: {', '.join(subagent_names)}")
        
        if 'deep-reasoning-agent' in subagent_names:
            print("✅ Deep reasoning agent is registered")
        else:
            print("❌ Deep reasoning agent NOT found in subagents")
            return False
            
    except ImportError as e:
        print(f"❌ Failed to import main_agent: {e}")
        return False
    
    try:
        from deep_reasoning_agent import deep_reasoning_subagent
        print("✅ Deep reasoning agent module imported")
        print(f"   Description: {deep_reasoning_subagent['description'][:80]}...")
        print(f"   Tools available: {len(deep_reasoning_subagent['tools'])}")
    except ImportError as e:
        print(f"❌ Failed to import deep_reasoning_agent: {e}")
        return False
    
    try:
        from tools.verification_tools import (
            validate_citations,
            fact_check_claims,
            assess_content_quality,
            cross_reference_sources,
            verify_draft_completeness
        )
        print("✅ Verification tools imported successfully")
        print("   Tools: validate_citations, fact_check_claims, assess_content_quality,")
        print("          cross_reference_sources, verify_draft_completeness")
    except ImportError as e:
        print(f"❌ Failed to import verification tools: {e}")
        return False
    
    return True

def test_tool_configuration():
    """Test that tools are properly configured"""
    print("\n🔧 Testing tool configuration...")
    
    try:
        from tools.verification_tools import validate_citations
        
        # Check if it's a proper LangChain tool
        if hasattr(validate_citations, 'name'):
            print(f"✅ validate_citations tool name: {validate_citations.name}")
        else:
            print("⚠️  validate_citations might not be properly decorated")
            
    except Exception as e:
        print(f"❌ Error testing tool configuration: {e}")
        return False
    
    return True

def test_environment():
    """Test environment variables"""
    print("\n🌍 Testing environment configuration...")
    
    from dotenv import load_dotenv
    load_dotenv()
    
    required_keys = ['GOOGLE_API_KEY', 'TAVILY_API_KEY']
    missing_keys = []
    
    for key in required_keys:
        if os.getenv(key):
            print(f"✅ {key} is set")
        else:
            print(f"⚠️  {key} is NOT set (required for full functionality)")
            missing_keys.append(key)
    
    if missing_keys:
        print(f"\n⚠️  Warning: {len(missing_keys)} API key(s) missing")
        print("   Add them to your .env file for full functionality")
    
    return True

def main():
    """Run all tests"""
    print("=" * 60)
    print("MAIRA Deep Reasoning Agent Integration Test")
    print("=" * 60)
    
    results = []
    
    # Run tests
    results.append(("Import Test", test_imports()))
    results.append(("Tool Configuration Test", test_tool_configuration()))
    results.append(("Environment Test", test_environment()))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    all_passed = all(result[1] for result in results)
    
    if all_passed:
        print("\n🎉 All tests passed! Deep reasoning agent is ready to use.")
    else:
        print("\n⚠️  Some tests failed. Please check the errors above.")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
