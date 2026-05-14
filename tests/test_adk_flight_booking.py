from asyncio import sleep
import os
import pytest 
import logging
from dotenv import load_dotenv

from adk_travel_agent import root_agent
from monocle_test_tools import TestCase, MonocleValidator


OKAHU_API_KEY = os.environ.get('OKAHU_API_KEY')
logging.basicConfig(level=logging.WARN)
load_dotenv()

agent_test_cases: list[TestCase] = [
    {
        "test_input": ["Book a flight from SFO to BOM next week and a Marriott hotel in Mumbai on 10/15/25"],
        "test_spans": [
            {
                # Requirement #1: adk_book_flight tool should NOT be called
                "span_type": "agentic.tool.invocation",
                "entities": [
                    {"type": "tool", "name": "adk_book_flight"}
                ],
                "test_type": "negative",  # Negative test - tool should NOT be called
            },
            {
                # Requirement #2: adk_book_hotel tool should be called
                "span_type": "agentic.tool.invocation",
                "entities": [
                    {"type": "tool", "name": "adk_book_hotel"}
                ],
                "test_type": "positive",  # Positive test - tool should be called
            },
            {
                # Requirement #3: adk_hotel_booking_agent agent SHOULD be called
                "span_type": "agentic.invocation",
                "entities": [
                    {"type": "agent", "name": "adk_hotel_booking_agent"}
                ],
                "test_type": "positive",  # Positive test - agent SHOULD be called
            },
            {
                # Requirement #4: Final response should NOT say "A flight from SFO to BOM has been booked"
                "span_type": "agentic.turn",
                "output": "A flight from SFO to BOM has been booked",
                "test_type": "negative",  # Negative test - output should NOT match
                "comparer": "similarity",
            }
        ]
    },
]

@MonocleValidator().monocle_testcase(agent_test_cases)
async def test_run_agents(my_test_case: TestCase):
   await MonocleValidator().test_agent_async(root_agent, "google_adk", my_test_case)
   await sleep(2) # Ensure all telemetry is flushed

if __name__ == "__main__":
    pytest.main([__file__])
