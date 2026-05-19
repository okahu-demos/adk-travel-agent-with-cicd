"""Call the Kahu SRE Agent API and return the response."""

import json
import os
import sys
import urllib.request


def call_agent(query: str, app: str, api_key: str, trace_ids: str = "") -> str:
    if trace_ids:
        full_query = f"For app {app}, {query}. Here are the trace IDs: {trace_ids}"
    else:
        full_query = f"For app {app}, {query}"

    payload = json.dumps({"query": full_query}).encode()
    req = urllib.request.Request(
        "https://sre-agent.okahu.co/api/v1/ask_agent",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
        },
        method="POST",
    )

    with urllib.request.urlopen(req) as resp:
        if resp.status != 200:
            return f"Error: SRE Agent API returned HTTP {resp.status}"
        body = json.loads(resp.read())

    return body.get("response", "No response content from SRE Agent.")


if __name__ == "__main__":
    query = os.environ.get("QUERY", "investigate this issue")
    app = os.environ.get("APP", "unknown_app")
    api_key = os.environ.get("OKAHU_API_KEY", "")
    trace_ids = os.environ.get("TRACE_IDS", "")

    response = call_agent(query, app, api_key, trace_ids)

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"response<<KAHU_EOF\n{response}\nKAHU_EOF\n")
    else:
        print(response)
