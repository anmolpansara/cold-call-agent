from __future__ import annotations

import asyncio
import logging
from dotenv import load_dotenv
import json
import os
from typing import Any

from livekit import rtc, api
from livekit.agents import (
    AgentSession,
    Agent,
    JobContext,
    function_tool,
    RunContext,
    get_job_context,
    cli,
    WorkerOptions,
    RoomInputOptions,
)
from livekit.plugins import (
    deepgram,
    openai,
    silero,
    google,
    noise_cancellation, 
)


# Load environment variables
load_dotenv(dotenv_path=".env")
logger = logging.getLogger("outbound-caller")
logger.setLevel(logging.INFO)

outbound_trunk_id = os.getenv("SIP_OUTBOUND_TRUNK_ID")


class OutboundCaller(Agent):
    def __init__(
        self,
        *,
        customer_name: str,
        phone_number: str,
        appointment_time: str = "next Tuesday at 3pm",
        business_name: str = "Intercontinental Commodity Exchange Dubai",
        transfer_to: str = None,
        script: str = None,
    ):
        super().__init__(
            instructions=f"""
            You are a representative for {business_name}. Your interface with the user will be voice.
            You will be on a call with a potential participant for the 2026 Intercontinental Commodity Exchange in Dubai. 
            Your goal is to present the event details, handle objections, and secure their participation.
            As a representative, you will be polite and professional at all times. Allow the user to end the conversation.

            The customer's name is {customer_name}. Their phone number is {phone_number}.
            
            Use the following script to guide the conversation:
            
            {script}
            """
        )
        self.participant: rtc.RemoteParticipant | None = None
        self.customer_name = customer_name
        self.phone_number = phone_number
        self.appointment_time = appointment_time
        self.transfer_to = transfer_to
        self.script = script

    def set_participant(self, participant: rtc.RemoteParticipant):
        self.participant = participant

    async def hangup(self):
        """Helper function to hang up the call by deleting the room"""
        job_ctx = get_job_context()
        await job_ctx.api.room.delete_room(
            api.DeleteRoomRequest(
                room=job_ctx.room.name,
            )
        )

    @function_tool()
    async def transfer_call(self, ctx: RunContext):
        """Transfer the call to a human agent, called after confirming with the user"""
        if not self.transfer_to:
            await ctx.session.generate_reply(
                instructions="Apologize that transfer is not available at the moment and offer to take a message or schedule a callback."
            )
            return "cannot transfer call - no transfer number configured"

        logger.info(f"transferring call to {self.transfer_to}")

        await ctx.session.generate_reply(
            instructions="Let the user know you'll be transferring them to a human agent now."
        )

        job_ctx = get_job_context()
        try:
            await job_ctx.api.sip.transfer_sip_participant(
                api.TransferSIPParticipantRequest(
                    room_name=job_ctx.room.name,
                    participant_identity=self.participant.identity,
                    transfer_to=f"tel:{self.transfer_to}",
                )
            )
            logger.info(f"transferred call to {self.transfer_to}")
        except Exception as e:
            logger.error(f"error transferring call: {e}")
            await ctx.session.generate_reply(
                instructions="I'm sorry, there was an error transferring the call. Let me try to help you directly."
            )

    @function_tool()
    async def end_call(self, ctx: RunContext):
        """Called when the user wants to end the call"""
        logger.info(f"ending the call for {self.customer_name} ({self.phone_number})")

        current_speech = ctx.session.current_speech
        if current_speech:
            await current_speech.wait_for_playout()

        await self.hangup()


async def entrypoint(ctx: JobContext):
    logger.info(f"connecting to room {ctx.room.name}")
    await ctx.connect()

    # Parse metadata from the job
    try:
        metadata = json.loads(ctx.job.metadata)
        logger.info(f"Received metadata: {metadata}")
    except Exception as e:
        logger.error(f"Failed to parse metadata: {e}")
        ctx.shutdown()
        return

    # Extract required information from metadata
    phone_number = metadata.get("phone_number")
    customer_name = metadata.get("user_name", "Customer")
    script = metadata.get("script", "Default script content")
    
    # Optional fields with defaults
    appointment_time = metadata.get("appointment_time", "next Tuesday at 3pm")
    business_name = metadata.get("business_name", "Intercontinental Commodity Exchange Dubai")
    transfer_to = metadata.get("transfer_to")

    if not phone_number:
        logger.error("Phone number not provided in metadata")
        ctx.shutdown()
        return

    participant_identity = phone_number

    # Create the outbound caller agent with metadata information
    agent = OutboundCaller(
        customer_name=customer_name,
        phone_number=phone_number,
        appointment_time=appointment_time,
        business_name=business_name,
        transfer_to=transfer_to,
        script=script,
    )

    stt_instance = deepgram.STT(
        model="nova-3",
        language="en-US",
        interim_results=True,  # Enable interim results for faster responses
        punctuate=True,
        smart_format=True,
        no_delay=True,  # Reduce delay for faster recognition
        endpointing_ms=15,  # Lower endpointing delay for quicker turn detection
        filler_words=True,  # Enable filler words for better turn detection
    )

    # Configure TTS for faster and concise speech
    tts_instance = openai.TTS(
        model="tts-1-hd",
        voice="alloy",
        speed=1.1,  # Slightly faster speech speed
    )

    llm_instance = google.LLM(
        model="gemini-2.0-flash-001",
        api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=0.7,  # Balanced creativity
        max_output_tokens=128,  # Limit token count for concise responses
        presence_penalty=0.5,  # Penalize repetition
        frequency_penalty=0.5,  # Penalize frequent words
    )

    # Configure the agent session with AI models
    session = AgentSession(
        vad=silero.VAD.load(),
        stt=stt_instance,
        tts=tts_instance,
        llm=llm_instance,
        allow_interruptions=True,  # Allow interruptions during conversation
        discard_audio_if_uninterruptible=True,  # Discard audio if agent cannot be interrupted
        min_interruption_duration=0.3,  # Reduce interruption duration for faster responses
        min_interruption_words=2,  # Allow interruptions after two word
        min_endpointing_delay=0.1,  # Reduce endpointing delay for quicker turn detection
        max_endpointing_delay=2.0,  # Reduce maximum endpointing delay
        max_tool_steps=2,  # Limit tool steps for faster responses
    )

    # Start the session first before dialing
    session_started = asyncio.create_task(
        session.start(
            agent=agent,
            room=ctx.room,
            room_input_options=RoomInputOptions(
                noise_cancellation=noise_cancellation.BVCTelephony(),
            ),
        )
    )

    # Create SIP participant and start dialing
    try:
        logger.info(f"Dialing {customer_name} at {phone_number}")
        
        await ctx.api.sip.create_sip_participant(
            api.CreateSIPParticipantRequest(
                room_name=ctx.room.name,
                sip_trunk_id=outbound_trunk_id,
                sip_call_to=phone_number,
                participant_identity=participant_identity,
                wait_until_answered=True,
            )
        )

        await session_started
        participant = await ctx.wait_for_participant(identity=participant_identity)
        logger.info(f"participant joined: {participant.identity}")

        agent.set_participant(participant)

        await session.generate_reply(
            instructions=f"Hello {customer_name}, this is a representative from {business_name}. Are you available to talk for a few minutes?"
        )

        while True:
            call_status = participant.attributes.get("sip.callStatus")
            if call_status == "hangup":
                logger.info("User hung up the call.")
                await agent.hangup()
                break
            await asyncio.sleep(0.5)

    except api.TwirpError as e:
        logger.error(
            f"error creating SIP participant: {e.message}, "
            f"SIP status: {e.metadata.get('sip_status_code')} "
            f"{e.metadata.get('sip_status')}"
        )
        ctx.shutdown()
    except Exception as e:
        logger.error(f"Unexpected error during call setup: {e}")
        ctx.shutdown()


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="outbound_cold_caller",
        )
    )