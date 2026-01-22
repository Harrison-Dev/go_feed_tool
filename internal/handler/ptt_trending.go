package handler

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/PuerkitoBio/goquery"
	"github.com/gorilla/feeds"
)

// PredictService URL (configured via environment variable)
var PredictServiceURL = getEnvOrDefault("PREDICT_SERVICE_URL", "http://localhost:5000")

func getEnvOrDefault(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

// PredictRequest matches the FastAPI service request schema
type PredictRequest struct {
	Board          string `json:"board"`
	Title          string `json:"title"`
	PostTime       string `json:"post_time"`
	Comments15Min  int    `json:"comments_15min"`
	Push15Min      int    `json:"push_15min"`
	Boo15Min       int    `json:"boo_15min"`
	HourOfDay      int    `json:"hour_of_day"`
	DayOfWeek      int    `json:"day_of_week"`
	TitleLength    int    `json:"title_length"`
	HasImage       bool   `json:"has_image"`
	TagType        string `json:"tag_type"`
}

// PredictResponse from the FastAPI service
type PredictResponse struct {
	Probability float64 `json:"probability"`
}

// TrendingArticle extends Article with prediction info
type TrendingArticle struct {
	Article
	PostTime    time.Time
	Comments    []Comment
	Probability float64
	PushCount   int  // 推文數
	IsViral     bool // 是否已爆文 (push >= 100)
}

// Comment represents a PTT comment
type Comment struct {
	Type    string
	User    string
	Content string
	Time    string
}

// GetPttTrending handles GET /ptt/trending?board=C_Chat&threshold=0.6&mode=all
// mode: "viral" (已爆文), "potential" (潛在爆文), "all" (兩者都要, 預設)
func GetPttTrending(w http.ResponseWriter, r *http.Request) {
	parser := NewPttParser(http.DefaultClient)

	board := r.URL.Query().Get("board")
	if board == "" {
		board = "C_Chat"
	}

	thresholdStr := r.URL.Query().Get("threshold")
	threshold := 0.5 // default
	if thresholdStr != "" {
		if t, err := strconv.ParseFloat(thresholdStr, 64); err == nil {
			threshold = t
		}
	}

	limitStr := r.URL.Query().Get("limit")
	limit := 20 // default
	if limitStr != "" {
		if l, err := strconv.Atoi(limitStr); err == nil {
			limit = l
		}
	}

	mode := r.URL.Query().Get("mode")
	if mode == "" {
		mode = "all"
	}

	rss, err := parser.FetchTrendingArticles(board, threshold, limit, mode)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/rss+xml; charset=utf-8")
	w.Write([]byte(rss))
}

// FetchTrendingArticles fetches recent articles and predicts viral potential
// mode: "viral" (已爆文), "potential" (潛在爆文), "all" (兩者都要)
func (p *PttParser) FetchTrendingArticles(board string, threshold float64, limit int, mode string) (string, error) {
	if board == "" {
		return "", fmt.Errorf("error: board name cannot be empty")
	}

	// Fetch recent articles (last 3 pages to get ~60 articles)
	articles, err := p.fetchRecentArticles(board, 3)
	if err != nil {
		return "", fmt.Errorf("failed to fetch articles: %w", err)
	}

	var viralArticles []TrendingArticle
	var potentialArticles []TrendingArticle

	cutoffTime := time.Now().Add(-15 * time.Minute)
	maxPotentialAge := time.Now().Add(-2 * time.Hour) // 潛在爆文最多看 2 小時內

	for _, article := range articles {
		// 計算推文數
		pushCount := 0
		for _, c := range article.Comments {
			if c.Type == "推" {
				pushCount++
			}
		}
		article.PushCount = pushCount

		// 已爆文: 推文數 >= 100
		if pushCount >= 100 {
			article.IsViral = true
			article.Probability = 1.0
			if mode == "viral" || mode == "all" {
				viralArticles = append(viralArticles, article)
			}
			continue
		}

		// 潛在爆文: 發文 15 分鐘以上、2 小時內，且預測機率高
		if mode == "potential" || mode == "all" {
			if article.PostTime.Before(cutoffTime) && article.PostTime.After(maxPotentialAge) {
				prob, err := p.predictViral(board, &article)
				if err != nil {
					fmt.Printf("Prediction error for %s: %v\n", article.Title, err)
					continue
				}

				article.Probability = prob
				if prob >= threshold {
					potentialArticles = append(potentialArticles, article)
				}
			}
		}
	}

	// 合併結果: 已爆文優先，再加潛在爆文
	var result []TrendingArticle

	// 已爆文按推文數排序
	sortByPushCount(viralArticles)
	result = append(result, viralArticles...)

	// 潛在爆文按機率排序
	sortByProbability(potentialArticles)
	result = append(result, potentialArticles...)

	// 限制數量
	if len(result) > limit {
		result = result[:limit]
	}

	// Generate RSS feed
	return p.generateTrendingFeed(board, threshold, result, mode)
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
		defer resp.Body.Close()

		doc, err := goquery.NewDocumentFromReader(resp.Body)
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

	doc, err := goquery.NewDocumentFromReader(resp.Body)
	if err != nil {
		return err
	}

	// Parse post time
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

// predictViral calls the prediction service
func (p *PttParser) predictViral(board string, article *TrendingArticle) (float64, error) {
	// Calculate 15-minute features
	cutoff := article.PostTime.Add(15 * time.Minute)
	var comments15Min, push15Min, boo15Min int

	for _, c := range article.Comments {
		commentTime := parseCommentTime(article.PostTime, c.Time)
		if commentTime.Before(cutoff) || commentTime.Equal(cutoff) {
			comments15Min++
			if c.Type == "推" {
				push15Min++
			} else if c.Type == "噓" {
				boo15Min++
			}
		}
	}

	// Extract tag type from title
	tagType := extractTagType(article.Title)

	// Check for image
	hasImage := strings.Contains(article.Summary, "imgur.com")

	req := PredictRequest{
		Board:          board,
		Title:          article.Title,
		PostTime:       article.PostTime.Format(time.RFC3339),
		Comments15Min:  comments15Min,
		Push15Min:      push15Min,
		Boo15Min:       boo15Min,
		HourOfDay:      article.PostTime.Hour(),
		DayOfWeek:      int(article.PostTime.Weekday()),
		TitleLength:    len(article.Title),
		HasImage:       hasImage,
		TagType:        tagType,
	}

	return callPredictService(req)
}

// parseCommentTime parses PTT comment time format (MM/DD HH:MM)
func parseCommentTime(postTime time.Time, commentTimeStr string) time.Time {
	commentTimeStr = strings.TrimSpace(commentTimeStr)
	parts := strings.Fields(commentTimeStr)
	if len(parts) < 2 {
		return postTime
	}

	// Extract date and time parts
	dateStr := parts[len(parts)-2]
	timeStr := parts[len(parts)-1]

	dateParts := strings.Split(dateStr, "/")
	timeParts := strings.Split(timeStr, ":")

	if len(dateParts) != 2 || len(timeParts) != 2 {
		return postTime
	}

	month, _ := strconv.Atoi(dateParts[0])
	day, _ := strconv.Atoi(dateParts[1])
	hour, _ := strconv.Atoi(timeParts[0])
	minute, _ := strconv.Atoi(timeParts[1])

	taipeiLoc, _ := time.LoadLocation("Asia/Taipei")
	commentTime := time.Date(postTime.Year(), time.Month(month), day, hour, minute, 0, 0, taipeiLoc)

	// Handle year boundary
	if commentTime.Before(postTime.Add(-24 * time.Hour)) {
		commentTime = commentTime.AddDate(1, 0, 0)
	}

	return commentTime
}

// extractTagType extracts [標籤] from title
func extractTagType(title string) string {
	start := strings.Index(title, "[")
	end := strings.Index(title, "]")
	if start >= 0 && end > start {
		return title[start+1 : end]
	}
	return ""
}

// callPredictService makes HTTP request to prediction service
func callPredictService(req PredictRequest) (float64, error) {
	jsonData, err := json.Marshal(req)
	if err != nil {
		return 0, err
	}

	url := PredictServiceURL + "/predict"
	resp, err := http.Post(url, "application/json", bytes.NewBuffer(jsonData))
	if err != nil {
		return 0, fmt.Errorf("predict service error: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return 0, fmt.Errorf("predict service returned %d: %s", resp.StatusCode, string(body))
	}

	var predictResp PredictResponse
	if err := json.NewDecoder(resp.Body).Decode(&predictResp); err != nil {
		return 0, err
	}

	return predictResp.Probability, nil
}

// sortByProbability sorts articles by probability descending
func sortByProbability(articles []TrendingArticle) {
	for i := 0; i < len(articles)-1; i++ {
		for j := i + 1; j < len(articles); j++ {
			if articles[j].Probability > articles[i].Probability {
				articles[i], articles[j] = articles[j], articles[i]
			}
		}
	}
}

// sortByPushCount sorts articles by push count descending
func sortByPushCount(articles []TrendingArticle) {
	for i := 0; i < len(articles)-1; i++ {
		for j := i + 1; j < len(articles); j++ {
			if articles[j].PushCount > articles[i].PushCount {
				articles[i], articles[j] = articles[j], articles[i]
			}
		}
	}
}

// generateTrendingFeed creates RSS feed from trending articles
func (p *PttParser) generateTrendingFeed(board string, threshold float64, articles []TrendingArticle, mode string) (string, error) {
	modeDesc := map[string]string{
		"viral":     "已爆文",
		"potential": "潛在爆文",
		"all":       "已爆文+潛在爆文",
	}

	feed := &feeds.Feed{
		Title:       fmt.Sprintf("PTT %s %s", board, modeDesc[mode]),
		Link:        &feeds.Link{Href: fmt.Sprintf("https://www.ptt.cc/bbs/%s/index.html", board)},
		Description: fmt.Sprintf("PTT %s 熱門文章 (預測門檻: %.0f%%)", board, threshold*100),
		Author:      &feeds.Author{Name: "PTT Viral Predictor"},
		Created:     time.Now(),
	}

	for _, article := range articles {
		// Convert to BePTT URL for better mobile reading
		bepttURL := strings.Replace(article.Url, "www.ptt.cc/bbs", "bbs.beptt.cc", -1)

		// 標題格式: 已爆文顯示推文數，潛在爆文顯示預測機率
		var title string
		if article.IsViral {
			title = fmt.Sprintf("[🔥%d推] %s", article.PushCount, article.Title)
		} else {
			title = fmt.Sprintf("[📈%.0f%%] %s", article.Probability*100, article.Title)
		}

		feed.Add(&feeds.Item{
			Title:       title,
			Link:        &feeds.Link{Href: bepttURL},
			Description: article.Summary,
			Created:     article.PostTime,
		})
	}

	return feed.ToRss()
}
