
import os
import sys

# Add project root to sys.path
sys.path.append(os.getcwd())

try:
    from src.core.config import settings
    print("Settings loaded.")
    key = settings.serpapi_api_key.get_secret_value()
    print(f"SERPAPI_API_KEY present: {bool(key)}")
    print(f"SERPAPI_API_KEY length: {len(key)}")
    print(f"SERPAPI_API_KEY masked: {key[:4]}...{key[-4:] if len(key)>8 else ''}")

    from langchain_community.utilities import SerpAPIWrapper
    try:
        search = SerpAPIWrapper(serpapi_api_key=key)
        print("SerpAPIWrapper instantiated successfully.")
    except Exception as e:
        print(f"SerpAPIWrapper instantiation failed: {e}")

except Exception as e:
    print(f"Config loading failed: {e}")
