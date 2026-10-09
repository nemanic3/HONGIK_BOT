"""Run only against an isolated test stack, with fictional accounts and generated files."""
import io
import json
import os
import time
import urllib.error
import urllib.request
import uuid

import pymupdf
from PIL import Image, ImageDraw, ImageFont


BASE = os.environ.get('HONGIK_TEST_BASE_URL', 'http://127.0.0.1:18082')
if not BASE.startswith('http://127.0.0.1:'):
    raise SystemExit('This smoke test is restricted to localhost test stacks.')
SECRET = os.environ['HONGIK_PROXY_SECRET']


def request(path, data=None, token=None, content_type='application/json', proxy=True, expected=200):
    headers = {'X-Forwarded-Proto': 'https'}
    if proxy:
        headers['X-Hongik-Proxy-Secret'] = SECRET
    if token:
        headers['Authorization'] = 'Bearer ' + token
    if data is not None:
        headers['Content-Type'] = content_type
        if not isinstance(data, bytes):
            data = json.dumps(data).encode()
    req = urllib.request.Request(BASE + path, data=data, headers=headers)
    try:
        response = urllib.request.urlopen(req, timeout=30)
    except urllib.error.HTTPError as exc:
        response = exc
    assert response.status == expected, (path, response.status, expected)
    assert 'no-store' in response.headers['Cache-Control'], path
    body = response.read()
    return json.loads(body) if body and 'application/json' in response.headers.get('Content-Type', '') else None


def signup(number):
    sid = f'T{number:06d}'
    request('/api/users/signup/', {'student_id': sid, 'full_name': '가상학생', 'password': 'Synthetic-smoke-only-2030!', 'major': '컴퓨터공학과', 'current_year': 2, 'admission_year': 2025, 'accreditation_track': 'non_accredited'}, expected=201)
    tokens = request('/api/users/login/', {'student_id': sid, 'password': 'Synthetic-smoke-only-2030!'})
    user = request('/api/users/me/', token=tokens['access'])
    request('/api/users/refresh/', {'refresh': tokens['refresh']})
    return user['id'], tokens['access'], tokens['refresh']


request('/api/health/', proxy=False, expected=403)
request('/api/users/me/', expected=401)
request('/media/synthetic.pdf', expected=404)
fixture_id = 800000 + int(uuid.uuid4().hex[:4], 16)
user, token, refresh = signup(fixture_id)
_, other, _ = signup(fixture_id + 1)

# No real transcript or student information is read.
image = Image.new('RGB', (1500, 500), 'white')
draw = ImageDraw.Draw(image)
font = ImageFont.truetype(os.environ.get('HONGIK_TEST_FONT', '/System/Library/Fonts/AppleSDGothicNeo.ttc'), 36)
draw.text((40, 40), '2030학년도 1학년 1학기', font=font, fill='black')
for y, values in [(150, ['학수번호', '과목명', '이수구분', '학점', '성적']), (250, ['009001', '가상과목', '전선', '3', 'A0'])]:
    for x, text in zip([40, 260, 750, 1050, 1250], values):
        draw.text((x, y), text, font=font, fill='black')
png = io.BytesIO()
image.save(png, format='PNG')
with pymupdf.open() as pdf:
    page = pdf.new_page()
    page.insert_text((40, 50), 'Semester: 2030-1')
    page.insert_text((40, 80), '001009 English 3 General A+ Required')
    pdf_data = pdf.tobytes()
boundary = 'hongik-synthetic-' + uuid.uuid4().hex
body = b''
for name, kind, content in [('synthetic-capture.png', 'image/png', png.getvalue()), ('synthetic-text.pdf', 'application/pdf', pdf_data)]:
    body += (f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="{name}"\r\nContent-Type: {kind}\r\n\r\n').encode() + content + b'\r\n'
body += f'--{boundary}--\r\n'.encode()
upload = request(f'/api/transcripts/{user}/', body, token, 'multipart/form-data; boundary=' + boundary, expected=201)
tid = upload['transcript_id']
for _ in range(90):
    detail = request(f'/api/transcripts/detail/{tid}/', token=token)
    if detail['status'] in ['done', 'error']:
        break
    time.sleep(1)
assert detail['status'] == 'done', 'Celery OCR did not finish successfully'
raw = detail['ocr_raw_data']['pages']
assert len(raw) == 2, 'Both uploaded sources must be extracted'
assert any('가상과목' in page.get('text', '') for page in raw), 'Real Korean PaddleOCR text missing'
assert any('English' in page.get('text', '') for page in raw), 'PDF embedded text missing'
preview = request(f'/api/transcripts/source/{tid}/1/', token=token)
assert preview['image'].startswith('data:image/jpeg;base64,')
request(f'/api/transcripts/detail/{tid}/', token=other, expected=404)
request(f'/api/transcripts/source/{tid}/1/', token=other, expected=404)
document = {'schema_version': 1, 'courses': [{'code': '009001', 'name': '가상과목', 'credit': 3, 'type': '전선', 'grade': 'A0', 'semester': '2030-1'}]}
request(f'/api/transcripts/confirm/{tid}/', document, token)
report = request(f'/api/analysis/report/?transcript_id={tid}', token=token)
assert report['transcript_id'] == tid
assert report['status'] == 'needs_verification'
assert len(report['courses']) == 1
request('/api/users/logout/', {'refresh': refresh}, token=token)
request('/api/users/refresh/', {'refresh': refresh}, expected=401)
print('PASS: signup, login, JWT refresh/revocation, async Korean image OCR + PDF, owner preview, foreign-owner denial, confirmation, graduation report, no-store, private media and proxy gate.')
