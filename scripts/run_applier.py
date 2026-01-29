
import asyncio
import os
import sys
from unittest.mock import AsyncMock

# Add backend root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.services.live_applier import LiveApplierService
from src.api.websocket import EventType

async def main():
    target_url = "https://stripe.com/jobs/listing/software-engineer-new-grad/7210112"
    print(f"🚀 Starting Live Applier Test targeting: {target_url}")

    # Mock Manager to print output
    mock_manager = AsyncMock()
    async def print_broadcast(event):
        # Filter out screenshot events (too spammy)
        if event.type != EventType.BROWSER_SCREENSHOT:
            print(f"📡 EVENT [{event.type.value}]: {event.message}")
            if event.agent:
                print(f"   Agent: {event.agent}")
    
    # Patch settings for test
    from src.core.config import settings
    # settings.openrouter_model = "qwen/qwen3-coder:free"
    settings.headless = False # Uncomment to see browser
    
    # Instantiate Service
    # Note: We use draft_mode=False for this test to avoid waiting forever for input 
    # unless we also mock input. Or we keep it True and risk timeout.
    # Let's set draft_mode=False for automation test or mocked confirmation.
    # Re-reading: The user wants to "test live applier agent".
    # Since I cannot interact with the CLI easily for HITL if it uses WebSocket,
    # I will set draft_mode=False to attempt full auto-application.
    service = LiveApplierService(session_id="test_cli_session", draft_mode=False)
    
    # Inject mock manager
    service._manager = mock_manager

    # Run
    try:
        result = await service.run(target_url)
        print(f"🏁 Result: {result}")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await service.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
