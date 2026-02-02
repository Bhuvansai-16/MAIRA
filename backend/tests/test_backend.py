"""
Backend Test Script - Tests the MAIRA API endpoints
Run with: python test_backend.py

NOTE: The backend now uses DETACHED BACKGROUND TASKS.
When you reload the browser, the agent continues running!
"""
import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_health():
    """Test health endpoint"""
    print("\n=== Testing /health ===")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    return response.status_code == 200

def test_db():
    """Test database connection"""
    print("\n=== Testing /db-test ===")
    response = requests.get(f"{BASE_URL}/db-test")
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Response: {json.dumps(data, indent=2)}")
    return data.get("status") == "success"

def test_create_thread():
    """Test creating a new thread"""
    print("\n=== Testing POST /threads ===")
    response = requests.post(f"{BASE_URL}/threads", json={"title": "Test Thread"})
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Response: {json.dumps(data, indent=2)}")
    return data.get("thread_id")

def test_list_threads():
    """Test listing threads"""
    print("\n=== Testing GET /threads ===")
    response = requests.get(f"{BASE_URL}/threads")
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Found {len(data)} threads")
    return response.status_code == 200

def test_run_agent(thread_id: str = None):
    """Test running the agent with a simple prompt"""
    print("\n=== Testing POST /run-agent (SSE Stream) ===")
    payload = {
        "prompt": "Hi, just say hello back in one sentence.",
        "thread_id": thread_id,
        "deep_research": False
    }
    
    print(f"Sending: {json.dumps(payload, indent=2)}")
    
    response = requests.post(
        f"{BASE_URL}/run-agent",
        json=payload,
        stream=True,
        headers={"Accept": "text/event-stream"}
    )
    
    print(f"Status: {response.status_code}")
    print("Streaming response:")
    
    result_thread_id = None
    final_response = None
    
    for line in response.iter_lines():
        if line:
            decoded = line.decode('utf-8')
            if decoded.startswith('data: '):
                try:
                    event_data = json.loads(decoded[6:])
                    event_type = event_data.get('type', 'unknown')
                    
                    if event_data.get('thread_id'):
                        result_thread_id = event_data.get('thread_id')
                    
                    if event_type == 'init':
                        print(f"  [INIT] Thread ID: {event_data.get('thread_id')}")
                    elif event_type == 'update':
                        messages = event_data.get('messages', [])
                        for msg in messages:
                            content = msg.get('content', '')[:100]
                            print(f"  [UPDATE] {msg.get('type', 'unknown')}: {content}...")
                            final_response = msg.get('content')
                    elif event_type == 'done':
                        print(f"  [DONE] Checkpoint: {event_data.get('checkpoint_id', 'N/A')[:20]}...")
                    elif event_type == 'error':
                        print(f"  [ERROR] {event_data.get('error')}")
                    else:
                        print(f"  [{event_type.upper()}] {json.dumps(event_data)[:100]}...")
                except json.JSONDecodeError:
                    print(f"  [RAW] {decoded[:100]}...")
    
    return result_thread_id, final_response

def test_get_messages(thread_id: str):
    """Test getting messages for a thread"""
    print(f"\n=== Testing GET /threads/{thread_id}/messages ===")
    response = requests.get(f"{BASE_URL}/threads/{thread_id}/messages")
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Found {len(data.get('messages', []))} messages")
    for msg in data.get('messages', []):
        content = msg.get('content', '')[:80]
        print(f"  - {msg.get('type', 'unknown')}: {content}...")
    return response.status_code == 200

def main():
    """Run all tests"""
    print("=" * 60)
    print("MAIRA Backend Test Suite")
    print("=" * 60)
    
    tests_passed = 0
    tests_total = 0
    
    # Test 1: Health check
    tests_total += 1
    if test_health():
        tests_passed += 1
        print("✅ Health check passed")
    else:
        print("❌ Health check failed")
    
    # Test 2: Database test
    tests_total += 1
    if test_db():
        tests_passed += 1
        print("✅ Database test passed")
    else:
        print("❌ Database test failed")
    
    # Test 3: Create thread
    tests_total += 1
    thread_id = test_create_thread()
    if thread_id:
        tests_passed += 1
        print(f"✅ Thread created: {thread_id}")
    else:
        print("❌ Thread creation failed")
    
    # Test 4: List threads
    tests_total += 1
    if test_list_threads():
        tests_passed += 1
        print("✅ List threads passed")
    else:
        print("❌ List threads failed")
    
    # Test 5: Run agent
    tests_total += 1
    result_thread_id, response = test_run_agent(thread_id)
    if result_thread_id and response:
        tests_passed += 1
        print(f"✅ Agent run passed")
    else:
        print("❌ Agent run failed")
    
    # Test 6: Get messages
    if result_thread_id:
        tests_total += 1
        time.sleep(1)  # Wait for state to be saved
        if test_get_messages(result_thread_id):
            tests_passed += 1
            print("✅ Get messages passed")
        else:
            print("❌ Get messages failed")
    
    # Summary
    print("\n" + "=" * 60)
    print(f"Results: {tests_passed}/{tests_total} tests passed")
    print("=" * 60)

if __name__ == "__main__":
    main()
