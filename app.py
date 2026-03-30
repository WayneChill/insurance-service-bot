"""
app.py ── 保險發展小幫手 LINE Bot
合併：產險助手 + 保服助手
Railway 部署：insurance-service-bot 專案（主）
"""
import os
import json
from urllib.parse import unquote
from datetime import datetime
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    FlexSendMessage, PostbackEvent
)

# ── 讀取 config.txt（Railway 環境變數優先）────────────────
def _read_config():
    config = {}
    if os.path.exists("config.txt"):
        with open("config.txt", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    config[k.strip()] = v.strip()
    return config

_cfg = _read_config()
for _k, _v in _cfg.items():
    if _k not in os.environ:
        os.environ[_k] = _v

# 自用版，無需授權金鑰驗證

# ── 初始化 ────────────────────────────────────────────────
from sheets import SheetsDB
from excel_reader import search_client
from flex_message import (
    build_client_card, build_cases_card, build_case_created_card,
    build_biz_list_card, build_biz_single_card,
    build_newcase_list_card, build_newcase_single_card,
    build_help_message
)
from scheduler import start_scheduler

app      = Flask(__name__)
line_bot = LineBotApi(os.environ["LINE_CHANNEL_ACCESS_TOKEN"])
handler  = WebhookHandler(os.environ["LINE_CHANNEL_SECRET"])

# ── 對話暫存（單人 Bot 用記憶體狀態）────────────────────
_pending: dict = {}   # user_id → pending action name

# ── DB（啟動時背景初始化，確保排程器能準時執行）─────────
_db = None

def get_db():
    global _db
    if _db is None:
        print("[DB] 初始化 SheetsDB...", flush=True)
        _db = SheetsDB()
        print("[DB] 完成，啟動排程", flush=True)
        start_scheduler(_db)
    return _db

def _startup_init():
    import threading
    def _init():
        try:
            get_db()
            print("[DB] 啟動時初始化完成，排程器已啟動", flush=True)
        except Exception as e:
            print(f"[DB] 啟動時初始化失敗，將於收到訊息時重試: {e}", flush=True)
    threading.Thread(target=_init, daemon=True).start()

_startup_init()

# ── Webhook ───────────────────────────────────────────────
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body      = request.get_data(as_text=True)
    print("RECV", body[:80], flush=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return str(e), 500
    return "OK"

# ── 文字訊息處理 ──────────────────────────────────────────
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text    = event.message.text.strip()
    user_id = event.source.user_id

    # 對話暫存：先檢查是否在等待使用者補充資料
    # 若使用者輸入的是已知指令，取消等待直接執行
    _COMMANDS = {
        "查詢","進度","早報","待辦","產險","壽險","新契約","銷售","增員",
        "新增新件","新增銷售","新增增員","新增卡片","刪除卡片","新增保服",
        "記錄","更新銷售","更新準增","更新新件","指令","使用說明","保服",
    }
    first_word = text.split()[0] if text.split() else ""
    if first_word in _COMMANDS and _pending.get(user_id):
        del _pending[user_id]

    pending = _pending.get(user_id)
    if pending == "查詢":
        del _pending[user_id]
        name     = text.strip()
        clients  = search_client(name)
        if not clients:
            reply = _t(f"❌ 找不到「{name}」的資料\n請確認姓名是否正確")
        else:
            cards    = get_db().get_cards(name)
            contents = build_client_card(clients, name, cards)
            reply    = _f(f"客戶資料：{name}", contents)

    elif pending == "進度":
        del _pending[user_id]
        name     = text.strip()
        cases    = get_db().get_cases(name)
        contents = build_cases_card(name, cases)
        reply    = _f(f"保服進度：{name}", contents)

    elif pending == "新增新件":
        parts = text.split()
        if len(parts) >= 2:
            del _pending[user_id]
            name     = parts[0]
            company  = " ".join(parts[1:])
            stage    = "核保中"
            rid      = get_db().add_newcase(name, company, stage)
            contents = build_newcase_single_card(rid, name, company, stage)
            reply    = _f(f"已新增新件 {name}", contents)
        else:
            reply = _t("❌ 請輸入「姓名 保險公司」，例如：\n王小明 國泰人壽")

    elif pending == "新增銷售":
        parts = text.split()
        if len(parts) >= 1:
            del _pending[user_id]
            name     = parts[0]
            phone    = parts[1] if len(parts) >= 2 else ""
            stage    = "已聯繫"
            rid      = get_db().add_biz(name, phone, stage)
            contents = build_biz_single_card(rid, name, phone, stage, "💼 銷售追蹤")
            reply    = _f(f"已新增銷售 {name}", contents)
        else:
            reply = _t("❌ 請輸入姓名（電話可省略），例如：\n王小明 0912345678")

    elif pending == "新增增員":
        parts = text.split()
        if len(parts) >= 1:
            del _pending[user_id]
            name     = parts[0]
            phone    = parts[1] if len(parts) >= 2 else ""
            stage    = "已聯繫"
            rid      = get_db().add_recruit(name, phone, stage)
            contents = build_biz_single_card(rid, name, phone, stage, "👥 準增追蹤")
            reply    = _f(f"已新增增員 {name}", contents)
        else:
            reply = _t("❌ 請輸入姓名（電話可省略），例如：\n王小明 0912345678")

    elif pending == "新增保服":
        parts = text.split()
        if len(parts) >= 2:
            del _pending[user_id]
            name     = parts[0]
            service  = " ".join(parts[1:])
            case_id  = get_db().add_case(name, service)
            contents = build_case_created_card(case_id, name, service)
            reply    = _f(f"案件開立 {name}", contents)
        else:
            reply = _t("❌ 請輸入「姓名 服務項目」，例如：\n王小明 理賠")

    else:
        reply = _parse_command(text)
        if reply["type"] == "pending":
            _pending[user_id] = reply["action"]
            reply = _t(reply["text"])

    if reply["type"] == "flex":
        line_bot.reply_message(
            event.reply_token,
            FlexSendMessage(alt_text=reply["alt"], contents=reply["contents"])
        )
    else:
        line_bot.reply_message(
            event.reply_token,
            TextSendMessage(text=reply["text"])
        )

# ── Postback 處理 ─────────────────────────────────────────
@handler.add(PostbackEvent)
def handle_postback(event):
    data   = event.postback.data
    params = dict(p.split("=", 1) for p in data.split("&") if "=" in p)
    action = params.get("action", "")
    name   = unquote(params.get("name", ""))
    policy = unquote(params.get("policy", ""))

    # ── 保服案件開立（理賠/契變/保費變更）
    if action in ("理賠", "契變", "保費變更"):
        case_id  = get_db().add_case(name, action, policy)
        contents = build_case_created_card(case_id, name, action, policy)
        _reply_flex(event, f"案件開立 {name}", contents)

    # ── 保服案件狀態更新
    elif action == "update":
        case_id = unquote(params.get("id", ""))
        status  = unquote(params.get("status", ""))
        get_db().update_case_status(case_id, status)
        _reply_text(event, f"✅ 案件 #{case_id} 已更新為「{status}」")

    # ── 查看保服進度
    elif action == "check_cases":
        cases    = get_db().get_cases(name)
        contents = build_cases_card(name, cases)
        _reply_flex(event, f"保服進度：{name}", contents)

    # ── 產險 Postback（報價/延後/不續保/續保完成）
    elif action in ("quoted", "delay", "delay7", "cancel", "done"):
        policy_id = unquote(params.get("id", ""))
        pname     = unquote(params.get("name", "保戶"))
        _LABELS = {
            "quoted": "已報價", "delay": "延後3天", "delay7": "延後7天",
            "cancel": "不續保", "done":  "續保完成",
        }
        _REPLIES = {
            "quoted": f"📋 {pname} 已報價，等待客戶確認",
            "delay":  f"⏰ {pname} 已延後，將在3天後提醒",
            "delay7": f"🔄 {pname} 已延後，將在7天後提醒",
            "cancel": f"❌ {pname} 已標記為不續保",
            "done":   f"✅ {pname} 續保完成，已記錄",
        }
        label = _LABELS[action]
        get_db().write_property_status(policy_id, pname, label)
        _reply_text(event, _REPLIES[action])

    else:
        _reply_text(event, "未知操作")


# ── 指令解析 ──────────────────────────────────────────────

def _parse_command(text: str) -> dict:
    parts = text.split()
    cmd   = parts[0] if parts else ""

    # 查詢（無參數 → 對話模式）
    if cmd == "查詢" and len(parts) == 1:
        return {"type": "pending", "action": "查詢", "text": "🔍 請輸入要查詢的客戶姓名"}

    # 查詢 <姓名>
    elif cmd == "查詢" and len(parts) >= 2:
        name    = parts[1]
        clients = search_client(name)
        if not clients:
            return _t(f"❌ 找不到「{name}」的資料\n請確認姓名是否正確")
        cards    = get_db().get_cards(name)
        contents = build_client_card(clients, name, cards)
        return _f(f"客戶資料：{name}", contents)

    # 進度（無參數 → 對話模式）
    elif cmd == "進度" and len(parts) == 1:
        return {"type": "pending", "action": "進度", "text": "📋 請輸入要查看進度的客戶姓名"}

    # 進度 <姓名>
    elif cmd == "進度" and len(parts) >= 2:
        name     = parts[1]
        cases    = get_db().get_cases(name)
        contents = build_cases_card(name, cases)
        return _f(f"保服進度：{name}", contents)

    # 早報（手動觸發）
    elif cmd == "早報":
        try:
            from scheduler import _build_morning_report
            report = _build_morning_report(get_db())
            return _t(report)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return _t(f"❌ 早報錯誤：{e}")

    # 新增保服（無參數 → 對話模式）
    elif cmd == "新增保服" and len(parts) == 1:
        return {"type": "pending", "action": "新增保服",
                "text": "📋 新增保服案件\n請輸入「姓名 服務項目」\n例如：王小明 理賠"}

    # 保服（待處理案件列表）
    elif cmd == "保服":
        pending  = get_db().get_all_pending_cases()
        if not pending:
            return _t("✅ 目前沒有待處理的保服案件")
        contents = build_cases_card("保服案件", pending)
        return _f("保服案件", contents)
        
 # 待辦（今日彙整）
    elif cmd == "待辦":
        try:
            import pandas as pd
            from excel_reader import download_excel, get_life_daily_detail
            from datetime import datetime

            # 產險急件
            buf = download_excel("42004.xlsx")
            df  = pd.read_excel(buf, header=3)
            df.columns = df.columns.str.strip()
            df = df[df["保單號碼"].notna()]
            df = df[~df["保單號碼"].astype(str).str.contains("險種代號|附約")]
            def _roc(v):
                try:
                    s = str(int(v)).zfill(7)
                    return pd.Timestamp(int(s[0:3])+1911, int(s[3:5]), int(s[5:7]))
                except: return pd.NaT
            df["到期日"] = df["保險迄日"].apply(_roc)
            today = pd.Timestamp(datetime.today().date())
            df["剩餘天數"] = (df["到期日"] - today).dt.days
            urgent_df = df[
                df["剩餘天數"].notna() &
                df["剩餘天數"].between(0, 10) &
                df["狀態"].astype(str).str.contains("正常")
            ]
            statuses = get_db().get_property_status()
            skip = {"續保完成", "不續保"}
            urgent_list = []
            for _, row in urgent_df.iterrows():
                pid = str(row["保單號碼"]).strip()
                cur = statuses.get(pid, {}).get("status", "")
                if cur not in skip:
                    urgent_list.append(f"▪️ {row['被保姓名']} 倒數{int(row['剩餘天數'])}天")

            # 保服未完成
            cases = get_db().get_all_pending_cases()

            # 業務待跟進
            biz = [r for r in get_db().get_biz_list() if r.get("階段") in ["已聯繫", "建議書"]]

            # 增員待跟進
            recruit = [r for r in get_db().get_recruit_list() if r.get("階段") in ["已聯繫", "約聊聊"]]

            # 新件追蹤（核保中/照會中/發單中）
            newcases = [r for r in get_db().get_newcase_list() if r.get("階段") in ["核保中", "照會中", "發單中"]]

            lines = ["📌 今日待辦彙整", ""]
            lines.append(f"🚨 產險急件（{len(urgent_list)} 組）")
            for u in urgent_list[:5]:
                lines.append(u)
            if not urgent_list:
                lines.append("▪️ 無急件")

            lines.append("")
            lines.append(f"📋 保服未完成（{len(cases)} 件）")
            for c in cases[:5]:
                lines.append(f"▪️ {c.get('客戶姓名','')} {c.get('服務項目','')} [{c.get('狀態','')}]")
            if not cases:
                lines.append("▪️ 無待處理")

            lines.append("")
            lines.append(f"💼 銷售待跟進（{len(biz)} 組）")
            for b in biz[:5]:
                lines.append(f"▪️ {b.get('姓名','')} [{b.get('階段','')}]")
            if not biz:
                lines.append("▪️ 無待跟進")

            lines.append("")
            lines.append(f"👥 準增待跟進（{len(recruit)} 組）")
            for r in recruit[:5]:
                lines.append(f"▪️ {r.get('姓名','')} [{r.get('階段','')}]")
            if not recruit:
                lines.append("▪️ 無待跟進")

            lines.append("")
            lines.append(f"📄 新件追蹤（{len(newcases)} 件）")
            for n in newcases[:5]:
                lines.append(f"▪️ {n.get('姓名','')} {n.get('保險公司','')} [{n.get('階段','')}]")
            if not newcases:
                lines.append("▪️ 無進行中")

            return _t("\n".join(lines))
        except Exception as e:
            import traceback
            traceback.print_exc()
            return _t(f"❌ 待辦彙整錯誤：{e}")

    # 使用說明（連結）
    elif cmd == "使用說明":
        return _t("📖 詳細使用說明請點以下連結：\nhttps://insurance-service-bot-production.up.railway.app/guide")

    # 指令 / help
    elif cmd in ("指令", "help", "?"):
        pending  = get_db().get_all_pending_cases()
        contents = build_help_message(pending)
        return _f("指令說明", contents)

    # 產險（顯示到期卡片）
    elif cmd == "產險":
        try:
            import pandas as pd
            from excel_reader import download_excel
            from flex_message import build_property_card
            buf = download_excel("42004.xlsx")
            df  = pd.read_excel(buf, header=3)
            df.columns = df.columns.str.strip()
            df = df[df["保單號碼"].notna()]
            df = df[~df["保單號碼"].astype(str).str.contains("險種代號|附約")]
            df["被保姓名"] = df["被保姓名"].astype(str).str.strip()
            df["行動電話"] = df["行動電話"].apply(lambda x: "0" + str(int(x)) if pd.notna(x) else "")
            def _roc(v):
                try:
                    s = str(int(v)).zfill(7)
                    return pd.Timestamp(int(s[0:3]) + 1911, int(s[3:5]), int(s[5:7]))
                except Exception:
                    return pd.NaT
            df["到期日"]   = df["保險迄日"].apply(_roc)
            from datetime import datetime
            today          = pd.Timestamp(datetime.today().date())
            df["剩餘天數"] = (df["到期日"] - today).dt.days
            urgent = df[
                df["剩餘天數"].notna() &
                df["剩餘天數"].between(0, 60) &
                df["狀態"].astype(str).str.contains("正常")
            ].copy().sort_values("剩餘天數")
            if urgent.empty:
                return _t("✅ 目前沒有60天內到期的產險")
            statuses = get_db().get_property_status()
            skip = {"續保完成", "不續保"}
            cards = []
            for _, row in urgent.iterrows():
                pid = str(row["保單號碼"]).strip()
                cur = statuses.get(pid, {}).get("status")
                if cur in skip:
                    continue
                cards.append(build_property_card(row, cur))
            if not cards:
                return _t("✅ 所有產險已處理完畢")
            contents = {"type": "carousel", "contents": cards[:10]}
            return _f(f"產險到期，共 {len(cards)} 筆", contents)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return _t(f"❌ 產險查詢錯誤：{e}")

    # 壽險（顯示壽星 + 保單周年卡片）
    elif cmd == "壽險":
        try:
            from excel_reader import get_life_daily_detail
            from flex_message import build_life_detail_card
            detail   = get_life_daily_detail()
            contents = build_life_detail_card(detail)
            return _f("壽險提醒", contents)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return _t(f"❌ 壽險查詢錯誤：{e}")

    # 新契約（列表，已完成不顯示）
    elif cmd == "新契約":
        records  = [r for r in get_db().get_newcase_list() if r.get("階段") != "已完成"]
        contents = build_newcase_list_card(records)
        return _f("新件追蹤", contents)

    # 銷售（列表，已結案不顯示）
    elif cmd == "銷售":
        records  = [r for r in get_db().get_biz_list() if r.get("階段") != "已結案"]
        contents = build_biz_list_card(records, "💼 銷售追蹤")
        return _f("銷售追蹤", contents)

    # 增員（列表，已結案不顯示）
    elif cmd == "增員":
        records  = [r for r in get_db().get_recruit_list() if r.get("階段") != "已結案"]
        contents = build_biz_list_card(records, "👥 準增追蹤")
        return _f("準增追蹤", contents)

    # 新增新件（無參數 → 進入對話模式）
    elif cmd == "新增新件" and len(parts) == 1:
        return {"type": "pending", "action": "新增新件",
                "text": "📄 新增新件\n請輸入姓名和保險公司（空格分隔）\n例如：王小明 國泰人壽"}

    # 新增新件 <姓名> <保險公司>
    elif cmd == "新增新件" and len(parts) >= 3:
        name    = parts[1]
        company = parts[2]
        stage   = parts[3] if len(parts) >= 4 else "核保中"
        rid     = get_db().add_newcase(name, company, stage)
        contents = build_newcase_single_card(rid, name, company, stage)
        return _f(f"已新增新件 {name}", contents)

    # 更新新件 <ID> <階段>
    elif cmd == "更新新件" and len(parts) >= 3:
        rid   = parts[1]
        stage = parts[2]
        ok    = get_db().update_newcase_stage(rid, stage)
        return _t(f"✅ 新件 {rid} 已更新為「{stage}」" if ok else f"❌ 找不到新件 {rid}")

    # 新增銷售（無參數 → 對話模式）
    elif cmd == "新增銷售" and len(parts) == 1:
        return {"type": "pending", "action": "新增銷售",
                "text": "💼 新增銷售追蹤\n請輸入姓名和電話（空格分隔，電話可省略）\n例如：王小明 0912345678"}

    # 新增銷售 <姓名> <電話> <階段>
    elif cmd == "新增銷售" and len(parts) >= 2:
        name  = parts[1]
        phone = parts[2] if len(parts) >= 3 else ""
        stage = parts[3] if len(parts) >= 4 else "已聯繫"
        rid   = get_db().add_biz(name, phone, stage)
        contents = build_biz_single_card(rid, name, phone, stage, "💼 銷售追蹤")
        return _f(f"已新增銷售 {name}", contents)

    # 新增增員（無參數 → 對話模式）
    elif cmd == "新增增員" and len(parts) == 1:
        return {"type": "pending", "action": "新增增員",
                "text": "👥 新增準增追蹤\n請輸入姓名和電話（空格分隔，電話可省略）\n例如：王小明 0912345678"}

    # 新增增員 <姓名> <電話> <階段>
    elif cmd == "新增增員" and len(parts) >= 2:
        name  = parts[1]
        phone = parts[2] if len(parts) >= 3 else ""
        stage = parts[3] if len(parts) >= 4 else "已聯繫"
        rid   = get_db().add_recruit(name, phone, stage)
        contents = build_biz_single_card(rid, name, phone, stage, "👥 準增追蹤")
        return _f(f"已新增增員 {name}", contents)

    # 記錄 <ID> [內容]  例：記錄 B001 已約好下週見面
    elif cmd == "記錄" and len(parts) >= 2:
        rid = parts[1]
        if len(parts) >= 3:
            note   = " ".join(parts[2:])
            prefix = rid.upper()[0] if rid else ""
            if prefix == "B":
                name = get_db().update_biz_note(rid, note)
            elif prefix == "R":
                name = get_db().update_recruit_note(rid, note)
            elif prefix == "N":
                name = get_db().update_newcase_note(rid, note)
            elif prefix == "C":
                name = get_db().update_case_note(rid, note)
            else:
                name = ""
            return _t(f"✅ {rid} 備註已記錄：{note}" if name else f"❌ 找不到 {rid}")
        else:
            return _t(f"✏️ 請輸入備註內容：\n格式：記錄 {rid} [內容]\n例：記錄 {rid} 已約好下週三見面")

    # 更新銷售 <ID> <階段>  例：更新銷售 B001 建議書
    elif cmd == "更新銷售" and len(parts) >= 3:
        rid   = parts[1]
        stage = parts[2]
        ok    = get_db().update_biz_stage(rid, stage)
        return _t(f"✅ 銷售 {rid} 已更新為「{stage}」" if ok else f"❌ 找不到銷售 {rid}")

    # 更新準增 <ID> <階段>
    elif cmd == "更新準增" and len(parts) >= 3:
        rid   = parts[1]
        stage = parts[2]
        ok    = get_db().update_recruit_stage(rid, stage)
        return _t(f"✅ 準增 {rid} 已更新為「{stage}」" if ok else f"❌ 找不到準增 {rid}")

    # 新增卡片 <姓名> <銀行> <卡號前4碼> <效期> [保單號碼]
    elif cmd == "新增卡片" and len(parts) >= 5:
        c_name   = parts[1]
        c_bank   = parts[2]
        c_num    = parts[3]
        c_exp    = parts[4]
        c_policy = parts[5] if len(parts) >= 6 else ""
        get_db().add_card(c_name, c_bank, c_num, c_exp, c_policy)
        note = f"（指定保單：{c_policy}）" if c_policy else "（所有保單）"
        return _t(f"✅ 已新增信用卡\n姓名：{c_name}\n銀行：{c_bank}\n卡號：{c_num}\n效期：{c_exp}\n{note}")

    # 刪除卡片 <姓名> <銀行> <卡號前4碼>
    elif cmd == "刪除卡片" and len(parts) >= 4:
        c_name = parts[1]
        c_bank = parts[2]
        c_num  = parts[3]
        ok     = get_db().delete_card(c_name, c_bank, c_num)
        if ok:
            return _t(f"✅ 已刪除「{c_name}」{c_bank} {c_num} 的信用卡")
        return _t("❌ 找不到該信用卡")

    else:
        return _t("❓ 看不懂指令，輸入「指令」查看所有指令")


# ── 工具 ──────────────────────────────────────────────────

def _t(text: str) -> dict:
    return {"type": "text", "text": text}

def _f(alt: str, contents: dict) -> dict:
    return {"type": "flex", "alt": alt, "contents": contents}

def _reply_text(event, text: str):
    line_bot.reply_message(event.reply_token, TextSendMessage(text=text))

def _reply_flex(event, alt: str, contents: dict):
    line_bot.reply_message(event.reply_token, FlexSendMessage(alt_text=alt, contents=contents))


LICENSE_SHEET_ID = os.environ.get("LICENSE_SHEET_ID", "1EzQtm2Egg4A-5DIRB-o_F_eWzksEeEjL-3_SWZ3dHq8")

# ── 授權金鑰驗證端點 ──────────────────────────────────────
@app.route("/verify-key", methods=["POST"])
def verify_key():
    from flask import jsonify
    import gspread, base64, tempfile
    from datetime import datetime as _dt
    try:
        body           = request.get_json(force=True) or {}
        key            = body.get("key", "").strip()
        channel_secret = body.get("channel_secret", "").strip()
        if not key:
            return jsonify({"valid": False, "message": "未提供金鑰"}), 400

        b64 = os.environ.get("GOOGLE_CREDENTIALS_B64", "")
        if b64:
            info = json.loads(base64.b64decode(b64).decode("utf-8"))
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
                json.dump(info, f)
                tmp_path = f.name
            gc = gspread.service_account(filename=tmp_path)
            os.unlink(tmp_path)
        else:
            path = os.environ.get("GOOGLE_CREDENTIALS_FILE", "credentials.json")
            gc = gspread.service_account(filename=path)

        rows = gc.open_by_key(LICENSE_SHEET_ID).sheet1.get_all_values()
        for row in rows:
            if not row or row[0].strip() != key:
                continue
            # A=金鑰 B=用戶名稱 C=到期日 D=狀態 E=Channel Secret
            user   = row[1] if len(row) > 1 else ""
            expiry = row[2] if len(row) > 2 else ""
            status = row[3] if len(row) > 3 else ""
            secret = row[4].strip() if len(row) > 4 else ""

            if status != "啟用":
                return jsonify({"valid": False, "message": "金鑰已停用"})
            try:
                if _dt.strptime(expiry, "%Y/%m/%d") < _dt.today():
                    return jsonify({"valid": False, "message": "金鑰已過期"})
            except ValueError:
                pass
            if secret and channel_secret != secret:
                return jsonify({"valid": False, "message": "金鑰與帳號不符"})
            return jsonify({"valid": True, "user": user, "expiry": expiry})

        return jsonify({"valid": False, "message": "金鑰不存在"})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"valid": False, "message": f"驗證錯誤：{e}"}), 500


# ── 健康檢查 ──────────────────────────────────────────────
@app.route("/", methods=["GET"])
def index():
    return "保險發展小幫手 LINE Bot ✅"

@app.route("/guide", methods=["GET"])
def guide():
    with open("guide.html", encoding="utf-8") as f:
        return f.read(), 200, {"Content-Type": "text/html; charset=utf-8"}

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    """相容舊 insurance-bot 的 webhook 路徑"""
    if request.method == "GET":
        return "OK", 200
    return callback()


# ── 啟動 ──────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
