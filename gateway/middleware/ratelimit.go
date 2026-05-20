// Package middleware — Token Bucket 限流中间件
package middleware

import (
	"context"
	"sync"
	"time"

	"github.com/cloudwego/hertz/pkg/app"
	"github.com/cloudwego/hertz/pkg/protocol/consts"
)

// TokenBucket 简易令牌桶实现
type TokenBucket struct {
	rate     int       // 每秒补充令牌数
	capacity int       // 桶容量
	tokens   float64   // 当前令牌数
	last     time.Time // 上次补充时间
	mu       sync.Mutex
}

func NewTokenBucket(rate, capacity int) *TokenBucket {
	return &TokenBucket{
		rate:     rate,
		capacity: capacity,
		tokens:   float64(capacity),
		last:     time.Now(),
	}
}

func (tb *TokenBucket) Allow() bool {
	tb.mu.Lock()
	defer tb.mu.Unlock()

	now := time.Now()
	elapsed := now.Sub(tb.last).Seconds()
	tb.tokens += elapsed * float64(tb.rate)
	if tb.tokens > float64(tb.capacity) {
		tb.tokens = float64(tb.capacity)
	}
	tb.last = now

	if tb.tokens >= 1 {
		tb.tokens--
		return true
	}
	return false
}

// RateLimiter 返回限流中间件
func RateLimiter(rps int) app.HandlerFunc {
	bucket := NewTokenBucket(rps, rps*2)
	return func(ctx context.Context, c *app.RequestContext) {
		if !bucket.Allow() {
			c.AbortWithStatusJSON(consts.StatusTooManyRequests, map[string]string{
				"error": "rate limit exceeded, please retry later",
			})
			return
		}
		c.Next(ctx)
	}
}
