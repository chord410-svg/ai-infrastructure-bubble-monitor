# AI 泡沫監測站

`Financial Evidence V1` 是一個可稽核、每週自動更新的 AI 基礎建設財務壓力監測站。它把官方數值轉成歷史風險百分位，區分「泡沫累積」與「金融破裂觸發」，不提供買賣建議，也不把分數稱為崩盤機率。

網站是純 HTML、CSS、JavaScript 與 JSON。GitHub Actions 定期更新資料，GitHub Pages 只提供已驗證的靜態檔案，因此不需要持續運行伺服器、資料庫或付費服務。

## What it measures

V1 聚合 Microsoft、Amazon、Alphabet、Meta 四家公司，測量：

- CapEx TTM 年增率減營業現金流 TTM 年增率。
- 現金自給率 `OCF TTM / CapEx TTM`。
- 應收帳款年增率減營收 TTM 年增率。
- `max(0, 淨負債年增額) / CapEx TTM`。
- Chicago Fed NFCI 水準與 13 週變化的金融條件衝擊。

每個會計指標至少需要 20 筆時間點正確歷史。每個原始值先轉成 0–100 歷史風險百分位，再依 `financial-evidence-v1` 固定權重加總。權重是透明政策選擇，不是統計預測模型。

所有歷史百分位從 2015 年起算，且只使用當時已公布的資料：財報以 SEC `filed` 日期為準；NFCI 官方說明為每週三公布前一個星期五的資料，遇假日可能延至週四，因此回填一律保守使用「資料週五 + 6 天」作為可用日。歷史觀測本身也採逐期擴張窗口，不讓後來資料反過來改變早期排名。

Amazon 在歷史期間曾由 `PaymentsToAcquirePropertyPlantAndEquipment` 轉用 `PaymentsToAcquireProductiveAssets`。收集器接受這兩個現金流量標籤並保存實際採用標籤；若任一 TTM 指標與最新資產負債表相差超過 130 天，整次更新會失敗，不會把舊年度數字接到最新季度。

## What it does not measure

V1 不直接測量 Token 總量、有效算力需求、GPU 租金與容量、資料中心電力、AI 專屬 CapEx、估值、事件或新聞／文字情緒。這些項目保留在 12 項規劃目錄中，標示「尚未涵蓋」，不使用猜測值，也不被當成零風險。

## Weekly operation

`.github/workflows/update-and-deploy.yml` 每週五執行，也可手動觸發：

1. 執行完整測試。
2. 從 SEC Company Facts 與 Chicago Fed NFCI 取得官方數值。
3. 依公布日期排除當時尚未公開的財報，建立候選資料包。
4. 驗證分數、來源、歷史順序與資料包契約。
5. 只有全部通過才原子替換 `site/data` 與 `data/observations`。
6. 再跑一次測試、提交驗證快照並部署同一份 `site/`。

首頁趨勢與狀態持續性以 ISO 週為單位；同一週內的手動重跑會更新該週快照，不會被算成新的連續週期。少於三個不同週的有效快照時，網站只顯示目前分數，不畫趨勢線。

啟用工作流程前，在 GitHub repository variables 新增 `SEC_USER_AGENT`，格式需包含專案或維護者名稱及真實聯絡信箱，例如 `ai-bubble-monitor/1.0 Name name@example.com`。接著在 Settings → Pages 選擇 GitHub Actions 作為來源。

超過 14 天沒有成功更新時，首頁會顯示資料過期警告並暫停顯示兩個分數；不會把舊結果冒充當前判讀。來源資料更新頻率不同：SEC 財報按申報更新，NFCI 每週更新，兩者各自顯示資料日期。

## Manual recovery

1. 查看失敗 workflow 的測試或資料來源錯誤。
2. 確認 `SEC_USER_AGENT` 仍為有效真實聯絡方式。
3. 在 Actions 手動執行 `Update evidence and deploy Pages`。
4. 若來源格式改變，先新增重現 fixture 與失敗測試，再修改收集器。
5. 在修復通過前不要手動覆寫 `site/data/latest.json`；Pages 會保留上一個有效部署。

本機驗證：

```bash
python3 -m unittest discover -s tests -v
SEC_USER_AGENT="ai-bubble-monitor/1.0 real-contact@example.com" python3 -m src.update --root .
python3 -m http.server 8000 --directory site
```

## Add an indicator

每個新指標必須同時具備六項內容：

1. 穩定且允許自動存取的數值來源。
2. 明確單位、公布日期、擷取時間與官方網址。
3. 透明公式、風險方向與最低歷史要求。
4. 時間點正確 fixture、邊界測試與失敗策略。
5. 指標目錄登記與所屬證據模組。
6. 新的計分模型版本、生效日期與舊版歷史保留策略。

新指標先獨立展示；累積足夠歷史並驗證後才建立新模型版本。不得直接改寫 v1 權重，否則不同時間的分數無法比較。原始觀測按指標與年份分割在 `data/observations/by-indicator/`。

## Data sources

- [SEC EDGAR XBRL Company Facts API](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)：10-K、10-Q 財務事實；不需 API key，但必須使用具識別性的 User-Agent。
- [Chicago Fed National Financial Conditions Index](https://www.chicagofed.org/research/data/nfci/current-data)：每週風險、信用與槓桿金融條件。NFCI 歷史可能修訂，因此每週保存當次觀測與來源網址。

原始下載不直接發布於網站；公開資料包保留來源網址、資料日期、取得時間與模型版本。歷史回填使用「申報公布日不晚於計算日」的規則，避免偷看未來資料。

標準化後的純數值歷史位於 `data/observations/by-indicator/<indicator-id>/<year>.json`。每筆包含指標 ID、數值、單位、計算日、資料期間、公布日、擷取時間、官方網址、品質狀態、目錄版本與模型版本。首頁的 GitHub 連結會在 GitHub Pages 上依 repository 網址自動指向這些檔案與 `src/` 計算程式。

## Disclaimer

本專案是研究與資料透明工具，不是投資建議、價格預測或泡沫破裂機率。使用者應自行核對官方來源並承擔決策責任。

MIT License，見 [LICENSE](LICENSE)。
