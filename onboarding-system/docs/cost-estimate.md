# Cost estimate — 50 onboarding events per month

Prepared 16 September 2026. Illustrative USD usage estimate for **US East (N. Virginia), us-east-1**. This is an arithmetic model, not a measured AWS bill or a regional quote. Existing account workloads may consume free allowances. Taxes and AWS Support are excluded.

## Workload assumptions

- 50 new hires plus 2 HR administrators actively signing in.
- 3 files per hire, averaging 3 MB: about 0.45 GB of new documents per month. Each file capped at 5 MB.
- 3,000 API calls; 5,000 Lambda invocations including uploads, reminders, admin interactions, and schedule runs.
- Average Lambda execution: 0.5 seconds at 256 MB. No provisioned concurrency or VPC/NAT Gateway.
- Four stage callbacks plus readiness = about 5 base state transitions per onboarding; four timeout reminder re-entries each gives roughly 450 transitions total. Budget 1,000 transitions for retries/failures. Verify exact billed transitions after the live demo.
- 1,000 outgoing emails, intentionally above the expected ordinary workload; no dedicated IP, Mail Manager, attachment emails, or paid SES deliverability plan.
- 30,000 DynamoDB write units and 50,000 read units, including size/transaction overhead. This budget covers the small starting dataset, not years of scan growth.
- 0.25 GB of logs; low web traffic; 14-day Lambda log retention.

## Estimated monthly cost

| Service | Calculation or budgeting basis | USD/month |
|---|---|---:|
| Step Functions Standard | 1,000 × $0.025 / 1,000; before free allowance | $0.025 |
| Lambda requests | 5,000 × $0.20 / million | $0.001 |
| Lambda compute | 5,000 × 0.5 s × 0.25 GB × $0.0000166667 | $0.0104 |
| API Gateway REST | 3,000 × $3.50 / million, excluding transfer | $0.0105 |
| SES outbound | 1,000 × $0.10 / 1,000 | $0.100 |
| DynamoDB requests, storage and PITR | Small-table allowance; requests about $0.025 | $0.05–$0.10 |
| S3 first-month storage and requests | 0.45 GB × $0.023 ≈ $0.0104; allow requests, web assets, versions | $0.02–$0.05 |
| Cognito Essentials | 52 direct-login MAUs within eligible shared 10,000-MAU free allowance | $0.00 |
| Logs, SNS, events, CloudFront and transfer | Conservative combined allowance for this small traffic level; not a fixed AWS fee | $0.20–$1.00 |
| **Modeled total** | With Cognito allowance; other major service free allowances not deducted | **about $0.42–$1.30** |

**Practical planning budget: $1–$5/month for the stated small workload.** This includes headroom; it is not a guaranteed maximum. The eligible Step Functions free allowance can make the 1,000 transitions free. Other AWS allowances may reduce costs further. If Cognito Essentials' direct-login free allowance is already exhausted, 52 additional MAUs at $0.015 add about **$0.78/month**.

Storage accumulates: after 12 months, 0.45 GB/month becomes about 5.4 GB before object versions and replacements. At the illustrative S3 rate this is around $0.12/month in storage alone. The template retains records and document versions, so repeated uploads, longer retention, larger files, and an expanding employee base increase the bill.

This estimate excludes custom domain registration, paid enterprise app licenses, external device-management integrations, malware scanning, optional MFA SMS, WAF, and paid support. They are not provisioned by this starter. CloudFront is used on a usage basis, with no paid flat-rate plan assumed.

## Official sources

- [AWS Step Functions pricing](https://aws.amazon.com/step-functions/pricing/): Standard state-transition pricing and free allowance.
- [AWS Lambda pricing](https://aws.amazon.com/lambda/pricing/): requests and duration.
- [API Gateway pricing](https://aws.amazon.com/api-gateway/pricing/): regional REST API examples.
- [Amazon SES pricing](https://aws.amazon.com/ses/pricing/): outbound email a-la-carte rates.
- [DynamoDB pricing](https://aws.amazon.com/dynamodb/pricing/): on-demand requests, storage and backup options.
- [Amazon S3 pricing](https://aws.amazon.com/s3/pricing/): storage, requests and transfer.
- [Cognito pricing](https://aws.amazon.com/cognito/pricing/): Essentials MAU rates and account/organization free allowances.
- [CloudWatch pricing](https://aws.amazon.com/cloudwatch/pricing/) and [CloudFront pricing](https://aws.amazon.com/cloudfront/pricing/): observability and delivery charges.

Before deployment, enter your selected region, retention, expected document size, and existing account usage into the [AWS Pricing Calculator](https://calculator.aws/). Review actual service usage after the demo.
