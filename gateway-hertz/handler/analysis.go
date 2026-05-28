// Package handler — 分析任务代理（含 SSE 特殊处理）
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

// ProxyAnalysis 代理分析请求到 FastAPI 后端
// POST /api/v1/analysis → http://backend/analyze
func ProxyAnalysis(backendURL string) app.HandlerFunc {
	return func(ctx context.Context, c *app.RequestContext) {
		body := c.Request.Body()
		proxyReq, err := http.NewRequestWithContext(ctx, "POST", backendURL+"/analyze", strings.NewReader(string(body)))
		if err != nil {
			c.AbortWithStatusJSON(consts.StatusInternalServerError, map[string]string{"error": err.Error()})
			return
		}
		proxyReq.Header.Set("Content-Type", "application/json")
		resp, err := http.DefaultClient.Do(proxyReq)
		if err != nil {
			c.AbortWithStatusJSON(consts.StatusBadGateway, map[string]string{"error": "backend unreachable: " + err.Error()})
			return
		}
		defer resp.Body.Close()

		respBody, _ := io.ReadAll(resp.Body)
		c.Data(resp.StatusCode, resp.Header.Get("Content-Type"), respBody)
	}
}

// ProxySSEAnalysis 代理 SSE 流式分析（POST → http://backend/analyze/stream）
// 关键：禁用响应缓冲，逐块转发事件到客户端
func ProxySSEAnalysis(backendURL string) app.HandlerFunc {
	return func(ctx context.Context, c *app.RequestContext) {
		body := c.Request.Body()
		proxyReq, err := http.NewRequestWithContext(ctx, "POST", backendURL+"/analyze/stream", strings.NewReader(string(body)))
		if err != nil {
			c.AbortWithStatusJSON(consts.StatusInternalServerError, map[string]string{"error": err.Error()})
			return
		}
		proxyReq.Header.Set("Content-Type", "application/json")
		proxyReq.Header.Set("Accept", "text/event-stream")

		resp, err := http.DefaultClient.Do(proxyReq)
		if err != nil {
			c.AbortWithStatusJSON(consts.StatusBadGateway, map[string]string{"error": "backend unreachable: " + err.Error()})
			return
		}
		defer resp.Body.Close()

		// SSE 响应头
		c.SetStatusCode(resp.StatusCode)
		c.Response.Header.Set("Content-Type", "text/event-stream")
		c.Response.Header.Set("Cache-Control", "no-cache")
		c.Response.Header.Set("Connection", "keep-alive")
		c.Response.Header.Set("X-Accel-Buffering", "no")

		// 逐块转发（关键：不能缓冲整个 SSE 流）
		buf := make([]byte, 4096)
		for {
			n, readErr := resp.Body.Read(buf)
			if n > 0 {
				c.Response.BodyWriter().Write(buf[:n])
				c.Response.Flush()
			}
			if readErr != nil {
				if readErr != io.EOF {
					log.Printf("[SSE] stream read error: %v", readErr)
				}
				break
			}
		}
	}
}

// GetAnalysisStatus GET /api/v1/analysis/:id/status → 查询分析状态
func GetAnalysisStatus(backendURL string) app.HandlerFunc {
	return func(ctx context.Context, c *app.RequestContext) {
		id := c.Param("id")
		resp, err := http.Get(backendURL + "/analysis/records/" + id)
		if err != nil {
			c.AbortWithStatusJSON(consts.StatusBadGateway, map[string]string{"error": err.Error()})
			return
		}
		defer resp.Body.Close()
		body, _ := io.ReadAll(resp.Body)
		c.Data(resp.StatusCode, "application/json", body)
	}
}
