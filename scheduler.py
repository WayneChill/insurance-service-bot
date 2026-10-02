"""
scheduler.py ── APScheduler 排程
  每日 08:00（台灣時間）同步產險續保，凌晨同步判決。
  早報、晚報自動推播已停用；保留手動查詢早報。
"""
import os
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from excel_reader import (
    get_life_daily_stats,
    get_property_daily_stats,
    get_property_renewal_rows,
)
from site_bridge import post_json


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

    # 新契約區
    newcase_counts = db.count_newcase_by_stage()

    # 保費區（扣款失敗各狀態統計）
    payment_failures = db.get_payment_failures()
    pay_pending  = sum(1 for r in payment_failures if r.get("狀態", "") == "待處理")
    pay_notified = sum(1 for r in payment_failures if r.get("狀態", "") == "已聯絡")
    pay_sent     = sum(1 for r in payment_failures if r.get("狀態", "") == "已送出")

    # 產險區（需要 42004.xlsx）
    prop_statuses = db.get_property_status()
    prop_counts   = get_property_daily_stats(prop_statuses)

    # 壽險區（需要 42003.xlsx）
    life_stats = get_life_daily_stats()

    # 行程區
    try:
        today_sched = db.get_today_schedule()
        week_sched  = db.get_week_schedule()
        month_sched = db.get_month_schedule()
        sched_today = len(today_sched)
        sched_week  = len(week_sched)
        sched_month = len(month_sched)
    except Exception:
        sched_today = sched_week = sched_month = 0

    lines = [
        f"主人早安！{today} 今日待辦如下：",
        "",
        "📅 行程區",
        f"▪️ 今日：{sched_today} 組",
        f"▪️ 本周：{sched_week} 組",
        f"▪️ 本月：{sched_month} 組",
        "",
        "🔔 壽險區",
        f"▪️ 當日壽星：{life_stats['birthday_count']} 位",
        f"▪️ 保單周年：{life_stats['anniversary_count']} 組",
        "",
        "🚨 產險區",
        f"▪️ 急件：{prop_counts['urgent']} 組",
        f"▪️ 追蹤：{prop_counts['track']} 組",
        f"▪️ 新件：{prop_counts['new']} 組",
        f"▪️ 延後：{prop_counts['delay']} 組",
        "",
        "📄 新件區",
        f"▪️ 核保中：{newcase_counts.get('核保中', 0)} 件",
        f"▪️ 照會中：{newcase_counts.get('照會中', 0)} 件",
        f"▪️ 發單中：{newcase_counts.get('發單中', 0)} 件",
        "",
        "📋 保服區",
        f"▪️ 已聯絡：{case_counts.get('已聯絡', 0)} 件",
        f"▪️ 已送出：{case_counts.get('已送出', 0)} 件",
        f"▪️ 核對中：{case_counts.get('核對中', 0)} 件",
        "",
        "💳 保費區",
        f"▪️ 待處理：{pay_pending} 件",
        f"▪️ 已聯絡：{pay_notified} 件",
        f"▪️ 已送出：{pay_sent} 件",
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


def _sync_property_renewals(db, line_user_id: str):
    secret = os.environ.get("LINE_BRIDGE_SECRET", "")
    site_base = os.environ.get(
        "SITE_BASE_URL", "https://claims-assistant.waynechiuchiu.chatgpt.site"
    ).rstrip("/")
    if not secret or not line_user_id:
        return
    rows = get_property_renewal_rows(db.get_property_status())
    status, data = post_json(
        f"{site_base}/api/renewals/import",
        secret,
        {"lineUserId": line_user_id, "rows": rows[:1000]},
        timeout=30,
    )
    if 200 <= status < 300 and data.get("ok") is True:
        print(f"[排程] 產險續保同步成功，共 {int(data.get('count', len(rows)))} 筆")
    else:
        print(f"[排程] 產險續保同步失敗，HTTP {status or 'network'}")


def _sync_judgments():
    """在司法院服務時段呼叫網站，由網站抓取官方每日異動。"""
    print(f"[排程] 開始判決同步 {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC", flush=True)
    secret = os.environ.get("JUDICIAL_SYNC_SECRET", "")
    site_base = os.environ.get(
        "SITE_BASE_URL", "https://claims-assistant.waynechiuchiu.chatgpt.site"
    ).rstrip("/")
    if not secret:
        print("[排程] 尚未設定 JUDICIAL_SYNC_SECRET，跳過判決同步", flush=True)
        return False
    utc_hour = datetime.utcnow().hour
    page = {16: 0, 18: 1, 20: 2}.get(utc_hour, 0)
    status, data = post_json(
        f"{site_base}/api/judgments/sync",
        secret,
        {"page": page},
        timeout=240,
    )
    if 200 <= status < 300 and data.get("ok") is True:
        print(
            f"[排程] 判決同步成功，第 {int(data.get('page', page)) + 1} 批、租戶 {int(data.get('tenants', 0))} 個、"
            f"清單 {int(data.get('listed', 0))} 筆、讀取 {int(data.get('fetched', 0))} 筆、"
            f"保險判決 {int(data.get('upserted', 0))} 筆、移除 {int(data.get('removed', 0))} 筆",
            flush=True,
        )
        return True
    else:
        reason = str(data.get("message") or data.get("error") or "未提供原因")[:160]
        print(f"[排程] 判決同步失敗，HTTP {status or 'network'}：{reason}", flush=True)
        return False


# ── 主排程任務 ────────────────────────────────────────────

def run_daily_sync(db):
    """每日 08:00 台灣時間同步產險續保，不發送 LINE 訊息。"""
    print(f"[排程] 開始每日資料同步 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    user_id = os.environ.get("LINE_USER_ID", "").strip()
    if not user_id:
        print("[排程] 缺少 LINE_USER_ID，跳過產險續保同步", flush=True)
        return
    try:
        _sync_property_renewals(db, user_id)
    except Exception as e:
        print(f"[排程] 產險續保同步失敗：{type(e).__name__}", flush=True)


# ── 啟動排程 ──────────────────────────────────────────────

def start_scheduler(db):
    """在 app 啟動時呼叫，傳入 SheetsDB 實例"""
    scheduler = BackgroundScheduler(timezone="UTC")
    # UTC 00:00 = 台灣時間 08:00
    scheduler.add_job(
        run_daily_sync,
        "cron",
        hour=0,
        minute=0,
        args=[db],
        id="property_renewal_sync",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=1800,
    )
    # 司法院 API 僅於台灣時間 00:00–06:00 開放。安排三次補跑，避免單一時間點漏執行。
    # UTC 16:10 / 18:10 / 20:10 = 台灣時間 00:10 / 02:10 / 04:10。
    scheduler.add_job(
        _sync_judgments,
        "cron",
        hour="16,18,20",
        minute=10,
        id="judgment_sync",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=1800,
    )
    scheduler.start()
    print("[排程] APScheduler 已啟動；早報與晚報自動推播已停用；產險續保每日台灣時間 08:00 同步；判決同步每日台灣時間 00:10、02:10、04:10 補跑", flush=True)
    return scheduler
