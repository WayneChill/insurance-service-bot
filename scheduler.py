"""
scheduler.py ── APScheduler 排程
  每日 08:00（台灣時間，UTC+8 = UTC 00:00）
  推送每日早報（文字訊息 1 則）
"""
import json
import urllib.request
import os
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from excel_reader import (
    get_life_daily_stats,
    get_property_daily_stats,
)


# ── 每日早報文字 ──────────────────────────────────────────

def _build_morning_report(db) -> str:
    """組合每日早報文字，db = SheetsDB 實例"""
    today = datetime.now().strftime("%m/%d")

    # 保服區
    case_counts = db.count_cases_by_status()

    # 業務區
    biz_counts = db.count_biz_by_stage()

    # 增員區
    recruit_counts = db.count_recruit_by_stage()

    # 產險區（需要 42004.xlsx）
    prop_statuses = db.get_property_status()
    prop_counts   = get_property_daily_stats(prop_statuses)

    # 壽險區（需要 42003.xlsx）
    life_stats = get_life_daily_stats()

    lines = [
        f"主人早安！{today} 今日待辦如下：",
        "",
        "🚨 產險區",
        f"▪️ 急件：{prop_counts['urgent']} 組",
        f"▪️ 追蹤：{prop_counts['track']} 組",
        f"▪️ 新件：{prop_counts['new']} 組",
        f"▪️ 延後：{prop_counts['delay']} 組",
        "",
        "🎂 壽險區",
        f"▪️ 當日壽星：{life_stats['birthday_count']} 位",
        f"▪️ 保單周年：{life_stats['anniversary_count']} 組",
        "",
        "📋 保服區",
        f"▪️ 待處理：{case_counts.get('待處理', 0)} 件",
        f"▪️ 已聯絡：{case_counts.get('已聯絡', 0)} 件",
        f"▪️ 已送出：{case_counts.get('已送出', 0)} 件",
        f"▪️ 核對中：{case_counts.get('核對中', 0)} 件",
        "",
        "💼 銷售區",
        f"▪️ 已聯繫：{biz_counts.get('已聯繫', 0)} 組",
        f"▪️ 建議書：{biz_counts.get('建議書', 0)} 組",
        f"▪️ 約簽約：{biz_counts.get('約簽約', 0)} 組",
        "",
        "👥 增員區",
        f"▪️ 已聯繫：{recruit_counts.get('已聯繫', 0)} 組",
        f"▪️ 約聊聊：{recruit_counts.get('約聊聊', 0)} 組",
        f"▪️ 約報聘：{recruit_counts.get('約報聘', 0)} 組",
    ]
    return "\n".join(lines)


# ── LINE Push 工具 ────────────────────────────────────────

def _push_text(token: str, user_id: str, text: str):
    url     = "https://api.line.me/v2/bot/message/push"
    headers = {"Content-Type": "application/json", "Authorization": "Bearer " + token}
    body    = json.dumps({"to": user_id, "messages": [{"type": "text", "text": text}]}).encode("utf-8")
    req     = urllib.request.Request(url, data=body, headers=headers, method="POST")
    urllib.request.urlopen(req)


# ── 主排程任務 ────────────────────────────────────────────

def run_daily(db):
    """每日 08:00 台灣時間執行：只推每日早報"""
    print(f"[排程] 開始每日任務 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    token   = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    user_id = os.environ.get("LINE_USER_ID", "")

    if not token or not user_id:
        print("[排程] 缺少 LINE_CHANNEL_ACCESS_TOKEN 或 LINE_USER_ID，跳過")
        return

    try:
        report = _build_morning_report(db)
        _push_text(token, user_id, report)
        print("[排程] 每日早報發送成功")
    except Exception as e:
        import traceback
        print(f"[排程] 早報發送失敗：{e}")
        traceback.print_exc()


# ── 啟動排程 ──────────────────────────────────────────────

def start_scheduler(db):
    """在 app 啟動時呼叫，傳入 SheetsDB 實例"""
    scheduler = BackgroundScheduler(timezone="UTC")
    # UTC 00:00 = 台灣時間 08:00
    scheduler.add_job(run_daily, "cron", hour=0, minute=0, args=[db])
    scheduler.start()
    print("[排程] APScheduler 已啟動，每日 UTC 00:00 執行")
    return scheduler
