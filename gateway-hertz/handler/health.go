// Package handler — 健康检查
package handler

import (
	"context"
	"net/http"
	"time"

	"github.com/cloudwego/hertz/pkg/app"
)

// HealthResponse 健康检查响应体
type HealthResponse struct {
	Status    string `json:"status"`
	Timestamp string `json:"timestamp"`
	Gateway   string `json:"gateway"`
}

// HealthHandler GET /health — 网关 + 后端双重健康检查
func HealthHandler(backendURL string) app.HandlerFunc {
	return func(ctx context.Context, c *app.RequestContext) {
		gatewayOK := true
		backendOK := false

		// 检查后端 FastAPI 健康状态
		client := &http.Client{Timeout: 3 * time.Second}
		resp, err := client.Get(backendURL + "/health")
		if err == nil && resp.StatusCode == 200 {
			backendOK = true
			resp.Body.Close()
		}

		c.JSON(200, map[string]interface{}{
			"status":    "ok",
			"timestamp": time.Now().UTC().Format(time.RFC3339),
			"gateway": map[string]interface{}{
				"version":  "1.0.0",
				"healthy":  gatewayOK,
				"backend":  backendOK,
				"framework": "CloudWeGo Hertz",
			},
		})
	}
}
