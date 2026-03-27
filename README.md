# 保服小幫手 LINE Bot

## 快速設定流程

### 1. LINE Developers 申請
1. 前往 https://developers.line.biz/
2. 建立 Provider → 建立 Messaging API Channel
3. 取得 `Channel Secret` 和 `Channel Access Token`
4. 在 Messaging API 設定頁：
   - 關閉「自動回應訊息」
   - 開啟「Allow bot to join group chats」（選用）

### 2. Google Sheets 設定
1. 前往 https://console.cloud.google.com/
2. 建立新專案 → 啟用 Google Sheets API 和 Google Drive API
3. 建立服務帳號（Service Account）→ 下載 JSON 金鑰
4. 將 JSON 金鑰重新命名為 `credentials.json`，放在專案根目錄
5. 在 Google Sheets 建立一個空白試算表
6. 將試算表分享給服務帳號的 email（編輯者權限）
7. 從試算表網址取得 Sheet ID：
   `https://docs.google.com/spreadsheets/d/【這段就是ID】/edit`

### 3. 本地測試
```bash
pip install -r requirements.txt
cp .env.example .env
# 填入 .env 中的各項設定值
python app.py

# 另開終端，使用 ngrok 建立公開網址
ngrok http 5000
# 將 https://xxxx.ngrok.io/callback 貼到 LINE Bot Webhook URL
```

### 4. 部署到 Railway
1. 前往 https://railway.app/，用 GitHub 登入
2. 上傳程式碼到 GitHub repo
3. Railway → New Project → Deploy from GitHub repo
4. 在 Variables 頁面設定環境變數（.env 內容）
5. credentials.json 透過 Railway 的 Files 功能上傳，或轉成 base64 放在環境變數
6. 取得部署網址，設定到 LINE Bot Webhook

## 指令一覽

| 指令 | 格式 | 說明 |
|------|------|------|
| 查詢 | `查詢 王小明` | 顯示客戶完整資料卡片 |
| 保服 | `保服 王小明` | 顯示保服進度 |
| 新增客戶 | `新增客戶 姓名 電話 地址 生日 身分證` | 建立新客戶 |
| 新增保單 | `新增保單 王小明 南山人壽 L-001 壽險` | 新增保單紀錄 |
| 新增案件 | `新增案件 王小明 理賠 備註` | 開立保服案件 |
| 更新進度 | `更新進度 C001 已完成` | 更新案件狀態 |
| 說明 | `說明` | 顯示指令說明卡片 |

## 服務項目類型
- 理賠
- 契變（契約變更）
- 授權書變更
- 保單貸款
- 受益人變更

## 案件狀態
- 待處理
- 處理中
- 已完成
