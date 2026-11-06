package taskboard

import (
	"context"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	dto "github.com/prometheus/client_model/go"
)

func TestDemoConfigValidation(t *testing.T) {
	for _, input := range [][2]string{{"-1", ""}, {"abc", ""}, {"0", "-1ms"}, {"0", "3s"}, {"", "oops"}} {
		if _, err := ParseDemoConfig(input[0], input[1]); err == nil {
			t.Fatalf("accepted invalid config: %v", input)
		}
	}
	config, err := ParseDemoConfig("3", "750ms")
	if err != nil || config.FailureEvery != 3 || config.Latency != 750*time.Millisecond {
		t.Fatal(config, err)
	}
	config, err = ParseDemoConfig("", "")
	if err != nil || config != (DemoConfig{}) {
		t.Fatal("demo must default to off", config, err)
	}
}

func TestDemoErrorsAreObservedOnTheirActualRoute(t *testing.T) {
	metrics := NewMetrics()
	handler := NewHandlerWithDemo(nil, t.TempDir(), metrics, DemoConfig{FailureEvery: 1})
	response := httptest.NewRecorder()
	handler.ServeHTTP(response, httptest.NewRequest("POST", "/api/tasks", nil))
	if response.Code != 503 {
		t.Fatal(response.Code)
	}
	if metricValue(t, metrics.requests.WithLabelValues("POST", "POST /api/tasks", "503")) != 1 || metricValue(t, metrics.created) != 0 {
		t.Fatal("injected failure must count as an HTTP failure, never a successful commit")
	}
	health := httptest.NewRecorder()
	handler.ServeHTTP(health, httptest.NewRequest("GET", "/healthz", nil))
	if health.Code != 200 {
		t.Fatal("demo must not affect liveness")
	}
}

func TestDemoFrequencyAndCancellation(t *testing.T) {
	demo := &demoBehavior{config: DemoConfig{FailureEvery: 3}}
	handler := demo.wrap(func(w http.ResponseWriter, _ *http.Request) { w.WriteHeader(204) })
	for _, expected := range []int{204, 204, 503, 204, 204, 503} {
		response := httptest.NewRecorder()
		handler(response, httptest.NewRequest("GET", "/", nil))
		if response.Code != expected {
			t.Fatal(response.Code, expected)
		}
	}
	demo.config = DemoConfig{Latency: time.Second}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	start := time.Now()
	response := httptest.NewRecorder()
	handler(response, httptest.NewRequest("GET", "/", nil).WithContext(ctx))
	if response.Code != 408 || time.Since(start) > 500*time.Millisecond {
		t.Fatal("delay must respect request cancellation")
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
