package main

import (
	"net/http"

	"github.com/Harrison-Dev/go_feed_tool/cache"
	"github.com/gin-gonic/gin"
)

var feedCache = cache.NewFeedCache(100) // 設置最大緩存數為100

func main() {
	r := gin.Default()

	// Plurk 路由
	r.GET("/plurk/search", func(c *gin.Context) {
		keyword := c.Query("keyword")
		rss, err := processPlurkSearch(keyword)
		if err != nil {
			c.String(500, err.Error())
			return
		}
		c.String(200, rss)
	})

	r.GET("/plurk/top", func(c *gin.Context) {
		qType := c.Query("qType")
		rss, err := processPlurkTop(qType)
		if err != nil {
			c.String(500, err.Error())
			return
		}
		c.String(200, rss)
	})

	// PTT 路由
	r.GET("/ptt/search", func(c *gin.Context) {
		parser := NewPttParser(http.DefaultClient)
		keyword := c.Query("keyword")
		board := c.Query("board")
		rss, err := parser.FetchArticles(board, keyword)
		if err != nil {
			c.String(500, err.Error())
			return
		}
		c.String(200, rss)
	})

	r.Run(":8080")
}
