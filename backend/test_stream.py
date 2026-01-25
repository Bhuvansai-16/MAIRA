from main_agent import agent
import asyncio

async def test_stream():
    print("Starting stream...")
    # Wrap in async for potential async stream
    try:
        # Check if it's an async stream or sync
        stream = agent.stream({"messages": [{"role": "user", "content": "What is the latest AI news?"}]})
        for chunk in stream:
            print("--- CHUNK ---")
            print(chunk)
    except Exception as e:
        print("Error streaming:", e)

if __name__ == "__main__":
    asyncio.run(test_stream())
