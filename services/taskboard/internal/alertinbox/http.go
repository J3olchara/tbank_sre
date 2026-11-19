package alertinbox

import (
	_ "embed"
	"encoding/json"
	"fmt"
	"html/template"
	"io"
	"log/slog"
	"net/http"
	"time"
)

//go:embed page.html
var page string

var inboxPage = template.Must(template.New("inbox").Parse(page))

type repository interface {
	Append(Payload, string, time.Time) (Notification, error)
	Snapshot() []Notification
}

func validate(p Payload) error {
	if p.Version != "4" || p.Receiver == "" || (p.Status != "firing" && p.Status != "resolved") || len(p.Alerts) < 1 || len(p.Alerts) > 32 {
		return fmt.Errorf("invalid webhook envelope")
	}
	firing := false
	for _, a := range p.Alerts {
		if (a.Status != "firing" && a.Status != "resolved") || a.Labels["alertname"] == "" || a.Labels["namespace"] != "taskboard-lab" || a.Labels["service"] != "taskboard" {
			return fmt.Errorf("invalid taskboard alert")
		}
		firing = firing || a.Status == "firing"
	}
	if (p.Status == "firing") != firing {
		return fmt.Errorf("inconsistent webhook status")
	}
	return nil
}

func NewHandler(store repository) http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, _ *http.Request) { w.WriteHeader(http.StatusOK) })
	mux.HandleFunc("GET /{$}", func(w http.ResponseWriter, _ *http.Request) {
		records := store.Snapshot()
		for i, j := 0, len(records)-1; i < j; i, j = i+1, j-1 {
			records[i], records[j] = records[j], records[i]
		}
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		w.Header().Set("Cache-Control", "no-store")
		if err := inboxPage.Execute(w, records); err != nil {
			slog.Error("inbox_render_failed")
		}
	})
	mux.HandleFunc("GET /api/notifications", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Header().Set("Cache-Control", "no-store")
		_ = json.NewEncoder(w).Encode(store.Snapshot())
	})
	mux.HandleFunc("POST /webhook", func(w http.ResponseWriter, r *http.Request) {
		r.Body = http.MaxBytesReader(w, r.Body, 64*1024)
		decoder := json.NewDecoder(r.Body)
		var payload Payload
		if decoder.Decode(&payload) != nil || validate(payload) != nil {
			http.Error(w, "invalid Alertmanager webhook", http.StatusBadRequest)
			return
		}
		var trailing any
		if decoder.Decode(&trailing) != io.EOF {
			http.Error(w, "expected a single JSON object", http.StatusBadRequest)
			return
		}
		record, err := store.Append(payload, r.RemoteAddr, time.Now())
		if err != nil {
			slog.Error("notification_persist_failed")
			http.Error(w, "notification was not stored", http.StatusServiceUnavailable)
			return
		}
		slog.Info("notification_received", "notification_id", record.ID, "status", payload.Status, "alerts", len(payload.Alerts))
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]uint64{"notification_id": record.ID})
	})
	return mux
}
