import os
import json
import base64
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]
SHEET_CASES = '\u4fdd\u670d\u6848\u4ef6'
SHEET_CARDS = '\u4fe1\u7528\u5361'


class CaseManager:
    def __init__(self):
        self.spreadsheet = self._connect()
        self._ensure_sheets()

    def _get_creds(self):
        b64 = os.environ.get('GOOGLE_CREDENTIALS_B64', '')
        if b64:
            creds_dict = json.loads(base64.b64decode(b64).decode('utf-8'))
        else:
            with open(os.environ.get('GOOGLE_CREDENTIALS_FILE', 'credentials.json'), encoding='utf-8') as f:
                creds_dict = json.load(f)
        return Credentials.from_service_account_info(creds_dict, scopes=SCOPES)

    def _connect(self):
        creds = self._get_creds()
        gc = gspread.authorize(creds)
        return gc.open_by_key(os.environ['GOOGLE_SHEET_ID'])

    def _ensure_sheets(self):
        existing = [ws.title for ws in self.spreadsheet.worksheets()]
        if SHEET_CASES not in existing:
            ws = self.spreadsheet.add_worksheet(SHEET_CASES, rows=1000, cols=10)
            ws.append_row(['\u6848\u4ef6ID', '\u5ba2\u6236\u59d3\u540d', '\u670d\u52d9\u9805\u76ee', '\u4fdd\u55ae\u865f\u78bc', '\u72c0\u614b', '\u5099\u8a3b', '\u5efa\u7acb\u6642\u9593', '\u66f4\u65b0\u6642\u9593'])
        if SHEET_CARDS not in existing:
            ws = self.spreadsheet.add_worksheet(SHEET_CARDS, rows=1000, cols=6)
            ws.append_row(['\u59d3\u540d', '\u9280\u884c\u540d', '\u5361\u865f\u524d4\u78bc', '\u6548\u671f', '\u5099\u8a3b\u4fdd\u55ae'])

    def _ws(self, name):
        return self.spreadsheet.worksheet(name)

    # ── 案件 ──
    def add_case(self, name, service_type, policy='', note=''):
        ws = self._ws(SHEET_CASES)
        records = ws.get_all_records()
        case_id = 'C' + str(len(records) + 1).zfill(3)
        now = datetime.now().strftime('%Y/%m/%d %H:%M')
        ws.append_row([case_id, name, service_type, policy, '\u5f85\u8655\u7406', note, now, now])
        return case_id

    def get_cases(self, name):
        ws = self._ws(SHEET_CASES)
        records = ws.get_all_records()
        return [r for r in records if r['\u5ba2\u6236\u59d3\u540d'] == name]

    def get_all_pending(self):
        ws = self._ws(SHEET_CASES)
        records = ws.get_all_records()
        return [r for r in records if r.get('\u72c0\u614b', '') in ['\u5f85\u8655\u7406', '\u5df2\u806f\u7d61', '\u5df2\u9001\u51fa', '\u6838\u5c0d\u4e2d']]

    def update_status(self, case_id, status):
        ws = self._ws(SHEET_CASES)
        records = ws.get_all_records()
        for i, r in enumerate(records, start=2):
            if r['\u6848\u4ef6ID'] == case_id:
                ws.update_cell(i, 5, status)
                ws.update_cell(i, 8, datetime.now().strftime('%Y/%m/%d %H:%M'))
                return True
        return False

    # ── 信用卡 ──
    def add_card(self, name, bank, card_num, expiry, policy_note=''):
        ws = self._ws(SHEET_CARDS)
        ws.append_row([name, bank, card_num, expiry, policy_note])

    def get_cards(self, name):
        ws = self._ws(SHEET_CARDS)
        records = ws.get_all_records()
        return [r for r in records if r['\u59d3\u540d'] == name]

    def delete_card(self, name, bank, card_num):
        ws = self._ws(SHEET_CARDS)
        records = ws.get_all_records()
        for i, r in enumerate(records, start=2):
            if r['\u59d3\u540d'] == name and r['\u9280\u884c\u540d'] == bank and r['\u5361\u865f\u524d4\u78bc'] == card_num:
                ws.delete_rows(i)
                return True
        return False
