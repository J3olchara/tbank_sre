package prober

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	dto "github.com/prometheus/client_model/go"
)

func TestProbeChecksUIAndDatabaseBackedJSON(t *testing.T) {
	for _, test := range []struct {
		name, ui, api string
		status        int
		ok            bool
	}{
		{"empty list", `<div id="root"></div><script src="/assets/app.js"></script>`, `[]`, 200, true},
		{"existing task", `<div id="root"></div><script></script>`, `[{"id":1,"title":"test","status":"done"}]`, 200, true},
		{"broken UI", `bad page`, `[]`, 200, false},
		{"database unavailable", `<div id="root"></div><script></script>`, `{}`, 503, false},
		{"wrong JSON type", `<div id="root"></div><script></script>`, `null`, 200, false},
		{"wrong schema", `<div id="root"></div><script></script>`, `[{"id":0}]`, 200, false},
	} {
		t.Run(test.name, func(t *testing.T) {
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				if r.Method != "GET" {
					t.Error("probe must be read-only")
				}
				if r.URL.Path == "/" {
					_, _ = w.Write([]byte(test.ui))
					return
				}
				w.WriteHeader(test.status)
				_, _ = w.Write([]byte(test.api))
			}))
			defer server.Close()
			p, err := New(server.URL, time.Second)
			if err != nil {
				t.Fatal(err)
			}
			err = p.Check(context.Background())
			if (err == nil) != test.ok {
				t.Fatal(err)
			}
			expected, result := float64(0), "failure"
			if test.ok {
				expected, result = 1, "success"
			}
			if metricValue(t, p.success) != expected || metricValue(t, p.checks.WithLabelValues(result)) != 1 || metricValue(t, p.lastRun) <= 0 {
				t.Fatal("incorrect synthetic result metrics")
			}
			request := httptest.NewRequest("GET", "/metrics", nil)
			request.Header.Set("Accept", "application/openmetrics-text; version=1.0.0")
			response := httptest.NewRecorder()
			p.Handler().ServeHTTP(response, request)
			if !strings.HasSuffix(response.Body.String(), "# EOF\n") {
				t.Fatal("OpenMetrics negotiation failed")
			}
		})
	}
}

func TestProbeDeadlineAndConfiguration(t *testing.T) {
	for _, target := range []string{"invalid", "file:///tmp/a", "http://user:secret@localhost", "http://localhost/path", "http://localhost?x=1"} {
		if _, err := New(target, time.Second); err == nil {
			t.Fatal("accepted invalid target")
		}
	}
	server := httptest.NewServer(http.HandlerFunc(func(_ http.ResponseWriter, r *http.Request) { <-r.Context().Done() }))
	defer server.Close()
	p, _ := New(server.URL, 30*time.Millisecond)
	start := time.Now()
	if err := p.Check(context.Background()); err == nil || time.Since(start) > time.Second || metricValue(t, p.success) != 0 {
		t.Fatal("probe must fail on timeouts")
	}
}

func TestProbeAcceptsMaximumValidTaskList(t *testing.T) {
	tasks := make([]map[string]any, 500)
	for i := range tasks {
		tasks[i] = map[string]any{"id": i + 1, "title": strings.Repeat("<", 200), "description": strings.Repeat("<", 2000), "status": "todo"}
	}
	encoded, err := json.Marshal(tasks)
	if err != nil {
		t.Fatal(err)
	}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/" {
			_, _ = w.Write([]byte(`<div id="root"></div><script></script>`))
			return
		}
		_, _ = w.Write(encoded)
	}))
	defer server.Close()
	p, err := New(server.URL, 2*time.Second)
	if err != nil {
		t.Fatal(err)
	}
	if err := p.Check(context.Background()); err != nil {
		t.Fatalf("a valid full task list must not look like an outage: %v", err)
	}
}

func metricValue(t *testing.T, metric prometheus.Metric) float64 {
	t.Helper()
	var value dto.Metric
	if err := metric.Write(&value); err != nil {
		t.Fatal(err)
	}
	if value.Counter != nil {
		return value.Counter.GetValue()
	}
	return value.Gauge.GetValue()
}
