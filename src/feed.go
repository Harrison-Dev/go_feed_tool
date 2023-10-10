package main

import (
	"encoding/json"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"

	"github.com/PuerkitoBio/goquery"
	"github.com/gin-gonic/gin"
	"github.com/gorilla/feeds"
)

type Plurk struct {
	ID      int    `json:"id"`
	Content string `json:"content"`
	Posted  string `json:"posted"`
}

// 更新的 Stats 結構
type Stats struct {
	PlurkID    int    `json:"plurk_id"`
	Posted     string `json:"posted"`
	Content    string `json:"content"`
	ContentRaw string `json:"content_raw"`
	Owner      struct {
		FullName string `json:"full_name"`
	} `json:"owner"`
}

// 新的 StatEntry 結構
type StatEntry struct {
	Index int   `json:"index"`
	Stats Stats `json:"stats"`
}

func getPlurkSearch(c *gin.Context) {
	keyword := c.Query("keyword")

	urlStr := "https://www.plurk.com/Search/search2" // Renamed variable to urlStr

	feed := &feeds.Feed{
		Title:       "Plurk Search - " + keyword,
		Link:        &feeds.Link{Href: urlStr},
		Description: "Search results from Plurk",
		Author:      &feeds.Author{Name: "Feed Generator"},
		Created:     time.Now(),
	}

	resp, err := http.PostForm(urlStr, url.Values{"query": {keyword}}) // Updated to urlStr
	if err != nil {
		c.String(http.StatusInternalServerError, err.Error())
		return
	}
	defer resp.Body.Close()

	var body struct {
		Plurks []Plurk `json:"plurks"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&body); err != nil {
		c.String(http.StatusInternalServerError, err.Error())
		return
	}

	for _, p := range body.Plurks {
		url := "https://www.plurk.com/p/" + strconv.FormatInt(int64(p.ID), 36)
		posted, _ := time.Parse(time.RFC3339, p.Posted)
		feed.Add(
			&feeds.Item{
				Title:       p.Content,
				Link:        &feeds.Link{Href: url},
				Description: p.Content,
				Created:     posted,
			},
		)
	}

	rss, err := feed.ToRss()
	if err != nil {
		c.String(http.StatusInternalServerError, err.Error())
		return
	}
	c.String(http.StatusOK, rss)
}

func getPlurkTop(c *gin.Context) {
	lang := c.Query("lang")

	url := "https://www.plurk.com/Stats/topReplurks?period=day&lang=" + lang + "&limit=10"

	feed := &feeds.Feed{
		Title:       "Plurk Top (" + lang + ")",
		Link:        &feeds.Link{Href: url},
		Description: "Top replurks from Plurk",
		Author:      &feeds.Author{Name: "Feed Generator"},
		Created:     time.Now(),
	}

	resp, err := http.Get(url)
	if err != nil {
		c.String(http.StatusInternalServerError, err.Error())
		return
	}
	defer resp.Body.Close()

	var body struct {
		Stats [][]interface{} `json:"stats"` // 更新這裡
	}
	if err := json.NewDecoder(resp.Body).Decode(&body); err != nil {
		c.String(http.StatusInternalServerError, err.Error())
		return
	}

	for _, statArray := range body.Stats {
		if len(statArray) < 2 {
			continue
		}
		statMap, ok := statArray[1].(map[string]interface{})
		if !ok {
			continue
		}
		statBytes, err := json.Marshal(statMap)
		if err != nil {
			continue
		}
		var stat Stats
		if err := json.Unmarshal(statBytes, &stat); err != nil {
			continue
		}

		url := "https://www.plurk.com/p/" + strconv.FormatInt(int64(stat.PlurkID), 36)
		posted, _ := time.Parse(time.RFC3339, stat.Posted)
		doc, err := goquery.NewDocumentFromReader(strings.NewReader(stat.Content))
		if err != nil {
			c.String(http.StatusInternalServerError, err.Error())
			return
		}
		content := doc.Text()
		feed.Add(
			&feeds.Item{
				Title:       content,
				Link:        &feeds.Link{Href: url},
				Description: content,
				Author:      &feeds.Author{Name: stat.Owner.FullName},
				Created:     posted,
			},
		)
	}

	rss, err := feed.ToRss()
	if err != nil {
		c.String(http.StatusInternalServerError, err.Error())
		return
	}
	c.String(http.StatusOK, rss)
}
