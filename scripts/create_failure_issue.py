"""Create a GitHub issue for test failures with optional Kahu SRE Agent analysis."""

import os
import subprocess
import sys
from datetime import datetime, timezone


def create_issue(
    workflow_name: str,
    test_file: str,
    test_output_path: str,
    run_id: str,
    actor: str,
    repo: str,
    kahu_response: str = "",
) -> str:
    test_output = ""
    if os.path.isfile(test_output_path):
        with open(test_output_path) as f:
            test_output = f.read()
    else:
        test_output = "Test output not available"

    body_parts = [
        "## Okahu Environment: Okahu-prod\n",
        f"## Test Failure: {test_file}\n",
        f"The test workflow `{workflow_name}` failed.\n",
        "### Workflow Error Output\n",
        f"```\n{test_output}\n```\n",
    ]

    if kahu_response:
        body_parts.append("### Kahu SRE Agent Analysis\n")
        body_parts.append(f"{kahu_response}\n")
        body_parts.append("---\n*Analysis from [Okahu SRE Agent](https://okahu.co)*\n")

    body_parts.extend([
        "---\n",
        "*This issue was automatically created by the GitHub Actions workflow.*\n",
        f"- Workflow Run ID: {run_id}\n",
        f"- GitHub Actor: {actor}\n",
    ])

    body = "\n".join(body_parts)
    body_file = "/tmp/issue_body.md"
    with open(body_file, "w") as f:
        f.write(body)

    result = subprocess.run(
        [
            "gh", "issue", "create",
            "--repo", repo,
            "--title", f"Test Failure: {test_file} - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "--body-file", body_file,
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"Error creating issue: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    issue_url = result.stdout.strip()
    print(f"Created issue: {issue_url}")
    return issue_url


if __name__ == "__main__":
    workflow_name = os.environ.get("WORKFLOW_NAME", "unknown")
    test_file = os.environ.get("TEST_FILE", "unknown_test.py")
    test_output_path = os.environ.get("TEST_OUTPUT_PATH", "test_output.txt")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    actor = os.environ.get("GITHUB_ACTOR", "")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    kahu_response = os.environ.get("KAHU_RESPONSE", "")

    issue_url = create_issue(
        workflow_name, test_file, test_output_path,
        run_id, actor, repo, kahu_response,
    )

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        issue_num = issue_url.rstrip("/").split("/")[-1]
        with open(github_output, "a") as f:
            f.write(f"issue_url={issue_url}\n")
            f.write(f"issue_number={issue_num}\n")
