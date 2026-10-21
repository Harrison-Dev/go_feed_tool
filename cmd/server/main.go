package main

import (
	"net/http"
	"strconv"
	"time"

	"github.com/Harrison-Dev/go_feed_tool/internal/handler"
	"github.com/gin-gonic/gin"
)

func main() {
	r := gin.Default()

	r.GET("/health", func(c *gin.Context) {
		c.String(http.StatusOK, "ok")
	})

	// Plurk 路由
	r.GET("/plurk/search", func(c *gin.Context) {
		keyword := c.Query("keyword")
		rss, err := handler.ProcessPlurkSearch(keyword)
		if err != nil {
			c.String(500, err.Error())
			return
		}
		c.String(200, rss)
	})

	r.GET("/plurk/top", func(c *gin.Context) {
		qType := c.Query("qType")
		rss, err := handler.ProcessPlurkTop(qType)
		if err != nil {
			c.String(500, err.Error())
			return
		}
		c.String(200, rss)
	})

	// PTT 路由
	r.GET("/ptt/search", func(c *gin.Context) {
		parser := handler.NewPttParser(&http.Client{Timeout: 15 * time.Second})
		keyword := c.Query("keyword")
		board := c.Query("board")
		page := 1
		if p, err := strconv.Atoi(c.DefaultQuery("page", "1")); err == nil {
			page = p
		}
		pages := 1
		if p, err := strconv.Atoi(c.DefaultQuery("pages", "1")); err == nil {
			pages = p
		}
		rss, err := parser.FetchArticlesPaged(board, keyword, page, pages)
		if err != nil {
			c.String(500, err.Error())
			return
		}
		c.Header("Content-Type", "application/rss+xml; charset=utf-8")
		c.String(200, rss)
	})

	// PTT 熱門文章：實際推文數至少 50；保留既有訂閱路徑。
	r.GET("/ptt/trending", gin.WrapF(handler.GetPttTrending))

	r.Run(":8080")
}
