// Package main — 竞品分析系统 API 网关 (CloudWeGo Hertz)
//
// 路由代理到 FastAPI 后端，承载飞书 Webhook 回调。
// 展示字节技术生态理解：Hertz + CloudWeGo 开源生态。
package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	"gateway/config"
	"gateway/handler"
	"gateway/middleware"

	"github.com/cloudwego/hertz/pkg/app"
	"github.com/cloudwego/hertz/pkg/app/server"
)

const banner = `
   ┌───────────────────────────────────────────────┐
   │  🔍 竞品分析多Agent系统 · API 网关              │
   │  CloudWeGo Hertz · 字节跳动开源生态              │
   │  Version 1.0.0 · 2026 ByteDance AI Challenge │
   └───────────────────────────────────────────────┘
`

func main() {
	fmt.Println(banner)

	cfg := config.Load()

	h := server.Default(
		server.WithHostPorts(":"+cfg.Port),
		server.WithReadTimeout(60*time.Second),
		server.WithWriteTimeout(120*time.Second),
		server.WithIdleTimeout(30*time.Second),
	)

	// ── 全局中间件 ──
	h.Use(middleware.CORS(cfg))
	h.Use(middleware.RequestLogger())
	h.Use(middleware.RateLimiter(cfg.RateLimitRPS))

	backend := cfg.BackendURL

	// ── 健康检查 ──
	h.GET("/health", handler.HealthHandler(backend))

	// ── 分析 API ──
	v1 := h.Group("/api/v1")
	{
		v1.POST("/analysis", handler.ProxyAnalysis(backend))
		v1.POST("/analysis/stream", handler.ProxySSEAnalysis(backend))
		v1.GET("/analysis/:id/status", handler.GetAnalysisStatus(backend))
	}

	// ── 竞品管理 API ──
	{
		v1.GET("/competitors", handler.ListCompetitors(backend))
		v1.POST("/competitors", handler.CreateCompetitor(backend))
		v1.DELETE("/competitors/:id", handler.DeleteCompetitor(backend))
	}

	// ── 报告 API ──
	{
		v1.GET("/reports", handler.ListReports(backend))
		v1.GET("/reports/:id", handler.GetReportByID(backend))
	}

	// ── 飞书 Webhook ──
	{
		v1.POST("/feishu/test", handler.FeishuTest(backend))
	}
	h.POST("/webhook/feishu/feedback", handler.FeishuFeedback(backend))

	// ── 可观测性 API ──
	{
		v1.GET("/infra/decision-logs", handler.GetDecisionLogs(backend))
		v1.GET("/infra/token-usage", handler.GetTokenUsage(backend))
	}

	// ── 路由表打印 ──
	h.GET("/routes", func(ctx context.Context, c *app.RequestContext) {
		c.JSON(200, map[string]interface{}{
			"routes": []string{
				"GET  /health",
				"GET  /routes",
				"POST /api/v1/analysis",
				"POST /api/v1/analysis/stream",
				"GET  /api/v1/analysis/:id/status",
				"GET  /api/v1/competitors",
				"POST /api/v1/competitors",
				"DELETE /api/v1/competitors/:id",
				"GET  /api/v1/reports",
				"GET  /api/v1/reports/:id",
				"POST /api/v1/feishu/test",
				"POST /webhook/feishu/feedback",
				"GET  /api/v1/infra/decision-logs",
				"GET  /api/v1/infra/token-usage",
			},
			"backend":  backend,
			"framework": "CloudWeGo Hertz v0.9",
		})
	})

	// ── 优雅退出 ──
	go func() {
		sigCh := make(chan os.Signal, 1)
		signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
		<-sigCh
		log.Println("[GATEWAY] shutting down...")
		h.Shutdown(context.Background())
	}()

	log.Printf("[GATEWAY] 🚀 CloudWeGo Hertz listening on :%s (backend: %s)", cfg.Port, backend)
	h.Spin()
}
