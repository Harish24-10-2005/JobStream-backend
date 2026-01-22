
import asyncio
import sys
import logging
from pathlib import Path
from pydantic import ValidationError

# Add project root to sys.path
root_dir = str(Path(__file__).resolve().parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# Initialize logger early
from src.core.logger import logger
from src.core.console import console

async def main():
    try:
        from src.workflows.job_manager import JobApplicationWorkflow
        
        query = "Software Engineer"
        location = "Remote"
        
        if len(sys.argv) > 2:
            query = sys.argv[1]
            location = sys.argv[2]
            
        workflow = JobApplicationWorkflow()
        await workflow.run(query, location)
        
    except ValidationError as e:
        console.error("Configuration Error: Missing API Keys or Invalid Settings")
        for error in e.errors():
            field = error.get('loc', ('unknown',))[-1]
            msg = error.get('msg', 'Invalid value')
            print(f"  ❌ {field}: {msg}")
        print("\n👉 Please check your .env file and ensure all required keys are set.")
        sys.exit(1)
        
    except KeyboardInterrupt:
        console.print("\n🛑 Execution stopped by user.")
    except Exception as e:
        logger.exception("Fatal error during execution")
        console.error(f"Fatal Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
