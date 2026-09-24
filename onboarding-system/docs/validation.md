# Validation report

Date: 16 September 2026

| Check | Result |
|---|---|
| Python domain and mocked AWS integration tests | 12 passed |
| CloudFormation/SAM template lint | Passed, no reported errors or warnings |
| Frontend JavaScript syntax | Passed with `node --check` |
| Python compilation | Passed |
| Browser visual/interaction checks | Not executed: Chromium binary absent; download timed out |
| Real AWS deployment and end-to-end smoke test | Not performed; AWS account access required |
| SES delivery, SNS subscription, real callback timeout | Must be verified after deployment |
| Execution-history screenshots and video | Not captured; capture instructions included |

Tests cover document signature and size checks, duplicate invitations, employee ownership and HR authorization, stage ordering, callback token redaction, mocked full journey, invalid uploads, stale upload events, verified-document replacement, equipment exclusivity, completion-before-registration callbacks, and reminder re-entry.

Mocked AWS tests exercise application logic but do not prove live IAM permissions, email deliverability, or service integration behavior. The browser test uses intercepted requests and synthetic data; it is provided for local follow-up.
