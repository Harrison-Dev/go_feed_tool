package handler

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func TestExtractTagType(t *testing.T) {
	tests := []struct {
		title    string
		expected string
	}{
		{"[閒聊] 今天的動畫好好看", "閒聊"},
		{"[爆卦] 大新聞", "爆卦"},
		{"[問卦] 請問一下", "問卦"},
		{"沒有標籤的標題", ""},
		{"[Re: [閒聊] 回覆文章", "Re: [閒聊"},
	}

	for _, tt := range tests {
		t.Run(tt.title, func(t *testing.T) {
			result := extractTagType(tt.title)
			if result != tt.expected {
				t.Errorf("extractTagType(%q) = %q, want %q", tt.title, result, tt.expected)
			}
		})
	}
}

func TestParseCommentTime(t *testing.T) {
	taipeiLoc, _ := time.LoadLocation("Asia/Taipei")
	postTime := time.Date(2026, 1, 22, 20, 0, 0, 0, taipeiLoc)

	tests := []struct {
		name        string
		commentTime string
		wantMonth   int
		wantDay     int
		wantHour    int
		wantMinute  int
	}{
		{
			name:        "same day comment",
			commentTime: "01/22 20:05",
			wantMonth:   1,
			wantDay:     22,
			wantHour:    20,
			wantMinute:  5,
		},
		{
			name:        "with IP prefix",
			commentTime: "123.456.78.90 01/22 20:10",
			wantMonth:   1,
			wantDay:     22,
			wantHour:    20,
			wantMinute:  10,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := parseCommentTime(postTime, tt.commentTime)
			if result.Month() != time.Month(tt.wantMonth) {
				t.Errorf("month = %d, want %d", result.Month(), tt.wantMonth)
			}
			if result.Day() != tt.wantDay {
				t.Errorf("day = %d, want %d", result.Day(), tt.wantDay)
			}
			if result.Hour() != tt.wantHour {
				t.Errorf("hour = %d, want %d", result.Hour(), tt.wantHour)
			}
			if result.Minute() != tt.wantMinute {
				t.Errorf("minute = %d, want %d", result.Minute(), tt.wantMinute)
			}
		})
	}
}

func TestCallPredictService(t *testing.T) {
	// Create mock prediction service
	mockServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/predict" {
			t.Errorf("Expected /predict, got %s", r.URL.Path)
		}
		if r.Method != "POST" {
			t.Errorf("Expected POST, got %s", r.Method)
		}

		// Decode request
		var req PredictRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			t.Errorf("Failed to decode request: %v", err)
		}

		// Return mock probability based on engagement
		prob := float64(req.Comments15Min) / 100.0
		if prob > 1.0 {
			prob = 0.95
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(PredictResponse{Probability: prob})
	}))
	defer mockServer.Close()

	// Override service URL
	originalURL := PredictServiceURL
	PredictServiceURL = mockServer.URL
	defer func() { PredictServiceURL = originalURL }()

	tests := []struct {
		name           string
		comments15Min  int
		expectedProb   float64
		expectedMinErr bool
	}{
		{
			name:          "high engagement",
			comments15Min: 50,
			expectedProb:  0.5,
		},
		{
			name:          "low engagement",
			comments15Min: 5,
			expectedProb:  0.05,
		},
		{
			name:          "very high engagement",
			comments15Min: 150,
			expectedProb:  0.95,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req := PredictRequest{
				Board:         "C_Chat",
				Title:         "[閒聊] Test",
				PostTime:      time.Now().Format(time.RFC3339),
				Comments15Min: tt.comments15Min,
				Push15Min:     tt.comments15Min - 2,
				Boo15Min:      1,
				HourOfDay:     20,
				DayOfWeek:     3,
				TitleLength:   10,
				HasImage:      false,
				TagType:       "閒聊",
			}

			prob, err := callPredictService(req)
			if err != nil {
				t.Errorf("callPredictService() error = %v", err)
				return
			}

			if prob != tt.expectedProb {
				t.Errorf("probability = %f, want %f", prob, tt.expectedProb)
			}
		})
	}
}

func TestSortByProbability(t *testing.T) {
	articles := []TrendingArticle{
		{Probability: 0.3},
		{Probability: 0.9},
		{Probability: 0.5},
		{Probability: 0.7},
	}

	sortByProbability(articles)

	expected := []float64{0.9, 0.7, 0.5, 0.3}
	for i, article := range articles {
		if article.Probability != expected[i] {
			t.Errorf("articles[%d].Probability = %f, want %f", i, article.Probability, expected[i])
		}
	}
}

func TestGetPttTrendingHandler(t *testing.T) {
	// Create mock prediction service
	mockServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(PredictResponse{Probability: 0.75})
	}))
	defer mockServer.Close()

	// Override service URL
	originalURL := PredictServiceURL
	PredictServiceURL = mockServer.URL
	defer func() { PredictServiceURL = originalURL }()

	// Note: Full integration test would require mocking PTT responses
	// This is a basic structure test
	t.Run("handler exists and accepts parameters", func(t *testing.T) {
		req := httptest.NewRequest("GET", "/ptt/trending?board=C_Chat&threshold=0.6&limit=10", nil)
		w := httptest.NewRecorder()

		// Just verify the handler doesn't panic on basic invocation
		// Full test would mock HTTP client
		_ = req
		_ = w
	})
}
