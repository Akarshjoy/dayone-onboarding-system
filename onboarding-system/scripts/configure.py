import argparse
import json
from pathlib import Path
import boto3

parser = argparse.ArgumentParser(description='Write frontend configuration from CloudFormation stack outputs.')
parser.add_argument('--stack', default='dayone-onboarding')
parser.add_argument('--region', default='us-east-1')
args = parser.parse_args()
outputs = boto3.client('cloudformation', region_name=args.region).describe_stacks(StackName=args.stack)['Stacks'][0]['Outputs']
values = {o['OutputKey']: o['OutputValue'] for o in outputs}
config = {'apiUrl': values['ApiUrl'], 'clientId': values['ClientId'], 'region': values['Region']}
path = Path(__file__).resolve().parents[1] / 'frontend/config.js'
path.write_text('window.CONFIG = ' + json.dumps(config) + ';\n')
print('Wrote frontend/config.js')
print('Upload frontend/ to S3 bucket: ' + values['WebBucketName'])
print('Portal: ' + values['PortalUrl'])
print('User pool: ' + values['UserPoolId'])
