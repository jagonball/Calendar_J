# 球賽共享行事曆

以月份檢視中職、冬盟、排球、籃球（之後可加日職、美職）賽程，朋友之間共享「想看／已買票／無法到場」狀態、留言與時間標記，並可在行事曆新增自訂事項。

架構：GitHub Pages（前端 `docs/index.html`）→ Google Apps Script（後端 API）→ Google 試算表（資料庫）。

```
baseball-calendar/
├── docs/index.html          前端網頁（GitHub Pages 從 docs/ 發佈）
├── docs/robots.txt
├── apps-script/Code.gs      後端程式
├── apps-script/appsscript.json
└── scripts/
    ├── fetch_cpbl.py        抓中職／冬盟賽程 → CSV
    ├── upload_games.py      把任何聯盟的 CSV 匯入試算表
    ├── games_template.csv   其他聯盟手動整理用的範本
    └── requirements.txt
```


## 一、建立試算表與後端

1. 新增一份 Google 試算表，命名例如「球賽行事曆」。
2. 選單「擴充功能 → Apps Script」，把 `Code.gs` 的內容整份貼上取代預設程式碼。
3. 左側「專案設定」勾選「在編輯器中顯示 appsscript.json」，回到編輯器把 `appsscript.json` 內容貼上（時區 Asia/Taipei）。
4. 函式選單選 `setup`，按「執行」，依提示授權。完成後會出現 Settings 頁和 Users、Sessions、Leagues、Games、Status、Comments、Events 等工作表。
5. 「執行記錄」會顯示**群組通關碼**和**ADMIN_KEY**（匯入賽程用）。通關碼也在 Settings 頁可以看到、修改。

## 二、部署 API

1. 右上「部署 → 新增部署作業」，類型選「網頁應用程式」。
2. 執行身分：**我**；存取權：**所有人**。
3. 複製網址（`https://script.google.com/macros/s/……/exec`），貼到 Settings 頁的 **API 網址**。

之後修改 `Code.gs`，要到「部署 → 管理部署作業 → 編輯（鉛筆）→ 版本選『新版本』→ 部署」，網址不會變。直接「新增部署作業」會產生新網址，邀請連結也要重新產生。

## 三、發佈前端

1. 把 `docs/` 推到 GitHub repo。
2. repo 的「Settings → Pages」：Source 選 `Deploy from a branch`，分支 `main`、資料夾 `/docs`（若 repo 只放前端檔案就選 `/ (root)`）。
3. 把 Pages 網址填到試算表 Settings 頁的 **網頁網址**。

## 四、分享給朋友

1. 重新整理試算表，上方會出現「球賽行事曆」選單（第一次會要求授權）。
2. 選「產生邀請連結」，連結會寫進 Settings 頁。
3. 把**邀請連結**和**群組通關碼**傳給朋友，建議分開傳（例如連結傳群組、通關碼私訊或當面說）。
4. 朋友第一次開啟：邀請連結 → 通關碼 → 名稱 → 設定 PIN。之後這台裝置會記住，直接進入行事曆。

## 五、匯入賽程

```bash
pip install -r scripts/requirements.txt

# 中職一軍例行賽
python scripts/fetch_cpbl.py --year 2026 --months 3-10 --out cpbl_2026.csv
python scripts/upload_games.py --url <API網址> --key <ADMIN_KEY> cpbl_2026.csv

# 亞洲冬季棒球聯盟（awb.cpbl.com.tw），預設抓 11–12 月，賽事類別自動偵測
python scripts/fetch_cpbl.py --site awb --year 2026 --out awb_2026.csv
python scripts/upload_games.py --url <API網址> --key <ADMIN_KEY> awb_2026.csv
```

匯入賽程用 ADMIN_KEY，不需要群組通關碼。匯入後資料版本會更新，大家的網頁會自動載入。

延賽改期時，重新執行抓取與匯入即可：`game_id` 用官方場次編號，匯入時會把同一場改成新日期。中職季後賽可加 `--kinds E,C`。網站若改版導致抓不到，加上 `--dump-raw raw.json --dump-html page.html` 把原始資料存下來檢查。

**排球、籃球、日職、美職**：照 `games_template.csv` 的欄位整理成 CSV（刪掉範例列）再用 `upload_games.py` 匯入。也可以直接貼到 Games 工作表，但這樣不會更新資料版本，朋友要按「立即更新」或等下次有人寫入才會看到。

## 六、資料版本與自動更新

- 每次有人寫入（狀態、留言、事項、新使用者、匯入賽程），資料版本就會加 1，並記錄最後更新者、時間與內容。網頁上方和網頁的設定裡會顯示，試算表 Settings 頁也會同步。
- 網頁定時檢查版本，版本變了才重新載入資料，所以檢查本身很輕量。預設間隔在 Settings 頁的「預設自動更新間隔（秒）」，每個人也可以在網頁的設定裡改成自己要的間隔，或關閉。
- 隨時可以按「立即更新」手動重新載入。切回網頁分頁時也會自動檢查一次。

## 七、配色

網頁的所有顏色都在 Settings 頁設定，分成「淺色｜…」和「深色｜…」兩組，各 14 項（背景、卡片底色、主要文字、次要文字、格線、強調色、想看、已買票、無法到場、刪除與錯誤等）。

- 值填色碼，格式 `#RRGGBB` 或 `#RGB`；留空就用預設值。
- D 欄「預覽」會顯示該顏色，格式錯誤會標示「格式錯誤」，那一項會自動改用預設值。
- 修改後立即生效：朋友重新開啟網頁，或下次自動更新時就會套用。
- 改壞了可以用選單「球賽行事曆 → 還原預設顏色」。
- 聯盟顏色在 Leagues 工作表的 color 欄設定。
- 配色會記在每個人的裝置上，所以邀請、通關碼、登入畫面也會使用同一套顏色。
- 「強調色」和「強調色上的文字」要有足夠對比，按鈕文字才看得清楚。

## 八、日常管理

- **忘記 PIN**：在 Users 工作表選取那個人的那一列，選單「清除選取使用者的 PIN」。他的所有裝置會被登出，下次登入時設定新 PIN。清除後請他盡快登入，避免別人先搶用名稱。
- **通關碼外流**：選單「重設群組通關碼」，所有人下次操作時會被要求輸入新通關碼（約 30 秒內生效）。
- **聯盟**：Leagues 工作表可改名稱、顏色，`enabled` 填 Y 代表網頁預設顯示，N 代表預設隱藏。新增聯盟就多加一列，`league_id` 要和 Games 的 `league` 一致。
- **刪除**：使用者只能刪除自己的留言和事項；管理者可以直接在試算表刪列。
- **深淺色**：每個人在網頁的設定裡選「跟隨系統／淺色／深色」，存在自己的裝置上。

## 從舊版升級

1. 把新的 `Code.gs` 整份貼上，執行一次 `setup()`：既有資料保留，舊的「設定」頁會自動改名為 Settings 並補上配色項目，也會新增 Sessions 工作表和 Users 的 PIN 欄位。
2. 「管理部署作業 → 編輯 → 新版本 → 部署」。
3. 更新 GitHub 上的 `docs/index.html`，並把原本寫在裡面的 `API_URL` 清空。**舊的 API 網址已經公開過**，最好改用「新增部署作業」產生新網址，再到 Apps Script「管理部署作業」把舊的部署封存。
4. 填好 Settings 頁的網頁網址與 API 網址，產生邀請連結傳給朋友。
5. 舊使用者第一次登入時，系統會請他設定 PIN。

## 資料欄位

| 工作表 | 欄位 |
|---|---|
| Settings | 項目、值、說明、預覽（A 欄文字請勿修改） |
| Users | name, created_at, last_seen, pin_hash, salt |
| Sessions | token_hash, user, created_at, last_used |
| Leagues | league_id, name, sport, color, enabled, sort |
| Games | game_id, league, date, time, away, home, venue, note, updated_at |
| Status | user, game_id, want, ticket, busy, updated_at（Y 或空白） |
| Comments | comment_id, game_id, user, text, tag_at, created_at |
| Events | event_id, date, time, title, note, created_by, created_at |

所有欄位都是純文字格式，日期 `YYYY-MM-DD`、時間 `HH:mm`、時間戳記 `YYYY-MM-DDTHH:mm:ss`（台灣時間）。
