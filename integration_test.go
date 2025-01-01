package main

import (
	"encoding/xml"
	"net/http"
	"net/http/httptest"
	"testing"

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

// RSS 结构体用于解析测试
type RSS struct {
	XMLName xml.Name `xml:"rss"`
	Channel struct {
		Title       string `xml:"title"`
		Description string `xml:"description"`
		Items       []struct {
			Title       string `xml:"title"`
			Link        string `xml:"link"`
			Description string `xml:"description"`
			Author      string `xml:"author"`
		} `xml:"item"`
	} `xml:"channel"`
}

func TestPTTSearch(t *testing.T) {
	router := setupRouter()

	tests := []struct {
		name           string
		board          string
		keyword        string
		expectedStatus int
		checkResponse  func(*testing.T, string)
	}{
		{
			name:           "基本搜索功能",
			board:          "C_Chat",
			keyword:        "閒聊",
			expectedStatus: 200,
			checkResponse: func(t *testing.T, response string) {
				assert.Contains(t, response, "<?xml")
				assert.Contains(t, response, "<rss")

				var rss RSS
				err := xml.Unmarshal([]byte(response), &rss)
				assert.NoError(t, err, "应该能够解析 XML")
				assert.NotEmpty(t, rss.Channel.Items, "应该有搜索结果")

				// 检查标题格式
				assert.Contains(t, rss.Channel.Title, "PTT C_Chat Search")
			},
		},
		{
			name:           "空看板测试",
			board:          "",
			keyword:        "test",
			expectedStatus: 500,
			checkResponse: func(t *testing.T, response string) {
				assert.Contains(t, response, "error")
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			w := httptest.NewRecorder()
			req, _ := http.NewRequest("GET", "/ptt/search?board="+tt.board+"&keyword="+tt.keyword, nil)
			router.ServeHTTP(w, req)

			assert.Equal(t, tt.expectedStatus, w.Code)
			tt.checkResponse(t, w.Body.String())
		})
	}
}

func TestPlurkSearch(t *testing.T) {
	router := setupRouter()

	tests := []struct {
		name           string
		keyword        string
		expectedStatus int
		checkResponse  func(*testing.T, string)
	}{
		{
			name:           "基本搜索功能",
			keyword:        "台灣",
			expectedStatus: 200,
			checkResponse: func(t *testing.T, response string) {
				assert.Contains(t, response, "<?xml")
				assert.Contains(t, response, "<rss")

				var rss RSS
				err := xml.Unmarshal([]byte(response), &rss)
				assert.NoError(t, err, "应该能够解析 XML")
				assert.NotEmpty(t, rss.Channel.Items, "应该有搜索结果")

				// 检查标题格式
				assert.Contains(t, rss.Channel.Title, "Plurk Search")
			},
		},
		{
			name:           "空关键词测试",
			keyword:        "",
			expectedStatus: 500,
			checkResponse: func(t *testing.T, response string) {
				assert.Contains(t, response, "error")
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			w := httptest.NewRecorder()
			req, _ := http.NewRequest("GET", "/plurk/search?keyword="+tt.keyword, nil)
			router.ServeHTTP(w, req)

			assert.Equal(t, tt.expectedStatus, w.Code)
			tt.checkResponse(t, w.Body.String())
		})
	}
}

func TestPlurkTop(t *testing.T) {
	router := setupRouter()

	tests := []struct {
		name           string
		qType          string
		expectedStatus int
		checkResponse  func(*testing.T, string)
	}{
		{
			name:           "热门回应测试",
			qType:          "topResponded",
			expectedStatus: 200,
			checkResponse: func(t *testing.T, response string) {
				assert.Contains(t, response, "<?xml")
				assert.Contains(t, response, "<rss")

				var rss RSS
				err := xml.Unmarshal([]byte(response), &rss)
				assert.NoError(t, err, "应该能够解析 XML")
				assert.NotEmpty(t, rss.Channel.Items, "应该有搜索结果")
			},
		},
		{
			name:           "无效类型测试",
			qType:          "invalid",
			expectedStatus: 500,
			checkResponse: func(t *testing.T, response string) {
				assert.Contains(t, response, "error")
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			w := httptest.NewRecorder()
			req, _ := http.NewRequest("GET", "/plurk/top?qType="+tt.qType, nil)
			router.ServeHTTP(w, req)

			assert.Equal(t, tt.expectedStatus, w.Code)
			tt.checkResponse(t, w.Body.String())
		})
	}
}
