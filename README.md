# go_feed_tool

自用 RSS 產生工具，使用 Golang 開發，支援 PTT 和 Plurk 內容的 RSS Feed 產生。

## API 使用說明

### PTT 搜尋 RSS
將 PTT 特定看板的搜尋結果轉換為 RSS feed。

bash
GET /ptt/search?board={board_name}&keyword={search_keyword}


參數說明:
- `board`: PTT 看板名稱 (例如: Gossiping, C_Chat, Baseball)
- `keyword`: 搜尋關鍵字

範例:
bash
搜尋 Gossiping 板上有關「問卦」的文章
curl "http://localhost:8080/ptt/search?board=Gossiping&keyword=問卦"
搜尋 C_Chat 板上有關「動畫」的文章
curl "http://localhost:8080/ptt/search?board=C_Chat&keyword=動畫"


### Plurk 搜尋 RSS
將 Plurk 搜尋結果轉換為 RSS feed。
GET /plurk/search?keyword={search_keyword}


參數說明:
- `keyword`: 搜尋關鍵字

範例:
搜尋含有「台灣」的噗文
curl "http://localhost:8080/plurk/search?keyword=台灣"

### Plurk 熱門 RSS
獲取 Plurk 熱門噗文的 RSS feed。

GET /plurk/top?qType={type}


參數說明:
- `qType`: 熱門類型
  - `hot`: 熱門噗文
  - `favorite`: 最多收藏
  - `responded`: 最多回應

範例:
獲取熱門噗文
curl "http://localhost:8080/plurk/top?qType=hot"
獲取最多收藏的噗文
curl "http://localhost:8080/plurk/top?qType=favorite"


## 本地運行

使用 Docker:
bash
構建和運行
docker-compose up --build
停止服務
docker-compose down