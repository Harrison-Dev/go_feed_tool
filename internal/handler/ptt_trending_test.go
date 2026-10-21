package handler

import (
	"encoding/xml"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

type trendingTransport func(*http.Request) (*http.Response, error)

func (f trendingTransport) RoundTrip(r *http.Request) (*http.Response, error) { return f(r) }

func TestTrendingThresholdSortingAndLimit(t *testing.T) {
	comments := func(n int) []Comment {
		cs := make([]Comment, n)
		for i := range cs {
			cs[i].Type = "推"
		}
		return append(cs, Comment{Type: "噓"}, Comment{Type: "→"})
	}
	now := time.Now()
	articles := []TrendingArticle{
		{Article: Article{Url: "49"}, PostTime: now, Comments: comments(49)},
		{Article: Article{Url: "50"}, PostTime: now.Add(-24 * time.Hour), Comments: comments(50)},
		{Article: Article{Url: "100"}, PostTime: now.Add(-time.Hour), Comments: comments(100)},
		{Article: Article{Url: "100"}, PostTime: now.Add(-time.Hour), Comments: comments(100)},
	}
	got := filterTrendingArticles(articles, 20)
	if len(got) != 2 || got[0].Url != "100" || got[1].Url != "50" || got[1].PushCount != 50 {
		t.Fatalf("unexpected selection: %+v", got)
	}
	if got := filterTrendingArticles(articles, 1); len(got) != 1 || got[0].Url != "100" {
		t.Fatalf("limit/order: %+v", got)
	}
	if got := filterTrendingArticles(articles, -1); len(got) != 1 {
		t.Fatalf("invalid limit should be bounded: %d", len(got))
	}
}

func TestTrendingEndpointKeepsLegacyURLsWithoutPrediction(t *testing.T) {
	old := http.DefaultTransport
	defer func() { http.DefaultTransport = old }()
	http.DefaultTransport = trendingTransport(func(r *http.Request) (*http.Response, error) {
		if r.URL.Host != "www.ptt.cc" {
			t.Fatalf("unexpected non-PTT request: %s", r.URL)
		}
		if r.Header.Get("Cookie") != "over18=1" {
			t.Fatal("missing over18 cookie")
		}
		var html string
		switch r.URL.Path {
		case "/bbs/C_Chat/index.html":
			for _, n := range []int{49, 50, 100} {
				html += fmt.Sprintf(`<div class="r-ent"><div class="nrec"><span>%d</span></div><div class="title"><a href="/bbs/C_Chat/M.%d.html">post-%d</a></div></div>`, n, n, n)
			}
		case "/bbs/C_Chat/M.49.html", "/bbs/C_Chat/M.50.html", "/bbs/C_Chat/M.100.html":
			var n int
			fmt.Sscanf(r.URL.Path, "/bbs/C_Chat/M.%d.html", &n)
			html = `<div id="main-content"><div class="article-metaline"><span class="article-meta-value">author</span></div><div class="article-metaline"><span class="article-meta-value">Fri Oct 2 15:04:05 2026</span></div>body`
			for i := 0; i < n; i++ {
				html += `<div class="push"><span class="push-tag">推 </span><span class="push-userid">user</span><span class="push-content">: good</span></div>`
			}
			html += `<div class="push"><span class="push-tag">噓 </span></div><div class="push"><span class="push-tag">→ </span></div></div>`
		default:
			t.Fatalf("unexpected path %s", r.URL.Path)
		}
		return &http.Response{StatusCode: 200, Body: io.NopCloser(strings.NewReader(html)), Header: make(http.Header)}, nil
	})
	for _, query := range []string{"", "?mode=potential&threshold=0.99", "?mode=viral&limit=-1", "?mode=all&limit=1"} {
		t.Run(query, func(t *testing.T) {
			w := httptest.NewRecorder()
			GetPttTrending(w, httptest.NewRequest("GET", "/ptt/trending"+query, nil))
			if w.Code != 200 {
				t.Fatalf("status %d: %s", w.Code, w.Body.String())
			}
			var rss struct {
				Channel struct {
					Title string `xml:"title"`
					Items []struct {
						Title string `xml:"title"`
						Link  string `xml:"link"`
					} `xml:"item"`
				} `xml:"channel"`
			}
			if err := xml.Unmarshal(w.Body.Bytes(), &rss); err != nil {
				t.Fatal(err)
			}
			expected := 2
			if strings.Contains(query, "limit=") {
				expected = 1
			}
			if len(rss.Channel.Items) != expected {
				t.Fatalf("got %d items, want %d", len(rss.Channel.Items), expected)
			}
			if !strings.Contains(rss.Channel.Title, "50 推以上") {
				t.Fatal(rss.Channel.Title)
			}
			if rss.Channel.Items[0].Title != "[50推] post-50" {
				t.Fatal(rss.Channel.Items[0].Title)
			}
			if !strings.HasPrefix(rss.Channel.Items[0].Link, "https://bbs.beptt.cc/") {
				t.Fatal(rss.Channel.Items[0].Link)
			}
		})
	}
}

func TestTrendingUpstreamError(t *testing.T) {
	p := NewPttParser(&http.Client{Transport: trendingTransport(func(*http.Request) (*http.Response, error) {
		return &http.Response{StatusCode: 503, Body: io.NopCloser(strings.NewReader("unavailable"))}, nil
	})})
	if _, err := p.FetchTrendingArticles("C_Chat", 20); err == nil {
		t.Fatal("expected upstream status error")
	}
	if _, err := p.FetchTrendingArticles("", 20); err == nil {
		t.Fatal("expected empty board error")
	}
}
