package handler

import (
	"fmt"
	"github.com/PuerkitoBio/goquery"
	"github.com/gorilla/feeds"
	"net/http"
	"sort"
	"strings"
	"time"
)

const trendingMinPushes = 50

type TrendingArticle struct {
	Article
	Author    string
	PostTime  time.Time
	Comments  []Comment
	PushCount int
}

type Comment struct{ Type, User, Content, Time string }

// GetPttTrending retains the RSS endpoint; legacy mode/threshold parameters are ignored.
func GetPttTrending(w http.ResponseWriter, r *http.Request) {
	parser := NewPttParser(&http.Client{Timeout: 15 * time.Second})
	board := r.URL.Query().Get("board")
	if board == "" {
		board = "C_Chat"
	}
	limit := parsePositiveInt(r.URL.Query().Get("limit"), 20, 1, 100)
	rss, err := parser.FetchTrendingArticles(board, limit)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "application/rss+xml; charset=utf-8")
	_, _ = w.Write([]byte(rss))
}

// FetchTrendingArticles includes articles with at least 50 affirmative push comments.
func (p *PttParser) FetchTrendingArticles(board string, limit int) (string, error) {
	if board == "" {
		return "", fmt.Errorf("error: board name cannot be empty")
	}
	articles, err := p.fetchRecentArticles(board, 3)
	if err != nil {
		return "", fmt.Errorf("failed to fetch articles: %w", err)
	}
	selected := filterTrendingArticles(articles, clampInt(limit, 1, 100))
	return p.generateTrendingFeed(board, selected)
}

func filterTrendingArticles(articles []TrendingArticle, limit int) []TrendingArticle {
	selected := make([]TrendingArticle, 0)
	seen := make(map[string]bool)
	for _, article := range articles {
		if seen[article.Url] {
			continue
		}
		seen[article.Url] = true
		article.PushCount = 0
		for _, comment := range article.Comments {
			if comment.Type == "推" {
				article.PushCount++
			}
		}
		if article.PushCount >= trendingMinPushes {
			selected = append(selected, article)
		}
	}
	sort.SliceStable(selected, func(i, j int) bool { return selected[i].PostTime.After(selected[j].PostTime) })
	limit = clampInt(limit, 1, 100)
	if len(selected) > limit {
		selected = selected[:limit]
	}
	return selected
}

// pttGet makes a GET request with over18 cookie
func (p *PttParser) pttGet(url string) (*http.Response, error) {
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Cookie", "over18=1")
	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
	return p.HttpClient.Do(req)
}

// fetchRecentArticles fetches recent articles from a board
func (p *PttParser) fetchRecentArticles(board string, pages int) ([]TrendingArticle, error) {
	var articles []TrendingArticle
	var prevLink string

	for page := 1; page <= pages; page++ {
		var pageURL string
		if page == 1 {
			pageURL = fmt.Sprintf("https://www.ptt.cc/bbs/%s/index.html", board)
		} else if prevLink != "" {
			pageURL = "https://www.ptt.cc" + prevLink
		} else {
			break
		}

		resp, err := p.pttGet(pageURL)
		if err != nil {
			return nil, err
		}
		if resp.StatusCode != http.StatusOK {
			resp.Body.Close()
			return nil, fmt.Errorf("PTT returned HTTP %d", resp.StatusCode)
		}
		doc, err := goquery.NewDocumentFromReader(resp.Body)
		resp.Body.Close()
		if err != nil {
			return nil, err
		}

		// Find the previous page link for next iteration
		prevLink, _ = doc.Find("a.btn.wide:contains('上頁')").Attr("href")

		// Parse articles from page
		doc.Find("div.r-ent").Each(func(i int, s *goquery.Selection) {
			titleElem := s.Find("div.title a")
			title := titleElem.Text()
			link, exists := titleElem.Attr("href")
			if !exists || title == "" {
				return
			}

			// Get push count (nrec)
			nrec := s.Find("div.nrec span").Text()

			article := TrendingArticle{
				Article: Article{
					Title: title,
					Url:   "https://www.ptt.cc" + link,
				},
			}

			// Fetch article details (post time, comments)
			if err := p.fetchArticleDetails(&article); err != nil {
				fmt.Printf("Error fetching details for %s: %v\n", title, err)
				return
			}

			// Only include articles with some activity
			if nrec != "" || len(article.Comments) > 0 {
				articles = append(articles, article)
			}
		})
	}

	return articles, nil
}

// fetchArticleDetails fetches post time and comments for an article
func (p *PttParser) fetchArticleDetails(article *TrendingArticle) error {
	resp, err := p.pttGet(article.Url)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("PTT returned HTTP %d", resp.StatusCode)
	}

	doc, err := goquery.NewDocumentFromReader(resp.Body)
	if err != nil {
		return err
	}

	// Parse author (first meta value)
	article.Author = doc.Find("div.article-metaline span.article-meta-value").First().Text()

	// Parse post time (last meta value)
	timeText := doc.Find("div.article-metaline span.article-meta-value").Last().Text()
	layout := "Mon Jan 2 15:04:05 2006"
	taipeiLoc, _ := time.LoadLocation("Asia/Taipei")
	if postTime, err := time.ParseInLocation(layout, timeText, taipeiLoc); err == nil {
		article.PostTime = postTime
	} else {
		article.PostTime = time.Now().Add(-1 * time.Hour) // default
	}

	// Parse comments
	doc.Find("div.push").Each(func(i int, s *goquery.Selection) {
		pushTag := s.Find("span.push-tag").Text()
		pushUser := s.Find("span.push-userid").Text()
		pushContent := s.Find("span.push-content").Text()
		pushTime := s.Find("span.push-ipdatetime").Text()

		// Normalize push type
		pushType := "→"
		pushTag = strings.TrimSpace(pushTag)
		if strings.Contains(pushTag, "推") {
			pushType = "推"
		} else if strings.Contains(pushTag, "噓") {
			pushType = "噓"
		}

		article.Comments = append(article.Comments, Comment{
			Type:    pushType,
			User:    strings.TrimSpace(pushUser),
			Content: strings.TrimPrefix(pushContent, ": "),
			Time:    strings.TrimSpace(pushTime),
		})
	})

	// Parse content for image detection
	content, _ := doc.Find("div#main-content").Html()
	article.Summary = content

	return nil
}

// generateTrendingFeed creates RSS feed from trending articles
func (p *PttParser) generateTrendingFeed(board string, articles []TrendingArticle) (string, error) {

	feed := &feeds.Feed{
		Title:       fmt.Sprintf("PTT %s 熱門文章（50 推以上）", board),
		Link:        &feeds.Link{Href: fmt.Sprintf("https://www.ptt.cc/bbs/%s/index.html", board)},
		Description: fmt.Sprintf("PTT %s 最近三頁中推文數至少 50 的文章，依發文時間排序", board),
		Author:      &feeds.Author{Name: "PTT Feed Generator"},
		Created:     time.Now(),
	}

	for _, article := range articles {
		// Convert to BePTT URL for better mobile reading
		bepttURL := strings.Replace(article.Url, "www.ptt.cc/bbs", "bbs.beptt.cc", -1)

		title := fmt.Sprintf("[%d推] %s", article.PushCount, article.Title)

		// 清理 Description，與 ptt search API 格式一致
		description := article.Summary
		description = strings.Split(description, "發信站: 批踢踢實業坊(ptt.cc)")[0]
		description = strings.Replace(description, "\n", "<br>", -1)

		feed.Add(&feeds.Item{
			Title:       title,
			Link:        &feeds.Link{Href: bepttURL},
			Description: description,
			Author:      &feeds.Author{Name: article.Author},
			Created:     article.PostTime,
		})
	}

	return feed.ToRss()
}
