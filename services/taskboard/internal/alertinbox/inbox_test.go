package alertinbox

import (
	"bytes"
	"encoding/json"
	"fmt"
	"log/slog"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"
)

func sample(status string) Payload {
	return Payload{Version: "4", Receiver: "taskboard-webhook", Status: status, GroupKey: "taskboard:runtime",
		Alerts: []Alert{{Status: status, StartsAt: time.Now().UTC(),
			Labels:      map[string]string{"alertname": "TaskboardGoHeapHigh", "namespace": "taskboard-lab", "service": "taskboard", "severity": "warning"},
			Annotations: map[string]string{"summary": "Go heap above limit"}}}}
}

func TestStorePersistsBoundsAndDoesNotShareMaps(t *testing.T) {
	path := filepath.Join(t.TempDir(), "notifications.json")
	store, err := Open(path)
	if err != nil {
		t.Fatal(err)
	}
	payload := sample("firing")
	for range historyLimit + 5 {
		if _, err := store.Append(payload, "127.0.0.1:1234", time.Now()); err != nil {
			t.Fatal(err)
		}
	}
	payload.Alerts[0].Labels["alertname"] = "mutated caller"
	reopened, err := Open(path)
	if err != nil {
		t.Fatal(err)
	}
	rows := reopened.Snapshot()
	if len(rows) != historyLimit || rows[0].ID != 6 || rows[len(rows)-1].ID != uint64(historyLimit+5) {
		t.Fatal("lost delivery IDs or unbounded journal")
	}
	if rows[0].Payload.Alerts[0].Labels["alertname"] != "TaskboardGoHeapHigh" {
		t.Fatal("caller modified a stored notification")
	}
	rows[0].Payload.Alerts[0].Labels["alertname"] = "mutated reader"
	if reopened.Snapshot()[0].Payload.Alerts[0].Labels["alertname"] != "TaskboardGoHeapHigh" {
		t.Fatal("HTTP readers share mutable data")
	}
}

func TestConcurrentDeliveriesHaveStableIDs(t *testing.T) {
	store, err := Open(filepath.Join(t.TempDir(), "notifications.json"))
	if err != nil {
		t.Fatal(err)
	}
	var workers sync.WaitGroup
	for range 12 {
		workers.Add(1)
		go func() {
			defer workers.Done()
			if _, err := store.Append(sample("firing"), "local", time.Now()); err != nil {
				t.Error(err)
			}
			_ = store.Snapshot()
		}()
	}
	workers.Wait()
	for i, row := range store.Snapshot() {
		if row.ID != uint64(i+1) {
			t.Fatal("duplicate or reordered delivery IDs")
		}
	}
}

func TestCorruptedJournalFailsStartup(t *testing.T) {
	path := filepath.Join(t.TempDir(), "notifications.json")
	for _, body := range []string{"{", "null", `[{"id":0}]`, "[] trailing"} {
		if err := os.WriteFile(path, []byte(body), 0600); err != nil {
			t.Fatal(err)
		}
		if _, err := Open(path); err == nil {
			t.Fatalf("silently accepted invalid history: %q", body)
		}
	}
}

func TestWebhookValidatesPersistsAndEscapesHTML(t *testing.T) {
	store, err := Open(filepath.Join(t.TempDir(), "notifications.json"))
	if err != nil {
		t.Fatal(err)
	}
	handler := NewHandler(store)
	for _, status := range []string{"firing", "resolved"} {
		payload := sample(status)
		payload.Alerts[0].Annotations["summary"] = `<script>alert("untrusted")</script>`
		body, _ := json.Marshal(payload)
		response := httptest.NewRecorder()
		handler.ServeHTTP(response, httptest.NewRequest("POST", "/webhook", bytes.NewReader(body)))
		if response.Code != 200 {
			t.Fatal(response.Code, response.Body.String())
		}
	}
	page := httptest.NewRecorder()
	handler.ServeHTTP(page, httptest.NewRequest("GET", "/", nil))
	if page.Code != 200 || strings.Contains(page.Body.String(), `<script>alert`) || !strings.Contains(page.Body.String(), "&lt;script&gt;") {
		t.Fatal("notification HTML was not escaped")
	}
	response := httptest.NewRecorder()
	handler.ServeHTTP(response, httptest.NewRequest("GET", "/api/notifications", nil))
	var rows []Notification
	if json.Unmarshal(response.Body.Bytes(), &rows) != nil || len(rows) != 2 || rows[1].Payload.Status != "resolved" {
		t.Fatal("firing/resolved deliveries were not kept")
	}
}

func TestWebhookRejectsMalformedForeignAndOversizedRequests(t *testing.T) {
	store, err := Open(filepath.Join(t.TempDir(), "notifications.json"))
	if err != nil {
		t.Fatal(err)
	}
	handler := NewHandler(store)
	valid, _ := json.Marshal(sample("firing"))
	foreign := sample("firing")
	foreign.Alerts[0].Labels["namespace"] = "some-other-project"
	foreignBody, _ := json.Marshal(foreign)
	inconsistent := sample("resolved")
	inconsistent.Alerts[0].Status = "firing"
	inconsistentBody, _ := json.Marshal(inconsistent)
	oversized := sample("firing")
	oversized.Alerts[0].Annotations["summary"] = strings.Repeat("x", 70*1024)
	oversizedBody, _ := json.Marshal(oversized)
	for _, body := range [][]byte{nil, []byte(`{}`), append(append([]byte(nil), valid...), []byte(` {}`)...), foreignBody, inconsistentBody, oversizedBody} {
		response := httptest.NewRecorder()
		handler.ServeHTTP(response, httptest.NewRequest("POST", "/webhook", bytes.NewReader(body)))
		if response.Code != 400 {
			t.Fatal("invalid webhook acknowledged", response.Code)
		}
	}
	if len(store.Snapshot()) != 0 {
		t.Fatal("invalid request changed the journal")
	}
}

type unavailableStore struct{}

func (unavailableStore) Append(Payload, string, time.Time) (Notification, error) {
	return Notification{}, fmt.Errorf("disk unavailable")
}
func (unavailableStore) Snapshot() []Notification { return nil }

func TestFailedPersistenceReturnsRetryableErrorAndDoesNotLogPayload(t *testing.T) {
	var log bytes.Buffer
	previous := slog.Default()
	slog.SetDefault(slog.New(slog.NewJSONHandler(&log, nil)))
	defer slog.SetDefault(previous)
	payload := sample("firing")
	payload.Alerts[0].Annotations["summary"] = "private-payload-marker"
	body, _ := json.Marshal(payload)
	response := httptest.NewRecorder()
	NewHandler(unavailableStore{}).ServeHTTP(response, httptest.NewRequest("POST", "/webhook", bytes.NewReader(body)))
	if response.Code != 503 || strings.Contains(log.String(), "private-payload-marker") {
		t.Fatal("failure must remain retryable and logs must omit payloads")
	}
}
