# Live demo and evidence capture

The optional browser test can generate HR and employee preview PNGs using synthetic fixtures. It could not run in the authoring environment because Chromium was unavailable and its download timed out. No preview PNGs, real cloud execution screenshots, or live-journey recording are included.

## Five-minute recording plan

| Time | Action | Evidence to show |
|---|---|---|
| 0:00–0:40 | HR submits a new-hire form | Structured fields and resulting employee row |
| 0:40–1:10 | Open invitation, sign in, change temporary password | Portal login and account setup; hide password |
| 1:10–1:40 | Accept offer | Step Functions execution appears with document stage waiting |
| 1:40–2:20 | Upload three synthetic documents | S3 versioned objects and received statuses |
| 2:20–2:50 | HR downloads and verifies documents | Document stage complete and SNS notification |
| 2:50–3:20 | Assign asset | IT complete, equipment ID, Employees group membership |
| 3:20–3:50 | Employee acknowledges policy | Policy stage complete and acknowledgement timestamp |
| 3:50–4:20 | HR confirms manager introduction | Progress reaches 100%, employee ready |
| 4:20–5:00 | Sign out, sign in again | Day 1 login, completed portal, workflow succeeded |

For the joining-day scheduled welcome, use today's date and schedule the demonstration before the configured daily run, or invoke `WelcomeFunction` manually with `{}` for a clearly labelled scheduling-handler demonstration. Do not present manual invocation as proof that the schedule fired.

## Required screenshots from real AWS

1. Step Functions execution graph after offer acceptance, waiting on `documents`.
2. History after a reminder timeout/re-entry. In a demo stack, set `ReminderSeconds=60`, then wait beyond one minute without completing the stage. Restore 86,400 for normal operation.
3. All four stages completed and execution `SUCCEEDED`.
4. DynamoDB record showing the same employee UUID across the identity mapping, Cognito username, and stage data. Hide task tokens and personal information.
5. S3 object version with server-side encryption enabled; use clearly synthetic documents.
6. HR dashboard and employee portal at 100%.

A genuine AWS console history cannot be generated without running the state machine in an AWS account. Avoid substituting the schematic ASL graph for evidence of successful execution.

## Live smoke-test checklist

- Invite twice with the same email: one employee UUID and one Cognito identity remain.
- Employee A tries Employee B's API URL: HTTP 403.
- New hire tries an HR-only endpoint: HTTP 403.
- Upload a text file renamed `.pdf`: rejected by content-signature validation.
- Upload over 5 MB: blocked by presigned policy and frontend check.
- HR cannot complete IT before document verification.
- Two hires cannot share the same asset ID.
- Policy acknowledgement records the actor and policy version.
- Leave a task pending: receive reminder after configured timeout.
- Complete immediately after a timeout: callback or next registration must continue the workflow.
- Observe SNS failure notification with a deliberately failed test execution, then redrive after fixing the test cause.

Use a separate browser profile for HR and the new hire. Recording with Windows Snipping Tool or another screen recorder is sufficient. Never record actual credentials or real ID documents.
