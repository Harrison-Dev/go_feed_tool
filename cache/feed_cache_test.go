package cache

import (
	"testing"
	"time"

	"github.com/gorilla/feeds"
	"github.com/stretchr/testify/assert"
)

func TestFeedCache(t *testing.T) {
	cache := NewFeedCache(2) // 設置較小的容量以便測試

	// 創建測試用的 feed
	feed1 := &feeds.Feed{
		Title:       "Test Feed 1",
		Description: "Test Description 1",
		Created:     time.Now(),
	}
	feed2 := &feeds.Feed{
		Title:       "Test Feed 2",
		Description: "Test Description 2",
		Created:     time.Now(),
	}
	feed3 := &feeds.Feed{
		Title:       "Test Feed 3",
		Description: "Test Description 3",
		Created:     time.Now(),
	}

	t.Run("基本的設置和獲取", func(t *testing.T) {
		key1 := CacheKey{Type: "test", Keyword: "key1"}
		cache.Set(key1, feed1)

		result, exists := cache.Get(key1)
		assert.True(t, exists)
		assert.Equal(t, feed1.Title, result.Title)
	})

	t.Run("容量限制測試", func(t *testing.T) {
		key1 := CacheKey{Type: "test", Keyword: "key1"}
		key2 := CacheKey{Type: "test", Keyword: "key2"}
		key3 := CacheKey{Type: "test", Keyword: "key3"}

		// 添加三個項目到容量為2的緩存中
		cache.Set(key1, feed1)
		cache.Set(key2, feed2)
		cache.Set(key3, feed3)

		// 檢查最舊的項目是否被移除
		_, exists := cache.Get(key1)
		assert.False(t, exists, "最舊的項目應該被移除")

		// 檢查新的項目是否存在
		result2, exists := cache.Get(key2)
		assert.True(t, exists)
		assert.Equal(t, feed2.Title, result2.Title)

		result3, exists := cache.Get(key3)
		assert.True(t, exists)
		assert.Equal(t, feed3.Title, result3.Title)
	})

	t.Run("時間戳保持不變", func(t *testing.T) {
		key := CacheKey{Type: "test", Keyword: "time_test"}
		originalTime := time.Now()
		feed := &feeds.Feed{
			Title:   "Time Test",
			Created: originalTime,
		}

		cache.Set(key, feed)
		time.Sleep(time.Millisecond * 100) // 等待一小段時間

		result, exists := cache.Get(key)
		assert.True(t, exists)
		assert.Equal(t, originalTime, result.Created)
	})
}
