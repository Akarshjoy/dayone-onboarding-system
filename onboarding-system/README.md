# DayOne — AWS employee onboarding

A deployable project starter covering the journey from HR invitation and new-hire offer acceptance to Day 1 readiness. It includes a two-view web portal, Python Lambda backend, SAM infrastructure, Step Functions callback workflow, tests, schema diagram, and cost estimate.

**Validation status:** 12 local tests passed against mocked AWS services; CloudFormation linting and JavaScript syntax checks passed. Browser rendering remains unverified because Chromium was unavailable and its download timed out. It has not been deployed to a real AWS account. Genuine Step Functions execution screenshots and a video of the live new-hire journey must be captured after deployment; see `docs/demo-guide.md`.

## What is implemented

| Requirement | Implementation |
|---|---|
| Canonical employee record | DynamoDB Employees table keyed by UUID `employee_id`; email identity mapping prevents duplicate records on invitation retries |
| Account and invitation | Admin-created Cognito account; temporary password and portal URL delivered using Cognito's SES email configuration; first-login password change |
| Structured attributes | Department, role, manager name, joining date, employment type |
| Offer acceptance | Authenticated employee confirms acceptance, then a named Step Functions execution starts |
| Four-stage workflow | Documents → IT → policy → manager; Lambda callback tasks with 24-hour timeout/re-entry reminders |
| Documents | Presigned S3 POST; 5 MB limit; PDF/PNG/JPEG content signatures; S3 encryption and versioning; HR verification separate from upload validation |
| HR notification | SNS email after all required documents are verified; SNS also reports workflow failures |
| Equipment | Atomic employee/equipment assignment; prevents assigning one asset to two employees or two assets to one employee |
| IT access | Adds the Cognito identity to the Employees group; actual Microsoft 365, Slack, or device-management provisioning needs organization-specific connectors |
| Policies | Versioned acknowledgement with employee identity and timestamp; sample text must be replaced by approved policy |
| Manager introduction | HR confirms that introduction occurred; the manager field is a display name, not a separate manager account |
| Day 1 communication | Completion email plus daily 09:00 Asia/Kolkata welcome schedule for ready employees joining that day |
| Frontend | Responsive employee portal and HR dashboard; progress bars and text-labelled statuses |
| Hosting | Static assets in private S3, delivered with HTTPS through CloudFront |

A human still verifies documents, allocates a real asset, signs policies, and performs the introduction. The system automates coordination, account creation, state tracking, and reminders.

## Repository

```text
backend/app.py                 AWS handlers and API
backend/domain.py              Validation and stage rules
frontend/                      Static web app, no frontend build required
scripts/build_template.py      Reproducible SAM template generator
scripts/configure.py           Writes public configuration from stack outputs
template.json                  Deployable AWS SAM template
tests/test_system.py           Mocked AWS integration and domain tests
tests/browser-check.cjs        Browser checks using synthetic data
requirements-dev.txt           Local Python test dependencies
docs/architecture.md           Design, API and schema
docs/schema.svg                ER diagram
docs/workflow.asl.json         Workflow definition with template references
docs/cost-estimate.md          Monthly usage assumptions and AWS sources
docs/demo-guide.md             Live demo and screenshot capture instructions
```

## Deploy from VS Code

Open this folder in VS Code, then use **Terminal → New Terminal**. The commands below work one at a time in PowerShell or bash unless marked otherwise.

### 1. Prerequisites

Install Python 3.12, AWS CLI v2, and AWS SAM CLI. Configure an AWS profile with permissions to deploy CloudFormation, IAM, Lambda, API Gateway, S3, CloudFront, Cognito, DynamoDB, SES, SNS, EventBridge, and Step Functions.

```sh
aws configure
aws sts get-caller-identity
python -m pip install -r requirements-dev.txt
```

Use `us-east-1` for the first demonstration. The SES identity and Cognito deployment must use a supported region configuration; this template expects a verified SES identity in the same region.

In the SES console, verify a sender email or domain. Copy its identity ARN. If the account is still in the SES sandbox, also verify the HR and demonstration new-hire recipient addresses. Confirm the SNS subscription email after deployment. No credentials belong in `config.js`.

### 2. Validate and deploy

```sh
python -m unittest discover -s tests -v
sam validate --lint --template template.json
sam build --template-file template.json
sam deploy --guided
```

Use these deployment inputs:

| Prompt | Value |
|---|---|
| Stack name | `dayone-onboarding` |
| Region | `us-east-1` |
| SenderEmail | Your verified SES sender |
| HREmail | Your HR test inbox |
| SESIdentityArn | Verified SES identity ARN |
| ReminderSeconds | `86400` normally; `60` for a short demonstration |
| Allow SAM IAM role creation | Yes, after reviewing the change set |

Deployment creates billable AWS resources. It creates the services, but does not upload the frontend files. S3 buckets, employee tables, and Cognito pool are retained on stack deletion to avoid accidental data loss.

### 3. Configure and upload frontend

```sh
python scripts/configure.py --stack dayone-onboarding --region us-east-1
aws cloudformation describe-stacks --stack-name dayone-onboarding --query "Stacks[0].Outputs"
```

Copy `WebBucketName` from the output, then replace `YOUR_WEB_BUCKET` below:

```sh
aws s3 sync frontend s3://YOUR_WEB_BUCKET --cache-control "max-age=60"
```

Open `PortalUrl`. CloudFront may need time to finish its initial deployment. A later frontend update becomes visible after its cache expires; optionally invalidate `/index.html`, `/app.js`, `/styles.css`, and `/config.js` in CloudFront.

### 4. Create the first HR administrator

Replace the placeholders with your stack's `UserPoolId` and your HR email. An invitation will be delivered using the configured SES identity.

```sh
aws cognito-idp admin-create-user --user-pool-id YOUR_POOL_ID --username hr-admin --user-attributes Name=email,Value=YOUR_HR_EMAIL Name=email_verified,Value=true --desired-delivery-mediums EMAIL
aws cognito-idp admin-add-user-to-group --user-pool-id YOUR_POOL_ID --username hr-admin --group-name HRAdmin
```

Sign in as `hr-admin` with the emailed temporary password, then set a new password. The HR account is an administrative principal; it intentionally does not have an employee profile.

### 5. Run the journey

1. HR: expand **Invite a new hire**, complete the form, submit.
2. New hire: open the email link in a separate browser profile, change the temporary password, accept the offer.
3. Upload three synthetic test documents. Wait a few seconds and refresh while S3 EventBridge validation runs.
4. HR: refresh, review each exact uploaded version, and verify each document. Confirm the SNS email.
5. HR: assign an equipment asset ID. This also enables Employees-group access in Cognito.
6. New hire: refresh, read the sample policy, and acknowledge it.
7. HR: confirm the manager introduction.
8. Refresh until status is `ready`. The completion email arrives; the joining-day welcome is scheduled separately.

Only the employee can accept the offer and sign the policy. HR completes the IT and introduction tasks. `docs/demo-guide.md` lists evidence to capture.

## Local preview and tests

```sh
python -m http.server 8080 --directory frontend
```

Visit `http://localhost:8080` to view the login design. Real sign-in and APIs require the deployed CloudFront URL because CORS is deliberately limited to that origin. The portal does not pretend to connect to AWS when configuration is empty.

```sh
python -m unittest discover -s tests -v
cfn-lint template.json
node --check frontend/app.js
```

For optional browser checks, install Playwright (`npm install --no-save playwright` and `npx playwright install chromium`), keep the preview server running, then run `node tests/browser-check.cjs`. Browser checks intercept network calls and use explicitly synthetic fixtures; they do not validate AWS deployment.

## Operational boundaries

- AWS deployment, real SES delivery, actual Step Functions callbacks/timeouts, S3 notifications, and CloudFront/Cognito integration must be smoke-tested in your account.
- File signature validation checks declared types and sizes; it is not antivirus scanning or automated proof of identity. HR downloads are restricted, expiring, version-specific links. Add malware scanning before production document review.
- Reminder delivery and notification operations are at-least-once. A crash after sending an email can cause a duplicate on retry. This starter does not claim exactly-once external delivery.
- The daily welcome job processes today's UTC date at 03:30 UTC (09:00 India). If readiness happens after that job, the immediate completion email still sends, but the day-specific welcome is not retried the following day. Customize scheduling for other time zones or catch-up requirements.
- The workflow stops after 90 days and alerts HR. For a failed execution, fix the cause and use Step Functions redrive where eligible; repeated offer acceptance never starts a second workflow. Execution status in AWS is authoritative for failures; the portal has no dedicated redrive screen.
- Documents, employee data, versions, and audit attributes have no automatic deletion policy. Set retention and erasure rules before handling real employee information. Replaced upload objects may remain in S3.
- Scan-based HR listing and daily welcome processing are suitable for the requested small workload. Add indexes and due-date queries as the employee base grows.
- Administrative MFA, account recovery screens, resignation/offboarding, asset return, cancellation, policy revisions after acceptance, external app provisioning, and a full append-only audit log are outside this starter.
- `config.js` contains public deployment IDs only. Browser tokens remain in memory and are lost on reload. There is no refresh-token persistence; sign in again when the token expires.

Do not publish screenshots containing temporary passwords, task tokens, or real employee documents.
