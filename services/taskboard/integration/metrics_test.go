//go:build integration

package integration

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strconv"
	"strings"
	"testing"
	"time"
)

// Point both URLs at the same pod (one port-forward with two ports). This checks
// counter semantics exactly; service-level traffic across replicas is tested via VM.
func TestBusinessMetrics(t *testing.T) {
	metricsURL := os.Getenv("TASKBOARD_METRICS_URL")
	if metricsURL == "" {
		t.Skip("set TASKBOARD_METRICS_URL and TASKBOARD_URL to the same instance")
	}
	base := os.Getenv("TASKBOARD_URL")
	if base == "" {
		t.Fatal("TASKBOARD_URL is required")
	}
	client := &http.Client{Timeout: 10 * time.Second}
	counters := func() map[string]float64 {
		t.Helper()
		response, err := client.Get(metricsURL + "/metrics")
		if err != nil {
			t.Fatal(err)
		}
		defer response.Body.Close()
		if response.StatusCode != 200 {
			t.Fatal(response.StatusCode)
		}
		data, err := io.ReadAll(response.Body)
		if err != nil {
			t.Fatal(err)
		}
		result := map[string]float64{}
		for _, line := range strings.Split(string(data), "\n") {
			fields := strings.Fields(line)
			if len(fields) == 2 && strings.HasPrefix(fields[0], "taskboard_task") {
				if value, err := strconv.ParseFloat(fields[1], 64); err == nil {
					result[fields[0]] = value
				}
			}
		}
		return result
	}
	request := func(method, path, body string, status int) []byte {
		t.Helper()
		req, err := http.NewRequest(method, base+path, strings.NewReader(body))
		if err != nil {
			t.Fatal(err)
		}
		req.Header.Set("Content-Type", "application/json")
		response, err := client.Do(req)
		if err != nil {
			t.Fatal(err)
		}
		defer response.Body.Close()
		data, err := io.ReadAll(response.Body)
		if err != nil {
			t.Fatal(err)
		}
		if response.StatusCode != status {
			t.Fatalf("%s %s: %d want %d: %s", method, path, response.StatusCode, status, data)
		}
		return data
	}
	before := counters()
	data := request("POST", "/api/tasks", `{"title":"metrics integration","status":"todo"}`, 201)
	var created struct {
		ID int64 `json:"id"`
	}
	if err := json.Unmarshal(data, &created); err != nil {
		t.Fatal(err)
	}
	path := fmt.Sprintf("/api/tasks/%d", created.ID)
	t.Cleanup(func() {
		req, _ := http.NewRequest("DELETE", base+path, nil)
		response, err := client.Do(req)
		if err == nil {
			response.Body.Close()
		}
	})
	request("GET", path, "", 200)
	request("GET", "/api/tasks", "", 200)
	request("PUT", path, `{"title":"updated","status":"done"}`, 200)
	request("PUT", path, `{"title":"","status":"done"}`, 400)
	request("DELETE", path, "", 204)
	request("GET", path, "", 404)
	request("DELETE", path, "", 404)
	request("GET", "/metrics", "", 404)
	after := counters()
	for _, name := range []string{"taskboard_tasks_created_total", "taskboard_tasks_updated_total", "taskboard_tasks_deleted_total", "taskboard_tasks_read_total", "taskboard_task_lists_viewed_total"} {
		value, ok := after[name]
		if !ok {
			t.Fatalf("missing counter %s", name)
		}
		if got := value - before[name]; got != 1 {
			t.Errorf("%s increased by %v, want 1", name, got)
		}
	}
}
