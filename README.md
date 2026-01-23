# go_feed_tool

自用 RSS 產生工具，使用 Golang 開發，支援 PTT 和 Plurk 內容的 RSS Feed 產生。

## 功能特色

- **PTT 搜尋 RSS** - 將 PTT 看板搜尋結果轉為 RSS
- **PTT 熱門文章預測** - AI 預測潛在爆文 + 已爆文追蹤
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

範例:
```bash
# 搜尋 Gossiping 板上有關「問卦」的文章
curl "http://localhost:8080/ptt/search?board=Gossiping&keyword=問卦"

# 搜尋 C_Chat 板上有關「動畫」的文章
curl "http://localhost:8080/ptt/search?board=C_Chat&keyword=動畫"
```

### PTT 熱門文章 (AI 預測)
獲取已爆文 + AI 預測潛在爆文的 RSS feed。

```
GET /ptt/trending?board={board}&threshold={threshold}&limit={limit}&mode={mode}
```

參數說明:
- `board`: PTT 看板名稱 (預設: C_Chat)
- `threshold`: 預測機率門檻 0.0-1.0 (預設: 0.5)
- `limit`: 回傳筆數上限 (預設: 20)
- `mode`: 文章類型
  - `viral`: 已爆文 (推文數 ≥ 100)
  - `potential`: 潛在爆文 (AI 預測)
  - `all`: 兩者都要 (預設)

範例:
```bash
# 取得 C_Chat 所有熱門文章 (已爆文 + 潛在爆文)
curl "http://localhost:8080/ptt/trending?board=C_Chat&mode=all&limit=10"

# 只看已爆文
curl "http://localhost:8080/ptt/trending?board=C_Chat&mode=viral"

# 只看 AI 預測的潛在爆文 (門檻 60%)
curl "http://localhost:8080/ptt/trending?board=C_Chat&mode=potential&threshold=0.6"

# Gossiping 板熱門文章
curl "http://localhost:8080/ptt/trending?board=Gossiping&mode=all"
```

RSS 標題格式:
- 已爆文: `[🔥150推] [閒聊] 標題內容`
- 潛在爆文: `[📈75%] [閒聊] 標題內容`

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

## 架構說明

```
go_feed_tool/
├── cmd/server/          # Go 主程式
├── internal/handler/    # API handlers
├── ml/                  # ML 預測系統
│   ├── training/        # 模型訓練 (爬蟲、特徵工程、訓練)
│   ├── inference/       # FastAPI 預測服務
│   └── models/          # 訓練好的模型檔
└── docker-compose.yml   # Docker 部署設定
```

### ML 預測系統

預測系統使用 XGBoost 模型，根據文章前 15 分鐘的互動數據預測是否會爆文：

**特徵 (15 個):**
- 前 5/15 分鐘留言數、推/噓數
- 留言速度 (velocity)、加速度比率 (velocity_ratio)
- 發文時間 (小時、星期幾、是否週末、黃金時段)
- 標題長度、標籤類型、是否有圖片、內文長度

**模型效能 (5-Fold Cross Validation):**
| 指標 | 數值 |
|------|------|
| Accuracy | 84.3% |
| Precision | 67.2% |
| Recall | 72.0% |
| F1 | 69.3% |
| AUC | 0.922 |

**訓練資料:** 1000 篇文章 (246 爆文 / 754 一般)

### ML 腳本使用

```bash
cd ml/scripts

# 查看資料集統計
python data_stats.py

# 合併所有資料集並去重
python data_stats.py --merge

# 增量爬取新文章 (避免重複)
python incremental_crawl.py --target 1500

# 指定看板和延遲 (避免被 ban)
python incremental_crawl.py --target 2000 --boards Gossiping Stock --delay-min 3.0 --delay-max 5.0
```

**重新訓練模型:**
```bash
cd ml/training
python train_model.py --data ../data/ptt_articles_merged.json --output ../models/viral_predictor.json
```

## 本地運行

### 使用 Docker Compose (推薦)

```bash
# 構建和運行 (包含 ML 預測服務)
docker-compose up --build

# 停止服務
docker-compose down
```

### 單獨運行 Go 服務

```bash
# 需要先啟動 ML 預測服務
cd ml && python -m uvicorn inference.predict_service:app --port 5000 &

# 運行 Go 服務
go run cmd/server/main.go
```

## 環境變數

| 變數 | 說明 | 預設值 |
|------|------|--------|
| `PREDICT_SERVICE_URL` | ML 預測服務 URL | `http://localhost:5000` |