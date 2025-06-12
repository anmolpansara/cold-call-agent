from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from livekit.api import LiveKitAPI, CreateRoomRequest
from livekit import api
import time
import json
import os
import uuid
from datetime import datetime, timezone
from dotenv import load_dotenv
import requests

load_dotenv()

app = FastAPI()

# LiveKit configuration
api_key = os.getenv("LIVEKIT_API_KEY")
api_secret = os.getenv("LIVEKIT_API_SECRET")
livekit_url = os.getenv("LIVEKIT_URL", "http://localhost:7880")

# Waalaxy configuration
waalaxy_username = os.getenv("WAALAXY_USERNAME")
waalaxy_password = os.getenv("WAALAXY_PASSWORD")
waalaxy_api_url = os.getenv("WAALAXY_API_URL", "https://api.waalaxy.com/api")

class CallRequest(BaseModel):
    user_name: str
    phone_number: str

class LinkedInMessageRequest(BaseModel):
    linkedin_profile_url: str
    message_content: str
    call_reference: str  # Reference to the call (room_name or dispatch_id)
    user_name: str

@app.post("/initiate_call")
async def initiate_call(request: CallRequest):
    """
    Initiate an outbound call with user name and phone number
    """
    if not api_key or not api_secret:
        raise HTTPException(
            status_code=500, 
            detail="LiveKit API credentials not configured"
        )
    
    lkapi = LiveKitAPI(url=livekit_url, api_key=api_key, api_secret=api_secret)
    
    try:
        # Read the script from the file
        script_path = "script.txt"
        with open(script_path, "r") as script_file:
            script_content = script_file.read()

        # Prepare metadata for the agent
        metadata_dict = {
            "phone_number": request.phone_number,
            "transfer_to": None,  # No transfer needed for demo
            "user_name": request.user_name,
            "script": script_content  # Pass the script content
        }
        metadata = json.dumps(metadata_dict)

        # Create a room with unique name
        room_name = f"call-{int(time.time())}-{request.phone_number.replace('+', '').replace(' ', '')}-{uuid.uuid4().hex[:8]}"
        
        room = await lkapi.room.create_room(CreateRoomRequest(
            name=room_name,
            empty_timeout=10 * 60,  # 10 minutes
            max_participants=20,
        ))

        # Create agent dispatch
        dispatch = await lkapi.agent_dispatch.create_dispatch(
            api.CreateAgentDispatchRequest(
                agent_name="outbound_cold_caller",  # Must match the agent name in outbound_call_agent.py
                room=room_name, 
                metadata=metadata
            )
        )

        return {
            "message": "Call initiated successfully",
            "call_details": {
                "user_name": request.user_name,
                "phone_number": request.phone_number,
                "room_name": room_name,
                "room_id": room.sid,
                "dispatch_id": dispatch.id,
                "status": "initiated",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initiate call: {str(e)}"
        )
    
    finally:
        await lkapi.aclose()

@app.post("/send_linkedin_message")
async def send_linkedin_message(request: LinkedInMessageRequest):
    """
    Send a follow-up LinkedIn message to a prospect after a call
    """
    if not waalaxy_username or not waalaxy_password:
        raise HTTPException(
            status_code=500,
            detail="Waalaxy credentials not configured"
        )
    
    try:
        # First, authenticate with Waalaxy
        auth_payload = {
            "username": waalaxy_username,
            "password": waalaxy_password
        }
        
        auth_response = requests.post(
            f"{waalaxy_api_url}/auth/login",
            json=auth_payload
        )
        
        if auth_response.status_code != 200:
            raise HTTPException(
                status_code=auth_response.status_code,
                detail=f"Waalaxy authentication failed: {auth_response.text}"
            )
        
        # Extract session cookie or token from response
        session_data = auth_response.json()
        session_token = session_data.get("token", "")

        # Prepare the message request for Waalaxy API
        waalaxy_payload = {
            "profileUrl": request.linkedin_profile_url,
            "message": request.message_content.format(
                user_name=request.user_name,
                call_reference=request.call_reference
            ),
            "campaign": "Cold Call Follow-up"
        }
        
        # Send the message using Waalaxy API
        headers = {
            "Cookie": f"session={session_token}",  # Or use appropriate header based on Waalaxy docs
            "Content-Type": "application/json"
        }
        
        response = requests.post(
            f"{waalaxy_api_url}/messages/send",
            json=waalaxy_payload,
            headers=headers
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Waalaxy API error: {response.text}"
            )
        
        return {
            "message": "LinkedIn follow-up message sent successfully",
            "details": {
                "linkedin_profile": request.linkedin_profile_url,
                "user_name": request.user_name,
                "call_reference": request.call_reference,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send LinkedIn message: {str(e)}"
        )

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)