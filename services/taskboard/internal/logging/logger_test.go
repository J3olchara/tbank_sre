package logging

import (
	"bytes"
	"encoding/json"
	"log/slog"
	"strings"
	"testing"
	"time"
)

func TestJSONSchemaAndEscaping(t *testing.T) {
	var output bytes.Buffer
	logger := New(&output, slog.LevelInfo, "taskboard")
	logger.Info("http_request", "method", "GET", "path", "/api/tasks", "duration_ms", 0.125)
	logger.Warn("bad_request", "detail", "line one\nline two")
	logger.Error("database_request_failed")
	lines := strings.Split(strings.TrimSpace(output.String()), "\n")
	if len(lines) != 3 {
		t.Fatalf("each event must occupy one line: %q", output.String())
	}
	for index, line := range lines {
		var event map[string]any
		if err := json.Unmarshal([]byte(line), &event); err != nil {
			t.Fatal(err)
		}
		if _, err := time.Parse(time.RFC3339Nano, event["timestamp"].(string)); err != nil {
			t.Fatal(err)
		}
		if event["service.name"] != "taskboard" || event["message"] == "" {
			t.Fatal(event)
		}
		if event["level"] != []string{"info", "warn", "error"}[index] {
			t.Fatal(event)
		}
		if _, ok := event["msg"]; ok {
			t.Fatal("legacy message key")
		}
		if _, ok := event["time"]; ok {
			t.Fatal("legacy timestamp key")
		}
	}
}

func TestLogLevelFilter(t *testing.T) {
	var output bytes.Buffer
	logger := New(&output, slog.LevelWarn, "taskboard")
	logger.Info("ignored")
	logger.Warn("included")
	if strings.Contains(output.String(), "ignored") || !strings.Contains(output.String(), "included") {
		t.Fatal(output.String())
	}
}
