package main

import (
	"encoding/json"
	"fmt"
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

// Gin handlers
func getPlurkSearch(c *gin.Context) {
	keyword := c.Query("keyword")
	rss, err := processPlurkSearch(keyword)
	if err != nil {
		c.String(http.StatusInternalServerError, err.Error())
		return
	}
	c.String(http.StatusOK, rss)
}

func getPlurkTop(c *gin.Context) {
	qType := c.Query("qType")
	rss, err := processPlurkTop(qType)
	if err != nil {
		c.String(http.StatusInternalServerError, err.Error())
		return
	}
	c.String(http.StatusOK, rss)
}

// Cloud Functions handlers
func GetPlurkSearch(w http.ResponseWriter, r *http.Request) {
	keyword := r.URL.Query().Get("keyword")
	rss, err := processPlurkSearch(keyword)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	w.Write([]byte(rss))
}

func GetPlurkTop(w http.ResponseWriter, r *http.Request) {
	qType := r.URL.Query().Get("qType")
	rss, err := processPlurkTop(qType)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	w.Write([]byte(rss))
}

func trimTitleFromContent(textContent string) string {
	maxLen := 160
	title := textContent
	if len(textContent) > maxLen {
		title = textContent[:maxLen] + "..."
	}
	return title
}

func processPlurkSearch(keyword string) (string, error) {
	if keyword == "" {
		return "", fmt.Errorf("error: search keyword cannot be empty")
	}
	urlStr := "https://www.plurk.com/Search/search2"
	feed := &feeds.Feed{
		Title:       "Plurk Search - " + keyword,
		Link:        &feeds.Link{Href: urlStr},
		Description: "Search results from Plurk",
		Author:      &feeds.Author{Name: "Feed Generator"},
		Created:     time.Now(),
	}

	resp, err := http.PostForm(urlStr, url.Values{"query": {keyword}})
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	var body struct {
		Plurks []Plurk `json:"plurks"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&body); err != nil {
		return "", err
	}

	for _, p := range body.Plurks {
		doc, err := goquery.NewDocumentFromReader(strings.NewReader(p.Content))
		if err != nil {
			return "", err
		}
		textContent := doc.Text()
		title := trimTitleFromContent(textContent)

		url := "https://www.plurk.com/p/" + strconv.FormatInt(int64(p.ID), 36)

		// 修正時間解析，使用GMT格式
		posted, err := time.Parse("Mon, 02 Jan 2006 15:04:05 GMT", p.Posted)
		if err != nil {
			fmt.Printf("時間解析錯誤: %v, 原始時間字串: %s\n", err, p.Posted)
			continue
		}

		// 轉換為台北時區
		taipeiLoc, _ := time.LoadLocation("Asia/Taipei")
		postedTPE := posted.In(taipeiLoc)

		desc := p.Content
		desc = strings.Replace(desc, "\n", "<br>", -1)
		feed.Add(
			&feeds.Item{
				Title:       title,
				Link:        &feeds.Link{Href: url},
				Description: desc,
				Created:     postedTPE, // 使用台北時間
			},
		)
	}

	rss, err := feed.ToRss()
	if err != nil {
		return "", err
	}
	return rss, nil
}

func processPlurkTop(qType string) (string, error) {
	if qType != "topResponded" && qType != "hot" && qType != "favorite" {
		return "", fmt.Errorf("error: invalid qType, must be one of: topResponded, hot, favorite")
	}
	url := "https://www.plurk.com/Stats/" + qType + "?period=day&lang=zh&limit=15"
	println(qType)
	println(url)
	feed := &feeds.Feed{
		Title:       "Plurk Top",
		Link:        &feeds.Link{Href: url},
		Description: "Top replurks from Plurk",
		Author:      &feeds.Author{Name: "Feed Generator"},
		Created:     time.Now(),
	}

	resp, err := http.Get(url)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	var body struct {
		Stats [][]interface{} `json:"stats"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&body); err != nil {
		return "", err
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

		// 修正時間解析
		posted, err := time.Parse("Mon, 02 Jan 2006 15:04:05 GMT", stat.Posted)
		if err != nil {
			fmt.Printf("時間解析錯誤: %v, 原始時間字串: %s\n", err, stat.Posted)
			continue
		}

		// 轉換為台北時區
		taipeiLoc, _ := time.LoadLocation("Asia/Taipei")
		postedTPE := posted.In(taipeiLoc)

		content := stat.Content
		title := stat.ContentRaw
		title = trimTitleFromContent(title)

		feed.Add(
			&feeds.Item{
				Title:       title,
				Link:        &feeds.Link{Href: url},
				Description: content,
				Author:      &feeds.Author{Name: stat.Owner.FullName},
				Created:     postedTPE, // 使用台北時間
			},
		)
	}

	rss, err := feed.ToRss()
	if err != nil {
		return "", err
	}
	return rss, nil
}
