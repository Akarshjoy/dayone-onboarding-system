import re
from datetime import date

STAGES = ('documents', 'it', 'policy', 'manager')
DOCUMENTS = ('id_proof', 'degree_certificate', 'signed_offer')
TYPES = {'application/pdf': b'%PDF-', 'image/png': b'\x89PNG\r\n\x1a\n', 'image/jpeg': b'\xff\xd8\xff'}
MAX_BYTES = 5 * 1024 * 1024
POLICY_VERSION = '2026-01'

class RequestError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status

def require(condition, message, status=400):
    if not condition:
        raise RequestError(message, status)

def profile(data):
    fields = ('name', 'email', 'department', 'role', 'manager', 'joining_date', 'employment_type')
    out = {}
    for field in fields:
        value = data.get(field)
        require(isinstance(value, str) and 0 < len(value.strip()) <= 200, 'Invalid ' + field)
        out[field] = value.strip()
    out['email'] = out['email'].lower()
    require(bool(re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', out['email'])), 'Invalid email')
    require(bool(re.fullmatch(r'\d{4}-\d{2}-\d{2}', out['joining_date'])), 'joining_date must be YYYY-MM-DD')
    try:
        date.fromisoformat(out['joining_date'])
    except ValueError:
        raise RequestError('joining_date must be YYYY-MM-DD')
    require(out['employment_type'] in ('full_time', 'part_time', 'contract', 'intern'), 'Invalid employment type')
    return out

def valid_document(content_type, size, prefix):
    return content_type in TYPES and 0 < size <= MAX_BYTES and prefix.startswith(TYPES[content_type])

def require_stage(employee, stage):
    require(stage in STAGES, 'Unknown stage')
    require(employee.get('accepted_at'), 'Accept the offer first', 409)
    for earlier in STAGES[:STAGES.index(stage)]:
        require(employee['stages'][earlier]['status'] == 'complete', 'Complete earlier stages first', 409)

def public_employee(employee):
    out = {k: v for k, v in employee.items() if k not in ('tokens',)}
    out['progress'] = sum(v['status'] == 'complete' for v in employee['stages'].values()) * 25
    out['missing_documents'] = [k for k in DOCUMENTS if employee.get('documents', {}).get(k, {}).get('status') != 'verified']
    return out
