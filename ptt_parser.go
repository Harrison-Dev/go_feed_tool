package feed

import (
	"fmt"
	"net/http"
	"net/url"
	"strings"
	"time"

	"github.com/PuerkitoBio/goquery"
	"github.com/gin-gonic/gin"
	"github.com/gorilla/feeds"
)

type PttParser struct {
	HttpClient *http.Client
}

func NewPttParser(client *http.Client) *PttParser {
	return &PttParser{HttpClient: client}
}

func GetPttSearch(w http.ResponseWriter, r *http.Request) {
	parser := NewPttParser(http.DefaultClient)
	keyword := r.URL.Query().Get("keyword")
	board := r.URL.Query().Get("board")
	rss, err := parser.FetchArticles(board, keyword)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	w.Write([]byte(rss))
}

func getPttSearch(c *gin.Context) {
	parser := NewPttParser(http.DefaultClient)
	keyword := c.Query("keyword")
	board := c.Query("board")
	rss, err := parser.FetchArticles(board, keyword)
	if err != nil {
		c.String(http.StatusInternalServerError, err.Error())
		return
	}
	c.String(http.StatusOK, rss)
}

func (p *PttParser) FetchArticles(board string, keyword string) (string, error) {
	searchUrl := fmt.Sprintf("https://www.ptt.cc/bbs/%s/search?q=%s", board, url.QueryEscape(keyword))
	resp, err := p.HttpClient.Get(searchUrl)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	doc, err := goquery.NewDocumentFromReader(resp.Body)
	if err != nil {
		return "", err
	}

	var articles []Article
	doc.Find("div.r-ent div.title a").Each(func(index int, element *goquery.Selection) {
		title := element.Text()
		link, _ := element.Attr("href")
		article := Article{
			Title: title,
			Url:   "https://www.ptt.cc" + link,
		}
		articles = append(articles, article)
	})

	feed := &feeds.Feed{
		Title:       fmt.Sprintf("PTT %s Search - %s", board, keyword),
		Link:        &feeds.Link{Href: searchUrl},
		Description: fmt.Sprintf("Search results from PTT %s for %s", board, keyword),
		Author:      &feeds.Author{Name: "Feed Generator"},
		Created:     time.Now(),
	}

	for i, article := range articles {
		resp, err := p.HttpClient.Get(article.Url)
		if err != nil {
			return "", err
		}
		defer resp.Body.Close()

		doc, err := goquery.NewDocumentFromReader(resp.Body)
		if err != nil {
			return "", err
		}

		// Parse author
		author := doc.Find("div.article-metaline span.article-meta-value").First().Text()

		// Parse creation time
		timeText := doc.Find("div.article-metaline span.article-meta-value").Last().Text()
		layout := "Mon Jan 2 15:04:05 2006"
		createdTime, err := time.Parse(layout, timeText)
		if err != nil {
			return "", err // handle error
		}

		// Keep original html as the description
		originalHtml, err := doc.Find("div#main-content").Html()
		if err != nil {
			return "", err // handle error
		}

		beptt_url := article.Url
		beptt_url = strings.Replace(beptt_url, "www.ptt.cc/bbs", "bbs.beptt.cc", -1)

		// trim the string after "發信站: 批踢踢實業坊(ptt.cc),"
		originalHtml = strings.Split(originalHtml, "發信站: 批踢踢實業坊(ptt.cc)")[0]
		articles[i].Summary = originalHtml // Set the original HTML as the summary

		feed.Add(&feeds.Item{
			Title:       article.Title,
			Link:        &feeds.Link{Href: beptt_url},
			Description: articles[i].Summary,
			Author:      &feeds.Author{Name: author},
			Created:     createdTime,
		})
	}

	rss, err := feed.ToRss()
	if err != nil {
		return "", err
	}
	return rss, nil
}

type Article struct {
	Title   string
	Url     string
	Summary string
}
