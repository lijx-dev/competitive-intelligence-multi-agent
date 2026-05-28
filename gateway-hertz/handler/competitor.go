// Package handler — 竞品管理代理
package handler

import (
	"context"
	"io"
	"net/http"
	"strings"

	"github.com/cloudwego/hertz/pkg/app"
	"github.com/cloudwego/hertz/pkg/protocol/consts"
)

// ListCompetitors GET /api/v1/competitors → http://backend/competitors/all
func ListCompetitors(backendURL string) app.HandlerFunc {
	return doProxy("GET", backendURL+"/competitors/all", false)
}

// CreateCompetitor POST /api/v1/competitors → http://backend/competitors
func CreateCompetitor(backendURL string) app.HandlerFunc {
	return doProxy("POST", backendURL+"/competitors", true)
}

// DeleteCompetitor DELETE /api/v1/competitors/:id → http://backend/competitors/:id
func DeleteCompetitor(backendURL string) app.HandlerFunc {
	return func(ctx context.Context, c *app.RequestContext) {
		id := c.Param("id")
		req, _ := http.NewRequestWithContext(ctx, "DELETE", backendURL+"/competitors/"+id, nil)
		resp, err := http.DefaultClient.Do(req)
		if err != nil {
			c.AbortWithStatusJSON(consts.StatusBadGateway, map[string]string{"error": err.Error()})
			return
		}
		defer resp.Body.Close()
		body, _ := io.ReadAll(resp.Body)
		c.Data(resp.StatusCode, "application/json", body)
	}
}

// doProxy 通用代理封装
func doProxy(method, url string, hasBody bool) app.HandlerFunc {
	return func(ctx context.Context, c *app.RequestContext) {
		var body io.Reader
		if hasBody {
			body = strings.NewReader(string(c.Request.Body()))
		}
		req, err := http.NewRequestWithContext(ctx, method, url, body)
		if err != nil {
			c.AbortWithStatusJSON(consts.StatusInternalServerError, map[string]string{"error": err.Error()})
			return
		}
		if hasBody {
			req.Header.Set("Content-Type", "application/json")
		}
		resp, err := http.DefaultClient.Do(req)
		if err != nil {
			c.AbortWithStatusJSON(consts.StatusBadGateway, map[string]string{"error": err.Error()})
			return
		}
		defer resp.Body.Close()
		respBody, _ := io.ReadAll(resp.Body)
		c.Data(resp.StatusCode, "application/json", respBody)
	}
}
