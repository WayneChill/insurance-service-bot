"""
sheets.py ── 統一 Google Sheets 存取層
工作表：
  保服案件    – 保服追蹤（原保服助手）
  信用卡      – 信用卡資料（原保服助手）
  業務追蹤    – 業務開發各階段（新）
  增員追蹤    – 增員各階段（新）
"""
import os
import json
import base64
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# 工作表名稱常數
WS_CASES   = "保服案件"
WS_CARDS   = "信用卡"
WS_BIZ     = "業務追蹤"
WS_RECRUIT = "增員追蹤"

# 業務 / 增員各階段
BIZ_STAGES     = ["已聯繫", "建議書", "約簽約", "送保單"]
RECRUIT_STAGES = ["已聯繫", "約聊聊", "約簽約"]


def _now() -> str:
    return datetime.now().strftime("%Y/%m/%d %H:%M")


def _get_creds():
    b64 = os.environ.get("GOOGLE_CREDENTIALS_B64", "")
    if b64:
        info = json.loads(base64.b64decode(b64).decode("utf-8"))
    else:
        path = os.environ.get("GOOGLE_CREDENTIALS_FILE", "credentials.json")
        with open(path, encoding="utf-8") as f:
            info = json.load(f)
    return Credentials.from_service_account_info(info, scopes=SCOPES)


class SheetsDB:
    """單例式 Google Sheets 連線（app 啟動時初始化一次）"""

    def __init__(self):
        print("[DB] 開始連線 Google Sheets...", flush=True)
        creds = _get_creds()
        print("[DB] 憑證取得成功", flush=True)
        b64 = os.environ.get("GOOGLE_CREDENTIALS_B64", "")
        if b64:
            import tempfile
            info2 = json.loads(base64.b64decode(b64).decode("utf-8"))
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
                json.dump(info2, f)
                tmp_path = f.name
            gc = gspread.service_account(filename=tmp_path)
            os.unlink(tmp_path)
        else:
            path = os.environ.get("GOOGLE_CREDENTIALS_FILE", "credentials.json")
            gc = gspread.service_account(filename=path)
        print(f"[DB] 嘗試開啟 GOOGLE_SHEET_ID: {os.environ.get('GOOGLE_SHEET_ID','未設定')}", flush=True)
        self.spreadsheet = gc.open_by_key(os.environ["GOOGLE_SHEET_ID"])
        print("[DB] Sheets 連線成功", flush=True)
        self._ensure_sheets()
        print("[DB] 工作表初始化完成", flush=True)

    # ── 初始化工作表 ───────────────────────────────────────────
    def _ensure_sheets(self):
        existing = [ws.title for ws in self.spreadsheet.worksheets()]

        if WS_CASES not in existing:
            ws = self.spreadsheet.add_worksheet(WS_CASES, rows=1000, cols=10)
            ws.append_row(["案件ID", "客戶姓名", "服務項目", "保單號碼", "狀態", "備註", "建立時間", "更新時間"])

        if WS_CARDS not in existing:
            ws = self.spreadsheet.add_worksheet(WS_CARDS, rows=1000, cols=6)
            ws.append_row(["姓名", "銀行名", "卡號前4碼", "效期", "備註保單"])

        if WS_BIZ not in existing:
            ws = self.spreadsheet.add_worksheet(WS_BIZ, rows=1000, cols=8)
            ws.append_row(["ID", "姓名", "電話", "階段", "備註", "建立時間", "更新時間"])

        if WS_RECRUIT not in existing:
            ws = self.spreadsheet.add_worksheet(WS_RECRUIT, rows=1000, cols=8)
            ws.append_row(["ID", "姓名", "電話", "階段", "備註", "建立時間", "更新時間"])

    def _ws(self, name):
        return self.spreadsheet.worksheet(name)

    # ══════════════════════════════════════════════════════════
    # 保服案件
    # ══════════════════════════════════════════════════════════
    def add_case(self, name: str, service_type: str, policy: str = "", note: str = "") -> str:
        ws = self._ws(WS_CASES)
        records = ws.get_all_records()
        case_id = "C" + str(len(records) + 1).zfill(3)
        ws.append_row([case_id, name, service_type, policy, "待處理", note, _now(), _now()])
        return case_id

    def get_cases(self, name: str) -> list:
        ws = self._ws(WS_CASES)
        return [r for r in ws.get_all_records() if r.get("客戶姓名") == name]

    def get_all_pending_cases(self) -> list:
        ws = self._ws(WS_CASES)
        pending_statuses = {"待處理", "已聯絡", "已送出", "核對中"}
        return [r for r in ws.get_all_records() if r.get("狀態", "") in pending_statuses]

    def update_case_status(self, case_id: str, status: str) -> bool:
        ws = self._ws(WS_CASES)
        for i, r in enumerate(ws.get_all_records(), start=2):
            if r.get("案件ID") == case_id:
                ws.update_cell(i, 5, status)   # 狀態
                ws.update_cell(i, 8, _now())   # 更新時間
                return True
        return False

    def count_cases_by_status(self) -> dict:
        """回傳每日早報用的保服統計"""
        ws = self._ws(WS_CASES)
        counts = {"待處理": 0, "已聯絡": 0, "已送出": 0, "核對中": 0}
        for r in ws.get_all_records():
            s = r.get("狀態", "")
            if s in counts:
                counts[s] += 1
        return counts

    # ══════════════════════════════════════════════════════════
    # 信用卡
    # ══════════════════════════════════════════════════════════
    def add_card(self, name: str, bank: str, card_num: str, expiry: str, policy_note: str = ""):
        self._ws(WS_CARDS).append_row([name, bank, card_num, expiry, policy_note])

    def get_cards(self, name: str) -> list:
        return [r for r in self._ws(WS_CARDS).get_all_records() if r.get("姓名") == name]

    def delete_card(self, name: str, bank: str, card_num: str) -> bool:
        ws = self._ws(WS_CARDS)
        for i, r in enumerate(ws.get_all_records(), start=2):
            if r.get("姓名") == name and r.get("銀行名") == bank and r.get("卡號前4碼") == card_num:
                ws.delete_rows(i)
                return True
        return False

    # ══════════════════════════════════════════════════════════
    # 業務追蹤
    # ══════════════════════════════════════════════════════════
    def add_biz(self, name: str, phone: str = "", stage: str = "已聯繫", note: str = "") -> str:
        ws = self._ws(WS_BIZ)
        records = ws.get_all_records()
        rid = "B" + str(len(records) + 1).zfill(3)
        ws.append_row([rid, name, phone, stage, note, _now(), _now()])
        return rid

    def get_biz_list(self) -> list:
        return self._ws(WS_BIZ).get_all_records()

    def update_biz_stage(self, rid: str, stage: str) -> bool:
        ws = self._ws(WS_BIZ)
        for i, r in enumerate(ws.get_all_records(), start=2):
            if r.get("ID") == rid:
                ws.update_cell(i, 4, stage)
                ws.update_cell(i, 7, _now())
                return True
        return False

    def update_biz_note(self, rid: str, note: str) -> str:
        """更新業務備註，回傳姓名（找不到回傳空字串）"""
        ws = self._ws(WS_BIZ)
        for i, r in enumerate(ws.get_all_records(), start=2):
            if r.get("ID") == rid:
                ws.update_cell(i, 5, note)
                ws.update_cell(i, 7, _now())
                return r.get("姓名", "")
        return ""

    def count_biz_by_stage(self) -> dict:
        counts = {s: 0 for s in BIZ_STAGES}
        for r in self._ws(WS_BIZ).get_all_records():
            s = r.get("階段", "")
            if s in counts:
                counts[s] += 1
        return counts

    # ══════════════════════════════════════════════════════════
    # 增員追蹤
    # ══════════════════════════════════════════════════════════
    def add_recruit(self, name: str, phone: str = "", stage: str = "已聯繫", note: str = "") -> str:
        ws = self._ws(WS_RECRUIT)
        records = ws.get_all_records()
        rid = "R" + str(len(records) + 1).zfill(3)
        ws.append_row([rid, name, phone, stage, note, _now(), _now()])
        return rid

    def get_recruit_list(self) -> list:
        return self._ws(WS_RECRUIT).get_all_records()

    def update_recruit_stage(self, rid: str, stage: str) -> bool:
        ws = self._ws(WS_RECRUIT)
        for i, r in enumerate(ws.get_all_records(), start=2):
            if r.get("ID") == rid:
                ws.update_cell(i, 4, stage)
                ws.update_cell(i, 7, _now())
                return True
        return False

    def update_recruit_note(self, rid: str, note: str) -> str:
        """更新增員備註，回傳姓名（找不到回傳空字串）"""
        ws = self._ws(WS_RECRUIT)
        for i, r in enumerate(ws.get_all_records(), start=2):
            if r.get("ID") == rid:
                ws.update_cell(i, 5, note)
                ws.update_cell(i, 7, _now())
                return r.get("姓名", "")
        return ""

    def count_recruit_by_stage(self) -> dict:
        counts = {s: 0 for s in RECRUIT_STAGES}
        for r in self._ws(WS_RECRUIT).get_all_records():
            s = r.get("階段", "")
            if s in counts:
                counts[s] += 1
        return counts

    # ══════════════════════════════════════════════════════════
    # 產險狀態（原 insurance-bot 的 SPREADSHEET_ID 同一份 Sheets）
    # ══════════════════════════════════════════════════════════
    def get_property_status(self) -> dict:
        """讀取第一個工作表（產險聯絡狀態）"""
        try:
            ws = self.spreadsheet.sheet1
            return {
                str(r.get("保單號碼", "")): {"status": r.get("狀態", ""), "name": r.get("姓名", "")}
                for r in ws.get_all_records() if r.get("保單號碼")
            }
        except Exception as e:
            print(f"[WARN] 產險狀態讀取失敗: {e}")
            return {}

    def write_property_status(self, policy_id: str, name: str, label: str):
        ws = self.spreadsheet.sheet1
        cells = ws.findall(policy_id, in_column=1)
        row_data = [policy_id, name, label, _now()]
        if cells:
            r = cells[0].row
            ws.update(f"A{r}:D{r}", [row_data])
        else:
            ws.append_row(row_data)
