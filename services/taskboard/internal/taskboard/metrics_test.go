package taskboard

import (
	"net/http/httptest"
	"strings"
	"testing"
)

func TestOpenMetricsAndPublicIsolation(t *testing.T) {
	metrics := NewMetrics()
	req := httptest.NewRequest("GET", "/metrics", nil)
	req.Header.Set("Accept", "application/openmetrics-text; version=1.0.0; charset=utf-8")
	response := httptest.NewRecorder()
	metrics.Handler().ServeHTTP(response, req)
	if response.Code != 200 || !strings.Contains(response.Header().Get("Content-Type"), "application/openmetrics-text") || !strings.HasSuffix(response.Body.String(), "# EOF\n") {
		t.Fatalf("invalid OpenMetrics response: %d %s", response.Code, response.Body.String())
	}
	for _, name := range []string{"go_goroutines", "process_cpu_seconds_total", "taskboard_tasks_created_total", "taskboard_tasks_updated_total", "taskboard_tasks_deleted_total", "taskboard_tasks_read_total", "taskboard_task_lists_viewed_total"} {
		if !strings.Contains(response.Body.String(), name+" ") {
			t.Errorf("missing %s", name)
		}
	}
	public := httptest.NewRecorder()
	NewHandler(nil, t.TempDir(), metrics).ServeHTTP(public, httptest.NewRequest("GET", "/metrics", nil))
	if public.Code != 404 {
		t.Fatalf("public API exposes metrics: %d", public.Code)
	}
}

func TestInvalidOperationDoesNotCountAndLabelsAreBounded(t *testing.T) {
	metrics := NewMetrics()
	handler := NewHandler(nil, t.TempDir(), metrics)
	for _, id := range []string{"invalid-one", "invalid-two"} {
		rec := httptest.NewRecorder()
		handler.ServeHTTP(rec, httptest.NewRequest("GET", "/api/tasks/"+id, nil))
		if rec.Code != 400 {
			t.Fatal(rec.Code)
		}
	}
	families, err := metrics.registry.Gather()
	if err != nil {
		t.Fatal(err)
	}
	for _, family := range families {
		if family.GetName() == "taskboard_tasks_read_total" && family.Metric[0].GetCounter().GetValue() != 0 {
			t.Fatal("failed reads counted as success")
		}
		if family.GetName() == "taskboard_http_requests_total" {
			if len(family.Metric) != 1 || family.Metric[0].Counter.GetValue() != 2 {
				t.Fatal("raw IDs created label series")
			}
			for _, label := range family.Metric[0].Label {
				if strings.Contains(label.GetValue(), "invalid-") {
					t.Fatal("raw task ID in labels")
				}
			}
		}
	}
}
