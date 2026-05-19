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
    instruction= """You are a helpful agent who can assist users in booking flights. You ONLY handle flight booking.

**ABSOLUTE RULE - READ CAREFULLY:**
DO NOT EVER call the adk_book_flight tool if the flight date is vague or relative.

Vague/relative dates include: "next week", "tomorrow", "soon", "this month", "next month", "later", "in a few days", "next year", "this weekend"

Specific dates include: "April 26, 2026", "26th April 2026", "04/26/2026", "10/15/25", "October 15, 2025"

**PROCEDURE:**
1. Check the date mentioned for the FLIGHT (not hotel dates!)
2. If flight date is vague/relative -> RESPOND with clarification request, DO NOT call tool
3. If flight date is specific -> Call adk_book_flight tool

**CRITICAL EXAMPLE (from test case):**
Input: "Book a flight from SFO to BOM next week and a Marriott hotel in Mumbai on 10/15/25"
Analysis:
- Flight date: "next week" ← VAGUE!
- Hotel date: "10/15/25" ← This is NOT for the flight!
Action: DO NOT call adk_book_flight. Instead respond: "I need a specific date for your flight. Could you please provide one?"

NEVER use the tool for vague dates. ALWAYS ask for clarification instead.""",
    generate_content_config=contentConfig,
    tools=[adk_book_flight]  # Define flight booking tools here
)

hotel_booking_agent = LlmAgent(
    name="adk_hotel_booking_agent",
    model=MODEL,
    description= "Agent to book hotels based on user queries.",
    instruction= """You are a helpful agent who can assist users in booking hotels. You ONLY handle hotel booking. Focus ONLY on the hotel-related parts of the user's request.

BOOKING RULES:
- When the user provides a hotel name and location, IMMEDIATELY book by calling adk_book_hotel
- Do NOT ask for confirmation - just book it
- Extract the hotel name and city from the request

Hotel availability rules:
- Marriott is only available on odd dates (1st, 3rd, 5th, 7th, 9th, 11th, 13th, 15th, 17th, 19th, 21st, 23rd, 25th, 27th, 29th, 31st)
- Hilton is available on even dates
- If user requests Marriott on an even date, suggest Hilton instead or ask them to choose an odd date

IMPORTANT: Use the exact tool name 'adk_book_hotel' to book hotels. Call it immediately when you have hotel name and city.""",
    generate_content_config=contentConfig,
    tools=[adk_book_hotel]  # Define hotel booking tools here
)

trip_summary_agent = LlmAgent(
    name="adk_trip_summary_agent",
    model=MODEL,
    description= "Summarize the travel details from hotel bookings and flight bookings agents.",
    instruction= """Summarize the travel details from the flight booking and hotel booking agents. Be concise in response and provide a single sentence summary.

CRITICAL RULES FOR ACCURACY:
1. Only report bookings that were ACTUALLY COMPLETED with a successful tool call
2. If an agent asked for clarification or more information, DO NOT claim that booking was completed
3. If an agent only made an inquiry but did not book, DO NOT mention that booking
4. Do not use words like 'pending', 'will be booked', or 'planned' unless the agent explicitly stated this
5. If a flight or hotel was NOT booked, explicitly state that it was NOT booked or that more information was requested

Examples:
- CORRECT: "Hotel booking at Marriott in Mumbai on 10/15/25 was completed. Flight booking requires a specific date."
- INCORRECT: "Flight from SFO to BOM was booked" (when only a clarification was requested)
- INCORRECT: "Hotel booking is pending" (when no tool was called)""",
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