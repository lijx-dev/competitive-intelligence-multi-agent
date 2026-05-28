// Package middleware — 请求日志中间件
package middleware

import (
	"context"
	"log"
	"time"

	"github.com/cloudwego/hertz/pkg/app"
)

// RequestLogger 记录每个请求的方法、路径、耗时、状态码
func RequestLogger() app.HandlerFunc {
	return func(ctx context.Context, c *app.RequestContext) {
		start := time.Now()
		c.Next(ctx)
		duration := time.Since(start)
		log.Printf("[GATEWAY] %s %s → %d (%dms)",
			string(c.Method()),
			string(c.Path()),
			c.Response.StatusCode(),
			duration.Milliseconds(),
		)
	}
}
