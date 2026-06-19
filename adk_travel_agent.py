import datetime
import asyncio
import logging
import os
from zoneinfo import ZoneInfo

from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from monocle_apptrace import setup_monocle_telemetry
setup_monocle_telemetry(workflow_name = 'adk_travel_agent_cicd', monocle_exporters_list = 'file,okahu')

# os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "TRUE"  # Set to TRUE to use Vertex AI
# Set GCP project and location (required for Vertex AI)
if not os.getenv("GOOGLE_CLOUD_PROJECT"):
    # Default to project from your console URL, or set via environment variable
    os.environ["GOOGLE_CLOUD_PROJECT"] = "fluent-radar-408119"
if not os.getenv("GOOGLE_CLOUD_LOCATION"):
    os.environ["GOOGLE_CLOUD_LOCATION"] = "us-central1"

MAX_OUTPUT_TOKENS = int(os.getenv("MAX_OUTPUT_TOKENS", "1000"))

if os.getenv("OPENAI_API_KEY"):
    MODEL = os.getenv("OPENAI_MODEL", "openai/gpt-3.5-turbo")
else:
    MODEL = os.getenv("GOOGLE_GENAI_MODEL", "gemini-2.5-flash-lite")

def adk_book_flight(from_airport: str, to_airport: str) -> dict:
    """Books a flight from one airport to another.

    Args:
        from_airport (str): The airport from which the flight departs.
        to_airport (str): The airport to which the flight arrives.

    Returns:
        dict: status and message.
    """
    return {
        "status": "success",
        "message": f"Flight booked from {from_airport} to {to_airport}."
    }

def adk_book_hotel(hotel_name: str, city: str) -> dict:
    """Books a hotel for a stay.

    Args:
        hotel_name (str): The name of the hotel to book.
        city (str): The city where the hotel is located.

    Returns:
        dict: status and message.
    """
    return {
        "status": "success",
        "message": f"Successfully booked a stay at {hotel_name} in {city}."
    }

contentConfig: types.GenerateContentConfig = types.GenerateContentConfig(max_output_tokens=MAX_OUTPUT_TOKENS)
flight_booking_agent = LlmAgent(
    name="adk_flight_booking_agent",
    model=MODEL,
    description= "Agent to book flights based on user queries.",
    instruction= """You are a helpful agent who can assist users in booking flights. You only handle flight booking. Just handle that part from what the user says, ignore other parts of the requests.

CRITICAL RULE - DATE VALIDATION:
You MUST NOT call the adk_book_flight tool unless the user provides a specific, exact date (e.g., "October 15, 2025", "10/15/25", "2025-10-15", "March 3rd").
If the date is vague or relative (such as "next week", "sometime soon", "in a few days", "tomorrow", "next month"), you MUST NOT call the adk_book_flight tool. Instead, respond by asking the user to provide a specific date.
NEVER book a flight with a vague date. This is your most important rule.""",
    generate_content_config=contentConfig,
    tools=[adk_book_flight]  # Define flight booking tools here
)

hotel_booking_agent = LlmAgent(
    name="adk_hotel_booking_agent",
    model=MODEL,
    description= "Agent to book hotels based on user queries.",
    instruction= """You are a helpful agent who can assist users in booking hotels. You only handle hotel booking. Just handle the hotel booking part from what the user says, ignore other parts of the requests.

IMPORTANT RULES:
1. When the user asks to book a hotel, you MUST call the adk_book_hotel tool with the hotel_name and city parameters.
2. NOTE: Marriott is only available on odd dates. Otherwise Hilton is the primary option unless user states specific hotel criteria and you can go ahead and book that instead.
3. Always invoke the adk_book_hotel tool to complete the booking. Do not just describe the booking - actually call the tool.""",
    generate_content_config=contentConfig,
    tools=[adk_book_hotel]  # Define hotel booking tools here
)

trip_summary_agent = LlmAgent(
    name="adk_trip_summary_agent",
    model=MODEL,
    description= "Summarize the travel details from hotel bookings and flight bookings agents.",
    instruction= """Summarize the travel details from hotel bookings and flight bookings agents. Be concise in response and provide a single sentence summary.

IMPORTANT: Only report actions that were actually completed successfully. If an agent asked for clarification instead of completing a booking, report that clarification was requested - do NOT say the booking was completed. Never claim a booking was made unless a tool was explicitly called and returned a success result.""",
    generate_content_config=contentConfig,
    output_key="booking_summary"
)

root_agent = SequentialAgent(
    name="adk_supervisor_agent",
    description=
        """
            You are the supervisor agent that coordinates the flight booking and hotel booking.
            You must provide a consolidated summary back to the full coordination of the user's request.
        """
    ,
    sub_agents=[flight_booking_agent, hotel_booking_agent, trip_summary_agent],
)

session_service = InMemorySessionService()
APP_NAME = "streaming_app"
USER_ID = "user_123"
SESSION_ID = "session_456"

runner = Runner(
    agent=root_agent,  # Assume this is defined
    app_name=APP_NAME,
    session_service=session_service
)

async def run_agent(test_message: str):
    session = await session_service.create_session(
        app_name=APP_NAME, 
        user_id=USER_ID,
        session_id=SESSION_ID
    )
    session.model_config
    content = types.Content(role='user', parts=[types.Part(text=test_message)])
    response = None
    # Process events as they arrive using async for\
    async for event in runner.run_async(
        user_id=USER_ID,
        session_id=SESSION_ID,
        new_message=content
    ):
        # For final response
        if event.is_final_response():
            response = event.content

    print(response.parts[0].text)  # Print the last response text

if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR)

    user_request = input("\nI am a travel booking agent. How can I assist you with your travel plans? ")
    asyncio.run(run_agent(user_request))