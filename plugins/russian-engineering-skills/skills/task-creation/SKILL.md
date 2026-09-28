---
name: task-creation
description: Create Yandex Tracker tasks when the user asks to add a task, issue, or ticket with a project, assignee, title, and description. Use this skill for live Tracker task creation, project lookup, assignee lookup, and post-create verification.
---

# Task Creation

## Overview

Use this skill to create tasks in Yandex Tracker through the live API and confirm that the created issue has the correct project, assignee, title, and description.

Prefer this skill when the user wants the task to be created for real, not just drafted.

## Workflow

1. Find Tracker credentials locally before asking the user for them.
2. Verify which organization header works.
3. Resolve the target project, queue, and assignee from the live API.
4. Create the issue.
5. Verify the returned issue fields and report the issue key back to the user.

## Credentials And Headers

- Read `TRACKER_TOKEN` and organization id from environment or trusted local files if they already exist in the workspace.
- First try `X-Cloud-Org-ID` for the organization header.
- If the API rejects the org with `X-Org-ID`, switch to `X-Cloud-Org-ID` and verify with `GET /v3/myself`.
- Do not print tokens or organization ids in the final response.

## Data Resolution

- Resolve the project from the live Tracker API instead of guessing.
- If the requested project name is not exact but there is one close, clearly state the assumption after creation.
- Resolve the assignee from Tracker users by exact login first, then by display name.
- Resolve the queue from the target project or from existing Tracker structures. If the project requires a queue, include both in the create payload.
- If the user says there is no due date or deadline, omit due date fields entirely.

## Create Request Rules

- Use `POST /v3/issues/`.
- Send `summary`, `description`, `assignee`, and the target `project.primary` when available.
- Use `markupType: md` for plain text descriptions unless the user explicitly asks for another markup mode.
- For Russian text, send the JSON body as UTF-8 bytes. Plain `Invoke-RestMethod` bodies can produce broken Cyrillic in Tracker.

## Verification

After creation, verify at least:

- issue key
- summary
- assignee
- project
- status

If the API response shows broken Cyrillic, patch the issue immediately with a UTF-8 encoded body and confirm the corrected result.

## Final Response

- Report the created issue key.
- Mention the resolved project and assignee.
- Mention any assumption you had to make, especially if the requested project name did not exactly match Tracker data.
- Do not claim a deadline was set when the user asked for none.
- Do not expose secrets.
