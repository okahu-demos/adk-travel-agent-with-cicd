import pytest

from adk_travel_agent import root_agent

# Single prompt input (same as test_adk_flight_booking.py): flight SFO->BOM "next week" + Marriott Mumbai 10/15/25.
# Expectation: adk_book_flight is NOT called (vague "next week"); adk_book_hotel and adk_hotel_booking_agent are used.
PROMPT = "Book a flight from SFO to BOM next week and a Marriott hotel in Mumbai on 10/15/25"


@pytest.mark.asyncio
async def test_flight_booking_fluent_single_trace(monocle_trace_asserter):
    """Run agent once with one prompt, then assert the same 4 requirements as test_adk_flight_booking plus Okahu eval."""
    await monocle_trace_asserter.run_agent_async(root_agent, "google_adk", PROMPT)

    # Requirement #1: adk_book_flight tool should NOT be called
    monocle_trace_asserter.does_not_call_tool("adk_book_flight")

    # Requirement #2: adk_book_hotel tool should be called
    monocle_trace_asserter.called_tool("adk_book_hotel", "adk_hotel_booking_agent")

    # Requirement #3: adk_hotel_booking_agent agent SHOULD be called
    monocle_trace_asserter.called_agent("adk_hotel_booking_agent")

    # Requirement #4: Final response should NOT say "A flight from SFO to BOM has been booked"
    monocle_trace_asserter.does_not_contain_output("A flight from SFO to BOM has been booked")

    # Requirement #5: Okahu evaluation on full trace (no agent filter)
    monocle_trace_asserter.with_evaluation("okahu") \
        .check_eval("hallucination", "no_hallucination")
        # .check_eval("conversation_completeness", "complete") \
        # .check_eval("contextual_relevancy", "relevant")


if __name__ == "__main__":
    pytest.main([__file__])
