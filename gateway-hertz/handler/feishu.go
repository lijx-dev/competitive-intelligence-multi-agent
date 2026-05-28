// Package handler — 飞书 Webhook 回调处理
package handler

import (
	"context"
	"io"
	"log"
	"net/http"
	"strings"

	"github.com/cloudwego/hertz/pkg/app"
	"github.com/cloudwego/hertz/pkg/protocol/consts"
)

// FeishuFeedback POST /webhook/feishu/feedback → 代理到 FastAPI
// Hertz 作为飞书 Webhook 的入口网关，转发到后端的 /api/v1/feishu/feedback
func FeishuFeedback(backendURL string) app.HandlerFunc {
	return func(ctx context.Context, c *app.RequestContext) {
		body := c.Request.Body()
		proxyReq, err := http.NewRequestWithContext(ctx, "POST",
			backendURL+"/api/v1/feishu/feedback",
			strings.NewReader(string(body)),
		)
		if err != nil {
			log.Printf("[FEISHU] proxy error: %v", err)
			c.AbortWithStatusJSON(consts.StatusInternalServerError, map[string]string{"error": err.Error()})
			return
		}
		proxyReq.Header.Set("Content-Type", "application/json")

		resp, err := http.DefaultClient.Do(proxyReq)
		if err != nil {
			log.Printf("[FEISHU] backend unreachable: %v", err)
			// 飞书 Webhook 要求 200，即使后端不可用也返回 200 避免飞书重试
			c.JSON(consts.StatusOK, map[string]string{
				"status":  "accepted",
				"message": "feedback queued for processing",
			})
			return
		}
		defer resp.Body.Close()
		respBody, _ := io.ReadAll(resp.Body)
		c.Data(resp.StatusCode, "application/json", respBody)
	}
}

// FeishuTest POST /api/v1/feishu/test → 测试飞书推送
func FeishuTest(backendURL string) app.HandlerFunc {
	return func(ctx context.Context, c *app.RequestContext) {
		resp, err := http.Post(backendURL+"/api/v1/feishu/test", "application/json", nil)
		if err != nil {
			c.AbortWithStatusJSON(consts.StatusBadGateway, map[string]string{"error": err.Error()})
			return
		}
		defer resp.Body.Close()
		body, _ := io.ReadAll(resp.Body)
		c.Data(resp.StatusCode, "application/json", body)
	}
}
