import os
import io
import json
import base64
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from openpyxl import load_workbook

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]
DRIVE_FOLDER = '\u4fdd\u670d\u8cc7\u6599'
LIFE_FILE = '42003.xlsx'
PROPERTY_FILE = '42004.xlsx'

def _clean_policy(policy, start_date):
    if not policy or not start_date or len(start_date) < 3:
        return policy
    year = start_date[:3]
    for y in [year, str(int(year) + 1)]:
        idx = policy.find(y)
        if idx > 0:
            return policy[:idx]
    return policy


def get_creds():
    b64 = os.environ.get('GOOGLE_CREDENTIALS_B64', '')
    if b64:
        creds_dict = json.loads(base64.b64decode(b64).decode('utf-8'))
    else:
        with open(os.environ.get('GOOGLE_CREDENTIALS_FILE', 'credentials.json'), encoding='utf-8') as f:
            creds_dict = json.load(f)
    return Credentials.from_service_account_info(creds_dict, scopes=SCOPES)


def download_excel(filename):
    creds = get_creds()
    drive = build('drive', 'v3', credentials=creds, cache_discovery=False)
    folder_res = drive.files().list(
        q="name='" + DRIVE_FOLDER + "' and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields='files(id)'
    ).execute()
    folders = folder_res.get('files', [])
    if not folders:
        raise RuntimeError('\u627e\u4e0d\u5230\u8cc7\u6599\u593e\u300c' + DRIVE_FOLDER + '\u300d')
    folder_id = folders[0]['id']
    file_res = drive.files().list(
        q="name='" + filename + "' and '" + folder_id + "' in parents and trashed=false",
        fields='files(id)',
        pageSize=1
    ).execute()
    files = file_res.get('files', [])
    if not files:
        raise RuntimeError('\u627e\u4e0d\u5230 ' + filename)
    req = drive.files().get_media(fileId=files[0]['id'])
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, req)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    buf.seek(0)
    return buf


def safe_str(val, default=''):
    if val is None:
        return default
    if isinstance(val, float):
        return str(int(val))
    if isinstance(val, int):
        return str(val)
    return str(val).strip().replace('\n', '')


def safe_get(row, idx, default=''):
    try:
        return safe_str(row[idx], default)
    except (IndexError, TypeError):
        return default


    m = _POLICY_SUFFIX.search(policy_num)
    return policy_num[:m.start()] if m else policy_num


def parse_life_excel(buf, name):
    wb = load_workbook(buf, read_only=True)
    ws = wb.active
    results = {}
    for i, row in enumerate(ws.iter_rows(values_only=True), 1):
        if i < 8:
            continue
        if not row or len(row) < 25:
            continue
        policy_raw = safe_get(row, 0)
        if not policy_raw or policy_raw.startswith('\u9644\u7d04') or policy_raw == '\u4fdd\u55ae\u865f\u78bc':
            continue
        insured = safe_get(row, 21)
        applicant = safe_get(row, 19)
        if name not in [insured, applicant]:
            continue
        key = insured if insured else applicant
        policy_num = _clean_policy(policy_raw, safe_get(row, 10))
        if not policy_num:
            continue
        if key not in results:
            idno_raw = safe_get(row, 23)
            idno = idno_raw[:10] if len(idno_raw) >= 10 else idno_raw
            results[key] = {
                'name': key,
                'applicant': applicant if applicant != key else '',
                'idno': idno,
                'tel': safe_get(row, 34),
                'addr': safe_get(row, 36),
                'policies': []
            }
        existing = {p['policy_num'] for p in results[key]['policies']}
        if policy_num not in existing:
            results[key]['policies'].append({
                'type': '\u58fd\u9669',
                'company': safe_get(row, 2),
                'policy_num': policy_num,
                'product': safe_get(row, 7),
                'status': safe_get(row, 32)
            })
    return list(results.values())


def parse_property_excel(buf, name):
    wb = load_workbook(buf, read_only=True)
    ws = wb.active
    results = {}
    for i, row in enumerate(ws.iter_rows(values_only=True), 1):
        if i < 5:
            continue
        if not row or len(row) < 20:
            continue
        policy_raw = safe_get(row, 1)
        if not policy_raw or len(policy_raw) < 5:
            continue
        company = safe_get(row, 3)
        if not company or company == '\u9669\u7a2e\u4ee3\u865f':
            continue
        insured = safe_get(row, 10)
        applicant = safe_get(row, 9)
        if name not in [insured, applicant]:
            continue
        key = insured if insured else applicant
        policy_num = _clean_policy(policy_raw, safe_get(row, 18))
        if not policy_num:
            continue
        if key not in results:
            results[key] = {
                'name': key,
                'applicant': applicant if applicant != key else '',
                'idno': safe_get(row, 11)[:10],
                'tel': safe_get(row, 23),
                'addr': safe_get(row, 25),
                'policies': []
            }
        existing = {p['policy_num'] for p in results[key]['policies']}
        if policy_num not in existing:
            results[key]['policies'].append({
                'type': '\u7522\u9669',
                'company': company,
                'policy_num': policy_num,
                'product': safe_get(row, 16),
                'status': safe_get(row, 21)
            })
    return list(results.values())


def search_client(name):
    combined = {}

    try:
        life_buf = download_excel(LIFE_FILE)
        for r in parse_life_excel(life_buf, name):
            k = r['name']
            if k not in combined:
                combined[k] = r
            else:
                existing = {p['policy_num'] for p in combined[k]['policies']}
                for p in r['policies']:
                    if p['policy_num'] not in existing:
                        combined[k]['policies'].append(p)
        print('Life OK', flush=True)
    except Exception as e:
        print('[WARN] \u58fd\u9669: ' + str(e), flush=True)

    try:
        prop_buf = download_excel(PROPERTY_FILE)
        for r in parse_property_excel(prop_buf, name):
            k = r['name']
            if k not in combined:
                combined[k] = r
            else:
                existing = {p['policy_num'] for p in combined[k]['policies']}
                for p in r['policies']:
                    if p['policy_num'] not in existing:
                        combined[k]['policies'].append(p)
        print('Property OK', flush=True)
    except Exception as e:
        print('[WARN] \u7522\u9669: ' + str(e), flush=True)

    return list(combined.values())
