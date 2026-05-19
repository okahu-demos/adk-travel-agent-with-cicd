"""Resolve a GitHub run ID to Okahu trace IDs and span summaries."""

import json
import os
import re
import sys
import urllib.request


def resolve_traces(query: str, app: str, api_key: str) -> dict:
    match = re.search(r"(?:github_)?(\d{10,})", query)
    if not match:
        return {"trace_ids": "", "trace_context": ""}

    run_id = match.group(1)
    url = f"https://api.okahu.co/api/v1/apps/{app}/traces?duration_fact=test_runs&fact_ids=github_{run_id}"
    req = urllib.request.Request(url, headers={"x-api-key": api_key})
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())

    traces = data.get("traces", [])
    trace_ids = [t["trace_id"] for t in traces if t.get("trace_id")]
    if not trace_ids:
        return {"trace_ids": "", "trace_context": ""}

    span_summary = ""
    for trace in traces:
        tid = trace.get("trace_id", "")
        wf = trace.get("workflow_name", "")
        if wf:
            spans_url = f"https://api.okahu.co/api/v1/workflows/{wf}/traces/{tid}/spans"
            spans_req = urllib.request.Request(spans_url, headers={"x-api-key": api_key})
            try:
                with urllib.request.urlopen(spans_req) as resp:
                    spans_data = json.loads(resp.read())
                count = len(spans_data.get("spans", []))
            except Exception:
                count = 0
            span_summary += f"Trace {tid} (workflow: {wf}, spans: {count}). "

    trace_id_list = ",".join(trace_ids)
    return {
        "trace_ids": trace_id_list,
        "trace_context": f"Resolved trace IDs: {trace_id_list}. {span_summary}",
    }


if __name__ == "__main__":
    query = os.environ.get("QUERY", "")
    app = os.environ.get("APP", "unknown_app")
    api_key = os.environ.get("OKAHU_API_KEY", "")

    result = resolve_traces(query, app, api_key)

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"trace_ids={result['trace_ids']}\n")
            f.write(f"trace_context<<TRACE_CTX_EOF\n{result['trace_context']}\nTRACE_CTX_EOF\n")
    else:
        print(json.dumps(result))
