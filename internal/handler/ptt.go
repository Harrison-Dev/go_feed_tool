package handler

import (
	"fmt"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"

	"github.com/PuerkitoBio/goquery"
	"github.com/gorilla/feeds"
)

type PttParser struct {
	HttpClient *http.Client
}

type Article struct {
	Title   string
	Url     string
	Summary string
}

func NewPttParser(client *http.Client) *PttParser {
	return &PttParser{HttpClient: client}
}

// Cloud Functions handler
func GetPttSearch(w http.ResponseWriter, r *http.Request) {
	parser := NewPttParser(&http.Client{Timeout: 15 * time.Second})
	keyword := r.URL.Query().Get("keyword")
	board := r.URL.Query().Get("board")
	page := parsePositiveInt(r.URL.Query().Get("page"), 1, 1, 1000)
	pages := parsePositiveInt(r.URL.Query().Get("pages"), 1, 1, 5)
	rss, err := parser.FetchArticlesPaged(board, keyword, page, pages)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "application/rss+xml; charset=utf-8")
	w.Write([]byte(rss))
}

func (p *PttParser) FetchArticles(board string, keyword string) (string, error) {
	return p.FetchArticlesPaged(board, keyword, 1, 1)
}

func (p *PttParser) FetchArticlesPaged(board string, keyword string, page int, pages int) (string, error) {
	if board == "" {
		return "", fmt.Errorf("error: board name cannot be empty")
	}
	page = clampInt(page, 1, 1000)
	pages = clampInt(pages, 1, 5)

	var articles []Article
	for currentPage := page; currentPage < page+pages; currentPage++ {
		pageArticles, err := p.fetchSearchResultPage(board, keyword, currentPage)
		if err != nil {
			return "", err
		}
		articles = append(articles, pageArticles...)
	}

	searchUrl := pttSearchURL(board, keyword, page)

	feed := &feeds.Feed{
		Title:       fmt.Sprintf("PTT %s Search - %s", board, keyword),
		Link:        &feeds.Link{Href: searchUrl},
		Description: fmt.Sprintf("Search results from PTT %s for %s", board, keyword),
		Author:      &feeds.Author{Name: "Feed Generator"},
		Created:     time.Now(),
	}

	for _, article := range articles {
		if err := p.addArticleToFeed(feed, article); err != nil {
			fmt.Printf("略過文章: %s, 網址: %s, 錯誤: %v\n", article.Title, article.Url, err)
			continue
		}
	}

	rss, err := feed.ToRss()
	if err != nil {
		return "", err
	}
	return rss, nil
}

func (p *PttParser) addArticleToFeed(feed *feeds.Feed, article Article) error {
	resp, err := p.pttGet(article.Url)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	doc, err := goquery.NewDocumentFromReader(resp.Body)
	if err != nil {
		return err
	}

	// Parse author
	author := doc.Find("div.article-metaline span.article-meta-value").First().Text()

	// Parse creation time
	timeText := doc.Find("div.article-metaline span.article-meta-value").Last().Text()
	layout := "Mon Jan 2 15:04:05 2006"
	taipeiLoc, _ := time.LoadLocation("Asia/Taipei")
	createdTime, err := time.ParseInLocation(layout, timeText, taipeiLoc)
	if err != nil {
		return err
	}

	fmt.Printf("標題: %s, 文章時間: %v, 網址: %s\n", article.Title, createdTime, article.Url)

	// Keep original html as the description
	originalHtml, err := doc.Find("div#main-content").Html()
	if err != nil {
		return err
	}

	bepttURL := strings.Replace(article.Url, "www.ptt.cc/bbs", "bbs.beptt.cc", -1)

	// trim the string after "發信站: 批踢踢實業坊(ptt.cc),"
	originalHtml = strings.Split(originalHtml, "發信站: 批踢踢實業坊(ptt.cc)")[0]

	originalHtml = strings.Replace(originalHtml, "\n", "<br>", -1)

	feed.Add(&feeds.Item{
		Title:       article.Title,
		Link:        &feeds.Link{Href: bepttURL},
		Description: originalHtml,
		Author:      &feeds.Author{Name: author},
		Created:     createdTime,
	})

	return nil
}

func (p *PttParser) fetchSearchResultPage(board string, keyword string, page int) ([]Article, error) {
	searchUrl := pttSearchURL(board, keyword, page)
	resp, err := p.pttGet(searchUrl)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	doc, err := goquery.NewDocumentFromReader(resp.Body)
	if err != nil {
		return nil, err
	}

	var articles []Article
	doc.Find("div.r-ent div.title a").Each(func(index int, element *goquery.Selection) {
		title := strings.TrimSpace(element.Text())
		link, _ := element.Attr("href")
		if title == "" || link == "" {
			return
		}
		article := Article{
			Title: title,
			Url:   "https://www.ptt.cc" + link,
		}
		articles = append(articles, article)
	})

	return articles, nil
}

func pttSearchURL(board string, keyword string, page int) string {
	return fmt.Sprintf("https://www.ptt.cc/bbs/%s/search?page=%d&q=%s", board, page, url.QueryEscape(keyword))
}

func parsePositiveInt(value string, fallback int, min int, max int) int {
	parsed, err := strconv.Atoi(value)
	if err != nil {
		return fallback
	}
	return clampInt(parsed, min, max)
}

func clampInt(value int, min int, max int) int {
	if value < min {
		return min
	}
	if value > max {
		return max
	}
	return value
}
