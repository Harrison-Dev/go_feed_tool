package cache

import (
	"sync"
	"time"

	"github.com/gorilla/feeds"
)

type CacheKey struct {
	Type    string // "plurk_search", "plurk_top", "ptt_search"
	Keyword string
}

type CacheEntry struct {
	Feed      *feeds.Feed
	CreatedAt time.Time
}

type FeedCache struct {
	mu       sync.RWMutex
	items    map[CacheKey]CacheEntry
	maxItems int
	keys     []CacheKey // 用於追蹤最舊的項目
}

func NewFeedCache(maxItems int) *FeedCache {
	return &FeedCache{
		items:    make(map[CacheKey]CacheEntry),
		maxItems: maxItems,
		keys:     make([]CacheKey, 0),
	}
}

func (c *FeedCache) Set(key CacheKey, feed *feeds.Feed) {
	c.mu.Lock()
	defer c.mu.Unlock()

	// 如果已達到最大容量且這是新的key
	if len(c.items) >= c.maxItems && c.items[key].Feed == nil {
		// 移除最舊的項目
		oldestKey := c.keys[0]
		delete(c.items, oldestKey)
		c.keys = c.keys[1:]
	}

	c.items[key] = CacheEntry{
		Feed:      feed,
		CreatedAt: time.Now(),
	}
	c.keys = append(c.keys, key)
}

func (c *FeedCache) Get(key CacheKey) (*feeds.Feed, bool) {
	c.mu.RLock()
	defer c.mu.RUnlock()

	entry, exists := c.items[key]
	if !exists {
		return nil, false
	}
	return entry.Feed, true
}
