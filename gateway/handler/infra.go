// Package handler — 可观测性数据代理
package handler

import (
	"context"
	"io"
	"net/http"

	"github.com/cloudwego/hertz/pkg/app"
	"github.com/cloudwego/hertz/pkg/protocol/consts"
)

// GetDecisionLogs GET /api/v1/infra/decision-logs → http://backend/api/infra/agent-logs
func GetDecisionLogs(backendURL string) app.HandlerFunc {
	return func(ctx context.Context, c *app.RequestContext) {
		q := c.QueryArgs().String()
		url := backendURL + "/api/infra/agent-logs"
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

// GetTokenUsage GET /api/v1/infra/token-usage → http://backend/api/infra/token/report
func GetTokenUsage(backendURL string) app.HandlerFunc {
	return func(ctx context.Context, c *app.RequestContext) {
		q := c.QueryArgs().String()
		url := backendURL + "/api/infra/token/report"
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
