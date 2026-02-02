# run_server.py
# Entry point that sets the event loop policy BEFORE importing anything else

import sys
import asyncio

# CRITICAL: Force SelectorEventLoop for psycopg async compatibility on Windows
# This MUST happen before any async code or imports that might create event loops
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Now import and run uvicorn
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        loop="asyncio"  # Use asyncio event loop (which now uses SelectorEventLoop on Windows)
    )
