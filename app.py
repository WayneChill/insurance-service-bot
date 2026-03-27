import os

from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, FlexSendMessage, PostbackEvent
from urllib.parse import unquote
from excel_reader import search_client
from case_manager import CaseManager
from flex_message import build_client_card, build_help_message, build_cases_card

app = Flask(__name__)
line_bot_api = LineBotApi(os.environ['LINE_CHANNEL_ACCESS_TOKEN'])
handler = WebhookHandler(os.environ['LINE_CHANNEL_SECRET'])
case_mgr = CaseManager()

@app.route('/callback', methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    print('RECEIVED', body[:80], flush=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return str(e), 500
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text.strip()
    reply = parse_command(text)
    if reply['type'] == 'flex':
        line_bot_api.reply_message(
            event.reply_token,
            FlexSendMessage(alt_text=reply['alt'], contents=reply['contents'])
        )
    else:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply['text'])
        )

@handler.add(PostbackEvent)
def handle_postback(event):
    data = event.postback.data
    params = dict(p.split('=', 1) for p in data.split('&') if '=' in p)
    action = params.get('action', '')
    name = unquote(params.get('name', ''))
    policy = unquote(params.get('policy', ''))

    service_types = ['\u7406\u8ce0', '\u5951\u8b8a', '\u4fdd\u8cbb\u8b8a\u66f4']
    if action in service_types:
        case_id = case_mgr.add_case(name, action, policy)
        msg = (
            '\u2705 \u5df2\u958b\u7acb\u6848\u4ef6 #' + case_id + '\n'
            '\u5ba2\u6236\uff1a' + name + '\n'
            '\u9805\u76ee\uff1a' + action + '\n\n'
            '\u8f38\u5165\u300c\u9032\u5ea6 ' + name + '\u300d\u67e5\u770b\u9032\u5ea6'
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
    elif action == 'update':
        case_id = unquote(params.get('id', ''))
        status = unquote(params.get('status', ''))
        case_mgr.update_status(case_id, status)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text='\u2705 \u6848\u4ef6 #' + case_id + ' \u5df2\u66f4\u65b0\u70ba\u300c' + status + '\u300d')
        )
    elif action == 'check_cases':
        cases = case_mgr.get_cases(name)
        contents = build_cases_card(name, cases)
        line_bot_api.reply_message(
            event.reply_token,
            FlexSendMessage(alt_text='\u4fdd\u670d\u9032\u5ea6\uff1a' + name, contents=contents)
        )

def parse_command(text):
    parts = text.split()
    cmd = parts[0] if parts else ''

    if cmd == '\u67e5\u8a62' and len(parts) >= 2:
        name = parts[1]
        print('Searching: ' + name, flush=True)
        result = search_client(name)
        if not result:
            return {'type': 'text', 'text': '\u274c \u627e\u4e0d\u5230\u300c' + name + '\u300d\u7684\u8cc7\u6599\n\u8acb\u78ba\u8a8d\u59d3\u540d\u662f\u5426\u6b63\u78ba'}
        cards = case_mgr.get_cards(name)
        contents = build_client_card(result, name, cards)
        return {'type': 'flex', 'alt': '\u5ba2\u6236\u8cc7\u6599\uff1a' + name, 'contents': contents}

    elif cmd == '\u9032\u5ea6' and len(parts) >= 2:
        name = parts[1]
        cases = case_mgr.get_cases(name)
        return {'type': 'flex', 'alt': '\u4fdd\u670d\u9032\u5ea6\uff1a' + name, 'contents': build_cases_card(name, cases)}

    elif cmd == '\u65b0\u589e\u5361\u7247' and len(parts) >= 5:
        c_name = parts[1]
        c_bank = parts[2]
        c_num = parts[3]
        c_exp = parts[4]
        c_policy = parts[5] if len(parts) >= 6 else ''
        case_mgr.add_card(c_name, c_bank, c_num, c_exp, c_policy)
        note = '\uff08\u6307\u5b9a\u4fdd\u55ae\uff1a' + c_policy + '\uff09' if c_policy else '\uff08\u6240\u6709\u4fdd\u55ae\uff09'
        return {'type': 'text', 'text': '\u2705 \u5df2\u65b0\u589e\u4fe1\u7528\u5361\n\u59d3\u540d\uff1a' + c_name + '\n\u9280\u884c\uff1a' + c_bank + '\n\u5361\u865f\uff1a' + c_num + '\n\u6548\u671f\uff1a' + c_exp + '\n' + note}

    elif cmd == '\u522a\u9664\u5361\u7247' and len(parts) >= 4:
        c_name = parts[1]
        c_bank = parts[2]
        c_num = parts[3]
        success = case_mgr.delete_card(c_name, c_bank, c_num)
        if success:
            return {'type': 'text', 'text': '\u2705 \u5df2\u522a\u9664\u300c' + c_name + '\u300d ' + c_bank + ' ' + c_num + ' \u7684\u4fe1\u7528\u5361'}
        return {'type': 'text', 'text': '\u274c \u627e\u4e0d\u5230\u8a72\u4fe1\u7528\u5361'}

    elif cmd in ['\u8aaa\u660e', 'help', '?']:
        all_pending = case_mgr.get_all_pending()
        contents = build_help_message(all_pending)
        return {'type': 'flex', 'alt': '\u6307\u4ee4\u8aaa\u660e', 'contents': contents}

    else:
        return {'type': 'text', 'text': '\u2753 \u770b\u4e0d\u61c2\uff0c\u8f38\u5165\u300c\u8aaa\u660e\u300d\u67e5\u770b\u6307\u4ee4'}

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
