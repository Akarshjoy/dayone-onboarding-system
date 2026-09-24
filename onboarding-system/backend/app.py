import os
import json
import uuid
import hashlib
from datetime import datetime, timezone
from decimal import Decimal
import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.types import TypeSerializer
from domain import STAGES, DOCUMENTS, TYPES, MAX_BYTES, POLICY_VERSION, RequestError, require, profile, valid_document, require_stage, public_employee

db = boto3.resource('dynamodb')
employees = db.Table(os.environ['EMPLOYEES'])
identities = db.Table(os.environ['IDENTITIES'])
assets = db.Table(os.environ['ASSETS'])
s3 = boto3.client('s3')
cognito = boto3.client('cognito-idp')
sfn = boto3.client('stepfunctions')
ses = boto3.client('ses')
sns = boto3.client('sns')

def now():
    return datetime.now(timezone.utc).isoformat()

def get_employee(employee_id):
    item = employees.get_item(Key={'employee_id': employee_id}, ConsistentRead=True).get('Item')
    require(item is not None, 'Employee not found', 404)
    return item

def update(employee_id, expression, values, names=None, condition=None):
    args = dict(Key={'employee_id': employee_id}, UpdateExpression=expression, ExpressionAttributeValues=values)
    if names:
        args['ExpressionAttributeNames'] = names
    if condition:
        args['ConditionExpression'] = condition
    return employees.update_item(**args)

def email(address, subject, body):
    ses.send_email(Source=os.environ['SENDER'], Destination={'ToAddresses': [address]}, Message={
        'Subject': {'Data': subject}, 'Body': {'Text': {'Data': body + '\n\n' + os.environ['PORTAL_URL']}}})

def complete_callback(employee_id, stage):
    employee = get_employee(employee_id)
    token = employee.get('tokens', {}).get(stage)
    if token and employee['stages'][stage]['status'] == 'complete':
        try:
            sfn.send_task_success(taskToken=token, output=json.dumps({'employee_id': employee_id, 'stage': stage}))
        except ClientError as error:
            if error.response['Error']['Code'] not in ('TaskDoesNotExist', 'TaskTimedOut', 'InvalidToken'):
                raise

def finish(employee_id, stage, actor):
    update(employee_id, 'SET stages.#s = :stage, updated_at = :now', {
        ':stage': {'status': 'complete', 'completed_at': now(), 'completed_by': actor}, ':now': now()}, {'#s': stage})
    complete_callback(employee_id, stage)

def invite(data):
    values = profile(data)
    identity_key = hashlib.sha256(values['email'].encode()).hexdigest()
    employee_id = str(uuid.uuid4())
    try:
        identities.put_item(Item={'email_hash': identity_key, 'employee_id': employee_id}, ConditionExpression='attribute_not_exists(email_hash)')
    except ClientError as error:
        if error.response['Error']['Code'] != 'ConditionalCheckFailedException':
            raise
        employee_id = identities.get_item(Key={'email_hash': identity_key}, ConsistentRead=True)['Item']['employee_id']
    try:
        employees.put_item(Item={**values, 'employee_id': employee_id, 'created_at': now(), 'status': 'invited',
            'stages': {s: {'status': 'pending'} for s in STAGES}, 'documents': {}, 'tokens': {}},
            ConditionExpression='attribute_not_exists(employee_id)')
    except ClientError as error:
        if error.response['Error']['Code'] != 'ConditionalCheckFailedException':
            raise
    employee = get_employee(employee_id)
    try:
        cognito.admin_create_user(UserPoolId=os.environ['POOL'], Username=employee_id,
            DesiredDeliveryMediums=['EMAIL'], UserAttributes=[
                {'Name': 'email', 'Value': employee['email']},
                {'Name': 'email_verified', 'Value': 'true'},
                {'Name': 'custom:employee_id', 'Value': employee_id}])
    except ClientError as error:
        if error.response['Error']['Code'] != 'UsernameExistsException':
            raise
    return public_employee(employee)

def start(employee_id):
    employee = get_employee(employee_id)
    if employee.get('execution_arn'):
        return public_employee(employee)
    update(employee_id, 'SET accepted_at = if_not_exists(accepted_at, :now), #st = :st', {':now': now(), ':st': 'onboarding'}, {'#st': 'status'})
    try:
        execution = sfn.start_execution(stateMachineArn=os.environ['WORKFLOW'], name=employee_id,
            input=json.dumps({'employee_id': employee_id}))
        update(employee_id, 'SET execution_arn = :arn', {':arn': execution['executionArn']})
    except ClientError as error:
        if error.response['Error']['Code'] != 'ExecutionAlreadyExists':
            raise
    return public_employee(get_employee(employee_id))

def api(event, context):
    try:
        claims = event.get('requestContext', {}).get('authorizer', {}).get('claims', {})
        require(claims.get('sub'), 'Authentication required', 401)
        groups = claims.get('cognito:groups', '')
        if isinstance(groups, str):
            groups = groups.strip('[]').replace('"', '').split(',')
        hr = 'HRAdmin' in [g.strip() for g in groups]
        actor = claims.get('cognito:username', claims['sub'])
        data = json.loads(event.get('body') or '{}')
        require(isinstance(data, dict), 'JSON object required')
        path = event['path'].strip('/').split('/')
        method = event['httpMethod']
        if path == ['employees'] and method == 'POST':
            require(hr, 'HR access required', 403)
            return response(201, invite(data))
        if path == ['employees'] and method == 'GET':
            require(hr, 'HR access required', 403)
            args = {'Limit': 50}
            cursor = (event.get('queryStringParameters') or {}).get('cursor')
            if cursor:
                args['ExclusiveStartKey'] = {'employee_id': cursor}
            result = employees.scan(**args)
            return response(200, {'items': [public_employee(e) for e in result['Items']],
                'cursor': result.get('LastEvaluatedKey', {}).get('employee_id')})
        if path == ['me'] and method == 'GET':
            return response(200, public_employee(get_employee(actor)))
        require(len(path) >= 2 and path[0] == 'employees', 'Route not found', 404)
        employee_id = path[1]
        require(hr or employee_id == actor, 'Access denied', 403)
        employee = get_employee(employee_id)
        if len(path) == 2 and method == 'GET':
            return response(200, public_employee(employee))
        action = path[2] if len(path) == 3 else ''
        if method == 'POST' and action == 'accept':
            require(employee_id == actor, 'Only the new hire can accept their offer', 403)
            require(data.get('accepted') is True, 'Offer acceptance required')
            return response(200, start(employee_id))
        if method == 'POST' and action == 'upload':
            require_stage(employee, 'documents')
            require(employee['stages']['documents']['status'] != 'complete', 'Documents already finalized', 409)
            kind, content_type = data.get('kind'), data.get('content_type')
            require(kind in DOCUMENTS and content_type in TYPES, 'Choose a required document and PDF, PNG, or JPEG')
            doc = employee['documents'].get(kind, {})
            require(doc.get('status') != 'verified', 'Verified document cannot be replaced', 409)
            key = employee_id + '/' + kind + '/' + str(uuid.uuid4())
            update(employee_id, 'SET documents.#k = :doc', {':doc': {'key': key, 'status': 'awaiting_upload', 'content_type': content_type}, ':verified': 'verified'}, {'#k': kind, '#s': 'status'}, 'attribute_not_exists(documents.#k.#s) OR documents.#k.#s <> :verified')
            signed = s3.generate_presigned_post(os.environ['DOCUMENT_BUCKET'], key,
                Fields={'Content-Type': content_type, 'x-amz-server-side-encryption': 'AES256'},
                Conditions=[{'Content-Type': content_type}, {'x-amz-server-side-encryption': 'AES256'}, ['content-length-range', 1, MAX_BYTES]], ExpiresIn=300)
            return response(200, signed)
        if method == 'POST' and action == 'review-link':
            require(hr, 'HR access required', 403)
            doc = employee['documents'].get(data.get('kind'), {})
            require(doc.get('status') in ('received', 'verified'), 'Document not ready', 409)
            url = s3.generate_presigned_url('get_object', Params={'Bucket': os.environ['DOCUMENT_BUCKET'], 'Key': doc['key'],
                'VersionId': doc['version_id'], 'ResponseContentDisposition': 'attachment'}, ExpiresIn=120)
            return response(200, {'url': url})
        if method == 'POST' and action == 'verify':
            require(hr, 'HR access required', 403)
            require_stage(employee, 'documents')
            kind = data.get('kind')
            doc = employee['documents'].get(kind, {})
            require(doc.get('status') in ('received', 'verified'), 'Document has not passed upload validation', 409)
            require(data.get('decision') in ('verified', 'rejected'), 'Invalid review decision')
            require(doc.get('status') != 'verified' or data['decision'] == 'verified', 'Verified document cannot be rejected after review', 409)
            require(employee['stages']['documents']['status'] != 'complete', 'Documents already finalized', 409)
            if doc.get('status') == 'received':
                update(employee_id, 'SET documents.#k.#s = :s, documents.#k.reviewed_by = :actor, documents.#k.reviewed_at = :now',
                {':s': data['decision'], ':actor': actor, ':now': now(), ':key': doc['key'], ':version': doc['version_id'], ':received': 'received'},
                {'#k': kind, '#s': 'status', '#key': 'key'}, 'documents.#k.#key = :key AND documents.#k.version_id = :version AND documents.#k.#s = :received')
            employee = get_employee(employee_id)
            if all(employee['documents'].get(k, {}).get('status') == 'verified' for k in DOCUMENTS):
                sns.publish(TopicArn=os.environ['TOPIC'], Subject='Documents verified', Message='All required documents verified for employee ' + employee_id)
                finish(employee_id, 'documents', actor)
            return response(200, public_employee(get_employee(employee_id)))
        if method == 'POST' and action == 'it':
            require(hr, 'HR access required', 403)
            require_stage(employee, 'it')
            asset_id = data.get('asset_id', '').strip()
            require(0 < len(asset_id) <= 100, 'Equipment asset ID required')
            require(not employee.get('asset_id') or employee['asset_id'] == asset_id, 'Asset already assigned', 409)
            serializer = TypeSerializer()
            encode = lambda obj: {k: serializer.serialize(v) for k, v in obj.items()}
            boto3.client('dynamodb').transact_write_items(TransactItems=[
                {'Update': {'TableName': os.environ['ASSETS'], 'Key': encode({'asset_id': asset_id}),
                    'UpdateExpression': 'SET employee_id = :id, assigned_at = :now',
                    'ConditionExpression': 'attribute_not_exists(employee_id) OR employee_id = :id',
                    'ExpressionAttributeValues': encode({':id': employee_id, ':now': now()})}},
                {'Update': {'TableName': os.environ['EMPLOYEES'], 'Key': encode({'employee_id': employee_id}),
                    'UpdateExpression': 'SET asset_id = :asset',
                    'ConditionExpression': 'attribute_not_exists(asset_id) OR asset_id = :asset',
                    'ExpressionAttributeValues': encode({':asset': asset_id})}}
            ])
            cognito.admin_add_user_to_group(UserPoolId=os.environ['POOL'], Username=employee_id, GroupName='Employees')
            finish(employee_id, 'it', actor)
            return response(200, public_employee(get_employee(employee_id)))
        if method == 'POST' and action == 'policy':
            require(employee_id == actor, 'Only the employee can sign', 403)
            require_stage(employee, 'policy')
            require(data.get('accepted') is True and data.get('version') == POLICY_VERSION, 'Read and accept the current policy')
            update(employee_id, 'SET policy_version = :v', {':v': POLICY_VERSION})
            finish(employee_id, 'policy', actor)
            return response(200, public_employee(get_employee(employee_id)))
        if method == 'POST' and action == 'manager':
            require(hr, 'HR access required', 403)
            require_stage(employee, 'manager')
            require(data.get('confirmed') is True, 'Confirm that the introduction took place')
            finish(employee_id, 'manager', actor)
            return response(200, public_employee(get_employee(employee_id)))
        raise RequestError('Route not found', 404)
    except RequestError as error:
        return response(error.status, {'error': str(error)})
    except (ValueError, TypeError, KeyError):
        return response(400, {'error': 'Invalid request'})
    except ClientError as error:
        code = error.response['Error']['Code']
        if code in ('ConditionalCheckFailedException', 'TransactionCanceledException'):
            return response(409, {'error': 'Record changed or equipment is already assigned. Refresh and retry.'})
        print(json.dumps({'error_code': code, 'request_id': getattr(context, 'aws_request_id', '')}))
        return response(503, {'error': 'A service operation failed. Retry the same request.'})

def response(status, body):
    return {'statusCode': status, 'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': os.environ['PORTAL_URL'],
        'Cache-Control': 'no-store'}, 'body': json.dumps(body, default=lambda v: int(v) if isinstance(v, Decimal) else str(v))}

def validate_upload(event, context):
    detail = event['detail']
    key = detail['object']['key']
    parts = key.split('/')
    if len(parts) != 3 or parts[1] not in DOCUMENTS:
        return
    employee_id, kind, _ = parts
    employee = get_employee(employee_id)
    doc = employee['documents'].get(kind, {})
    if doc.get('key') != key or doc.get('status') != 'awaiting_upload':
        return
    version = detail['object'].get('version-id')
    require(version, 'Versioned upload required')
    obj = s3.get_object(Bucket=os.environ['DOCUMENT_BUCKET'], Key=key, VersionId=version)
    prefix = obj['Body'].read(16)
    obj['Body'].close()
    valid = valid_document(obj.get('ContentType'), obj['ContentLength'], prefix)
    try:
        update(employee_id, 'SET documents.#k.#s = :s, documents.#k.version_id = :v, documents.#k.received_at = :now',
            {':s': 'received' if valid else 'rejected', ':v': version, ':now': now(), ':key': key, ':pending': 'awaiting_upload'},
            {'#k': kind, '#s': 'status', '#key': 'key'}, 'documents.#k.#key = :key AND documents.#k.#s = :pending')
    except ClientError as error:
        if error.response['Error']['Code'] != 'ConditionalCheckFailedException':
            raise
    if not valid:
        s3.delete_object(Bucket=os.environ['DOCUMENT_BUCKET'], Key=key, VersionId=version)

def stage(event, context):
    employee_id, stage_name, token = event['employee_id'], event['stage'], event['token']
    employee = get_employee(employee_id)
    update(employee_id, 'SET tokens.#s = :token', {':token': token}, {'#s': stage_name})
    if employee['stages'][stage_name]['status'] == 'complete':
        complete_callback(employee_id, stage_name)
        return
    is_reminder = employee['stages'][stage_name]['status'] == 'in-progress'
    try:
        update(employee_id, 'SET stages.#s.#status = :active', {':active': 'in-progress', ':complete': 'complete'},
            {'#s': stage_name, '#status': 'status'}, 'stages.#s.#status <> :complete')
    except ClientError as error:
        if error.response['Error']['Code'] != 'ConditionalCheckFailedException':
            raise
    employee = get_employee(employee_id)
    if employee['stages'][stage_name]['status'] == 'complete':
        complete_callback(employee_id, stage_name)
        return
    recipient = os.environ['HR_EMAIL'] if stage_name in ('it', 'manager') else employee['email']
    email(recipient, ('Reminder: ' if is_reminder else 'Next step: ') + stage_name,
        'Onboarding task: ' + stage_name + '\nEmployee: ' + employee['name'] + '\nPlease complete the pending task in the portal.')
    if stage_name == 'documents' and is_reminder:
        email(os.environ['HR_EMAIL'], 'Document review reminder', 'Check pending documents for employee ' + employee_id)

def ready(event, context):
    employee_id = event['employee_id']
    update(employee_id, 'SET #s = :s, ready_at = if_not_exists(ready_at, :now)', {':s': 'ready', ':now': now()}, {'#s': 'status'})
    employee = get_employee(employee_id)
    email(employee['email'], 'You are ready for Day 1', 'Your onboarding is complete. Your joining date is ' + employee['joining_date'] + '. Use your account to sign in on Day 1.')
    return {'employee_id': employee_id}

def welcome(event, context):
    today = datetime.now(timezone.utc).date().isoformat()
    args = {}
    while True:
        result = employees.scan(**args)
        for employee in result['Items']:
            if employee['joining_date'] == today and employee['status'] == 'ready' and not employee.get('welcome_sent_at'):
                email(employee['email'], 'Welcome — your first day is here', 'Welcome, ' + employee['name'] + '. Your manager is ' + employee['manager'] + '. Sign in to view your completed checklist.')
                update(employee['employee_id'], 'SET welcome_sent_at = :now', {':now': now()})
        if not result.get('LastEvaluatedKey'):
            break
        args['ExclusiveStartKey'] = result['LastEvaluatedKey']
