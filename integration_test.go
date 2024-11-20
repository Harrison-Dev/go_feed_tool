package main

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"encoding/xml"
	"strings"

	"github.com/gin-gonic/gin"
	"github.com/stretchr/testify/assert"
)

func setupRouter() *gin.Engine {
	r := gin.Default()
	r.GET("/ptt/search", getPttSearch)
	r.GET("/plurk/search", getPlurkSearch)
	r.GET("/plurk/top", getPlurkTop)
	return r
}

func TestPTTSearch(t *testing.T) {
	router := setupRouter()

	t.Run("PTT搜尋功能測試", func(t *testing.T) {
		w := httptest.NewRecorder()
		req, _ := http.NewRequest("GET", "/ptt/search?board=C_Chat&keyword=recommend:40", nil)
		router.ServeHTTP(w, req)

		assert.Equal(t, 200, w.Code)
		assert.Contains(t, w.Body.String(), "<?xml")
		assert.Contains(t, w.Body.String(), "<rss")

		// 解析 XML 以檢查時間戳
		type RSS struct {
			Channel struct {
				Items []struct {
					Title   string `xml:"title"`
					PubDate string `xml:"pubDate"`
					Link    string `xml:"link"`
				} `xml:"item"`
			} `xml:"channel"`
		}

		var rss RSS
		err := xml.Unmarshal([]byte(w.Body.String()), &rss)
		assert.NoError(t, err, "XML解析應該成功")

		// 確保至少有一個項目
		assert.Greater(t, len(rss.Channel.Items), 0, "應該至少有一個文章")

		// 檢查每個項目都有時間戳
		var lastTime time.Time
		for i, item := range rss.Channel.Items {
			// 檢查時間是否存在且有效
			assert.NotEmpty(t, item.PubDate, "文章應該要有發布時間")
			pubTime, err := time.Parse("Mon, 02 Jan 2006 15:04:05 -0700", item.PubDate)
			assert.NoError(t, err, fmt.Sprintf("時間格式應該正確，收到的時間格式為: %s", item.PubDate))

			// 檢查時間順序（從新到舊）
			if i > 0 {
				assert.True(t, pubTime.Before(lastTime) || pubTime.Equal(lastTime),
					"文章應該按時間從新到舊排序")
			}
			lastTime = pubTime

			t.Logf("文章 %d - 標題: %s", i+1, item.Title)
			t.Logf("文章 %d - 時間: %s", i+1, item.PubDate)
			t.Logf("文章 %d - 連結: %s", i+1, item.Link)
		}
	})
}

func TestPlurkSearch(t *testing.T) {
	router := setupRouter()

	t.Run("Plurk搜尋功能測試", func(t *testing.T) {
		w := httptest.NewRecorder()
		req, _ := http.NewRequest("GET", "/plurk/search?keyword=百合", nil)
		router.ServeHTTP(w, req)

		assert.Equal(t, 200, w.Code)
		assert.Contains(t, w.Body.String(), "<?xml")
		assert.Contains(t, w.Body.String(), "<rss")

		type RSS struct {
			Channel struct {
				Items []struct {
					Title   string `xml:"title"`
					PubDate string `xml:"pubDate"`
					Link    string `xml:"link"`
				} `xml:"item"`
			} `xml:"channel"`
		}

		var rss RSS
		err := xml.Unmarshal([]byte(w.Body.String()), &rss)
		assert.NoError(t, err, "XML解析應該成功")

		assert.Greater(t, len(rss.Channel.Items), 0, "應該至少有一個噗文")

		var lastTime time.Time
		for i, item := range rss.Channel.Items {
			assert.NotEmpty(t, item.PubDate, "噗文應該要有發布時間")
			pubTime, err := time.Parse("Mon, 02 Jan 2006 15:04:05 -0700", item.PubDate)
			assert.NoError(t, err, fmt.Sprintf("時間格式應該正確，收到的時間格式為: %s", item.PubDate))

			if i > 0 {
				assert.True(t, pubTime.Before(lastTime) || pubTime.Equal(lastTime),
					"噗文應該按時間從新到舊排序")
			}
			lastTime = pubTime

			t.Logf("噗文 %d - 標題: %s", i+1, item.Title)
			t.Logf("噗文 %d - 時間: %s", i+1, item.PubDate)
			t.Logf("噗文 %d - 連結: %s", i+1, item.Link)
		}
	})
}

func TestPlurkTop(t *testing.T) {
	router := setupRouter()

	t.Run("Plurk熱門功能測試", func(t *testing.T) {
		w := httptest.NewRecorder()
		req, _ := http.NewRequest("GET", "/plurk/top?qType=topResponded", nil)
		router.ServeHTTP(w, req)

		assert.Equal(t, 200, w.Code)
		assert.Contains(t, w.Body.String(), "<?xml")
		assert.Contains(t, w.Body.String(), "<rss")

		// 測試緩存
		w2 := httptest.NewRecorder()
		router.ServeHTTP(w2, req)
		assert.Equal(t, w.Body.String(), w2.Body.String(), "緩存的響應應該相同")
	})

	t.Run("Plurk無效類型測試", func(t *testing.T) {
		w := httptest.NewRecorder()
		req, _ := http.NewRequest("GET", "/plurk/top?qType=invalid", nil)
		router.ServeHTTP(w, req)

		assert.Equal(t, 500, w.Code)
	})
}

func TestPTTSearchTimestamp(t *testing.T) {
	router := setupRouter()

	t.Run("PTT搜尋時間戳一致性測試", func(t *testing.T) {
		// 第一次請求
		w1 := httptest.NewRecorder()
		req1, _ := http.NewRequest("GET", "/ptt/search?board=C_Chat&keyword=recommend:40", nil)
		router.ServeHTTP(w1, req1)

		assert.Equal(t, 200, w1.Code)
		firstResponse := w1.Body.String()

		// 等待一段時間後進行第二次請求
		time.Sleep(time.Second * 2)

		// 第二次請求
		w2 := httptest.NewRecorder()
		req2, _ := http.NewRequest("GET", "/ptt/search?board=C_Chat&keyword=recommend:40", nil)
		router.ServeHTTP(w2, req2)

		assert.Equal(t, 200, w2.Code)
		secondResponse := w2.Body.String()

		// 檢查兩次響應是否完全相同
		assert.Equal(t, firstResponse, secondResponse, "兩次請求的響應應該完全相同")

		// 解析 XML 以檢查時間戳
		type RSS struct {
			Channel struct {
				Items []struct {
					Title     string `xml:"title"`
					PubDate   string `xml:"pubDate"`
					Link      string `xml:"link"`
					Author    string `xml:"author"`
					Created   string `xml:"created"`
					Published string `xml:"published"`
				} `xml:"item"`
			} `xml:"channel"`
		}

		var rss1, rss2 RSS
		err1 := xml.Unmarshal([]byte(firstResponse), &rss1)
		err2 := xml.Unmarshal([]byte(secondResponse), &rss2)

		assert.NoError(t, err1, "第一次響應的XML解析應該成功")
		assert.NoError(t, err2, "第二次響應的XML解析應該成功")

		// 確保至少有一個項目
		assert.Greater(t, len(rss1.Channel.Items), 0, "應該至少有一個文章")
		assert.Greater(t, len(rss2.Channel.Items), 0, "應該至少有一個文章")

		// 比較第一個項目的時間戳
		firstItem1 := rss1.Channel.Items[0]
		firstItem2 := rss2.Channel.Items[0]

		assert.Equal(t, firstItem1.PubDate, firstItem2.PubDate, "發布時間應該相同")
		assert.Equal(t, firstItem1.Created, firstItem2.Created, "創建時間應該相同")
		assert.Equal(t, firstItem1.Published, firstItem2.Published, "發布時間應該相同")

		// 檢查標題是否包含預期的內容
		foundRecommendPost := false
		for _, item := range rss1.Channel.Items {
			if strings.Contains(item.Title, "[討論]") || strings.Contains(item.Title, "[閒聊]") {
				foundRecommendPost = true
				break
			}
		}
		assert.True(t, foundRecommendPost, "應該能找到討論或閒聊文章")

		t.Logf("測試文章標題: %s", rss1.Channel.Items[0].Title)
		t.Logf("測試文章時間: %s", rss1.Channel.Items[0].PubDate)
	})
}

func TestPlurkSearchTimestamp(t *testing.T) {
	router := setupRouter()

	t.Run("Plurk搜尋時間戳一致性測試", func(t *testing.T) {
		// 第一次請求
		w1 := httptest.NewRecorder()
		req1, _ := http.NewRequest("GET", "/plurk/search?keyword=百合", nil)
		router.ServeHTTP(w1, req1)

		assert.Equal(t, 200, w1.Code)
		firstResponse := w1.Body.String()

		// 等待一段時間後進行第二次請求
		time.Sleep(time.Second * 2)

		// 第二次請求
		w2 := httptest.NewRecorder()
		req2, _ := http.NewRequest("GET", "/plurk/search?keyword=百合", nil)
		router.ServeHTTP(w2, req2)

		assert.Equal(t, 200, w2.Code)
		secondResponse := w2.Body.String()

		// 檢查兩次響應是否完全相同
		assert.Equal(t, firstResponse, secondResponse, "兩次請求的響應應該完全相同")

		// 解析 XML 以檢查時間戳
		type RSS struct {
			Channel struct {
				Items []struct {
					Title     string `xml:"title"`
					PubDate   string `xml:"pubDate"`
					Link      string `xml:"link"`
					Created   string `xml:"created"`
					Published string `xml:"published"`
				} `xml:"item"`
			} `xml:"channel"`
		}

		var rss1, rss2 RSS
		err1 := xml.Unmarshal([]byte(firstResponse), &rss1)
		err2 := xml.Unmarshal([]byte(secondResponse), &rss2)

		assert.NoError(t, err1, "第一次響應的XML解析應該成功")
		assert.NoError(t, err2, "第二次響應的XML解析應該成功")

		// 確保至少有一個項目
		assert.Greater(t, len(rss1.Channel.Items), 0, "應該至少有一個噗文")
		assert.Greater(t, len(rss2.Channel.Items), 0, "應該至少有一個噗文")

		// 比較第一個項目的時間戳
		firstItem1 := rss1.Channel.Items[0]
		firstItem2 := rss2.Channel.Items[0]

		assert.Equal(t, firstItem1.PubDate, firstItem2.PubDate, "發布時間應該相同")
		assert.Equal(t, firstItem1.Created, firstItem2.Created, "創建時間應該相同")
		assert.Equal(t, firstItem1.Published, firstItem2.Published, "發布時間應該相同")

		t.Logf("測試噗文標題: %s", rss1.Channel.Items[0].Title)
		t.Logf("測試噗文時間: %s", rss1.Channel.Items[0].PubDate)
	})
}

func TestPlurkTopTimestamp(t *testing.T) {
	router := setupRouter()

	t.Run("Plurk熱門時間戳一致性測試", func(t *testing.T) {
		// 第一次請求
		w1 := httptest.NewRecorder()
		req1, _ := http.NewRequest("GET", "/plurk/top?qType=topResponded", nil)
		router.ServeHTTP(w1, req1)

		assert.Equal(t, 200, w1.Code)
		firstResponse := w1.Body.String()

		// 等待一段時間後進行第二次請求
		time.Sleep(time.Second * 2)

		// 第二次請求
		w2 := httptest.NewRecorder()
		req2, _ := http.NewRequest("GET", "/plurk/top?qType=topResponded", nil)
		router.ServeHTTP(w2, req2)

		assert.Equal(t, 200, w2.Code)
		secondResponse := w2.Body.String()

		// 檢查兩次響應是否完全相同
		assert.Equal(t, firstResponse, secondResponse, "兩次請求的響應應該完全相同")

		// 解析 XML 以檢查時間戳
		type RSS struct {
			Channel struct {
				Items []struct {
					Title     string `xml:"title"`
					PubDate   string `xml:"pubDate"`
					Link      string `xml:"link"`
					Created   string `xml:"created"`
					Published string `xml:"published"`
				} `xml:"item"`
			} `xml:"channel"`
		}

		var rss1, rss2 RSS
		err1 := xml.Unmarshal([]byte(firstResponse), &rss1)
		err2 := xml.Unmarshal([]byte(secondResponse), &rss2)

		assert.NoError(t, err1, "第一次響應的XML解析應該成功")
		assert.NoError(t, err2, "第二次響應的XML解析應該成功")

		// 確保至少有一個項目
		assert.Greater(t, len(rss1.Channel.Items), 0, "應該至少有一個噗文")
		assert.Greater(t, len(rss2.Channel.Items), 0, "應該至少有一個噗文")

		// 比較第一個項目的時間戳
		firstItem1 := rss1.Channel.Items[0]
		firstItem2 := rss2.Channel.Items[0]

		assert.Equal(t, firstItem1.PubDate, firstItem2.PubDate, "發布時間應該相同")
		assert.Equal(t, firstItem1.Created, firstItem2.Created, "創建時間應該相同")
		assert.Equal(t, firstItem1.Published, firstItem2.Published, "發布時間應該相同")

		t.Logf("測試噗文標題: %s", rss1.Channel.Items[0].Title)
		t.Logf("測試噗文時間: %s", rss1.Channel.Items[0].PubDate)
	})
}
