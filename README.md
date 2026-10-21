# go_feed_tool

自用 RSS 產生工具，使用 Golang 開發，支援 PTT 和 Plurk 內容的 RSS Feed 產生。

## 功能特色

- **PTT 搜尋 RSS** - 將 PTT 看板搜尋結果轉為 RSS
- **PTT 熱門文章** - 實際推文數至少 50 的文章
- **Plurk 搜尋/熱門 RSS** - Plurk 內容 RSS 輸出

## API 使用說明

### PTT 搜尋 RSS
將 PTT 特定看板的搜尋結果轉換為 RSS feed。

```
GET /ptt/search?board={board_name}&keyword={search_keyword}
```

參數說明:
- `board`: PTT 看板名稱 (例如: Gossiping, C_Chat, Baseball)
- `keyword`: 搜尋關鍵字
- `page`: PTT 搜尋結果頁碼，預設 `1`
- `pages`: 從 `page` 開始連續抓幾頁，預設 `1`，最多 `5`

範例:
```bash
# 搜尋 Gossiping 板上有關「問卦」的文章
curl "http://localhost:8080/ptt/search?board=Gossiping&keyword=問卦"

# 搜尋 C_Chat 板上有關「動畫」的文章
curl "http://localhost:8080/ptt/search?board=C_Chat&keyword=動畫"

# 搜尋 Beauty 板表特爆文，從第 2 頁開始抓 3 頁
curl "http://localhost:8080/ptt/search?board=Beauty&keyword=recommend:80&page=2&pages=3"
```

### PTT 熱門文章（50 推以上）

```
GET /ptt/trending?board=C_Chat&limit=20
```

- `board`：看板名稱，預設 `C_Chat`。
- `limit`：最多回傳筆數，預設 20，範圍 1–100。
- 從看板最近三頁收集文章，只納入實際「推」留言數 ≥ 50 的文章，依發文時間由新到舊排序。噓與箭頭不計入推數。
- 舊訂閱網址的 `threshold` 與 `mode` 參數仍可傳入，但已忽略，全部採用同一個 50 推門檻。
- RSS 標題範例：`[50推] [閒聊] 標題內容`。保留 BePTT 閱讀連結。
- 已移除 ML 預測、Python 推論服務、訓練程式、模型及相關依賴。

### Plurk 搜尋 RSS
將 Plurk 搜尋結果轉換為 RSS feed。

```
GET /plurk/search?keyword={search_keyword}
```

參數說明:
- `keyword`: 搜尋關鍵字

範例:
```bash
# 搜尋含有「台灣」的噗文
curl "http://localhost:8080/plurk/search?keyword=台灣"
```

### Plurk 熱門 RSS
獲取 Plurk 熱門噗文的 RSS feed。

```
GET /plurk/top?qType={type}
```

參數說明:
- `qType`: 熱門類型
  - `hot`: 熱門噗文
  - `favorite`: 最多收藏
  - `responded`: 最多回應

範例:
```bash
# 獲取熱門噗文
curl "http://localhost:8080/plurk/top?qType=hot"

# 獲取最多收藏的噗文
curl "http://localhost:8080/plurk/top?qType=favorite"
```

## 架構與運行

只有一個 Go 服務，提供 `/health`、PTT 與 Plurk RSS API，不需模型或其他後端服務。

```sh
go run ./cmd/server
# 或使用 Docker Compose（需既有 traefik_web network，並設定自己的 domain）
docker compose up -d --build
```

Docker 使用多階段建置，正式映像只含 Go 執行檔、CA 憑證與時區資料，不包含 Go 編譯器、原始碼、ML 模型或 Python 依賴。

## 測試

```sh
go test ./internal/handler ./cmd/server
go vet ./internal/handler ./cmd/server
```

`tests/` 另有需要連線 PTT／Plurk 的既有整合測試，可用 `go test ./tests` 執行。
