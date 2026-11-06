package taskboard

import (
	"net/http"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/collectors"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

// Metrics owns a registry per process; tests never mutate the global registry.
// Business counters count committed successful operations, not attempted requests.
type Metrics struct {
	registry *prometheus.Registry
	created  prometheus.Counter
	updated  prometheus.Counter
	deleted  prometheus.Counter
	read     prometheus.Counter
	listed   prometheus.Counter
	requests *prometheus.CounterVec
	duration *prometheus.HistogramVec
}

func NewMetrics() *Metrics {
	counter := func(name, help string) prometheus.Counter {
		return prometheus.NewCounter(prometheus.CounterOpts{Namespace: "taskboard", Name: name, Help: help})
	}
	m := &Metrics{
		registry: prometheus.NewRegistry(),
		created:  counter("tasks_created_total", "Tasks successfully created in PostgreSQL."),
		updated:  counter("tasks_updated_total", "Tasks successfully updated, including unchanged replacements."),
		deleted:  counter("tasks_deleted_total", "Tasks successfully deleted from PostgreSQL."),
		read:     counter("tasks_read_total", "Successful reads of an individual task."),
		listed:   counter("task_lists_viewed_total", "Successful task list views, including empty lists."),
		requests: prometheus.NewCounterVec(prometheus.CounterOpts{Name: "taskboard_http_requests_total", Help: "HTTP requests by bounded method, route template and response code."}, []string{"method", "route", "code"}),
		duration: prometheus.NewHistogramVec(prometheus.HistogramOpts{Name: "taskboard_http_request_duration_seconds", Help: "HTTP request duration in seconds.", Buckets: prometheus.DefBuckets}, []string{"method", "route"}),
	}
	m.registry.MustRegister(collectors.NewGoCollector(), collectors.NewProcessCollector(collectors.ProcessCollectorOpts{}),
		m.created, m.updated, m.deleted, m.read, m.listed, m.requests, m.duration)
	return m
}

// Handler is served only by the separate metrics listener, never by the public API.
// OpenMetrics 1.0 is negotiated when the scraper requests it; Prometheus text is
// also supported for standard VictoriaMetrics scrapes and command-line curl.
func (m *Metrics) Handler() http.Handler {
	mux := http.NewServeMux()
	mux.Handle("GET /metrics", promhttp.HandlerFor(m.registry, promhttp.HandlerOpts{EnableOpenMetrics: true}))
	return mux
}
