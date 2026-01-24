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

預測系統使用 XGBoost 模型，根據文章發文後指定時窗內的互動數據預測是否會爆文。

#### 模型架構

**模型類型:** XGBoost 二元分類器 (Binary Classifier)

**XGBoost 超參數:**
```
n_estimators=100          # 樹的數量
max_depth=6               # 樹的最大深度
learning_rate=0.1         # 學習率
objective=binary:logistic # 二元分類目標函數
eval_metric=logloss       # 評估指標
scale_pos_weight=<auto>   # 根據類別不平衡自動計算權重
```

#### 特徵工程 (15 個特徵)

**支援的時間窗口:** 可配置 5、10 或 15 分鐘（預設 10 分鐘）

1. **互動指標 (時窗相關):**
   - `comments_{time_window}min` - 指定時窗內的評論數
   - `comments_{early_window}min` - 早期時窗的評論數（約為時窗的 1/2）
   - `push_{time_window}min` - 推文數（贊同）
   - `boo_{time_window}min` - 噓文數（反對）
   - `push_ratio_{time_window}min` - 推/(推+噓)的比例，範圍 [0, 1]

2. **速度特徵:**
   - `comment_velocity` - 評論速度（評論數 / 時窗分鐘數）
   - `velocity_ratio` - 加速度比率（早期評論數 / 總評論數），高值表示爆發力強

3. **時間特徵:**
   - `hour_of_day` - 發文時間（0-23 小時）
   - `day_of_week` - 星期幾（0=星期一, 6=星期日）
   - `is_weekend` - 是否週末（布林值）
   - `is_prime_time` - 是否黃金時段 18:00-23:59（布林值）

4. **文本特徵:**
   - `title_length` - 標題長度（字數）
   - `has_tag` - 是否有分類標籤（布林值）
   - `has_image` - 是否含有圖片連結（布林值）
   - `content_length` - 內文長度（字數）

#### 模型效能

**測試結果 (時間分割驗證):**
| 指標 | 數值 |
|------|------|
| Accuracy | 84.3% |
| Precision | 67.2% |
| Recall | 72.0% |
| F1 | 69.3% |
| AUC | 0.922 |

**訓練資料:** ~1000 篇文章 (246 爆文 / 754 一般)
- **爆文定義:** 推文數 ≥ 100
- **不平衡處理:** 自動計算 `scale_pos_weight` 提升少數類別權重

#### 推論方式 (Inference)

**預測服務架構:**
- FastAPI 微服務，監聽 `0.0.0.0:5000`
- 支援單個和批量預測
- 自動加載對應時窗的模型檔案

**推論流程:**

1. **請求格式** (JSON):
```json
{
  "board": "C_Chat",
  "title": "[閒聊] 標題",
  "post_time": "2024-01-15T20:30:00",
  "comments_window": 45,      // 時窗內評論數
  "push_window": 12,          // 時窗內推文數
  "boo_window": 3,            // 時窗內噓文數
  "comments_early": null,     // (選填) 早期窗口評論數，不提供則自動估算
  "hour_of_day": 20,
  "day_of_week": 0,           // 0=星期一
  "title_length": 15,
  "has_image": true,
  "tag_type": "閒聊"
}
```

2. **輸出:** 爆文概率 [0.0, 1.0]
```json
{
  "probability": 0.78
}
```

3. **特徵向量構建:**
   - 計算衍生特徵（push_ratio、comment_velocity、velocity_ratio）
   - 若未提供 `comments_early`，自動估算：`comments_early = comments_window * (early_window / time_window)`
   - 按特徵名稱順序組成向量
   - 傳入模型進行 `predict_proba()` 獲得概率

**API 端點:**

```bash
# 健康檢查
curl http://localhost:5000/health

# 單個預測
curl -X POST http://localhost:5000/predict \
  -H "Content-Type: application/json" \
  -d '{"board": "C_Chat", "title": "...", ...}'

# 批量預測
curl -X POST http://localhost:5000/predict/batch \
  -H "Content-Type: application/json" \
  -d '{"articles": [{...}, {...}]}'
```

**環境變數設置:**
```bash
# 設定預測時間窗口 (支援 5, 10, 15 分鐘)
export PREDICTION_TIME_WINDOW=10
python -m uvicorn inference.predict_service:app --port 5000
```

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

基本訓練 (使用預設 15 分鐘時窗):
```bash
cd ml/training
python train_model.py --data ../data/ptt_articles_merged.json
```

自訂時間窗口訓練:
```bash
# 訓練 10 分鐘窗口模型
python train_model.py \
  --data ../data/ptt_articles_merged.json \
  --time-window 10

# 訓練 5 分鐘窗口模型
python train_model.py \
  --data ../data/ptt_articles_merged.json \
  --time-window 5 \
  --output ../models/viral_predictor_5min.json

# 自訂訓練/測試分割日期
python train_model.py \
  --data ../data/ptt_articles_merged.json \
  --time-window 15 \
  --split-date "2024-12-01"
```

**訓練參數說明:**
- `--data`: 訓練資料 JSON 檔案路徑 (必需)
- `--time-window`: 時間窗口 [5, 10, 15] 分鐘 (預設 15)
- `--output`: 輸出模型路徑 (預設: `../models/viral_predictor_{time_window}min.json`)
- `--split-date`: 訓練/測試分割日期 ISO 格式 (預設: 2025-12-01)

**訓練輸出:**
```
=== Training with 15-minute window ===
Features: comments_15min, comments_7min, push_15min, ...
Loading data from ../data/ptt_articles_merged.json...
Loaded 1000 articles
Splitting at 2025-12-01...
Train: 800, Test: 200
Preparing training data...
Training features shape: (800, 15)
Viral ratio in train: 24.62%
Training model...

=== Test Results (15-min window) ===
Accuracy: 84.3%
Precision: 67.2%
Recall: 72.0%
AUC: 0.922
Model saved to ../models/viral_predictor_15min.json
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

需要先啟動 ML 預測服務，然後運行 Go 服務：

```bash
# 終端 1: 啟動 ML 預測服務 (預設 10 分鐘時窗)
cd ml
python -m uvicorn inference.predict_service:app --port 5000

# 或指定時間窗口
export PREDICTION_TIME_WINDOW=15
python -m uvicorn inference.predict_service:app --port 5000
```

```bash
# 終端 2: 運行 Go 服務
go run cmd/server/main.go
```

**驗證服務:**
```bash
# 檢查 ML 服務健康狀態
curl http://localhost:5000/health

# 測試預測 API
curl -X POST http://localhost:5000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "board": "C_Chat",
    "title": "[閒聊] 測試文章",
    "post_time": "2024-01-15T20:30:00",
    "comments_window": 45,
    "push_window": 12,
    "boo_window": 3,
    "hour_of_day": 20,
    "day_of_week": 0,
    "title_length": 15,
    "has_image": true,
    "tag_type": "閒聊"
  }'
```

## 模型檔案管理

訓練好的模型存放在 `ml/models/` 目錄下：

```
ml/models/
├── viral_predictor_5min.json   # 5 分鐘時窗模型
├── viral_predictor_10min.json  # 10 分鐘時窗模型（推薦）
├── viral_predictor_15min.json  # 15 分鐘時窗模型
└── viral_predictor.json        # 向後相容用（15 分鐘）
```

**自動模型選擇邏輯:**
1. 優先選擇時窗相符的模型 (`viral_predictor_{TIME_WINDOW}min.json`)
2. 若無此模型，則嘗試 `viral_predictor_final.json`
3. 最後回退至 `viral_predictor.json`
4. Docker 環境會嘗試 `/app/models/` 路徑下的模型

## 環境變數

| 變數 | 說明 | 預設值 | 可用值 |
|------|------|--------|--------|
| `PREDICTION_TIME_WINDOW` | ML 預測服務使用的時間窗口（分鐘） | `10` | `5, 10, 15` |
| `PREDICT_SERVICE_URL` | ML 預測服務 URL | `http://localhost:5000` | - |