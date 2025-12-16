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