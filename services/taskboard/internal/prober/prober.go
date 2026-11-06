// Package prober checks the user-facing HTTP Service, including a real DB read.
package prober

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

type Prober struct {
	base     string
	client   *http.Client
	registry *prometheus.Registry
	success  prometheus.Gauge
	duration prometheus.Gauge
	lastRun  prometheus.Gauge
	checks   *prometheus.CounterVec
}

func New(target string, timeout time.Duration) (*Prober, error) {
	u, err := url.Parse(target)
	if err != nil || u.Host == "" || (u.Scheme != "http" && u.Scheme != "https") || u.User != nil || u.RawQuery != "" || u.Fragment != "" || (u.Path != "" && u.Path != "/") || timeout <= 0 {
		return nil, fmt.Errorf("PROBE_TARGET must be an HTTP(S) origin without credentials; timeout must be positive")
	}
	gauge := func(name, help string) prometheus.Gauge {
		return prometheus.NewGauge(prometheus.GaugeOpts{Namespace: "taskboard_probe", Name: name, Help: help})
	}
	p := &Prober{
		base:     strings.TrimRight(target, "/"),
		client:   &http.Client{Timeout: timeout, CheckRedirect: func(_ *http.Request, _ []*http.Request) error { return http.ErrUseLastResponse }},
		registry: prometheus.NewRegistry(),
		success:  gauge("success", "1 if the last complete UI and task-list check succeeded; otherwise 0."),
		duration: gauge("duration_seconds", "Duration of the last UI and API check, including network time."),
		lastRun:  gauge("last_run_timestamp_seconds", "Unix time of the last completed check."),
		checks:   prometheus.NewCounterVec(prometheus.CounterOpts{Namespace: "taskboard_probe", Name: "checks_total", Help: "Completed synthetic checks by bounded result."}, []string{"result"}),
	}
	p.checks.WithLabelValues("success")
	p.checks.WithLabelValues("failure")
	p.registry.MustRegister(p.success, p.duration, p.lastRun, p.checks)
	return p, nil
}

func (p *Prober) Handler() http.Handler {
	mux := http.NewServeMux()
	mux.Handle("GET /metrics", promhttp.HandlerFor(p.registry, promhttp.HandlerOpts{EnableOpenMetrics: true}))
	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, _ *http.Request) { w.WriteHeader(http.StatusOK) })
	return mux
}

func (p *Prober) get(ctx context.Context, path string) ([]byte, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, p.base+path, nil)
	if err != nil {
		return nil, err
	}
	response, err := p.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("probe transport failed")
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("probe %s returned HTTP %d", path, response.StatusCode)
	}
	// 500 valid tasks can exceed 6 MiB after JSON escaping of title/description.
	const maximum = 8 * 1024 * 1024
	body, err := io.ReadAll(io.LimitReader(response.Body, maximum+1))
	if err != nil || len(body) > maximum {
		return nil, fmt.Errorf("probe response is unreadable or too large")
	}
	return body, nil
}

// Check does not modify tasks. The caller supplies one deadline for the whole check.
func (p *Prober) Check(ctx context.Context) (err error) {
	start := time.Now()
	defer func() {
		result, success := "success", float64(1)
		if err != nil {
			result, success = "failure", 0
		}
		p.success.Set(success)
		p.duration.Set(time.Since(start).Seconds())
		p.lastRun.Set(float64(time.Now().UnixNano()) / 1e9)
		p.checks.WithLabelValues(result).Inc()
	}()
	body, err := p.get(ctx, "/")
	if err != nil {
		return err
	}
	if !strings.Contains(string(body), `<div id="root">`) || !strings.Contains(string(body), "<script") {
		return fmt.Errorf("probe UI has no React root or script")
	}
	body, err = p.get(ctx, "/api/tasks")
	if err != nil {
		return err
	}
	var tasks []struct {
		ID     int64  `json:"id"`
		Title  string `json:"title"`
		Status string `json:"status"`
	}
	if err := json.Unmarshal(body, &tasks); err != nil || tasks == nil {
		return fmt.Errorf("probe API response is not a JSON array")
	}
	for _, task := range tasks {
		if task.ID < 1 || task.Title == "" || (task.Status != "todo" && task.Status != "doing" && task.Status != "done") {
			return fmt.Errorf("probe task schema is invalid")
		}
	}
	if ctx.Err() != nil {
		return fmt.Errorf("probe deadline exceeded")
	}
	return nil
}
