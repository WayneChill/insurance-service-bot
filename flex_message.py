from urllib.parse import quote

STATUS_COLOR = {
    '\u5f85\u8655\u7406': '#888780',
    '\u5df2\u806f\u7d61': '#4DABF7',
    '\u5df2\u9001\u51fa': '#FFD43B',
    '\u6838\u5c0d\u4e2d': '#FF922B',
    '\u5df2\u5b8c\u6210': '#20C997'
}
STATUS_EMOJI = {
    '\u5f85\u8655\u7406': '\u23f0',
    '\u5df2\u806f\u7d61': '\U0001f4de',
    '\u5df2\u9001\u51fa': '\U0001f4e4',
    '\u6838\u5c0d\u4e2d': '\U0001f50d',
    '\u5df2\u5b8c\u6210': '\u2705'
}
TYPE_COLOR = {'\u58fd\u9669': '#4DABF7', '\u7522\u9669': '#FF6B6B'}
KEY_SERVICE = '\u670d\u52d9\u9805\u76ee'
KEY_POLICY = '\u4fdd\u55ae\u865f\u78bc'
KEY_STATUS = '\u72c0\u614b'
KEY_CREATED = '\u5efa\u7acb\u6642\u9593'
KEY_CASE_ID = '\u6848\u4ef6ID'
KEY_CLIENT = '\u5ba2\u6236\u59d3\u540d'

UPDATE_BTNS = ['\u5df2\u806f\u7d61', '\u5df2\u9001\u51fa', '\u6838\u5c0d\u4e2d', '\u5df2\u5b8c\u6210']
BTN_COLORS = ['#4DABF7', '#FFD43B', '#FF922B', '#20C997']


def build_client_card(clients, search_name, cards=None):
    if not clients:
        return {
            'type': 'bubble',
            'body': {'type': 'box', 'layout': 'vertical', 'contents': [
                {'type': 'text', 'text': '\u672a\u627e\u5230\u8cc7\u6599', 'color': '#888780'}
            ]}
        }
    if len(clients) == 1:
        return _single_bubble(clients[0], search_name, cards)
    return {
        'type': 'carousel',
        'contents': [_single_bubble(c, search_name, cards) for c in clients[:10]]
    }


def _single_bubble(client, search_name, cards=None):
    name = client['name']
    applicant = client.get('applicant', '')
    policies = [p for p in client.get('policies', []) if p.get('policy_num')]

    policy_rows = []
    for p in policies[:8]:
        color = TYPE_COLOR.get(p['type'], '#888780')
        policy_rows.append({
            'type': 'box', 'layout': 'horizontal', 'spacing': 'sm', 'margin': 'sm',
            'contents': [
                {
                    'type': 'box', 'layout': 'vertical', 'width': '36px',
                    'backgroundColor': color, 'cornerRadius': '4px', 'paddingAll': '4px',
                    'justifyContent': 'center',
                    'contents': [{'type': 'text', 'text': p['type'], 'size': 'xxs', 'color': '#FFFFFF', 'align': 'center', 'gravity': 'center'}]
                },
                {
                    'type': 'box', 'layout': 'vertical', 'flex': 1,
                    'contents': [
                        {'type': 'text', 'text': p['company'], 'size': 'sm', 'weight': 'bold', 'color': '#2C2C2A'},
                        {'type': 'text', 'text': p['policy_num'], 'size': 'xs', 'color': '#888780', 'wrap': True}
                    ]
                }
            ]
        })

    if not policy_rows:
        policy_rows = [{'type': 'text', 'text': '\u5c1a\u7121\u4fdd\u55ae\u8cc7\u6599', 'size': 'sm', 'color': '#888780'}]

    name_enc = quote(search_name)
    policy_enc = quote(policies[0]['policy_num']) if policies else ''

    info_rows = []
    tel = client.get('tel', '').strip()
    addr = client.get('addr', '').strip()
    info_rows.append(_info_row('\U0001f4de', '\u96fb\u8a71', tel if tel else '-'))
    info_rows.append(_info_row('\U0001f4cd', '\u5730\u5740', addr if addr else '-'))
    if applicant:
        info_rows.append(_info_row('\U0001f464', '\u8981\u4fdd\u4eba', applicant))

    # 信用卡區塊
    card_rows = []
    if cards:
        card_rows.append({'type': 'separator', 'margin': 'sm'})
        card_rows.append({
            'type': 'text', 'text': '\U0001f4b3 \u4fe1\u7528\u5361',
            'size': 'sm', 'weight': 'bold', 'color': '#0F6E56', 'margin': 'sm'
        })
        for cd in cards:
            bank = str(cd.get('\u9280\u884c\u540d', '')).strip()
            num = str(cd.get('\u5361\u865f\u524d4\u78bc', '')).strip()
            exp = str(cd.get('\u6548\u671f', '')).strip()
            note = str(cd.get('\u5099\u8a3b\u4fdd\u55ae', '')).strip()
            label = bank + ' ' + num + '  ' + exp
            if note:
                label += '  \u2192 ' + note
            else:
                label += '  \uff08\u6240\u6709\u4fdd\u55ae\uff09'
            card_rows.append({
                'type': 'text', 'text': label,
                'size': 'xs', 'color': '#5F5E5A', 'wrap': True
            })

    body_contents = info_rows + [
        {'type': 'separator', 'margin': 'sm'},
        {'type': 'text', 'text': '\u4fdd\u55ae\uff08' + str(len(policies)) + ' \u5f35\uff09',
         'size': 'sm', 'weight': 'bold', 'color': '#0F6E56', 'margin': 'sm'},
    ] + policy_rows + card_rows

    return {
        'type': 'bubble', 'size': 'kilo',
        'header': {
            'type': 'box', 'layout': 'vertical', 'paddingAll': '16px',
            'contents': [
                {'type': 'text', 'text': name, 'weight': 'bold', 'size': 'xl', 'color': '#2C2C2A', 'align': 'center'},
                {'type': 'text', 'text': client.get('idno', ''), 'size': 'xs', 'color': '#888780', 'margin': 'xs', 'align': 'center'}
            ]
        },
        'body': {
            'type': 'box', 'layout': 'vertical', 'spacing': 'sm',
            'contents': body_contents
        },
        'footer': {
            'type': 'box', 'layout': 'vertical', 'spacing': 'sm',
            'contents': [
                {'type': 'text', 'text': '\u958b\u7acb\u4fdd\u670d\u6848\u4ef6', 'size': 'xs', 'color': '#888780', 'align': 'center'},
                {
                    'type': 'box', 'layout': 'horizontal', 'spacing': 'sm',
                    'contents': [
                        _postback_btn('\u7406\u8ce0', 'action=\u7406\u8ce0&name=' + name_enc + '&policy=' + policy_enc, '#FF6B6B'),
                        _postback_btn('\u5951\u8b8a', 'action=\u5951\u8b8a&name=' + name_enc + '&policy=' + policy_enc, '#4DABF7'),
                        _postback_btn('\u4fdd\u8cbb', 'action=\u4fdd\u8cbb\u8b8a\u66f4&name=' + name_enc + '&policy=' + policy_enc, '#FFD43B')
                    ]
                },
                _postback_btn('\u67e5\u770b\u4fdd\u670d\u9032\u5ea6', 'action=check_cases&name=' + name_enc, '#20C997')
            ]
        },
        'styles': {
            'header': {'backgroundColor': '#E1F5EE'},
            'body': {'backgroundColor': '#FFFFFF'},
            'footer': {'backgroundColor': '#F1EFE8'}
        }
    }


def build_cases_card(name, cases):
    pending = [c for c in cases if c.get(KEY_STATUS, '') != '\u5df2\u5b8c\u6210']
    done = [c for c in cases if c.get(KEY_STATUS, '') == '\u5df2\u5b8c\u6210']
    all_cases = pending + done

    if not all_cases:
        items = [{'type': 'text', 'text': '\u76ee\u524d\u6c92\u6709\u4fdd\u670d\u6848\u4ef6', 'size': 'sm', 'color': '#888780'}]
    else:
        items = [_case_item(c, name) for c in all_cases]

    return {
        'type': 'bubble', 'size': 'kilo',
        'header': {
            'type': 'box', 'layout': 'vertical', 'backgroundColor': '#E1F5EE',
            'contents': [
                {'type': 'text', 'text': '\u4fdd\u670d\u9032\u5ea6', 'weight': 'bold', 'size': 'lg', 'color': '#0F6E56'},
                {'type': 'text', 'text': name + ' \u00b7 \u5f85\u8655\u7406 ' + str(len(pending)) + ' \u4ef6', 'size': 'xs', 'color': '#0F6E56'}
            ]
        },
        'body': {'type': 'box', 'layout': 'vertical', 'spacing': 'sm', 'contents': items}
    }


def build_help_message(pending_cases=None):
    commands = [
        ('\u67e5\u8a62 \u738b\u5c0f\u660e', '\u67e5\u770b\u5ba2\u6236\u8cc7\u6599\u548c\u4fdd\u55ae'),
        ('\u9032\u5ea6 \u738b\u5c0f\u660e', '\u67e5\u770b\u4fdd\u670d\u6848\u4ef6\u9032\u5ea6'),
        ('\u65b0\u589e\u5361\u7247 \u738b\u5c0f\u660e \u570b\u6cf0\u4e16\u83ef 5678 12/27', '\u65b0\u589e\u4fe1\u7528\u5361\uff08\u52a0\u4fdd\u55ae\u865f\u78bc\u53ef\u6307\u5b9a\u4fdd\u55ae\uff09'),
        ('\u522a\u9664\u5361\u7247 \u738b\u5c0f\u660e \u570b\u6cf0\u4e16\u83ef 5678', '\u522a\u9664\u6307\u5b9a\u4fe1\u7528\u5361'),
    ]
    rows = []
    for cmd, desc in commands:
        rows.append({
            'type': 'box', 'layout': 'vertical', 'spacing': 'xs',
            'paddingAll': '10px', 'backgroundColor': '#F1EFE8',
            'cornerRadius': '6px', 'margin': 'sm',
            'contents': [
                {'type': 'text', 'text': cmd, 'size': 'sm', 'weight': 'bold', 'color': '#0F6E56', 'wrap': True},
                {'type': 'text', 'text': desc, 'size': 'xs', 'color': '#5F5E5A'}
            ]
        })

    pending_section = []
    if pending_cases:
        pending_section.append({'type': 'separator', 'margin': 'md'})
        pending_section.append({
            'type': 'text',
            'text': '\u5f85\u8655\u7406\u6848\u4ef6\uff08' + str(len(pending_cases)) + ' \u4ef6\uff09',
            'size': 'sm', 'weight': 'bold', 'color': '#FF6B6B', 'margin': 'md'
        })
        for c in pending_cases[:5]:
            pending_section.append(_case_item(c, c.get(KEY_CLIENT, '')))

    return {
        'type': 'bubble', 'size': 'kilo',
        'header': {
            'type': 'box', 'layout': 'vertical', 'backgroundColor': '#E1F5EE',
            'contents': [
                {'type': 'text', 'text': '\u4fdd\u670d\u5c0f\u5e6b\u624b', 'weight': 'bold', 'size': 'lg', 'color': '#0F6E56'},
                {'type': 'text', 'text': '\u6307\u4ee4\u8aaa\u660e', 'size': 'sm', 'color': '#0F6E56'}
            ]
        },
        'body': {'type': 'box', 'layout': 'vertical', 'contents': rows + pending_section}
    }


def _case_item(c, name):
    status = c.get(KEY_STATUS, '\u5f85\u8655\u7406')
    color = STATUS_COLOR.get(status, '#888780')
    emoji = STATUS_EMOJI.get(status, '?')
    case_id = c.get(KEY_CASE_ID, '')
    service = c.get(KEY_SERVICE, '')
    created = c.get(KEY_CREATED, '')
    client_name = c.get(KEY_CLIENT, name)
    name_enc = quote(client_name)
    id_enc = quote(case_id)
    header_text = case_id + ' \u00b7 ' + client_name + ' \u00b7 ' + service

    btn_row = {
        'type': 'box', 'layout': 'vertical', 'spacing': 'xs', 'margin': 'sm',
        'contents': [
            {
                'type': 'box', 'layout': 'horizontal', 'spacing': 'xs',
                'contents': [
                    _postback_btn(UPDATE_BTNS[0], 'action=update&id=' + id_enc + '&name=' + name_enc + '&status=' + quote(UPDATE_BTNS[0]), BTN_COLORS[0]),
                    _postback_btn(UPDATE_BTNS[1], 'action=update&id=' + id_enc + '&name=' + name_enc + '&status=' + quote(UPDATE_BTNS[1]), BTN_COLORS[1]),
                ]
            },
            {
                'type': 'box', 'layout': 'horizontal', 'spacing': 'xs',
                'contents': [
                    _postback_btn(UPDATE_BTNS[2], 'action=update&id=' + id_enc + '&name=' + name_enc + '&status=' + quote(UPDATE_BTNS[2]), BTN_COLORS[2]),
                    _postback_btn(UPDATE_BTNS[3], 'action=update&id=' + id_enc + '&name=' + name_enc + '&status=' + quote(UPDATE_BTNS[3]), BTN_COLORS[3]),
                ]
            }
        ]
    }

    return {
        'type': 'box', 'layout': 'vertical', 'spacing': 'xs',
        'paddingAll': '10px', 'backgroundColor': '#F1EFE8',
        'cornerRadius': '8px', 'margin': 'sm',
        'contents': [
            {
                'type': 'box', 'layout': 'horizontal',
                'contents': [
                    {'type': 'text', 'text': header_text, 'size': 'xs', 'weight': 'bold', 'color': '#2C2C2A', 'flex': 1, 'wrap': True},
                    {'type': 'text', 'text': emoji + ' ' + status, 'size': 'xs', 'color': color, 'align': 'end', 'flex': 0}
                ]
            },
            {'type': 'text', 'text': '\u5efa\u7acb\uff1a' + created, 'size': 'xxs', 'color': '#B4B2A9'},
            btn_row
        ]
    }


def _info_row(icon, label, value):
    display = str(value).strip() if value else '-'
    if not display:
        display = '-'
    return {
        'type': 'box', 'layout': 'horizontal', 'spacing': 'sm',
        'contents': [
            {'type': 'text', 'text': icon, 'size': 'sm', 'flex': 0},
            {'type': 'text', 'text': label, 'size': 'sm', 'color': '#888780', 'flex': 1},
            {'type': 'text', 'text': display, 'size': 'sm', 'color': '#2C2C2A', 'flex': 3, 'align': 'end', 'wrap': True}
        ]
    }


def _postback_btn(label, data, color):
    return {
        'type': 'button',
        'action': {'type': 'postback', 'label': label, 'data': data},
        'style': 'primary', 'color': color, 'height': 'sm', 'flex': 1
    }
