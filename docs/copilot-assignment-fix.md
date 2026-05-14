# Copilot Assignment Fix Documentation

## Problem Statement

The GitHub Actions workflow `.github/workflows/test_adk_flight_booking_auto_pr_copilot.yml` was not successfully assigning issues to the GitHub Copilot coding agent when tests failed.

## Root Cause Analysis (RCA)

### The Issue
The workflow's "Assign Copilot Agent" step was using an incorrect value for the `actorIds` parameter:

```yaml
actorIds: ["COPILOT"]  # ❌ INCORRECT
```

### Why This Failed
The GitHub GraphQL API's `replaceActorsForAssignable` mutation requires the `actorIds` parameter to contain an array of **GraphQL node IDs** (base64-encoded strings like `"MDU6Qm90MTIzNDU="`), not string literals like `"COPILOT"`.

Each GitHub actor (user, bot, organization) has a unique node ID that must be fetched dynamically via the GraphQL API.

## The Solution

### Overview
The fix involves two key changes:

1. **Fetch the Copilot agent's node ID dynamically** using a GraphQL query to `repository.suggestedActors`
2. **Use the fetched node ID** in the assignment mutation instead of a hardcoded string

### Implementation Details

#### Step 1: Query for Copilot Agent Node ID

The workflow now queries the repository's suggested actors to find the Copilot bot:

```graphql
query($owner: String!, $repo: String!, $number: Int!) {
  repository(owner: $owner, name: $repo) {
    issue(number: $number) {
      id
    }
    suggestedActors(capabilities: [CAN_BE_ASSIGNED], first: 100) {
      nodes {
        login
        __typename
        ... on Bot {
          id
        }
      }
    }
  }
}
```

The JavaScript code then searches for the bot with login `copilot-swe-agent`:

```javascript
const copilotAgent = data.repository.suggestedActors.nodes.find(
  node => node.login === "copilot-swe-agent" && node.__typename === "Bot"
);

if (copilotAgent) {
  core.setOutput("copilot_id", copilotAgent.id);
  console.log(`Found Copilot agent with ID: ${copilotAgent.id}`);
} else {
  console.log("Copilot agent not found in suggestedActors");
  core.setOutput("copilot_id", "");
}
```

#### Step 2: Use the Node ID in Assignment

The assignment step now uses the dynamically fetched ID:

```javascript
const copilotId = "${{ steps.get_node.outputs.copilot_id }}";

if (!copilotId) {
  console.log("Copilot agent ID not available. Skipping assignment.");
  return;
}

const variables = {
  input: {
    actorIds: [copilotId],  // ✅ CORRECT - using actual node ID
    assignableId: "${{ steps.get_node.outputs.node_id }}"
  }
};

await github.graphql(query, variables, {
  headers: {
    "GraphQL-Features": "issues_copilot_assignment_api_support"
  }
});
```

### Additional Improvements

1. **Error Handling**: Added try-catch block to handle API failures gracefully
2. **Validation**: Checks if Copilot ID is available before attempting assignment
3. **Logging**: Enhanced logging for debugging purposes
4. **Graceful Degradation**: If Copilot is not available, the workflow logs a message and continues

## Is It Possible?

**Yes!** Assigning issues to GitHub Copilot via the API is fully supported as of December 2024 (GitHub Changelog: "Assign issues to Copilot using the API").

### Requirements

1. The repository must have GitHub Copilot access
2. The workflow must use `GITHUB_TOKEN` with appropriate permissions:
   - `issues: write` (already present)
   - `actions: read` (already present)
3. The GraphQL request must include the header:
   ```
   "GraphQL-Features": "issues_copilot_assignment_api_support"
   ```

### Limitations

- You **cannot** assign a custom Copilot agent via the API (only the default `copilot-swe-agent`)
- Custom agent assignment is only available through the GitHub web UI
- The REST API does not support Copilot assignment; you must use GraphQL

## Testing

To test this workflow:

1. Trigger the workflow manually via `workflow_dispatch`
2. If tests fail, the workflow will:
   - Create an issue with test failure details
   - Fetch the Copilot agent's node ID
   - Assign the issue to Copilot
3. Verify in the GitHub UI that the issue is assigned to `copilot-swe-agent`

## References

- [GitHub Changelog: Assign issues to Copilot using the API](https://github.blog/changelog/2025-12-03-assign-issues-to-copilot-using-the-api/)
- [GitHub Docs: Managing coding agents](https://docs.github.com/en/copilot/how-tos/use-copilot-agents/manage-agents)
- [GitHub GraphQL API Reference](https://docs.github.com/en/graphql)
- [Community Discussion: Unable to assign a custom copilot agent to an issue via GraphQL API](https://github.com/orgs/community/discussions/180431)

## Summary

The workflow now correctly assigns issues to GitHub Copilot by:
1. Dynamically fetching the Copilot agent's node ID using GraphQL
2. Using that node ID (instead of a hardcoded string) in the assignment mutation
3. Including proper error handling and validation

This fix ensures that when tests fail, GitHub Copilot is automatically assigned to investigate and fix the issue.
