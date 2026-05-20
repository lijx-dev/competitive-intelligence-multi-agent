// Package config — 网关配置（全部通过环境变量读取）
package config

import "os"

type Config struct {
	Port      string
	BackendURL string
	CORSOrigins string
	RateLimitRPS int
}

// Load 从环境变量加载配置，缺失时回退到默认值
func Load() *Config {
	return &Config{
		Port:         getEnv("HERTZ_PORT", "8080"),
		BackendURL:   getEnv("BACKEND_URL", "http://localhost:8000"),
		CORSOrigins:  getEnv("CORS_ORIGINS", "*"),
		RateLimitRPS: getEnvInt("RATE_LIMIT_RPS", 100),
	}
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func getEnvInt(key string, fallback int) int {
	v := os.Getenv(key)
	if v == "" {
		return fallback
	}
	var n int
	for _, c := range v {
		if c < '0' || c > '9' {
			return fallback
		}
		n = n*10 + int(c-'0')
	}
	return n
}
