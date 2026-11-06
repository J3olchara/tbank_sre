package taskboard

import (
	"bytes"
	"encoding/json"
	"log/slog"
	"net/http/httptest"
	"strings"
	"testing"

	"tbank-sre/taskboard/internal/logging"
)

func TestHTTPLogSchemaSeverityAndCorrelation(t *testing.T) {
	previous := slog.Default()
	defer slog.SetDefault(previous)
	var output bytes.Buffer
	slog.SetDefault(logging.New(&output, slog.LevelInfo, "taskboard"))
	handler := NewHandler(nil, t.TempDir(), NewMetrics())
	for _, path := range []string{"/healthz", "/api/tasks/invalid"} {
		req := httptest.NewRequest("GET", path+"?token=must-not-log", nil)
		req.Header.Set("X-Request-ID", "untrusted-client-value")
		rec := httptest.NewRecorder()
		handler.ServeHTTP(rec, req)
		var event map[string]any
		if err := json.Unmarshal(output.Bytes(), &event); err != nil {
			t.Fatal(err)
		}
		if event["request.id"] != rec.Header().Get("X-Request-ID") || event["request.id"] == "untrusted-client-value" {
			t.Fatal("invalid request correlation")
		}
		if event["timestamp"] == nil || event["message"] != "http_request" || event["service.name"] != "taskboard" {
			t.Fatal(event)
		}
		if event["duration_ms"].(float64) < 0 {
			t.Fatal(event)
		}
		expected := "info"
		if rec.Code >= 400 {
			expected = "warn"
		}
		if event["level"] != expected {
			t.Fatal(event)
		}
		if strings.Contains(output.String(), "must-not-log") {
			t.Fatal("query parameters leaked")
		}
		output.Reset()
	}
}
