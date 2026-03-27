import os
import base64
import json
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# Google Sheets 工作表名稱
SHEET_CLIENTS  = "clients"   # 客戶基本資料
SHEET_POLICIES = "policies"  # 保單
SHEET_CASES    = "cases"     # 保服案件

class SheetsDB:
    def __init__(self):
        b64 = os.environ.get("GOOGLE_CREDENTIALS_B64")
        if b64:
            info = json.loads(base64.b64decode(b64).decode("utf-8"))
            creds = Credentials.from_service_account_info(info, scopes=SCOPES)
        else:
            creds = Credentials.from_service_account_file(
                os.environ["GOOGLE_CREDENTIALS_FILE"],
                scopes=SCOPES
            )
        gc = gspread.authorize(creds)
        self.spreadsheet = gc.open_by_key(os.environ["GOOGLE_SHEET_ID"])
        self._ensure_sheets()

    # ── 初始化工作表（首次使用自動建立表頭）──────────────────────
    def _ensure_sheets(self):
        existing = [ws.title for ws in self.spreadsheet.worksheets()]

        if SHEET_CLIENTS not in existing:
            ws = self.spreadsheet.add_worksheet(SHEET_CLIENTS, rows=1000, cols=10)
            ws.append_row(["姓名", "電話", "地址", "出生年月日", "身分證字號", "建立時間"])

        if SHEET_POLICIES not in existing:
            ws = self.spreadsheet.add_worksheet(SHEET_POLICIES, rows=1000, cols=10)
            ws.append_row(["客戶姓名", "保險公司", "保單號碼", "險種", "建立時間"])

        if SHEET_CASES not in existing:
            ws = self.spreadsheet.add_worksheet(SHEET_CASES, rows=1000, cols=10)
            ws.append_row(["案件ID", "客戶姓名", "服務項目", "備註", "狀態", "建立時間", "更新時間"])

    def _ws(self, name):
        return self.spreadsheet.worksheet(name)

    # ── 客戶 CRUD ─────────────────────────────────────────────
    def get_client(self, name: str) -> dict | None:
        ws = self._ws(SHEET_CLIENTS)
        records = ws.get_all_records()
        for r in records:
            if r["姓名"] == name:
                return r
        return None

    def add_client(self, name, phone, addr, dob, idno):
        ws = self._ws(SHEET_CLIENTS)
        ws.append_row([name, phone, addr, dob, idno, _now()])

    # ── 保單 CRUD ─────────────────────────────────────────────
    def get_policies(self, name: str) -> list[dict]:
        ws = self._ws(SHEET_POLICIES)
        records = ws.get_all_records()
        return [r for r in records if r["客戶姓名"] == name]

    def add_policy(self, name, company, policy_num, policy_type):
        ws = self._ws(SHEET_POLICIES)
        ws.append_row([name, company, policy_num, policy_type, _now()])

    # ── 案件 CRUD ─────────────────────────────────────────────
    def get_cases(self, name: str) -> list[dict]:
        ws = self._ws(SHEET_CASES)
        records = ws.get_all_records()
        return [r for r in records if r["客戶姓名"] == name]

    def add_case(self, name, service_type, note="") -> str:
        ws = self._ws(SHEET_CASES)
        records = ws.get_all_records()
        # 自動產生案件 ID（C001, C002...）
        case_id = f"C{len(records) + 1:03d}"
        ws.append_row([case_id, name, service_type, note, "待處理", _now(), _now()])
        return case_id

    def update_case_status(self, case_id: str, status: str) -> bool:
        ws = self._ws(SHEET_CASES)
        records = ws.get_all_records()
        for i, r in enumerate(records, start=2):  # 第1列是表頭，資料從第2列開始
            if r["案件ID"] == case_id:
                # 狀態在第5欄，更新時間在第7欄
                ws.update_cell(i, 5, status)
                ws.update_cell(i, 7, _now())
                return True
        return False

def _now() -> str:
    return datetime.now().strftime("%Y/%m/%d %H:%M")
