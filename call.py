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
from linkedin_automation import send_linkedin_message

load_dotenv()

app = FastAPI()

# LiveKit configuration
api_key = os.getenv("LIVEKIT_API_KEY")
api_secret = os.getenv("LIVEKIT_API_SECRET")
livekit_url = os.getenv("LIVEKIT_URL", "http://localhost:7880")

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
async def api_send_linkedin_message(request: LinkedInMessageRequest):
    """
    Send a follow-up LinkedIn message to a prospect after a call using Selenium
    """
    try:
        if not request.linkedin_profile_url:
            raise HTTPException(
                status_code=400,
                detail="LinkedIn profile URL is required"
            )
            
        # Format the message with the user's name
        formatted_message = request.message_content.format(
            user_name=request.user_name,
            call_reference=request.call_reference
        )
            
        # Send the message using Selenium automation
        result = send_linkedin_message(
            request.linkedin_profile_url,
            formatted_message
        )
        
        if result["status"] == "success":
            return {
                "message": "LinkedIn follow-up message sent successfully",
                "details": {
                    "linkedin_profile": request.linkedin_profile_url,
                    "user_name": request.user_name,
                    "call_reference": request.call_reference,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=f"LinkedIn automation error: {result['message']}"
            )
        
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