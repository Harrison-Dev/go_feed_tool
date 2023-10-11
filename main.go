package feed

import (
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
