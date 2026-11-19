// Package alertinbox persists actual Alertmanager webhook deliveries for the lab.
package alertinbox

import (
	"encoding/json"
	"fmt"
	"io"
	"maps"
	"os"
	"path/filepath"
	"sync"
	"time"
)

const historyLimit = 100

type Alert struct {
	Status       string            `json:"status"`
	Labels       map[string]string `json:"labels"`
	Annotations  map[string]string `json:"annotations"`
	StartsAt     time.Time         `json:"startsAt"`
	EndsAt       time.Time         `json:"endsAt"`
	Fingerprint  string            `json:"fingerprint"`
	GeneratorURL string            `json:"generatorURL"`
}

type Payload struct {
	Version           string            `json:"version"`
	Receiver          string            `json:"receiver"`
	Status            string            `json:"status"`
	Alerts            []Alert           `json:"alerts"`
	GroupLabels       map[string]string `json:"groupLabels"`
	CommonLabels      map[string]string `json:"commonLabels"`
	CommonAnnotations map[string]string `json:"commonAnnotations"`
	ExternalURL       string            `json:"externalURL"`
	GroupKey          string            `json:"groupKey"`
	TruncatedAlerts   int               `json:"truncatedAlerts"`
}

type Notification struct {
	ID         uint64    `json:"id"`
	ReceivedAt time.Time `json:"received_at"`
	RemoteAddr string    `json:"remote_addr"`
	Payload    Payload   `json:"payload"`
}

type Store struct {
	mu      sync.Mutex
	path    string
	records []Notification
}

func Open(path string) (*Store, error) {
	if err := os.MkdirAll(filepath.Dir(path), 0750); err != nil {
		return nil, fmt.Errorf("create inbox data directory: %w", err)
	}
	s := &Store{path: path, records: []Notification{}}
	file, err := os.Open(path)
	if os.IsNotExist(err) {
		return s, nil
	}
	if err != nil {
		return nil, fmt.Errorf("open notification history: %w", err)
	}
	defer file.Close()
	decoder := json.NewDecoder(io.LimitReader(file, 8*1024*1024))
	if err := decoder.Decode(&s.records); err != nil || s.records == nil || len(s.records) > historyLimit {
		return nil, fmt.Errorf("invalid notification history")
	}
	var trailing any
	if decoder.Decode(&trailing) != io.EOF {
		return nil, fmt.Errorf("invalid notification history suffix")
	}
	for i, record := range s.records {
		if record.ID == 0 || (i > 0 && record.ID <= s.records[i-1].ID) || validate(record.Payload) != nil {
			return nil, fmt.Errorf("invalid notification history entry")
		}
	}
	return s, nil
}

func (s *Store) Append(payload Payload, remote string, received time.Time) (Notification, error) {
	if err := validate(payload); err != nil {
		return Notification{}, err
	}
	payload = clonePayload(payload)
	s.mu.Lock()
	defer s.mu.Unlock()
	var id uint64 = 1
	if len(s.records) > 0 {
		id = s.records[len(s.records)-1].ID + 1
	}
	record := Notification{ID: id, ReceivedAt: received.UTC(), RemoteAddr: remote, Payload: payload}
	updated := append(append([]Notification(nil), s.records...), record)
	if len(updated) > historyLimit {
		updated = updated[len(updated)-historyLimit:]
	}
	data, err := json.Marshal(updated)
	if err != nil {
		return Notification{}, err
	}
	file, err := os.CreateTemp(filepath.Dir(s.path), ".notification-*.tmp")
	if err != nil {
		return Notification{}, err
	}
	defer os.Remove(file.Name())
	_, writeErr := file.Write(data)
	syncErr := file.Sync()
	closeErr := file.Close()
	if writeErr != nil || syncErr != nil || closeErr != nil {
		return Notification{}, fmt.Errorf("persist notification history")
	}
	if err := os.Rename(file.Name(), s.path); err != nil {
		return Notification{}, err
	}
	s.records = updated
	record.Payload = clonePayload(record.Payload)
	return record, nil
}

// Snapshot returns independent data; HTTP readers never share maps with writers.
func (s *Store) Snapshot() []Notification {
	s.mu.Lock()
	defer s.mu.Unlock()
	result := make([]Notification, len(s.records))
	for i, record := range s.records {
		record.Payload = clonePayload(record.Payload)
		result[i] = record
	}
	return result
}

func clonePayload(payload Payload) Payload {
	payload.GroupLabels = maps.Clone(payload.GroupLabels)
	payload.CommonLabels = maps.Clone(payload.CommonLabels)
	payload.CommonAnnotations = maps.Clone(payload.CommonAnnotations)
	payload.Alerts = append([]Alert(nil), payload.Alerts...)
	for i := range payload.Alerts {
		payload.Alerts[i].Labels = maps.Clone(payload.Alerts[i].Labels)
		payload.Alerts[i].Annotations = maps.Clone(payload.Alerts[i].Annotations)
	}
	return payload
}
