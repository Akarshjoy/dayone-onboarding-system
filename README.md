# DayOne — Smart Employee Onboarding System

A serverless employee onboarding application built with AWS. DayOne brings employee account creation, document collection, equipment assignment, policy acknowledgement, and onboarding progress into one platform.

## Overview

Employee onboarding often involves scattered emails, manual checklists, and repeated data entry. DayOne provides a shared system where HR teams manage onboarding and new employees complete their tasks.

Each employee receives a unique employee ID that connects their profile, documents, equipment, and workflow progress.

## Features

### Employee Identity and Authentication

- Creates employee profiles in Amazon DynamoDB with UUID-based employee IDs.
- Stores department, role, manager, joining date, and employment type.
- Creates Amazon Cognito accounts with temporary login credentials.
- Sends invitation emails through Cognito's Amazon SES integration.
- Provides separate access for HR administrators and employees.

### Onboarding Workflow

AWS Step Functions coordinates four stages:

1. Document Collection
2. IT Provisioning
3. Policy Sign-off
4. Manager Introduction

Each stage uses AWS Lambda and stores its completion status in DynamoDB. The workflow is designed to send reminders for incomplete stages after 24 hours.

### Document Collection

- Upload ID proof, degree certificate, and signed offer letter.
- Supports PDF, JPEG, and PNG files up to 5 MB each.
- Stores documents in an encrypted, versioned Amazon S3 bucket.
- Validates file size, type, and content signatures.
- Allows HR to review, verify, or request replacement documents.
- Notifies HR through Amazon SNS after all required documents are verified.

### Equipment and Access

- Records equipment assignments using asset IDs.
- Prevents conflicting equipment assignments.
- Adds employees to the appropriate Cognito access group.

### Policy Acknowledgement

- Displays a sample workplace policy.
- Records employee acknowledgement, policy version, and timestamp.
- Updates onboarding progress after sign-off.

### Manager Introduction and Readiness

- Allows HR to confirm that the manager introduction has taken place.
- Checks completion of all onboarding stages.
- Marks the employee as ready for Day 1.
- Includes completion emails and a scheduled joining-day welcome job.

## User Views

### HR Dashboard

HR administrators can:

- Invite new employees.
- View the onboarding pipeline.
- Track individual progress.
- Review employee documents.
- Assign equipment.
- Confirm manager introductions.

### Employee Portal

Employees can:

- Sign in and change their temporary password.
- Accept their offer.
- Upload required documents.
- Acknowledge policies.
- View their manager, joining date, equipment, and onboarding progress.

## Technology Stack

| Component | Technology |
|---|---|
| Frontend | HTML, CSS, JavaScript |
| Backend | Python, AWS Lambda |
| API | Amazon API Gateway |
| Database | Amazon DynamoDB |
| Authentication | Amazon Cognito |
| Workflow orchestration | AWS Step Functions |
| Document storage | Amazon S3 |
| Email delivery | Amazon SES |
| HR notifications | Amazon SNS |
| Event handling and scheduling | Amazon EventBridge |
| Website delivery | Amazon CloudFront and S3 |
| Infrastructure as code | AWS SAM and CloudFormation |
| Logging | Amazon CloudWatch |

## How It Works

1. HR submits a new employee's details.
2. The backend creates a DynamoDB employee record and Cognito account.
3. The employee receives an invitation and signs in.
4. Offer acceptance starts the onboarding workflow.
5. The employee uploads documents, which HR reviews.
6. HR assigns equipment and enables employee access.
7. The employee acknowledges the workplace policy.
8. HR confirms the manager introduction.
9. The readiness check marks onboarding complete when all stages pass.

## Project Structure

- `backend/` — Lambda handlers, API logic, and validation rules.
- `frontend/` — HR dashboard and employee portal.
- `scripts/` — Infrastructure generation and frontend configuration.
- `tests/` — Automated tests.
- `docs/` — Architecture, schema diagram, cost estimate, and demo guide.
- `template.json` — Generated AWS SAM infrastructure template.
- `requirements-dev.txt` — Development and test dependencies.

## Deployment Overview

1. Install Python matching the template runtime, AWS CLI, and AWS SAM CLI.
2. Configure an AWS profile with the required deployment permissions.
3. Verify the sender identity in Amazon SES.
4. Generate the infrastructure template using `scripts/build_template.py`.
5. Validate and build the application with AWS SAM.
6. Deploy using `sam deploy --guided`.
7. Generate frontend configuration using `scripts/configure.py`.
8. Upload the frontend to the website S3 bucket.
9. Create a Cognito HR administrator and add it to the `HRAdmin` group.
10. Open the CloudFront URL and test the onboarding journey.

If SES remains in sandbox mode, verify recipient email addresses before testing invitations and reminders.

## Security Measures

- Cognito authentication for application access.
- Backend checks for HR and employee permissions.
- Private S3 buckets with public access blocked.
- HTTPS website delivery through CloudFront.
- Encrypted document storage.
- Temporary upload and download permissions.
- Version-specific document review.
- IAM roles for AWS service access.

Credentials, temporary passwords, callback tokens, and real employee documents must not be committed to this repository.

## Current Status

The AWS infrastructure has been deployed, and both the HR dashboard and employee portal have been accessed.

End-to-end workflow validation is still in progress. The latest reviewed Step Functions execution failed and requires further diagnosis before the complete onboarding flow can be considered verified.

## Scope and Limitations

- HR manually reviews documents and confirms manager introductions.
- Equipment assignment records an asset ID; it does not physically provision a device.
- IT access currently uses Cognito groups. External services such as Slack, Microsoft 365, and GitHub require additional integrations.
- Manager meeting scheduling is not implemented.
- Policy content is a demonstration sample.
- File validation is not malware scanning or automatic identity verification.
- Production use requires further security, reliability, and operational testing.

## Documentation and Deliverables

- [Architecture and API documentation](docs/architecture.md)
- [DynamoDB schema diagram](docs/schema.svg)
- [Cost estimate for 50 monthly onboarding events](docs/cost-estimate.md)
- [Demo and screenshot guide](docs/demo-guide.md)

Successful Step Functions execution screenshots and a video of the complete journey will be added after live workflow validation.

## Future Improvements

- External application account provisioning.
- Automated manager meeting scheduling.
- Malware scanning for uploaded documents.
- More detailed audit history.
- Employee offboarding and equipment return workflows.
- Improved reporting and reminder delivery.
- Stronger administrator authentication and account recovery.

## Project Purpose

DayOne demonstrates how AWS serverless services can coordinate employee onboarding around a consistent employee identity, shared progress tracking, and automated communication.
