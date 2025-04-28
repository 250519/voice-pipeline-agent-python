import asyncio
import logging
import os
from dotenv import load_dotenv
from livekit.agents import (
    AutoSubscribe, JobContext, JobProcess, WorkerOptions, cli, llm, metrics, APIConnectOptions
)
from livekit.agents.pipeline import VoicePipelineAgent
from livekit.plugins import deepgram, openai, silero, cartesia
from system_prompt import systemPrompt
from agent_functions import AssistantFunction
from db_utils import setup_database, save_participant, save_transcript, get_db_connection, save_patient_details
from datetime import datetime
from concurrent_log_handler import ConcurrentRotatingFileHandler
from groq import Groq  # Import Groq API
from langchain_google_genai import GoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain.chains import LLMChain

import json

from google import genai
# import google.generativeai as genai

# Load environment variables
load_dotenv(dotenv_path=".env")
logger = logging.getLogger("voice-assistant")

# Set up logging
log_handler = ConcurrentRotatingFileHandler(
    "voice_agent.log", maxBytes=10*1024*1024, backupCount=5
)
logging.basicConfig(
    level=logging.INFO,
    handlers=[log_handler],
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("voice-agent")

setup_database()
conn = get_db_connection()

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load(
        min_speech_duration=0.2,        
        min_silence_duration=0.35,       
        prefix_padding_duration=0.15,    
        activation_threshold=0.45,      
        max_buffered_speech=60.0        
    )

log_queue = asyncio.Queue()
# client = Groq(api_key=os.environ.get("GROQ_API_KEY"), )
# client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

async def extract_appointment_details(transcript):
    api_key="AIzaSyDT9xCJmJ9-KroeDsNC8Fnt_j468ozBA9s"
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in environment variables")

    llm = GoogleGenerativeAI(
        model='gemini-2.0-flash',
        temperature=0.9,
        google_api_key=api_key
    )

    template = '''You are a precise JSON extractor for patient appointment information. Follow these guidelines:

1. Extract the following fields from the given conversation:
   - name: Full name of the patient (string)
   - phone: Patient's contact phone number (string)
   - doctor: Name of the doctor (string)
   - timeSlot: Scheduled appointment time (string)

2. Parsing Rules:
   - Be case-sensitive and exact in capturing information
   - Remove any extra whitespace
   - Standardize phone number format (e.g., XXX-XXX-XXXX)
   - If ANY required field is missing, return null for the entire JSON object

3. Output Format:
   {{
     "name": "Patient Name" or null,
     "phone": "Phone Number" or null,
     "doctor": "Doctor Name" or null,
     "timeSlot": "Appointment Time" or null
   }}

Example Input: "Hi, I want to book an appointment with Dr. Smith for John Doe at 2 PM tomorrow. His number is 555-1234."
Example Output: 
{{
  "name": "John Doe",
  "phone": "555-1234",
  "doctor": "Dr. Smith", 
  "timeSlot": "2 PM tomorrow"
}}

Now extract the information from this conversation:
{transcript}
'''

    prompt = PromptTemplate.from_template(template)
    chain = LLMChain(llm=llm, prompt=prompt, verbose=True)

    result = chain.invoke({"transcript": transcript})
    return result["text"]

print("CARTESIA",os.getenv("CARTESIA_API_KEY"))
async def entrypoint(ctx: JobContext):
    initial_ctx = llm.ChatContext().append(
        role="system",
        text=systemPrompt,
    )

    logger.info(f"connecting to room {ctx.room.name}")
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    # Initialize the transcript variable
    transcript = ""  # Define transcript here

    # wait for the first participant to connect
    participant = await ctx.wait_for_participant()
    logger.info(f"starting voice assistant for participant {participant.identity}")

    fnc_ctx = AssistantFunction(ctx)

    agent = VoicePipelineAgent(
        vad=ctx.proc.userdata["vad"],
        stt=deepgram.STT(language="en-IN"),
        llm=openai.LLM.with_groq(model="llama-3.3-70b-versatile"),
        tts=cartesia.TTS(language='hi',voice="28ca2041-5dda-42df-8123-f58ea9c3da00",api_key=os.getenv("CARTESIA_API_KEY")),
        chat_ctx=initial_ctx,
        fnc_ctx=fnc_ctx,
        preemptive_synthesis=True,
        min_endpointing_delay=0.4,
        interrupt_speech_duration=0.5,
        interrupt_min_words=1,
        allow_interruptions=True
    )

    agent.start(ctx.room, participant)

    usage_collector = metrics.UsageCollector()

    @agent.on("metrics_collected")
    def _on_metrics_collected(mtrcs: metrics.AgentMetrics):
        metrics.log_metrics(mtrcs)
        usage_collector.collect(mtrcs)

    # Generate a unique UUID for the participant
    participant_uuid = save_participant(conn)

    # Event handlers for user and agent speech
    @agent.on("user_speech_committed")
    def on_user_speech_committed(msg: llm.ChatMessage):
        nonlocal transcript  # Use the transcript variable defined earlier
        if isinstance(msg.content, list):
            msg.content = "\n".join(
                "[image]" if isinstance(x, llm.ChatImage) else x for x in msg.content
            )
        log_queue.put_nowait(f"[{datetime.now()}] USER:\n{msg.content}\n\n")
        transcript += msg.content  # Append user speech to the transcript
    
    @agent.on("agent_speech_committed")
    def on_agent_speech_committed(msg: llm.ChatMessage):
        log_queue.put_nowait(f"[{datetime.now()}] AGENT:\n{msg.content}\n\n")
    
    async def write_transcription():
        nonlocal transcript  # Use the transcript variable defined earlier
        while True:
            msg = await log_queue.get()
            if msg is None:  # End of conversation
                break
            transcript += msg
        # Save the transcript for this participant
        save_transcript(conn, participant_uuid, transcript)
    
    write_task = asyncio.create_task(write_transcription())

    async def log_usage_finish_log_queue():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: ${summary}")
        log_queue.put_nowait(None)
        await write_task

    ctx.add_shutdown_callback(log_usage_finish_log_queue)

    async def finalize_transcription():
        nonlocal transcript  # Use the transcript variable defined earlier
        save_transcript(conn, participant_uuid, transcript)
        appointment_details = await extract_appointment_details(transcript)
        
        if appointment_details:
            try:
                if appointment_details.startswith("```json"):
                    appointment_details = appointment_details.strip("```json").strip("```").strip()
                details = json.loads(appointment_details)  # Use json.loads instead of eval
                if isinstance(details, dict) and all(key in details for key in ["name", "phone", "doctor", "timeSlot"]):
                    save_patient_details(conn, details["name"], details["phone"], details["doctor"], details["timeSlot"])
                    logger.info("Patient details saved successfully.")

                    # Save to local text file
                    with open("patient_appointments.txt", "a", encoding="utf-8") as file:
                        file.write(
                            f"Name: {details['name']}\n"
                            f"Phone: {details['phone']}\n"
                            f"Doctor: {details['doctor']}\n"
                            f"Time Slot: {details['timeSlot']}\n"
                            f"Logged At: {datetime.now()}\n"
                            f"{'-'*40}\n"
                        )
                    logger.info("Patient details also saved to local text file.")

                else:
                    logger.warning("Incomplete details extracted from transcript.")
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing extracted details: {e}")

    
    async def log_usage_finish():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: ${summary}")
        await finalize_transcription()
    
    ctx.add_shutdown_callback(log_usage_finish)
    
    await agent.say("""Good day! Welcome to Vedanta, your trusted Ayurveda care provider. How may I assist you with your healthcare needs today?""", allow_interruptions=True)

if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
        ),
    )
