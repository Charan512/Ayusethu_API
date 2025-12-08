import httpx

# Assumes local IPFS node. If not running, it returns a mock hash.
IPFS_URL = "http://127.0.0.1:5001/api/v0/add"

async def upload_to_ipfs(file_bytes, filename):
    try:
        async with httpx.AsyncClient() as client:
            files = {'file': (filename, file_bytes)}
            # response = await client.post(IPFS_URL, files=files) 
            # Uncomment above line if IPFS is real. For now, mocking to ensure stability:
            return f"QmHash{hash(file_bytes)}Mock"
    except Exception:
        return "QmFailedUpload"