from pathlib import Path
from html import escape
root=Path(__file__).resolve().parents[1]
svg=['<svg xmlns="http://www.w3.org/2000/svg" width="1260" height="850" viewBox="0 0 1260 850">', '<rect width="1260" height="850" fill="#f4f7f5"/>', '<style>text{font-family:Arial,sans-serif;fill:#193b4e}.title{font-size:30px;font-weight:bold}.label{font-size:13px;fill:#658078}.head{font-size:17px;font-weight:bold;fill:white}.row{font-size:14px}</style>', '<text x="50" y="55" class="title">DayOne · employee identity and onboarding</text>', '<text x="50" y="84" class="label">Physical DynamoDB tables + embedded structures. Relationships enforced by application logic.</text>']
def line(x1,y1,x2,y2,label,x,y):
    svg.append(f'<path d="M{x1} {y1} L{x2} {y2}" fill="none" stroke="#8aa396" stroke-width="2"/>')
    svg.append(f'<text x="{x}" y="{y}" class="label">{escape(label)}</text>')
def box(x,y,w,title,rows):
    h=54+len(rows)*25
    svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9" fill="white" stroke="#ccdcd1"/>')
    svg.append(f'<path d="M{x+9} {y} H{x+w-9} Q{x+w} {y} {x+w} {y+9} V{y+42} H{x} V{y+9} Q{x} {y} {x+9} {y}" fill="#214a59"/>')
    svg.append(f'<text x="{x+16}" y="{y+27}" class="head">{escape(title)}</text>')
    for i,row in enumerate(rows): svg.append(f'<text x="{x+16}" y="{y+65+i*25}" class="row">{escape(row)}</text>')
line(335,195,460,195,'1 : 1',376,183)
line(790,195,915,195,'1 : 1',830,183)
line(790,400,915,400,'embeds 4',816,388)
line(625,573,625,635,'embeds up to 3',639,612)
line(335,475,460,475,'0..1 : 0..1',351,460)
box(50,135,285,'IDENTITIES · DynamoDB',['PK  email_hash','FK  employee_id'])
box(460,135,330,'EMPLOYEES · DynamoDB',['PK  employee_id (UUID)','name, email','department, role, manager','joining_date, employment_type','status, accepted_at','stages (map)','documents (map)','tokens (private map)','execution_arn','FK  asset_id','policy_version','ready_at, welcome_sent_at','created_at, updated_at'])
box(915,135,295,'COGNITO USER',['username = employee_id','sub (Cognito subject)','custom:employee_id','email'])
box(915,345,295,'STAGE · embedded map',['stage_name (map key)','status','completed_at','completed_by'])
box(50,405,285,'ASSETS · DynamoDB',['PK  asset_id','FK  employee_id (exclusive)','assigned_at'])
box(460,635,465,'DOCUMENT · embedded map',['kind (map key), status','S3 key + exact version_id','content_type, received_at','reviewed_by, reviewed_at'])
svg.append('<text x="50" y="810" class="label">Documents stored separately in private, encrypted, versioned S3.</text></svg>')
(root/'docs/schema.svg').write_text('\n'.join(svg))
