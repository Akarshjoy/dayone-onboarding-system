import os
import sys
import json
import unittest
import importlib
from pathlib import Path
from unittest.mock import patch
import boto3
from moto import mock_aws
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from domain import profile, valid_document, MAX_BYTES, RequestError

class DomainTests(unittest.TestCase):
    def test_content_signatures_and_limits(self):
        self.assertTrue(valid_document('application/pdf', 20, b'%PDF-1.7'))
        self.assertFalse(valid_document('application/pdf', 20, b'<script>'))
        self.assertFalse(valid_document('image/png', MAX_BYTES + 1, b'\x89PNG\r\n\x1a\n'))
        self.assertFalse(valid_document('application/pdf', 0, b'%PDF-'))

@mock_aws
class SystemTests(unittest.TestCase):
    def setUp(self):
        os.environ.update(AWS_DEFAULT_REGION='us-east-1', EMPLOYEES='employees', IDENTITIES='identities', ASSETS='assets',
            DOCUMENT_BUCKET='test-documents', SENDER='hr@example.com', HR_EMAIL='hr@example.com', PORTAL_URL='https://example.com', WORKFLOW='arn:aws:states:us-east-1:123456789012:stateMachine:test')
        db = boto3.client('dynamodb')
        for table, key in [('employees','employee_id'), ('identities','email_hash'), ('assets','asset_id')]:
            db.create_table(TableName=table, KeySchema=[{'AttributeName':key,'KeyType':'HASH'}], AttributeDefinitions=[{'AttributeName':key,'AttributeType':'S'}], BillingMode='PAY_PER_REQUEST')
        cognito=boto3.client('cognito-idp')
        os.environ['POOL']=cognito.create_user_pool(PoolName='test')['UserPool']['Id']
        cognito.create_group(UserPoolId=os.environ['POOL'], GroupName='Employees')
        os.environ['TOPIC']=boto3.client('sns').create_topic(Name='test')['TopicArn']
        s3=boto3.client('s3'); s3.create_bucket(Bucket='test-documents'); s3.put_bucket_versioning(Bucket='test-documents', VersioningConfiguration={'Status':'Enabled'})
        boto3.client('ses').verify_email_identity(EmailAddress='hr@example.com')
        import app
        self.app=importlib.reload(app)
        self.values=dict(name='Sample Hire', email='hire@example.com', department='Engineering', role='Developer', manager='Sample Manager', joining_date='2026-10-01', employment_type='full_time')
        self.employee=self.app.invite(self.values)
        self.id=self.employee['employee_id']
    def call(self,path,body=None,hr=False,actor=None):
        claims={'sub':'sub','cognito:username':actor or self.id}
        if hr: claims['cognito:groups']='HRAdmin'
        result=self.app.api({'requestContext':{'authorizer':{'claims':claims}},'path':path,'httpMethod':'GET' if body is None else 'POST','body':None if body is None else json.dumps(body)},None)
        return result['statusCode'],json.loads(result['body'])
    def accepted(self):
        self.app.update(self.id,'SET accepted_at = :at',{':at':self.app.now()})
    def test_retry_invitation_preserves_identity(self):
        again=self.app.invite(self.values)
        self.assertEqual(self.id,again['employee_id'])
        self.assertEqual(self.app.employees.scan()['Count'],1)
    def test_access_control(self):
        self.assertEqual(self.call('/employees/'+self.id, actor='different')[0],403)
        self.assertEqual(self.call('/employees')[0],403)
        self.assertEqual(self.call('/employees',self.values)[0],403)
        self.assertEqual(self.call('/employees/'+self.id+'/manager',{'confirmed':True})[0],403)
    def test_stage_order_cannot_be_skipped(self):
        self.accepted()
        self.assertEqual(self.call('/employees/'+self.id+'/policy',{'accepted':True,'version':'2026-01'})[0],409)
        self.assertEqual(self.call('/employees/'+self.id+'/it',{'asset_id':'A'},hr=True)[0],409)
    def test_private_tokens_are_not_exposed(self):
        self.app.update(self.id,'SET tokens = :tokens',{':tokens':{'documents':'secret'}})
        self.assertNotIn('tokens',self.call('/me')[1])
        self.assertNotIn('tokens',self.call('/employees',hr=True)[1]['items'][0])
    def upload(self,kind,body=b'%PDF-1.7 test'):
        status,signed=self.call('/employees/'+self.id+'/upload',{'kind':kind,'content_type':'application/pdf'})
        self.assertEqual(status,200)
        key=signed['fields']['key']
        obj=self.app.s3.put_object(Bucket='test-documents',Key=key,Body=body,ContentType='application/pdf')
        event={'detail':{'object':{'key':key,'version-id':obj['VersionId']}}}
        self.app.validate_upload(event,None)
        return event
    def test_full_journey(self):
        with patch.object(self.app.sfn,'start_execution',return_value={'executionArn':'execution'}):
            self.assertEqual(self.call('/employees/'+self.id+'/accept',{'accepted':True})[0],200)
        for kind in ('id_proof','degree_certificate','signed_offer'):
            self.upload(kind)
            self.assertEqual(self.call('/employees/'+self.id+'/verify',{'kind':kind,'decision':'verified'},hr=True)[0],200)
        self.assertEqual(self.call('/employees/'+self.id+'/it',{'asset_id':'LAP-001'},hr=True)[0],200)
        self.assertEqual(self.call('/employees/'+self.id+'/policy',{'accepted':True,'version':'2026-01'})[0],200)
        self.assertEqual(self.call('/employees/'+self.id+'/manager',{'confirmed':True},hr=True)[0],200)
        self.app.ready({'employee_id':self.id},None)
        result=self.call('/me')[1]
        self.assertEqual(result['progress'],100)
        self.assertEqual(result['status'],'ready')
        self.assertEqual(result['missing_documents'],[])
        with patch.object(self.app.sfn,'start_execution') as start:
            self.assertEqual(self.call('/employees/'+self.id+'/accept',{'accepted':True})[1]['status'],'ready')
            start.assert_not_called()
    def test_invalid_upload_rejected(self):
        self.accepted(); self.upload('id_proof',b'not really a PDF')
        self.assertEqual(self.app.get_employee(self.id)['documents']['id_proof']['status'],'rejected')
        self.assertEqual(self.call('/employees/'+self.id+'/verify',{'kind':'id_proof','decision':'verified'},hr=True)[0],409)
    def test_old_event_cannot_overwrite_replacement(self):
        self.accepted(); old=self.upload('id_proof')
        self.upload('id_proof',b'%PDF-1.7 new version')
        latest=self.app.get_employee(self.id)['documents']['id_proof']
        self.app.validate_upload(old,None)
        self.assertEqual(self.app.get_employee(self.id)['documents']['id_proof'],latest)
    def test_verified_document_cannot_be_replaced(self):
        self.accepted(); self.upload('id_proof')
        self.call('/employees/'+self.id+'/verify',{'kind':'id_proof','decision':'verified'},hr=True)
        self.assertEqual(self.call('/employees/'+self.id+'/upload',{'kind':'id_proof','content_type':'application/pdf'})[0],409)
    def test_equipment_is_exclusive(self):
        self.accepted(); self.app.finish(self.id,'documents','HR')
        self.app.assets.put_item(Item={'asset_id':'TAKEN','employee_id':'another'})
        self.assertEqual(self.call('/employees/'+self.id+'/it',{'asset_id':'TAKEN'},hr=True)[0],409)
        self.assertEqual(self.call('/employees/'+self.id+'/it',{'asset_id':'FREE'},hr=True)[0],200)
        self.assertEqual(self.call('/employees/'+self.id+'/it',{'asset_id':'OTHER'},hr=True)[0],409)
    def test_callback_registration_handles_already_complete(self):
        self.accepted(); self.app.finish(self.id,'documents','HR')
        with patch.object(self.app.sfn,'send_task_success') as callback:
            self.app.stage({'employee_id':self.id,'stage':'documents','token':'token'},None)
            callback.assert_called_once()
    def test_reminder_on_reentry(self):
        self.accepted()
        with patch.object(self.app,'email') as mail:
            self.app.stage({'employee_id':self.id,'stage':'documents','token':'a'},None)
            self.assertTrue(mail.call_args.args[1].startswith('Next step:'))
            self.app.stage({'employee_id':self.id,'stage':'documents','token':'b'},None)
            subjects=[call.args[1] for call in mail.call_args_list]
            self.assertIn('Reminder: documents',subjects)

if __name__=='__main__': unittest.main()
