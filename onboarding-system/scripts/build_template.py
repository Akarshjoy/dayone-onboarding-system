import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
def ref(name): return {'Ref': name}
def arn(name): return {'Fn::GetAtt': [name, 'Arn']}
def sub(value): return {'Fn::Sub': value}
def resource(kind, props, **extra): return {'Type': kind, 'Properties': props, **extra}
def policy(actions, resources): return {'Effect': 'Allow', 'Action': actions, 'Resource': resources}
R = {}
for name, key in [('Employees', 'employee_id'), ('Identities', 'email_hash'), ('Assets', 'asset_id')]:
    R[name] = resource('AWS::DynamoDB::Table', {'BillingMode': 'PAY_PER_REQUEST',
        'AttributeDefinitions': [{'AttributeName': key, 'AttributeType': 'S'}],
        'KeySchema': [{'AttributeName': key, 'KeyType': 'HASH'}], 'SSESpecification': {'SSEEnabled': True},
        'PointInTimeRecoverySpecification': {'PointInTimeRecoveryEnabled': True}}, DeletionPolicy='Retain', UpdateReplacePolicy='Retain')
block = {'BlockPublicAcls': True, 'BlockPublicPolicy': True, 'IgnorePublicAcls': True, 'RestrictPublicBuckets': True}
encryption = {'ServerSideEncryptionConfiguration': [{'ServerSideEncryptionByDefault': {'SSEAlgorithm': 'AES256'}}]}
R['WebBucket'] = resource('AWS::S3::Bucket', {'PublicAccessBlockConfiguration': block, 'BucketEncryption': encryption}, DeletionPolicy='Retain', UpdateReplacePolicy='Retain')
R['OAC'] = resource('AWS::CloudFront::OriginAccessControl', {'OriginAccessControlConfig': {
    'Name': sub('${AWS::StackName}-oac'), 'OriginAccessControlOriginType': 's3', 'SigningBehavior': 'always', 'SigningProtocol': 'sigv4'}})
R['Distribution'] = resource('AWS::CloudFront::Distribution', {'DistributionConfig': {'Enabled': True,
    'DefaultRootObject': 'index.html', 'HttpVersion': 'http2', 'PriceClass': 'PriceClass_100',
    'Origins': [{'Id': 'web', 'DomainName': {'Fn::GetAtt': ['WebBucket', 'RegionalDomainName']},
        'OriginAccessControlId': ref('OAC'), 'S3OriginConfig': {'OriginAccessIdentity': ''}}],
    'DefaultCacheBehavior': {'TargetOriginId': 'web', 'ViewerProtocolPolicy': 'redirect-to-https',
        'AllowedMethods': ['GET', 'HEAD'], 'CachedMethods': ['GET', 'HEAD'],
        'ForwardedValues': {'QueryString': False}, 'MinTTL': 0, 'DefaultTTL': 60, 'MaxTTL': 300,
        'ResponseHeadersPolicyId': '67f7725c-6f97-4210-82d7-5512b31e9d03'},
    'ViewerCertificate': {'CloudFrontDefaultCertificate': True}}})
portal = sub('https://${Distribution.DomainName}')
R['WebPolicy'] = resource('AWS::S3::BucketPolicy', {'Bucket': ref('WebBucket'), 'PolicyDocument': {'Version': '2012-10-17', 'Statement': [
    {'Effect': 'Allow', 'Principal': {'Service': 'cloudfront.amazonaws.com'}, 'Action': 's3:GetObject',
        'Resource': sub('${WebBucket.Arn}/*'), 'Condition': {'StringEquals': {'AWS:SourceArn': sub('arn:${AWS::Partition}:cloudfront::${AWS::AccountId}:distribution/${Distribution}')}}},
    {'Effect': 'Deny', 'Principal': '*', 'Action': 's3:*', 'Resource': [arn('WebBucket'), sub('${WebBucket.Arn}/*')], 'Condition': {'Bool': {'aws:SecureTransport': 'false'}}}]}})
R['Documents'] = resource('AWS::S3::Bucket', {'BucketEncryption': encryption, 'PublicAccessBlockConfiguration': block,
    'VersioningConfiguration': {'Status': 'Enabled'}, 'NotificationConfiguration': {'EventBridgeConfiguration': {'EventBridgeEnabled': True}},
    'CorsConfiguration': {'CorsRules': [{'AllowedHeaders': ['*'], 'AllowedMethods': ['POST'], 'AllowedOrigins': [portal], 'MaxAge': 300}]},
    'LifecycleConfiguration': {'Rules': [{'Id': 'abort-incomplete', 'Status': 'Enabled', 'AbortIncompleteMultipartUpload': {'DaysAfterInitiation': 1}}]}},
    DeletionPolicy='Retain', UpdateReplacePolicy='Retain')
R['DocumentPolicy'] = resource('AWS::S3::BucketPolicy', {'Bucket': ref('Documents'), 'PolicyDocument': {'Version': '2012-10-17', 'Statement': [
    {'Effect': 'Deny', 'Principal': '*', 'Action': 's3:*', 'Resource': [arn('Documents'), sub('${Documents.Arn}/*')], 'Condition': {'Bool': {'aws:SecureTransport': 'false'}}}]}})
R['Pool'] = resource('AWS::Cognito::UserPool', {'UserPoolName': sub('${AWS::StackName}-users'), 'AliasAttributes': ['email'],
    'UsernameConfiguration': {'CaseSensitive': False}, 'AdminCreateUserConfig': {'AllowAdminCreateUserOnly': True,
    'InviteMessageTemplate': {'EmailSubject': 'Your onboarding account', 'EmailMessage': sub('Welcome! Your username is {username} and temporary password is {####}. Sign in at https://${Distribution.DomainName} and choose a new password.')}},
    'Policies': {'PasswordPolicy': {'MinimumLength': 12, 'RequireLowercase': True, 'RequireUppercase': True, 'RequireNumbers': True, 'RequireSymbols': True, 'TemporaryPasswordValidityDays': 7}},
    'EmailConfiguration': {'EmailSendingAccount': 'DEVELOPER', 'SourceArn': ref('SESIdentityArn'), 'From': ref('SenderEmail')},
    'Schema': [{'Name': 'employee_id', 'AttributeDataType': 'String', 'Mutable': False, 'StringAttributeConstraints': {'MinLength': '36', 'MaxLength': '36'}}],
    'UserPoolTier': 'ESSENTIALS'}, DeletionPolicy='Retain', UpdateReplacePolicy='Retain')
R['Client'] = resource('AWS::Cognito::UserPoolClient', {'UserPoolId': ref('Pool'), 'GenerateSecret': False,
    'ExplicitAuthFlows': ['ALLOW_USER_PASSWORD_AUTH', 'ALLOW_REFRESH_TOKEN_AUTH'], 'PreventUserExistenceErrors': 'ENABLED',
    'AccessTokenValidity': 1, 'IdTokenValidity': 1, 'RefreshTokenValidity': 1,
    'ReadAttributes': ['email', 'custom:employee_id'], 'WriteAttributes': ['email']})
for group in ['HRAdmin', 'Employees']:
    R[group + 'Group'] = resource('AWS::Cognito::UserPoolGroup', {'UserPoolId': ref('Pool'), 'GroupName': group})
R['Topic'] = resource('AWS::SNS::Topic', {'Subscription': [{'Protocol': 'email', 'Endpoint': ref('HREmail')}]})
R['Api'] = resource('AWS::Serverless::Api', {'StageName': 'prod', 'EndpointConfiguration': {'Type': 'REGIONAL'},
    'Cors': {'AllowOrigin': sub("'https://${Distribution.DomainName}'"), 'AllowHeaders': "'Content-Type,Authorization'", 'AllowMethods': "'GET,POST,OPTIONS'"},
    'Auth': {'DefaultAuthorizer': 'Cognito', 'AddDefaultAuthorizerToCorsPreflight': False,
        'Authorizers': {'Cognito': {'UserPoolArn': arn('Pool')}}}})
common = {'EMPLOYEES': ref('Employees'), 'IDENTITIES': ref('Identities'), 'ASSETS': ref('Assets'),
    'POOL': ref('Pool'), 'DOCUMENT_BUCKET': ref('Documents'), 'TOPIC': ref('Topic'), 'SENDER': ref('SenderEmail'),
    'HR_EMAIL': ref('HREmail'), 'PORTAL_URL': portal}
db_policy = policy(['dynamodb:GetItem', 'dynamodb:PutItem', 'dynamodb:UpdateItem', 'dynamodb:Scan'], [arn('Employees'), arn('Identities'), arn('Assets')])
send_policy = policy(['ses:SendEmail'], [ref('SESIdentityArn')])
callback_policy = policy(['states:SendTaskSuccess'], '*')
def function(name, handler, policies, events=None, extra_env=None):
    props = {'CodeUri': 'backend/', 'Runtime': 'python3.14', 'Handler': 'app.' + handler,
        'Timeout': 30, 'MemorySize': 256, 'Environment': {'Variables': {**common, **(extra_env or {})}},
        'Policies': [{'Version': '2012-10-17', 'Statement': policies}]}
    if events: props['Events'] = events
    R[name] = resource('AWS::Serverless::Function', props)
    R[name + 'Logs'] = resource('AWS::Logs::LogGroup', {'LogGroupName': sub('/aws/lambda/${' + name + '}'), 'RetentionInDays': 14})
function('ApiFunction', 'api', [db_policy, callback_policy,
    policy(['cognito-idp:AdminCreateUser', 'cognito-idp:AdminAddUserToGroup'], arn('Pool')),
    policy(['s3:PutObject', 's3:GetObjectVersion'], sub('${Documents.Arn}/*')),
    policy(['sns:Publish'], ref('Topic')), policy(['states:StartExecution'], ref('Workflow'))],
    {'Proxy': {'Type': 'Api', 'Properties': {'RestApiId': ref('Api'), 'Path': '/{proxy+}', 'Method': 'ANY'}}}, {'WORKFLOW': ref('Workflow')})
function('Validator', 'validate_upload', [db_policy, policy(['s3:GetObjectVersion', 's3:DeleteObjectVersion'], sub('${Documents.Arn}/*'))],
    {'Upload': {'Type': 'EventBridgeRule', 'Properties': {'Pattern': {'source': ['aws.s3'], 'detail-type': ['Object Created'],
        'detail': {'bucket': {'name': [ref('Documents')]}}}}}})
function('StageFunction', 'stage', [db_policy, send_policy, callback_policy])
function('ReadyFunction', 'ready', [db_policy, send_policy])
function('WelcomeFunction', 'welcome', [db_policy, send_policy],
    {'Daily': {'Type': 'Schedule', 'Properties': {'Schedule': 'cron(30 3 * * ? *)', 'Description': 'Day 1 welcome at 09:00 India time'}}})
states = {
    'Prepare': {
        'Type': 'Pass',
        'Parameters': {
            'employee_id.$': '$.employee_id',
            'reminder_seconds.$': sub("States.StringToJson('${ReminderSeconds}')")
        },
        'Next': 'documents'
    }
}
stage_names = ['documents', 'it', 'policy', 'manager']
retry = [{'ErrorEquals': ['Lambda.ServiceException', 'Lambda.AWSLambdaException', 'Lambda.SdkClientException', 'Lambda.TooManyRequestsException'], 'IntervalSeconds': 2, 'MaxAttempts': 3, 'BackoffRate': 2}]
for i, name in enumerate(stage_names):
    states[name] = {'Type': 'Task', 'Resource': 'arn:aws:states:::lambda:invoke.waitForTaskToken',
        'Parameters': {'FunctionName': arn('StageFunction'), 'Payload': {'employee_id.$': '$.employee_id', 'stage': name, 'token.$': '$$.Task.Token'}},
        'TimeoutSecondsPath': '$.reminder_seconds', 'ResultPath': None, 'Retry': retry,
        'Catch': [{'ErrorEquals': ['States.Timeout'], 'ResultPath': None, 'Next': name}, {'ErrorEquals': ['States.ALL'], 'ResultPath': '$.error', 'Next': 'NotifyFailure'}],
        'Next': stage_names[i + 1] if i < 3 else 'Ready'}
states['Ready'] = {'Type': 'Task', 'Resource': arn('ReadyFunction'), 'Retry': retry,
    'Catch': [{'ErrorEquals': ['States.ALL'], 'ResultPath': '$.error', 'Next': 'NotifyFailure'}], 'End': True}
states['NotifyFailure'] = {'Type': 'Task', 'Resource': 'arn:aws:states:::sns:publish',
    'Parameters': {'TopicArn': ref('Topic'), 'Subject': 'Onboarding workflow needs attention', 'Message.$': '$.employee_id'}, 'Next': 'Failed'}
states['Failed'] = {'Type': 'Fail', 'Error': 'OnboardingTaskFailed'}
R['Workflow'] = resource('AWS::Serverless::StateMachine', {'Type': 'STANDARD', 'Name': sub('${AWS::StackName}-workflow'),
    'Definition': {'Comment': 'Human completion callbacks; 24-hour task timeout loops send reminders.', 'StartAt': 'Prepare', 'TimeoutSeconds': 7776000, 'States': states},
    'Policies': [{'Version': '2012-10-17', 'Statement': [policy(['lambda:InvokeFunction'], [arn('StageFunction'), arn('ReadyFunction')]), policy(['sns:Publish'], ref('Topic'))]}]})
R['ExecutionFailures'] = resource('AWS::Events::Rule', {'EventPattern': {'source': ['aws.states'], 'detail-type': ['Step Functions Execution Status Change'],
    'detail': {'stateMachineArn': [ref('Workflow')], 'status': ['FAILED', 'TIMED_OUT', 'ABORTED']}},
    'Targets': [{'Arn': ref('Topic'), 'Id': 'HR', 'InputTransformer': {'InputPathsMap': {'execution': '$.detail.executionArn', 'status': '$.detail.status'}, 'InputTemplate': '"Workflow <execution> is <status>. Review in Step Functions."'}}]})
R['TopicPolicy'] = resource('AWS::SNS::TopicPolicy', {'Topics': [ref('Topic')], 'PolicyDocument': {'Version': '2012-10-17', 'Statement': [
    {'Effect': 'Allow', 'Principal': {'Service': 'events.amazonaws.com'}, 'Action': 'sns:Publish', 'Resource': ref('Topic'),
    'Condition': {'ArnEquals': {'aws:SourceArn': arn('ExecutionFailures')}}}]}})
outputs = {'ApiUrl': sub('https://${Api}.execute-api.${AWS::Region}.amazonaws.com/prod'), 'PortalUrl': portal,
    'WebBucketName': ref('WebBucket'), 'DocumentBucketName': ref('Documents'), 'UserPoolId': ref('Pool'), 'ClientId': ref('Client'),
    'Region': ref('AWS::Region'), 'WorkflowArn': ref('Workflow'), 'DistributionId': ref('Distribution')}
template = {'AWSTemplateFormatVersion': '2010-09-09', 'Transform': 'AWS::Serverless-2016-10-31',
    'Description': 'DayOne onboarding starter', 'Parameters': {'SenderEmail': {'Type': 'String'}, 'HREmail': {'Type': 'String'},
    'SESIdentityArn': {'Type': 'String', 'Description': 'Verified SES identity ARN in the deployment region'},
    'ReminderSeconds': {'Type': 'Number', 'Default': 86400, 'MinValue': 60, 'MaxValue': 86400, 'Description': 'Use 60 only for a demonstration; production 86400'}},
    'Resources': R, 'Outputs': {k: {'Value': v} for k, v in outputs.items()}}
(root / 'docs').mkdir(parents=True, exist_ok=True)
(root / 'template.json').write_text(json.dumps(template, indent=2) + '\n')
(root / 'docs/workflow.asl.json').write_text(json.dumps(template['Resources']['Workflow']['Properties']['Definition'], indent=2) + '\n')
print('Generated template.json and docs/workflow.asl.json')
