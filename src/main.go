package main

import (
	"github.com/GoogleCloudPlatform/functions-framework-go/functions"
	"github.com/gin-gonic/gin"
)

func main() {
	r := gin.Default()
	r.GET("/", func(c *gin.Context) {
		c.String(200, "Hello, World!")
	})
	// r.GET("/feed", getFeed)
	r.GET("/plurk_search", getPlurkSearch)
	r.GET("/plurk_top", getPlurkTop)
	r.Run(":8080")
}

func init() {
	functions.HTTP("GetPlurkSearch", GetPlurkSearch)
	functions.HTTP("GetPlurkTop", GetPlurkTop)
}
