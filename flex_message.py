"""
flex_message.py ── 所有 LINE Flex Message 組裝函式
"""
from urllib.parse import quote

# ── 保服狀態顏色 / emoji ──────────────────────────────────
STATUS_COLOR = {
    "待處理": "#888780",
    "已聯絡": "#4DABF7",
    "已送出": "#FFD43B",
    "核對中": "#FF922B",
    "已完成": "#20C997",
}
STATUS_EMOJI = {
    "待處理": "⏰",
    "已聯絡": "📞",
    "已送出": "📤",
    "核對中": "🔍",
    "已完成": "✅",
}
UPDATE_BTNS   = ["已聯絡", "已送出", "核對中", "已完成"]
UPDATE_COLORS = ["#4DABF7", "#FFD43B", "#FF922B", "#20C997"]

# 產險狀態
PROP_STATUS_EMOJI = {"已報價": "📋", "延後3天": "⏰", "延後7天": "🔄", "續保完成": "✅", "不續保": "❌"}
PROP_STATUS_COLOR = {"已報價": "#3B82F6", "延後3天": "#F59E0B", "延後7天": "#F59E0B", "續保完成": "#10B981", "不續保": "#6B7280"}

TYPE_COLOR = {"壽險": "#4DABF7", "產險": "#FF6B6B"}


# ══════════════════════════════════════════════════════════
# 保服相關
# ══════════════════════════════════════════════════════════

def build_client_card(clients, search_name, cards=None):
    if not clients:
        return {"type": "bubble", "body": {"type": "box", "layout": "vertical", "contents": [
            {"type": "text", "text": "未找到資料", "color": "#888780"}
        ]}}
    if len(clients) == 1:
        return _single_bubble(clients[0], search_name, cards)
    return {"type": "carousel", "contents": [_single_bubble(c, search_name, cards) for c in clients[:10]]}


def _single_bubble(client, search_name, cards=None):
    name      = client["name"]
    applicant = client.get("applicant", "")
    policies  = [p for p in client.get("policies", []) if p.get("policy_num")]

    policy_rows = []
    for p in policies[:8]:
        color = TYPE_COLOR.get(p["type"], "#888780")
        policy_rows.append({
            "type": "box", "layout": "horizontal", "spacing": "sm", "margin": "sm",
            "contents": [
                {"type": "box", "layout": "vertical", "width": "36px",
                 "backgroundColor": color, "cornerRadius": "4px", "paddingAll": "4px",
                 "justifyContent": "center",
                 "contents": [{"type": "text", "text": p["type"], "size": "xxs",
                               "color": "#FFFFFF", "align": "center", "gravity": "center"}]},
                {"type": "box", "layout": "vertical", "flex": 1,
                 "contents": [
                     {"type": "text", "text": p["company"], "size": "sm", "weight": "bold", "color": "#2C2C2A"},
                     {"type": "text", "text": p["policy_num"], "size": "xs", "color": "#888780", "wrap": True},
                 ]},
            ]
        })

    if not policy_rows:
        policy_rows = [{"type": "text", "text": "尚無保單資料", "size": "sm", "color": "#888780"}]

    name_enc   = quote(search_name)
    policy_enc = quote(policies[0]["policy_num"]) if policies else ""

    info_rows = [
        _info_row("📞", "電話", client.get("tel", "") or "-"),
        _info_row("📍", "地址", client.get("addr", "") or "-"),
    ]
    if applicant:
        info_rows.append(_info_row("👤", "要保人", applicant))

    card_rows = []
    if cards:
        card_rows.append({"type": "separator", "margin": "sm"})
        card_rows.append({"type": "text", "text": "💳 信用卡", "size": "sm", "weight": "bold",
                          "color": "#0F6E56", "margin": "sm"})
        for cd in cards:
            bank  = str(cd.get("銀行名", "")).strip()
            num   = str(cd.get("卡號前4碼", "")).strip()
            exp   = str(cd.get("效期", "")).strip()
            note  = str(cd.get("備註保單", "")).strip()
            label = f"{bank} {num}  {exp}"
            label += f"  → {note}" if note else "  （所有保單）"
            card_rows.append({"type": "text", "text": label, "size": "xs", "color": "#5F5E5A", "wrap": True})

    body_contents = info_rows + [
        {"type": "separator", "margin": "sm"},
        {"type": "text", "text": f"保單（{len(policies)} 張）",
         "size": "sm", "weight": "bold", "color": "#0F6E56", "margin": "sm"},
    ] + policy_rows + card_rows

    return {
        "type": "bubble", "size": "kilo",
        "header": {
            "type": "box", "layout": "vertical", "paddingAll": "16px",
            "contents": [
                {"type": "text", "text": name, "weight": "bold", "size": "xl",
                 "color": "#2C2C2A", "align": "center"},
                {"type": "text", "text": client.get("idno", ""), "size": "xs",
                 "color": "#888780", "margin": "xs", "align": "center"},
            ]
        },
        "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": body_contents},
        "footer": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "contents": [
                {"type": "text", "text": "開立保服案件", "size": "xs", "color": "#888780", "align": "center"},
                {"type": "box", "layout": "horizontal", "spacing": "sm",
                 "contents": [
                     _postback_btn("理賠", f"action=理賠&name={name_enc}&policy={policy_enc}", "#FF6B6B"),
                     _postback_btn("契變", f"action=契變&name={name_enc}&policy={policy_enc}", "#4DABF7"),
                     _postback_btn("保費", f"action=保費變更&name={name_enc}&policy={policy_enc}", "#FFD43B"),
                 ]},
                _postback_btn("查看保服進度", f"action=check_cases&name={name_enc}", "#20C997"),
            ]
        },
        "styles": {
            "header": {"backgroundColor": "#E1F5EE"},
            "body":   {"backgroundColor": "#FFFFFF"},
            "footer": {"backgroundColor": "#F1EFE8"},
        }
    }


def build_cases_card(name, cases):
    pending = [c for c in cases if c.get("狀態", "") != "已完成"]
    done    = [c for c in cases if c.get("狀態", "") == "已完成"]
    all_c   = pending + done
    items   = [_case_item(c, name) for c in all_c] if all_c else [
        {"type": "text", "text": "目前沒有保服案件", "size": "sm", "color": "#888780"}
    ]
    return {
        "type": "bubble", "size": "kilo",
        "header": {
            "type": "box", "layout": "vertical", "backgroundColor": "#E1F5EE",
            "contents": [
                {"type": "text", "text": "保服進度", "weight": "bold", "size": "lg", "color": "#0F6E56"},
                {"type": "text", "text": f"{name} · 待處理 {len(pending)} 件",
                 "size": "xs", "color": "#0F6E56"},
            ]
        },
        "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": items}
    }


def _case_item(c, name):
    status   = c.get("狀態", "待處理")
    color    = STATUS_COLOR.get(status, "#888780")
    emoji    = STATUS_EMOJI.get(status, "?")
    case_id  = c.get("案件ID", "")
    service  = c.get("服務項目", "")
    created  = c.get("建立時間", "")
    client_n = c.get("客戶姓名", name)
    name_enc = quote(client_n)
    id_enc   = quote(case_id)

    return {
        "type": "box", "layout": "vertical", "spacing": "xs",
        "paddingAll": "10px", "backgroundColor": "#F1EFE8",
        "cornerRadius": "8px", "margin": "sm",
        "contents": [
            {"type": "box", "layout": "horizontal",
             "contents": [
                 {"type": "text", "text": f"{case_id} · {client_n} · {service}",
                  "size": "xs", "weight": "bold", "color": "#2C2C2A", "flex": 1, "wrap": True},
                 {"type": "text", "text": f"{emoji} {status}",
                  "size": "xs", "color": color, "align": "end", "flex": 0},
             ]},
            {"type": "text", "text": f"建立：{created}", "size": "xxs", "color": "#B4B2A9"},
            {"type": "box", "layout": "vertical", "spacing": "xs", "margin": "sm",
             "contents": [
                 {"type": "box", "layout": "horizontal", "spacing": "xs",
                  "contents": [
                      _postback_btn(UPDATE_BTNS[0], f"action=update&id={id_enc}&name={name_enc}&status={quote(UPDATE_BTNS[0])}", UPDATE_COLORS[0]),
                      _postback_btn(UPDATE_BTNS[1], f"action=update&id={id_enc}&name={name_enc}&status={quote(UPDATE_BTNS[1])}", UPDATE_COLORS[1]),
                  ]},
                 {"type": "box", "layout": "horizontal", "spacing": "xs",
                  "contents": [
                      _postback_btn(UPDATE_BTNS[2], f"action=update&id={id_enc}&name={name_enc}&status={quote(UPDATE_BTNS[2])}", UPDATE_COLORS[2]),
                      _postback_btn(UPDATE_BTNS[3], f"action=update&id={id_enc}&name={name_enc}&status={quote(UPDATE_BTNS[3])}", UPDATE_COLORS[3]),
                  ]},
             ]},
        ]
    }


# ══════════════════════════════════════════════════════════
# 業務 / 增員追蹤
# ══════════════════════════════════════════════════════════

def build_biz_list_card(records: list, title: str = "業務追蹤") -> dict:
    """顯示業務/增員列表，每筆一行"""
    if not records:
        items = [{"type": "text", "text": "目前沒有記錄", "size": "sm", "color": "#888780"}]
    else:
        items = []
        for r in records[:20]:
            rid   = r.get("ID", "")
            name  = r.get("姓名", "")
            stage = r.get("階段", "")
            phone = r.get("電話", "")
            items.append({
                "type": "box", "layout": "horizontal", "spacing": "sm",
                "paddingAll": "8px", "backgroundColor": "#F1EFE8",
                "cornerRadius": "6px", "margin": "sm",
                "contents": [
                    {"type": "box", "layout": "vertical", "flex": 3,
                     "contents": [
                         {"type": "text", "text": f"{rid} {name}", "size": "sm", "weight": "bold", "color": "#2C2C2A"},
                         {"type": "text", "text": phone, "size": "xxs", "color": "#888780"},
                     ]},
                    {"type": "text", "text": stage, "size": "xs", "color": "#0F6E56",
                     "align": "end", "flex": 2, "gravity": "center"},
                ]
            })

    return {
        "type": "bubble", "size": "kilo",
        "header": {
            "type": "box", "layout": "vertical", "backgroundColor": "#E1F5EE",
            "contents": [
                {"type": "text", "text": title, "weight": "bold", "size": "lg", "color": "#0F6E56"},
                {"type": "text", "text": f"共 {len(records)} 筆", "size": "xs", "color": "#0F6E56"},
            ]
        },
        "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": items}
    }


# ══════════════════════════════════════════════════════════
# 產險 Flex 卡片
# ══════════════════════════════════════════════════════════

def _prop_group(days):
    if days <= 10:
        return "急件催辦", "#FF4757"
    elif days <= 30:
        return "10天追蹤", "#FFA502"
    return "新續保件", "#2ED573"



def build_life_detail_card(detail: dict) -> dict:
    """壽星 + 保單周年 Flex 卡片"""
    birthdays     = detail.get("birthdays", [])
    anniversaries = detail.get("anniversaries", [])
    contents = []

    if birthdays:
        contents.append({"type": "text", "text": "🎂 當日壽星",
                         "weight": "bold", "size": "sm", "color": "#0F6E56"})
        for b in birthdays:
            contents.append({
                "type": "box", "layout": "horizontal", "spacing": "sm",
                "paddingAll": "8px", "backgroundColor": "#F1EFE8",
                "cornerRadius": "6px", "margin": "sm",
                "contents": [
                    {"type": "box", "layout": "vertical", "flex": 3,
                     "contents": [
                         {"type": "text", "text": b["name"], "size": "sm",
                          "weight": "bold", "color": "#2C2C2A"},
                         {"type": "text", "text": b["dob"], "size": "xxs", "color": "#888780"},
                     ]},
                    {"type": "text", "text": b.get("tel", ""), "size": "xs",
                     "color": "#0F6E56", "align": "end", "flex": 2, "gravity": "center"},
                ]
            })

    if anniversaries:
        if contents:
            contents.append({"type": "separator", "margin": "md"})
        contents.append({"type": "text", "text": "📋 保單周年",
                         "weight": "bold", "size": "sm", "color": "#0F6E56", "margin": "md"})
        for a in anniversaries:
            contents.append({
                "type": "box", "layout": "vertical", "spacing": "xs",
                "paddingAll": "8px", "backgroundColor": "#F1EFE8",
                "cornerRadius": "6px", "margin": "sm",
                "contents": [
                    {"type": "box", "layout": "horizontal",
                     "contents": [
                         {"type": "text", "text": a["name"], "size": "sm",
                          "weight": "bold", "color": "#2C2C2A", "flex": 3},
                         {"type": "text", "text": f"第{a['years']}年",
                          "size": "xs", "color": "#FF6B6B", "align": "end", "flex": 1},
                     ]},
                    {"type": "text", "text": f"{a['company']}  {a['policy_num']}",
                     "size": "xxs", "color": "#888780"},
                    {"type": "text", "text": a.get("tel", ""),
                     "size": "xxs", "color": "#0F6E56"},
                ]
            })

    if not contents:
        contents = [{"type": "text", "text": "今日無壽星或保單周年",
                     "size": "sm", "color": "#888780"}]

    return {
        "type": "bubble", "size": "kilo",
        "header": {
            "type": "box", "layout": "vertical", "backgroundColor": "#E1F5EE",
            "contents": [
                {"type": "text", "text": "壽險提醒", "weight": "bold",
                 "size": "lg", "color": "#0F6E56"},
                {"type": "text", "text": f"壽星 {len(birthdays)} 位・周年 {len(anniversaries)} 組",
                 "size": "xs", "color": "#0F6E56"},
            ]
        },
        "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": contents}
    }


def build_property_card(row, current_status=None) -> dict:
    """產險單張 bubble（同原 insurance-bot）"""
    import urllib.parse
    days         = int(row["剩餘天數"])
    label, color = _prop_group(days)
    policy_id    = str(row["保單號碼"]).strip()
    name         = str(row["被保姓名"]).strip()
    pid_enc      = urllib.parse.quote(policy_id)
    name_enc     = urllib.parse.quote(name[:8])

    def pb(a):
        return f"action={a}&id={pid_enc}&name={name_enc}"

    st_text  = current_status or "尚未聯絡"
    st_emoji = PROP_STATUS_EMOJI.get(st_text, "⏳")
    st_color = PROP_STATUS_COLOR.get(st_text, "#FFA502")

    return {
        "type": "bubble", "size": "kilo",
        "header": {
            "type": "box", "layout": "vertical", "backgroundColor": color,
            "contents": [
                {"type": "text", "text": f"倒數 {days} 天", "color": "#FFFFFF", "size": "xl", "weight": "bold"},
                {"type": "text", "text": label, "color": "#FFFFFF", "size": "sm"},
            ]
        },
        "body": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "contents": [
                {"type": "text", "text": name, "weight": "bold", "size": "lg"},
                {"type": "separator"},
                {"type": "box", "layout": "vertical", "spacing": "xs", "contents": [
                    {"type": "text", "text": f"保單號碼：{policy_id}", "size": "sm", "color": "#555555"},
                    {"type": "text", "text": f"保險公司：{row['公司名稱']}", "size": "sm", "color": "#555555"},
                    {"type": "text", "text": f"險種：{row['險別名稱']}", "size": "sm", "color": "#555555"},
                    {"type": "text", "text": f"電話：{row['行動電話']}", "size": "sm", "color": "#555555"},
                    {"type": "text", "text": f"到期日：{row['到期日'].strftime('%Y/%m/%d')}",
                     "size": "sm", "color": "#FF4757", "weight": "bold"},
                    {"type": "text", "text": f"總保費：$ {int(row['總保費']):,} 元",
                     "size": "sm", "color": "#FF4757", "weight": "bold"},
                    {"type": "text", "text": f"{st_emoji} 狀態：{st_text}",
                     "size": "sm", "color": st_color, "weight": "bold"},
                ]},
            ]
        },
        "footer": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "contents": [
                {"type": "box", "layout": "horizontal", "spacing": "sm",
                 "contents": [
                     _postback_btn("📋 報價",  pb("quoted"),  "#3B82F6"),
                     _postback_btn("⏰ 延3天", pb("delay"),   "#F59E0B"),
                 ]},
                {"type": "box", "layout": "horizontal", "spacing": "sm",
                 "contents": [
                     _postback_btn("🔄 延7天", pb("delay7"),  "#F59E0B"),
                     _postback_btn("❌ 不續保", pb("cancel"), "#6B7280"),
                 ]},
                _postback_btn("✅ 續保完成", pb("done"), "#10B981"),
            ]
        }
    }


# ══════════════════════════════════════════════════════════
# 說明選單
# ══════════════════════════════════════════════════════════

def build_help_message(pending_cases=None) -> dict:
    commands = [
        ("查詢 王小明",       "查看客戶資料和保單"),
        ("進度 王小明",       "查看保服案件進度"),
        ("待辦",              "顯示所有待處理案件"),
        ("產險",              "查看產險到期名單"),
        ("壽險",              "查看當日壽星/保單周年"),
        ("業務",              "查看業務追蹤列表"),
        ("增員",              "查看增員追蹤列表"),
        ("新增業務 姓名 電話 階段", "新增業務追蹤（階段：已聯繫/建議書/約簽約/送保單）"),
        ("新增增員 姓名 電話 階段", "新增增員追蹤（階段：已聯繫/約聊聊/約簽約）"),
        ("更新業務 B001 建議書", "更新業務追蹤階段"),
        ("更新增員 R001 約聊聊", "更新增員追蹤階段"),
        ("新增卡片 姓名 銀行 卡號前4碼 效期", "新增信用卡"),
        ("刪除卡片 姓名 銀行 卡號前4碼", "刪除信用卡"),
        ("說明",              "顯示此說明"),
    ]
    rows = []
    for cmd, desc in commands:
        rows.append({
            "type": "box", "layout": "vertical", "spacing": "xs",
            "paddingAll": "10px", "backgroundColor": "#F1EFE8",
            "cornerRadius": "6px", "margin": "sm",
            "contents": [
                {"type": "text", "text": cmd,  "size": "sm", "weight": "bold", "color": "#0F6E56", "wrap": True},
                {"type": "text", "text": desc, "size": "xs", "color": "#5F5E5A"},
            ]
        })

    pending_section = []
    if pending_cases:
        pending_section.append({"type": "separator", "margin": "md"})
        pending_section.append({
            "type": "text",
            "text": f"待處理案件（{len(pending_cases)} 件）",
            "size": "sm", "weight": "bold", "color": "#FF6B6B", "margin": "md"
        })
        for c in pending_cases[:5]:
            pending_section.append(_case_item(c, c.get("客戶姓名", "")))

    return {
        "type": "bubble", "size": "kilo",
        "header": {
            "type": "box", "layout": "vertical", "backgroundColor": "#E1F5EE",
            "contents": [
                {"type": "text", "text": "保險發展小幫手", "weight": "bold", "size": "lg", "color": "#0F6E56"},
                {"type": "text", "text": "指令說明", "size": "sm", "color": "#0F6E56"},
            ]
        },
        "body": {"type": "box", "layout": "vertical", "contents": rows + pending_section}
    }


# ── 通用按鈕 ──────────────────────────────────────────────
def _postback_btn(label, data, color):
    return {
        "type": "button",
        "action": {"type": "postback", "label": label, "data": data},
        "style": "primary", "color": color, "height": "sm", "flex": 1,
    }


def _info_row(icon, label, value):
    display = str(value).strip() if value else "-"
    return {
        "type": "box", "layout": "horizontal", "spacing": "sm",
        "contents": [
            {"type": "text", "text": icon,    "size": "sm", "flex": 0},
            {"type": "text", "text": label,   "size": "sm", "color": "#888780", "flex": 1},
            {"type": "text", "text": display, "size": "sm", "color": "#2C2C2A",
             "flex": 3, "align": "end", "wrap": True},
        ]
    }
