"""
scheduler.py ── APScheduler 排程
  每日 08:00（台灣時間，UTC+8 = UTC 00:00）
  推送每日早報（文字訊息 1 則）
"""
import json
import urllib.request
import os
import time
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


# ── LINE Push 工具 ────────────────────────────────────────

def _push_text(token: str, user_id: str, text: str):
    url     = "https://api.line.me/v2/bot/message/push"
    headers = {"Content-Type": "application/json", "Authorization": "Bearer " + token}
    body    = json.dumps({"to": user_id, "messages": [{"type": "text", "text": text}]}).encode("utf-8")
    req     = urllib.request.Request(url, data=body, headers=headers, method="POST")
    urllib.request.urlopen(req)


# ── 晚間待辦任務 ──────────────────────────────────────────
def run_evening(db):
    """每日 20:00 台灣時間執行：推送晚間待辦"""
    print(f"[排程] 開始晚間待辦 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    user_id = os.environ.get("LINE_USER_ID", "")
    if not token or not user_id:
        print("[排程] 缺少 LINE 設定，跳過")
        return

    try:
        today = datetime.now().strftime("%m/%d")
        lines = [f"🌙 {today} 晚間待辦提醒", ""]

        # 產險急件
        try:
            from excel_reader import get_property_daily_stats
            import pandas as pd
            from excel_reader import download_excel
            from datetime import datetime as _dt
            buf = download_excel("42004.xlsx")
            df = pd.read_excel(buf, header=3)
            df.columns = df.columns.str.strip()
            def _roc(v):
                try:
                    s = str(v).strip()
                    if len(s) == 7:
                        y, rest = int(s[:3]) + 1911, s[3:]
                        return pd.Timestamp(f"{y}-{rest[:2]}-{rest[4:]}")
                except Exception:
                    pass
                return pd.NaT
            df["到期日"] = df["保險迄日"].apply(_roc)
            today_ts = pd.Timestamp(_dt.today().date())
            df["剩餘天數"] = (df["到期日"] - today_ts).dt.days
            prop_statuses = db.get_property_status()
            skip = {"續保完成", "不續保"}
            urgent_rows = df[
                df["剩餘天數"].notna() &
                df["剩餘天數"].between(0, 10) &
                df["狀態"].astype(str).str.contains("正常")
            ]
            urgent_list = []
            for _, row in urgent_rows.iterrows():
                pid = str(row["保單號碼"]).strip()
                cur = prop_statuses.get(pid, {}).get("status", "")
                if cur not in skip:
                    name = str(row["被保姓名"]).strip().replace("\n", "")
                    urgent_list.append(f"  ■ {name} 倒數{int(row['剩餘天數'])}天")
            if urgent_list:
                lines.append(f"🚨 產險急件（{len(urgent_list)} 組）")
                for u in urgent_list[:5]:
                    lines.append(u)
                lines.append("")
        except Exception as e:
            import traceback
            print(f"[排程] 產險急件讀取失敗：{e}", flush=True)
            traceback.print_exc()

        # 新件追蹤
        newcase_list = [r for r in db.get_newcase_list() if r.get("階段") != "已完成"]
        if newcase_list:
            lines.append(f"📋 新件追蹤（{len(newcase_list)} 件）")
            for r in newcase_list:
                lines.append(f"  ■ {r.get('姓名','')} {r.get('保險公司','')} [{r.get('階段','')}]")
            lines.append("")

        # 保服未完成
        case_list = db.get_all_pending_cases()
        if case_list:
            lines.append(f"📄 保服未完成（{len(case_list)} 件）")
            for r in case_list:
                lines.append(f"  ■ {r.get('客戶姓名','')} {r.get('服務項目','')} [{r.get('狀態','')}]")
            lines.append("")

        # 扣款失敗
        payment_list = [r for r in db.get_payment_failures() if r.get("狀態") != "已完成"]
        if payment_list:
            lines.append(f"💳 扣款失敗（{len(payment_list)} 件）")
            for r in payment_list:
                lines.append(f"  ■ {r.get('要保人','')} {r.get('公司','')} [{r.get('類別','')}]")
            lines.append("")

        # 銷售待跟進
        biz_list = [r for r in db.get_biz_list() if r.get("階段") not in ["送保單", "已完成", "已結案"]]
        if biz_list:
            lines.append(f"💼 銷售待跟進（{len(biz_list)} 組）")
            for r in biz_list[:3]:
                lines.append(f"  ■ {r.get('姓名','')} [{r.get('階段','')}]")
            lines.append("")

        # 增員待跟進
        recruit_list = [r for r in db.get_recruit_list() if r.get("階段") not in ["約報聘", "已完成", "已結案"]]
        if recruit_list:
            lines.append(f"👥 準增待跟進（{len(recruit_list)} 組）")
            for r in recruit_list[:3]:
                lines.append(f"  ■ {r.get('姓名','')} [{r.get('階段','')}]")
        else:
            lines.append("👥 準增待跟進（0 組）")
            lines.append("  ■ 無待跟進")

        msg = "\n".join(lines)
        _push_text(token, user_id, msg)
        print("[排程] 晚間待辦發送成功")

    except Exception as e:
        import traceback
        print(f"[排程] 晚間待辦失敗：{e}")
        traceback.print_exc()
      
# ── 主排程任務 ────────────────────────────────────────────

def run_daily(db):
    """每日 08:00 台灣時間執行：只推每日早報"""
    print(f"[排程] 開始每日任務 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    token   = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    user_id = os.environ.get("LINE_USER_ID", "")

    if not token or not user_id:
        print("[排程] 缺少 LINE_CHANNEL_ACCESS_TOKEN 或 LINE_USER_ID，跳過")
        return

    report = None
    for attempt in range(1, 4):
        try:
            report = _build_morning_report(db)
            break
        except Exception as e:
            import traceback
            print(f"[排程] 早報建立失敗（第 {attempt} 次）：{e}")
            traceback.print_exc()
            if attempt < 3:
                time.sleep(30)
            else:
                print("[排程] 早報建立連續失敗 3 次，放棄發送")
                return

    try:
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
    scheduler.add_job(run_evening, "cron", hour=12, minute=0, args=[db])
    scheduler.start()
    print("[排程] APScheduler 已啟動，每日 UTC 00:00 執行")
    return scheduler
