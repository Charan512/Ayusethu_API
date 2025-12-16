# backend/app/ipfs_handler.py (MODIFIED to support local/public fallback)

import httpx
import os

# --- NEW/MODIFIED ENVIRONMENT VARIABLES ---
# 1. Local Gateway (For prototype testing, based on your log)
# Set in .env: IPFS_GATEWAY_LOCAL="http://127.0.0.1:8080/ipfs/"
IPFS_GATEWAY_LOCAL = os.getenv("IPFS_GATEWAY_LOCAL", "http://127.0.0.1:8080/ipfs/")

# Set in .env: IPFS_GATEWAY_PUBLIC="https://ipfs.io/ipfs/" (or Pinata)
IPFS_GATEWAY_PUBLIC = os.getenv("IPFS_GATEWAY_PUBLIC", "https://ipfs.io/ipfs/")

def get_public_url(cid: str, is_local_dev: bool = False) -> str:
    """
    Resolves an IPFS hash (CID) to a URL, prioritizing local gateway 
    if running, otherwise falling back to the public gateway.
    """
    if not cid:
        return ""
    
    # 1. Determine the Base URL to use
    if is_local_dev:
        # If running locally, use the local gateway URL
        base_url = IPFS_GATEWAY_LOCAL
    else:
        # For all other cases (production, public testing), use the public fallback
        base_url = IPFS_GATEWAY_PUBLIC
        
    # Ensure the base URL ends with a slash before appending the CID
    gateway = base_url.rstrip('/') + '/'
    return f"{gateway}{cid}"
# Add this function definition to app/ipfs_handler.py

async def upload_to_ipfs(file_data: bytes, filename: str) -> str | None:
    """Uploads file data to the configured IPFS upload service and returns the CID."""
    
    # You MUST have this environment variable set in Render's dashboard.
    # This will be your Ngrok URL or Pinata upload URL.
    IPFS_UPLOAD_URL = os.getenv("IPFS_UPLOAD_URL") 
    
    if not IPFS_UPLOAD_URL:
        # Log a critical error if the URL is missing
        print("CRITICAL: IPFS_UPLOAD_URL is not set in environment variables.")
        return None

    try:
        # Use httpx to post the file content (multipart/form-data)
        async with httpx.AsyncClient(timeout=30.0) as client:
            files = {'file': (filename, file_data, 'application/octet-stream')}
            response = await client.post(
                IPFS_UPLOAD_URL,
                files=files
                # Add headers for authentication if using a service like Pinata
            )
            response.raise_for_status() # Raise exception for 4xx/5xx status codes
            
            # The response body should contain the CID (e.g., {"Hash": "..."})
            result = response.json()
            return result.get("Hash") # Return the CID/Hash

    except httpx.HTTPStatusError as e:
        print(f"IPFS upload failed with status {e.response.status_code}: {e.response.text}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred during IPFS upload: {e}")
        return None