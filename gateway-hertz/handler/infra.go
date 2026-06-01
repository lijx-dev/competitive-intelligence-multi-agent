// Package handler — 可观测性数据代理
package handler

import (
	"context"
	"io"
	"net/http"
	"strings"

	"github.com/cloudwego/hertz/pkg/app"
	"github.com/cloudwego/hertz/pkg/protocol/consts"
)

// GetDecisionLogs GET /api/v1/infra/decision-logs → http://backend/api/v1/infra/decision-logs
func GetDecisionLogs(backendURL string) app.HandlerFunc {
	return func(ctx context.Context, c *app.RequestContext) {
		q := c.QueryArgs().String()
		url := backendURL + "/api/v1/infra/decision-logs"
		if q != "" {
			url += "?" + q
		}
		resp, err := http.Get(url)
		if err != nil {
			c.AbortWithStatusJSON(consts.StatusBadGateway, map[string]string{"error": err.Error()})
			return
		}
		defer resp.Body.Close()
		body, _ := io.ReadAll(resp.Body)
		c.Data(resp.StatusCode, "application/json", body)
	}
}

// GetTokenUsage GET /api/v1/infra/token-usage → http://backend/api/v1/infra/token-usage
func GetTokenUsage(backendURL string) app.HandlerFunc {
	return func(ctx context.Context, c *app.RequestContext) {
		q := c.QueryArgs().String()
		url := backendURL + "/api/v1/infra/token-usage"
		if q != "" {
			url += "?" + q
		}
		resp, err := http.Get(url)
		if err != nil {
			c.AbortWithStatusJSON(consts.StatusBadGateway, map[string]string{"error": err.Error()})
			return
		}
		defer resp.Body.Close()
		body, _ := io.ReadAll(resp.Body)
		c.Data(resp.StatusCode, "application/json", body)
	}
}

// ListReports GET /api/v1/reports → http://backend/analysis/records
func ListReports(backendURL string) app.HandlerFunc {
	return func(ctx context.Context, c *app.RequestContext) {
		q := c.QueryArgs().String()
		url := backendURL + "/analysis/records"
		if q != "" {
			url += "?" + q
		}
		resp, err := http.Get(url)
		if err != nil {
			c.AbortWithStatusJSON(consts.StatusBadGateway, map[string]string{"error": err.Error()})
			return
		}
		defer resp.Body.Close()
		body, _ := io.ReadAll(resp.Body)
		c.Data(resp.StatusCode, "application/json", body)
	}
}

// GetReportByID GET /api/v1/reports/:id → http://backend/analysis/records/:id
func GetReportByID(backendURL string) app.HandlerFunc {
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

// GenericAPIProxy 通用反向代理：将 /api/v1/* 或 /api/* 转发到后端同名路径
// 用于覆盖 RAG、进化、配置、Ontology 等未显式注册的路由
func GenericAPIProxy(backendURL string) app.HandlerFunc {
	return func(ctx context.Context, c *app.RequestContext) {
		path := string(c.Request.Path())
		method := string(c.Request.Method())

		var body io.Reader
		if method == "POST" || method == "PUT" || method == "PATCH" {
			body = strings.NewReader(string(c.Request.Body()))
		}

		proxyURL := backendURL + path
		if q := c.QueryArgs().String(); q != "" {
			proxyURL += "?" + q
		}

		req, err := http.NewRequestWithContext(ctx, method, proxyURL, body)
		if err != nil {
			c.AbortWithStatusJSON(consts.StatusInternalServerError, map[string]string{"error": err.Error()})
			return
		}

		// 透传 Content-Type
		contentType := string(c.Request.Header.ContentType())
		if contentType != "" {
			req.Header.Set("Content-Type", contentType)
		}

		resp, err := http.DefaultClient.Do(req)
		if err != nil {
			c.AbortWithStatusJSON(consts.StatusBadGateway, map[string]string{"error": "backend unreachable: " + err.Error()})
			return
		}
		defer resp.Body.Close()

		respBody, _ := io.ReadAll(resp.Body)
		c.Data(resp.StatusCode, resp.Header.Get("Content-Type"), respBody)
	}
}
