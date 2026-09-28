import requests
import base64
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse

app = FastAPI()

# ==============================
# Service principal credentials
# ==============================
TENANT_ID = "04c72f56-1848-46a2-8167-8e5d36510cbc"
CLIENT_ID = "cbae082b-8255-4d0d-8e8f-9c8c42be0a24"
CLIENT_SECRET = "secret"

# ==============================
# OneLake token file location
# ==============================
ONELAKE_URL = (
    "https://onelake.dfs.fabric.microsoft.com/"
    "c5e18ea2-8e0b-44a3-81f3-1db64d256d5a/"
    "029367b2-188b-4c11-879a-29b1b41a64e1/Files/mwc_tokenr.txt"
)

# ==============================
# Fabric GPT‑5.1 endpoint
# ==============================
FABRIC_OPENAI_URL = (
    "https://f31e716cb5b3452db5c8cb6d47af5983.pbidedicated.windows.net/"
    "webapi/capacities/f31e716c-b5b3-452d-b5c8-cb6d47af5983/"
    "workloads/ML/ML/Automatic/"
    "workspaceid/c5e18ea2-8e0b-44a3-81f3-1db64d256d5a/"
    "cognitive/openai/openai/deployments/gpt-5.1/chat/completions"
    "?api-version=2024-02-15-preview"
)

@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [{"id": "gpt-5.1", "object": "model", "owned_by": "fabric"}]
    }






# ==============================
# Step 1: Get storage token
# ==============================
def get_storage_token():
    url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    payload = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": "https://storage.azure.com/.default",
        "grant_type": "client_credentials"
    }
    response = requests.post(url, data=payload)
    response.raise_for_status()
    return response.json()["access_token"]

# ==============================
# Step 2: Read MWC token from OneLake
# ==============================
def read_token_from_onelake(storage_token):
    headers = {"Authorization": f"Bearer {storage_token}"}
    r = requests.get(ONELAKE_URL, headers=headers, timeout=60)
    r.raise_for_status()
    encoded = r.text.strip()
    token = base64.b64decode(encoded).decode()
    if not token.startswith("MwcToken "):
        raise RuntimeError("Decoded value is not a MwcToken")
    return token

# ==============================
# Step 3: Call Fabric GPT‑5.1
# ==============================
@app.post("/v1/chat/completions")
async def proxy_chat(request: Request):
    try:
        # 1. Reuse your working token functions sequentially
        storage_token = get_storage_token()
        mwc_token = read_token_from_onelake(storage_token)
        
        # 2. Extract the prompt data and settings sent by Cline
        client_body = await request.json()
        is_streaming = client_body.get("stream", False)

        # 3. Setup headers exactly like your original script
        headers = {
            "Authorization": mwc_token,
            "Content-Type": "application/json"
        }

        # 4. Forward the dynamic body payload directly to Fabric
        response = requests.post(
            FABRIC_OPENAI_URL, 
            headers=headers, 
            json=client_body, 
            stream=is_streaming,
            timeout=60
        )
        response.raise_for_status()

        # 5. Handle streaming chunks or standard static JSON responses
        if is_streaming:
            def stream_generator():
                for chunk in response.iter_content(chunk_size=512):
                    if chunk:
                        yield chunk
                        
            return StreamingResponse(
                stream_generator(), 
                media_type="text/event-stream"
            )
        else:
            return response.json()

    except Exception as e:
        print(f"[PROXY ERROR]: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))






if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5001)
