// taskboard-load produces real, temporary CRUD traffic for the SLO demonstration.
package main

import (
	"context"
	"encoding/json"
	"io"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"syscall"
	"time"

	"tbank-sre/taskboard/internal/logging"
)

func main() {
	slog.SetDefault(logging.New(os.Stdout, slog.LevelInfo, "taskboard-load"))
	target := os.Getenv("LOAD_TARGET")
	if target == "" {
		target = "http://taskboard:8080"
	}
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()
	client := &http.Client{Timeout: 3 * time.Second}
	call := func(ctx context.Context, method, path, body string) (int, []byte) {
		req, err := http.NewRequestWithContext(ctx, method, target+path, strings.NewReader(body))
		if err != nil {
			return 0, nil
		}
		req.Header.Set("Content-Type", "application/json")
		response, err := client.Do(req)
		if err != nil {
			return 0, nil
		}
		defer response.Body.Close()
		data, _ := io.ReadAll(io.LimitReader(response.Body, 2*1024*1024))
		return response.StatusCode, data
	}
	slog.Info("traffic_started")
	defer slog.Info("traffic_stopped")
	ticker := time.NewTicker(300 * time.Millisecond)
	defer ticker.Stop()
	for {
		call(ctx, "GET", "/api/tasks", "")
		status, data := call(ctx, "POST", "/api/tasks", `{"title":"SLO demo: temporary task","status":"todo"}`)
		if status == 201 {
			var task struct {
				ID int64 `json:"id"`
			}
			if json.Unmarshal(data, &task) == nil && task.ID > 0 {
				// Cleanup only this generated ID, even when the parent is shutting down.
				cleanup, cancel := context.WithTimeout(context.Background(), 10*time.Second)
				deleted := false
				for attempt := 0; attempt < 6; attempt++ {
					code, _ := call(cleanup, "DELETE", "/api/tasks/"+strconv.FormatInt(task.ID, 10), "")
					if code == 204 || code == 404 {
						deleted = true
						break
					}
				}
				cancel()
				if !deleted {
					slog.Warn("demo_task_cleanup_failed", "task.id", task.ID)
				}
			}
		}
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
		}
	}
}
