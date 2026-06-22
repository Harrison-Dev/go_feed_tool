package main

import (
	"net/http"
	"strconv"

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
		parser := handler.NewPttParser(http.DefaultClient)
		keyword := c.Query("keyword")
		board := c.Query("board")
		rss, err := parser.FetchArticles(board, keyword)
		if err != nil {
			c.String(500, err.Error())
			return
		}
		c.String(200, rss)
	})

	// PTT 熱門文章 (已爆文 + AI 預測潛在爆文)
	// GET /ptt/trending?board=C_Chat&threshold=0.5&limit=20&mode=all
	// mode: "viral" (已爆文), "potential" (潛在爆文), "all" (兩者都要, 預設)
	r.GET("/ptt/trending", func(c *gin.Context) {
		parser := handler.NewPttParser(http.DefaultClient)
		board := c.DefaultQuery("board", "C_Chat")
		threshold := c.DefaultQuery("threshold", "0.5")
		limit := c.DefaultQuery("limit", "20")
		mode := c.DefaultQuery("mode", "all")

		thresholdFloat := 0.5
		if t, err := strconv.ParseFloat(threshold, 64); err == nil {
			thresholdFloat = t
		}

		limitInt := 20
		if l, err := strconv.Atoi(limit); err == nil {
			limitInt = l
		}

		rss, err := parser.FetchTrendingArticles(board, thresholdFloat, limitInt, mode)
		if err != nil {
			c.String(500, err.Error())
			return
		}
		c.Header("Content-Type", "application/rss+xml; charset=utf-8")
		c.String(200, rss)
	})

	r.Run(":8080")
}
